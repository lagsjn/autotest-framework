r"""
SQL 第 2 讲配套沙盒：接口 vs 数据库 交叉验证演练场（配套 docs/SQL第2讲-接口数据地图.md）
- 纪律不变：sqlite3 内存库，断开即消失，绝不连被测系统的真库。
- 玩法：每个场景模拟"真实后端的两步"——
    第 1 步 动作：替后端执行它该执行的 INSERT/UPDATE（等价于接口内部逻辑）；
    第 2 步 对账：拿"接口返回体"（模拟字典，字段抄自真实实测）和验证 SQL 的结果逐字段比。
  将来接上只读账号，把 check() 两边的来源换成 requests 响应 + psycopg2/pymysql 查询，骨架不变。
- 注意 V6 是【故意造的不一致】样例：接口 total 口径含退课、列表不含——对账抓口径 bug 的现场演示。
- 用法：& ".venv\Scripts\python.exe" "script\sql_verify_sandbox.py"
        练习题答案：加 --answers
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlite3

db = sqlite3.connect(":memory:")
cur = db.cursor()

# ========== 建表：第 1 讲四张 + 课堂域两张（lesson A 级、lesson_step 按 §2.2 "行表"假设练手） ==========
cur.executescript("""
CREATE TABLE teacher (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL, real_name TEXT NOT NULL);
CREATE TABLE course (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, invite_code TEXT NOT NULL UNIQUE,
    teacher_id INTEGER NOT NULL REFERENCES teacher(id),
    status TEXT NOT NULL DEFAULT 'active', created_at TEXT, updated_at TEXT);
CREATE TABLE student (
    id INTEGER PRIMARY KEY, student_no TEXT NOT NULL UNIQUE, real_name TEXT NOT NULL);
CREATE TABLE enrollment (
    id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES course(id),
    student_id INTEGER NOT NULL REFERENCES student(id),
    status TEXT NOT NULL DEFAULT 'joined', joined_at TEXT,
    UNIQUE (course_id, student_id));
CREATE TABLE lesson (
    id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES course(id),
    title TEXT NOT NULL, week_no INTEGER NOT NULL, weekday INTEGER NOT NULL,
    period TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT, updated_at TEXT);
CREATE TABLE lesson_step (
    id INTEGER PRIMARY KEY, lesson_id INTEGER NOT NULL REFERENCES lesson(id),
    kind TEXT NOT NULL, seq INTEGER NOT NULL,
    courseware_id INTEGER, quiz_id INTEGER, topic TEXT);
