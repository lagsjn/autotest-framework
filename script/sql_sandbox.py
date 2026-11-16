r"""
SQL 练习沙盒（配套 docs/SQL第1讲-课程选课三表.md）—— 2026-11-11
- 为什么能不用装数据库就练 SQL：Python 标准库自带 sqlite3，一个内存连接就是一个临时数据库，
  跑完就丢，绝不碰被测环境的真库（这一点纪律上很重要：练手 SQL 严禁连生产/测试真库）。
- 表和数据全部照抄今天接口实测到的字段与真实行为（同名课两门、重复加入只留一行、归档改 status），
  所以你能看到"接口行为"和"SQL 结果"是同一件事的两种表现。
- 用法：直接运行看输出；做到第 5 节 EXERCISES 时把 ?? 换成你自己写的 SQL，再跑一次对答案（答案在文件末尾）。
- 运行：& ".venv\Scripts\python.exe" "script\sql_sandbox.py"
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlite3

# 内存数据库：连接一关就没了，不留任何痕迹
db = sqlite3.connect(":memory:")
cur = db.cursor()

# ========== 1. 建表：主键、外键、唯一约束都在这一段 ==========
cur.executescript("""
CREATE TABLE teacher (
    id        INTEGER PRIMARY KEY,          -- 主键：唯一 + 非空 + 自动递增
    username  TEXT NOT NULL,
    real_name TEXT NOT NULL
);

