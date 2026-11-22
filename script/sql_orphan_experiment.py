r"""
实验二：孤儿引用（第 2 讲 §7 待验证清单第②项）
问题：本地真库（=公司库原版结构）没有任何物理外键 FOREIGN KEY，
     那么"流程步骤指向的课件被删了"这种事，数据库会拦吗？删完之后，读回时怎么发现？
做法（纯 DB 层，不启动应用）：
  1) 造一套完整沙箱：老师 user → course → lesson → 两份课件 courseware → flow 四步，
     其中两步 slides 分别指向两份课件；
  2) 直接 DELETE 其中一份课件——观察数据库是否报错（预期：不拦，1 行说删就删）；
  3) 用 LEFT JOIN 回读 flow——指向已删课件的那步会被查出来（"孤儿"现形）。
     这条 SQL 就是后端 GET flow 代码里 missing=True 标记的数据库原版实现
     （源码 Service/lesson_flow_service.py _to_resp 第 163-165 行）。
运行：& ".venv\Scripts\python.exe" "script\sql_orphan_experiment.py"
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pymysql

ENV_PATH = r"D:\参考资料\TeachingPlatform-main\backend\.env"

conf = {}
with open(ENV_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            conf[k.strip()] = v.strip()

if conf.get("DB_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
    sys.exit("[拒绝运行] 只许连本地练手库。")

db = pymysql.connect(host=conf["DB_HOST"], port=int(conf["DB_PORT"]), user=conf["DB_USER"],
                     password=conf["DB_PASSWORD"], database=conf["DB_NAME"],
                     charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = db.cursor()

TAG = "orphan1"
print("=" * 70)
print("实验二：无物理外键的库里，删掉被 flow 引用的课件会发生什么")
print("=" * 70)

# ---------- 1. 造沙箱：人 → 课 → 讲次 → 两份课件 ----------
cur.execute("""INSERT INTO user (username, password_hash, real_name, role, status)
               VALUES (%s, 'fake', '孤儿实验老师', 'teacher', 'active')""", (f"orph_{TAG}",))
tid = cur.lastrowid
cur.execute("""INSERT INTO course (name, invite_code, teacher_id, status)
               VALUES (%s, %s, %s, 'active')""", (f"AT-孤儿实验-{TAG}", f"orph{TAG[:4]}".ljust(8, "x")[:8], tid))
cid = cur.lastrowid
cur.execute("""INSERT INTO lesson (course_id, title, seq, status)
               VALUES (%s, '孤儿实验讲次', 1, 'draft')""", (cid,))
lid = cur.lastrowid
cw_ids = []
for name in ("课件A-将被删除", "课件B-保留"):
    cur.execute("""INSERT INTO courseware (course_id, uploader_id, name, file_path, file_size,
                                          page_count, process_status)
                   VALUES (%s, %s, %s, 'fake/path.pdf', 1024, 10, 'done')""", (cid, tid, name))
    cw_ids.append(cur.lastrowid)
db.commit()
print(f"[铺垫] teacher={tid} course={cid} lesson={lid} courseware={cw_ids[0]}(A) {cw_ids[1]}(B)")

# ---------- 2. flow 四步：signin → slides(课件A) → slides(课件B) → end ----------
flow = [("signin", None), ("slides", cw_ids[0]), ("slides", cw_ids[1]), ("end", None)]
for seq, (kind, cw) in enumerate(flow):
    cur.execute("""INSERT INTO lesson_flow_step (lesson_id, seq, kind, courseware_id, page_from, page_to)
                   VALUES (%s, %s, %s, %s, 1, 10)""", (lid, seq, kind, cw))
db.commit()
print(f"[铺垫] flow 四步已落库：signin → slides(A#{cw_ids[0]}) → slides(B#{cw_ids[1]}) → end")

# ---------- 3. 基准对账：此时不该有孤儿 ----------
BASE = """
    SELECT s.seq, s.kind, s.courseware_id,
           c.name AS courseware_name,          -- 关联得上就有名字
           (s.courseware_id IS NOT NULL AND c.id IS NULL) AS missing
           -- 孤儿定义要两个条件同时成立：本该有引用（courseware_id 非空），且关联不上（c.id 为空）。
           -- 少了前一半，signin/end 这种本就无课件的步骤会被误报（第一次跑就中招了）
    FROM lesson_flow_step s
    LEFT JOIN courseware c ON c.id = s.courseware_id
    WHERE s.lesson_id = %s
    ORDER BY s.seq"""
cur.execute(BASE, (lid,))
rows = cur.fetchall()
orphan = [r for r in rows if r["missing"]]
print(f"\n[第 1 次读回] 共 {len(rows)} 步，孤儿 {len(orphan)} 个 —— 基准状态，一切健康")

# ---------- 4. 动手删课件 A：数据库拦不拦？ ----------
print(f"\n[动作] DELETE FROM courseware WHERE id={cw_ids[0]}  （删掉课件 A）")
try:
    n = cur.execute("DELETE FROM courseware WHERE id=%s", (cw_ids[0],))
    db.commit()
    print(f"[结果] 删除成功，影响 {n} 行。数据库【没有拦】——因为表上没有 FOREIGN KEY 约束，")
    print(f"       它根本不知道 lesson_flow_step 在引用这行。这就是无外键库的代价。")
except pymysql.err.IntegrityError as e:
    db.rollback()
    print(f"[结果] 被数据库拦下：{e} （若当初建了物理外键，会走这条世界线）")

# ---------- 5. 再次读回：孤儿现形 ----------
cur.execute(BASE, (lid,))
rows = cur.fetchall()
orphan = [r for r in rows if r["missing"]]
print(f"\n[第 2 次读回] 共 {len(rows)} 步，孤儿 {len(orphan)} 个：")
for r in rows:
    flag = "  <-- 指向已删除的课件（孤儿）" if r["missing"] else ""
    print(f"   seq={r['seq']} kind={r['kind']} courseware_id={r['courseware_id']} "
          f"name={r['courseware_name']} missing={r['missing']}{flag}")

print("""
[结论]
 1. 没有物理外键时，删被引用的行数据库不报错、不级联——引用完整性全靠应用层自觉；
 2. 但库不会替你发现孤儿，LEFT JOIN + IS NULL 一句 SQL 就让它们全部现形；
 3. 后端 _to_resp 已经在读回时打 missing=True（源码第 165 行），前端拿到标记后如何展示，
    就是我们接下来可以在公司测试环境实测的断言点。
""")

# ---------- 6. 清理 ----------
cur.execute("DELETE FROM lesson_flow_step WHERE lesson_id=%s", (lid,))
cur.execute("DELETE FROM lesson WHERE id=%s", (lid,))
cur.execute("DELETE FROM courseware WHERE course_id=%s", (cid,))
cur.execute("DELETE FROM course WHERE id=%s", (cid,))
cur.execute("DELETE FROM user WHERE id=%s", (tid,))
db.commit()
cur.execute("SELECT COUNT(*) AS n FROM lesson_flow_step WHERE lesson_id=%s", (lid,))
print(f"[清理完成] 实验数据已删除，flow 残留 {cur.fetchone()['n']} 行（应为 0）")

db.close()