""")

cur.executescript("""
INSERT INTO teacher VALUES (2, 'demo_teacher', 'T老师');
INSERT INTO course    VALUES (14, '大数据技术与原理', 'XXUK4W', 2, 'active', '2026-10-20', '2026-11-11');
INSERT INTO student   VALUES (3, 'demo_student', '蔡小小'), (4, 's002', '李小小'), (5, 's003', '王小小');
""")
db.commit()


def check(title, api_said, sql_said):
    """对账核心：接口返回的 dict vs SQL 查到的 dict，逐字段比，字段名对齐后只比共有键。
    打印两边原文 = 纪律 6"失败留证据"，就算全对也让你习惯证据长什么样。"""
    print(f"\n----- {title}")
    print(f"      接口说: {api_said}")
    print(f"      库  说: {sql_said}")
    keys = sorted(set(api_said) & set(sql_said))          # 只比两边都有的字段
    diffs = [k for k in keys if api_said[k] != sql_said[k]]
    if diffs:
        print(f"      [FAIL] 不一致字段: { {k: (api_said[k], sql_said[k]) for k in diffs } }")
    else:
        print(f"      [PASS] {len(keys)} 个字段全部一致")
    return not diffs


print("=" * 70)
print("V1 建课：接口说建好了，库里真躺着一行吗？（纪律 3：锁主键不锁名字）")
print("=" * 70)
# 后端动作（替它执行）
cur.execute("""INSERT INTO course (name, invite_code, teacher_id, status, created_at, updated_at)
               VALUES ('AT-SQL2-1118', 'K7M2QX', 2, 'active', '2026-11-18', '2026-11-18')""")
db.commit()
new_course_id = cur.lastrowid            # 等价于接口返回体里的 data.id
# 假设接口返回体（字段抄自第 1 讲实测格式）
api = {"id": new_course_id, "name": "AT-SQL2-1118", "invite_code": "K7M2QX", "status": "active"}
row = cur.execute("SELECT id, name, invite_code, status FROM course WHERE id=?",
                  (new_course_id,)).fetchone()
check("V1 建课对账", api, dict(zip(["id", "name", "invite_code", "status"], row)))

print("\n" + "=" * 70)
print("V2 幂等加入：发了两次'加入成功'，库里必须恰好 1 行（COUNT 才是证据）")
print("=" * 70)
for _ in range(2):   # 模拟学生 demo_student 用邀请码连点两次加入
    cur.execute("""INSERT OR IGNORE INTO enrollment (course_id, student_id, status, joined_at)
                   VALUES (?, 3, 'joined', '2026-11-18')""", (new_course_id,))
db.commit()
cnt = cur.execute("""SELECT COUNT(*) FROM enrollment
                    WHERE course_id=? AND student_id=3""", (new_course_id,)).fetchone()[0]
check("V2 幂等对账", {"两次请求都返回": 200, "数据层证据该行数": 1},
      {"两次请求都返回": 200, "数据层证据该行数": cnt})

print("\n" + "=" * 70)
print("V4 上课状态机：start 接口说 ongoing，查库确认落库（不是只在内存里翻）")
print("=" * 70)
cur.execute("""INSERT INTO lesson (course_id, title, week_no, weekday, period, status, created_at, updated_at)
               VALUES (?, '第1讲', 1, 3, '1-2节', 'draft', '2026-11-18', '2026-11-18')""",
            (new_course_id,))
db.commit()
lesson_id = cur.lastrowid
cur.execute("UPDATE lesson SET status='ongoing', updated_at='2026-11-18' WHERE id=?", (lesson_id,))
db.commit()
check("V4 状态机对账", {"action": "POST /lessons/{}/start".format(lesson_id), "status": "ongoing"},
      {"action": "POST /lessons/{}/start".format(lesson_id),
       "status": cur.execute("SELECT status FROM lesson WHERE id=?", (lesson_id,)).fetchone()[0]})

print("\n" + "=" * 70)
print("V5 flow 行表假设：PUT flow = 删旧插新，对账按 seq 读回 kind 序列")
print("=" * 70)
# 后端 PUT /lessons/{id}/flow 的内部动作：删掉旧步、插入新步（第 1 步）
cur.execute("DELETE FROM lesson_step WHERE lesson_id=?", (lesson_id,))
for seq, kind in enumerate(["signin", "rollcall", "end"], start=1):
    cur.execute("INSERT INTO lesson_step (lesson_id, kind, seq) VALUES (?,?,?)",
                (lesson_id, kind, seq))
db.commit()
# 接口回读说 steps 是这三步（模拟 GET flow 的返回体压扁成可比字段）
api_steps = [s["kind"] for s in [{"kind": "signin"}, {"kind": "rollcall"}, {"kind": "end"}]]
db_steps = [r[0] for r in cur.execute(
    "SELECT kind FROM lesson_step WHERE lesson_id=? ORDER BY seq", (lesson_id,))]
check("V5 flow 对账", {"steps_kinds": api_steps, "saved": True},
      {"steps_kinds": db_steps, "saved": bool(db_steps)})   # 行表设计里 saved≈有持久化的行

print("\n" + "=" * 70)
print("V6 【故意造的不一致】total 口径 bug 现场：接口数了退课的，列表没列")
print("=" * 70)
cur.execute("""INSERT INTO enrollment (course_id, student_id, status, joined_at)
               VALUES (?, 4, 'joined', '2026-11-18')""", (new_course_id,))
cur.execute("""INSERT INTO enrollment (course_id, student_id, status, joined_at)
               VALUES (?, 5, 'dropped', '2026-11-18')""", (new_course_id,))
db.commit()
# 某后端偷懒：total 直接 COUNT 全表行（含 dropped），items 却筛了 joined —— 口径不一致
api_total_all_status = cur.execute(
    "SELECT COUNT(*) FROM enrollment WHERE course_id=?", (new_course_id,)).fetchone()[0]
correct_total = cur.execute(
    "SELECT COUNT(*) FROM enrollment WHERE course_id=? AND status='joined'",
    (new_course_id,)).fetchone()[0]
check("V6 成员 total 对账（应 FAIL——接口把 dropped 也计进了 total）",
      {"total": api_total_all_status, "items_len": correct_total},
      {"total": correct_total, "items_len": correct_total})
print("      ↑ 这就是对账抓到 bug 的样子：total 和 items 口径不一致，真实项目高频错误")

print("\n" + "=" * 70)
print("V3 归档（软删除）：status 改了 + 选课数据【没被连带删】——引用完整性")
print("=" * 70)
enroll_before = cur.execute("SELECT COUNT(*) FROM enrollment WHERE course_id=?",
                            (new_course_id,)).fetchone()[0]
cur.execute("UPDATE course SET status='archived', updated_at='2026-11-18' WHERE id=?",
            (new_course_id,))
db.commit()
enroll_after = cur.execute("SELECT COUNT(*) FROM enrollment WHERE course_id=?",
                           (new_course_id,)).fetchone()[0]
check("V3a 归档状态对账", {"action": "DELETE /courses/{}".format(new_course_id), "status": "archived"},
      {"action": "DELETE /courses/{}".format(new_course_id),
       "status": cur.execute("SELECT status FROM course WHERE id=?", (new_course_id,)).fetchone()[0]})
check("V3b 软删不伤关联数据", {"enrollment_rows_before": enroll_before, "after": enroll_before},
      {"enrollment_rows_before": enroll_before, "after": enroll_after})

EXERCISES = """
=================  练习题（在纸上/复制本文件里写，答案先别看）  =================
F1 写出 V4 里"下课"动作之后应该跑的验证 SQL（接口：POST /lessons/{id}/end，
   它内部执行 UPDATE lesson SET status='ended' WHERE id=?）
    select status from lesson where id=?;