CREATE TABLE course (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,              -- 注意这里没有 UNIQUE：实测允许同名课程
    invite_code TEXT NOT NULL UNIQUE,       -- 唯一约束：邀请码不许重复（也顺带是一条索引）
    teacher_id  INTEGER NOT NULL REFERENCES teacher(id),   -- 外键：指向 teacher.id
    status      TEXT NOT NULL DEFAULT 'active',            -- active / archived
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE student (
    id        INTEGER PRIMARY KEY,
    student_no TEXT NOT NULL UNIQUE,
    real_name  TEXT NOT NULL
);

CREATE TABLE enrollment (                        -- 选课关联表：多对多靠它落地
    id         INTEGER PRIMARY KEY,
    course_id  INTEGER NOT NULL REFERENCES course(id),
    student_id INTEGER NOT NULL REFERENCES student(id),
    status     TEXT NOT NULL DEFAULT 'joined',
    joined_at  TEXT,
    UNIQUE (course_id, student_id)               -- 同一学生同一门课最多一行 -> 加入接口幂等的数据层原因
);
""")

# ========== 2. 灌数据：照实测的返回值造 ==========
cur.executescript("""
INSERT INTO teacher VALUES (2, 'demo_teacher', 'T老师');

-- 演示课 + 我们今天建的三门课（26/28 已归档，27 是 active）
INSERT INTO course VALUES (14, '大数据技术与原理', 'XXUK4W', 2, 'active',   '2026-10-20', '2026-11-11');
INSERT INTO course VALUES (26, 'AT-API-1111162954', 'C9Y946', 2, 'archived', '2026-11-11', '2026-11-11');
INSERT INTO course VALUES (27, 'AT-API2-1111163148', 'SRHBQR', 2, 'active',   '2026-11-11', '2026-11-11');
INSERT INTO course VALUES (28, 'AT-API2-1111163148', 'CBQ6HU', 2, 'archived', '2026-11-11', '2026-11-11');
--        ↑ 27 和 28 同名，库里存得下：证明 name 上没有唯一约束

INSERT INTO student VALUES (3, 'demo_student', '蔡小小');
INSERT INTO student VALUES (4, 's002', '李小小');
INSERT INTO student VALUES (5, 's003', '王小小');

-- demo_student 选了演示课和 27 号课；s002 只选演示课；s003 一门没选（给 LEFT JOIN 练手用）
INSERT INTO enrollment (id, course_id, student_id, status, joined_at)
VALUES (1, 14, 3, 'joined', '2026-10-21'), (2, 14, 4, 'joined', '2026-10-21'),
       (3, 27, 3, 'joined', '2026-11-11');
""")
db.commit()


def run(title, sql, params=()):
    """跑一条 SQL 并把结果打成表，边跑边看结果长什么样"""
    print(f"\n----- {title}")
    print(f"      {sql.strip()}".replace("\n", "\n      "))
    try:
        rows = cur.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        print(f"      [SQL 报错] {e}")
        return
    for r in rows:
        print(f"      {r}")
    print(f"      共 {len(rows)} 行")


print("=" * 70)
print("第 2 节：增删改查——把今天四个接口动作翻译成 SQL")
print("=" * 70)

run("建课=INSERT（数据库自动给 id）",
    """INSERT INTO course (name, invite_code, teacher_id, status, created_at, updated_at)
       VALUES ('AT-SQL-练习', 'ZZZZZ1', 2, 'active', '2026-11-11', '2026-11-11')""")
run("看一眼刚插入的行（id 是数据库给的）",
    "SELECT id, name, invite_code, status FROM course WHERE invite_code = 'ZZZZZ1'")

run("唯一约束拦重复：同一学生重复加入同一门课，第二次插不进去",
    """INSERT INTO enrollment (course_id, student_id, status, joined_at)
       VALUES (27, 3, 'joined', '2026-11-11')""")
run("撞约束不报错的写法（幂等加入，等价于接口的表现）",
    """INSERT OR IGNORE INTO enrollment (course_id, student_id, status, joined_at)
       VALUES (27, 3, 'joined', '2026-11-11')""")

run("归档=UPDATE 改状态（软删除），不是 DELETE",
    "UPDATE course SET status='archived', updated_at='2026-11-11' WHERE invite_code='ZZZZZ1'")
run("归档后按邀请码+active 找课：0 行——这就是接口回 404/40401 的原因",
    "SELECT id, status FROM course WHERE invite_code='ZZZZZ1' AND status='active'")
run("硬删除（本项目绝不这么干，只在沙盒里看效果）",
    "DELETE FROM course WHERE invite_code='ZZZZZ1'")

print("\n" + "=" * 70)
print("第 3 节：JOIN——成员接口那份名单就是这么查出来的")
print("=" * 70)

run("27 号课的学生名单（两张表拼）",
    """SELECT e.course_id, s.student_no, s.real_name, e.status
       FROM enrollment e
       JOIN student s ON s.id = e.student_id
       WHERE e.course_id = 27""")

run("错误示范：忘写 ON 会出笛卡尔积（行数=两表相乘，全是废话）",
    "SELECT COUNT(*) FROM enrollment, student")
run("正确写法下的行数",
    "SELECT COUNT(*) FROM enrollment e JOIN student s ON s.id = e.student_id")

run("s003 一门课都没选——INNER JOIN 查不到他，LEFT JOIN 才留得住",
    """SELECT s.student_no, e.course_id
       FROM student s
       LEFT JOIN enrollment e ON e.student_id = s.id
       ORDER BY s.id""")
run("筛出'没选任何课的学生'：判空必须 IS NULL（写 = NULL 永远不成立）",
    """SELECT s.student_no, s.real_name
       FROM student s
       LEFT JOIN enrollment e ON e.student_id = s.id
       WHERE e.id IS NULL""")

print("\n" + "=" * 70)
print("第 4 节：GROUP BY / HAVING——total 字段的来路")
print("=" * 70)

run("每门课各有多少人",
    """SELECT course_id, COUNT(*) AS member_count
       FROM enrollment WHERE status='joined'
       GROUP BY course_id""")

run("先造一门 0 人课（active 但没人加入）——真实场景就是刚建完课还没让学生加",
    """INSERT INTO course (name, invite_code, teacher_id, status, created_at, updated_at)
       VALUES ('AT-SQL-0人课', 'ZZZZZ2', 2, 'active', '2026-11-11', '2026-11-11')""")

run("T老师每门 active 课的人数（含 0 人课，必须 LEFT JOIN）",
    """SELECT c.id, c.name, COUNT(e.id) AS cnt
       FROM course c
       LEFT JOIN enrollment e ON e.course_id = c.id
       WHERE c.teacher_id = 2 AND c.status = 'active'
       GROUP BY c.id, c.name""")
run("同上但用 INNER JOIN：0 人的课整行消失（和上一题比行数，这就是最常见的统计漏数 bug）",
    """SELECT c.id, c.name, COUNT(e.id) AS cnt
       FROM course c
       JOIN enrollment e ON e.course_id = c.id
       WHERE c.teacher_id = 2 AND c.status = 'active'
       GROUP BY c.id, c.name""")
run("HAVING：分组之后再筛（只要满 2 人的班）",
    """SELECT course_id, COUNT(*) AS cnt FROM enrollment
       GROUP BY course_id HAVING COUNT(*) >= 2""")

print("\n" + "=" * 70)
print("第 5 节：EXPLAIN——看有没有走索引")
print("=" * 70)
run("按 invite_code 查（有 UNIQUE 约束=有索引，输出里能看到 USING INDEX）",
    "EXPLAIN QUERY PLAN SELECT * FROM course WHERE invite_code='SRHBQR'")
run("按 name 查（没索引，只能 SCAN 全表扫描）",
    "EXPLAIN QUERY PLAN SELECT * FROM course WHERE name='大数据技术与原理'")

EXERCISES = """
=================  练习题（自己写，写完把 ?? 替换掉再跑本脚本）  =================
E1 查所有已归档课程的 id 与名字
   SELECT id,name FROM course WHERE status="achieved"

E2 查 demo_student 加入的所有课程名与邀请码（enrollment 和 course 两张表拼）
   SELECT c.name, c.invite_code FROM enrollment e
   JOIN course c ON e.course_id = c.id
   JOIN student s ON s.id = e.student_id
   WHERE s.student_no = 'demo_student'

E3 查每个学生的选课门数，包含一门没选的（要显示 0）
   SELECT s.student_no, COUNT(e.id) AS cnt
   FROM student s
   LEFT JOIN enrollment e ON e.student_id = s.id
   GROUP BY s.student_no

E4 找出"同一门课超过 1 人选"的课程 id 和人数
   SELECT course_id, COUNT(*) AS cnt FROM enrollment
   GROUP BY course_id
   HAVING COUNT(*) > 1

E5 把 28 号课恢复成进行中（想想该用 INSERT 还是 UPDATE 还是 DELETE）
   UPDATE course SET status='active' WHERE id=28

答案不默认打印，要它：& ".venv\\Scripts\\python.exe" "script\\sql_sandbox.py" --answers
"""

# ==================== 参考答案（先自己做，再来对） ====================
ANSWERS = """
----- 参考答案 -----
E1  SELECT id, name FROM course WHERE status = 'archived'
E2  SELECT c.name, c.invite_code FROM enrollment e
    JOIN course c  ON c.id = e.course_id
    JOIN student s ON s.id = e.student_id
    WHERE s.student_no = 'demo_student'
E3  SELECT s.student_no, COUNT(e.id) AS cnt FROM student s
    LEFT JOIN enrollment e ON e.student_id = s.id
    GROUP BY s.student_no
    -- 用 INNER JOIN 的话 s003 整行消失，出不来 0
E4  SELECT course_id, COUNT(*) AS cnt FROM enrollment
    GROUP BY course_id HAVING COUNT(*) > 1
E5  UPDATE course SET status = 'active' WHERE id = 28
    -- 归档/恢复都是改状态列 => UPDATE；INSERT 是新增一行，DELETE 是删行，都不对
"""

print(EXERCISES)

# 答案不默认打印：先自己写完再显式要（防住“顺手偷看”）
if "--answers" in sys.argv:
    print(ANSWERS)

db.close()   # 内存库关掉即消失，不留残留