F2 用 lesson_step 行表写 SQL：查 lesson_id=? 的流程里有没有 quiz 步（kind='quiz'），
   有则返回它的 quiz_id —— 这就是"V5 之后顺手验证资源引用是否有效"的下一跳
   select quize_id from lesson_step where  lesson_id=? and kind ='quiz';
F3 【思考题，不用连库】V6 那种 total/items 口径 bug，如果只有接口黑盒（不给查库），
   你能设计什么请求组合把它测出来？（提示：构造一个 dropped 学生再请求 members）
先让一个学生退课（或 PATCH attendance 成 dropped，如果有这入口），再 GET /courses/{id}/members：
    断言 total == len(items)。黑盒也能抓——不需要库权限，库只是让定位（是 COUNT 口径错还是列表筛选错）更快。
"""

ANSWERS = """
----- 参考答案 -----
F1  SELECT status FROM lesson WHERE id=?
    -- 期望 'ended'；纪律：先调接口拿到 200，再跑这条；锁主键、逐字段（这里就 status 一个关键字段）
F2  SELECT quiz_id FROM lesson_step WHERE lesson_id=? AND kind='quiz'
    -- 返回 0 行=没有随堂测步；返回 quiz_id 后可再验它指向的 quiz 资源真的存在（外键孤儿检查）：
    --   SELECT COUNT(*) FROM quiz q JOIN lesson_step s ON s.quiz_id=q.id WHERE s.lesson_id=? AND s.kind='quiz'
    --   两边行数不等 => flow 里引用了已被删除的随堂测（软删时代的孤儿引用 bug）
F3  先让一个学生退课（或 PATCH attendance 成 dropped，如果有这入口），再 GET /courses/{id}/members：
    断言 total == len(items)。黑盒也能抓——不需要库权限，库只是让定位（是 COUNT 口径错还是列表筛选错）更快。
"""

print(EXERCISES)

if "--answers" in sys.argv:
    print(ANSWERS)

db.close()
print("\n沙盒关闭：内存库随之消失，零残留。")
