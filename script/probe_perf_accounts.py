"""性能测试前置侦察：本机后端是否活着 + 本机库里有没有能用的压测账号。

为什么必须查这个：项目 .env 里的 TEST_USERNAME 是【内网测试环境】的账号，
而本机后端连的是【本机 teaching_platform 库】（SQL 第二站自己重建的那份），
两边数据完全独立，内网账号在本机大概率登录不上。压测脚本要用的账号，
必须在本机库里坐实存在，否则压出来的全是 401，数据全废。

运行：& ".venv\Scripts\python.exe" script\probe_perf_accounts.py
"""
import os
import sys

import pymysql
import requests
from dotenv import dotenv_values

BACKEND_DIR = r"D:\参考资料\TeachingPlatform-main\backend"
LOCAL_API = "http://127.0.0.1:8000/api/v1"


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check_service():
    """第 1 步：后端活着没（端口 + 依赖项，只看 200 不够）"""
    section("1) 本机后端服务状态")
    try:
        body = requests.get(f"{LOCAL_API}/health", timeout=5).json()
    except Exception as exc:
        print(f"  服务不通：{type(exc).__name__} -> 先启动后端再跑本脚本")
        return False
    data = body.get("data") or {}
    print(f"  HTTP 可达 | database={data.get('database')} | redis={data.get('redis')}")
    if data.get("database") != "ok":
        print("  ⚠ 数据库未通，此时压测的响应时间不含真实查库开销，数据无效")
    return True


def check_accounts():
    """第 2 步：本机库 user 表里有哪些账号（列名先探，不猜）"""
    section("2) 本机库 user 表现状")
    env = dotenv_values(os.path.join(BACKEND_DIR, ".env"))
    conf = {
        "host": env.get("DB_HOST", "127.0.0.1"),
        "port": int(env.get("DB_PORT", 3306)),
        "user": env.get("DB_USER"),
        "password": env.get("DB_PASSWORD"),
        "database": env.get("DB_NAME"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }
    print(f"  连接目标：{conf['host']}:{conf['port']} / 库={conf['database']}（凭证读自 backend/.env）")
    conn = pymysql.connect(**conf)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM `user`")
            cols = [r["Field"] for r in cur.fetchall()]
            print(f"  user 表列：{cols}")

            cur.execute("SELECT COUNT(*) AS n FROM `user`")
            print(f"  账号总数：{cur.fetchone()['n']}")

            # 只挑对压测有用的列，不存在就跳过，避免脚本因列名差异崩掉
            want = [c for c in ("id", "username", "real_name", "role", "status",
                                "is_deleted", "student_no") if c in cols]
            cur.execute(f"SELECT {', '.join('`%s`' % c for c in want)} "
                        f"FROM `user` ORDER BY id LIMIT 12")
            rows = cur.fetchall()
            print(f"  前 {len(rows)} 条：")
            for r in rows:
                print("    " + " | ".join(f"{k}={r[k]}" for k in want))

            # 压测首选管理员/老师：按 role 分组看数量，决定用哪类身份压
            if "role" in cols:
                cur.execute("SELECT role, COUNT(*) AS n FROM `user` GROUP BY role")
                print(f"  按角色分布：{cur.fetchall()}")
            return rows
    finally:
        conn.close()


def try_login(rows):
    """第 3 步：拿 backend/.env 里的管理员账号真登录一次，坐实 token 能拿到"""
    section("3) 实测登录（压测脚本的 on_start 就是这个动作）")
    env = dotenv_values(os.path.join(BACKEND_DIR, ".env"))
    candidates = [
        ("backend/.env ADMIN_USERNAME", env.get("ADMIN_USERNAME"), env.get("ADMIN_PASSWORD")),
    ]
    for label, u, p in candidates:
        if not u or not p:
            print(f"  {label}: 配置为空，跳过")
            continue
        try:
            resp = requests.post(f"{LOCAL_API}/auth/login",
                                 json={"username": u, "password": p}, timeout=5)
            body = resp.json()
            data = body.get("data")
            token = data.get("access_token") if isinstance(data, dict) else None
            print(f"  {label} = {u} -> HTTP {resp.status_code} | code={body.get('code')} "
                  f"| msg={body.get('message')} | token={'有' if token else '无'}")
            if token:
                # 拿到 token 立刻验一个业务只读接口，确认鉴权头格式可用
                r2 = requests.get(f"{LOCAL_API}/courses", timeout=5,
                                  params={"page": 1, "page_size": 100},
                                  headers={"Authorization": f"Bearer {token}"})
                d2 = r2.json().get("data") or {}
                print(f"  带 token 查 /courses -> HTTP {r2.status_code} | "
                      f"total={d2.get('total')} | items={len(d2.get('items') or [])}")
                print("  ✅ 压测账号与接口链路已坐实，可用于 locustfile")
                return
        except Exception as exc:
            print(f"  {label} 请求异常：{type(exc).__name__}: {exc}")
    print("  ❌ 尚无可登录账号 -> 用 backend/scripts/create_admin.py 造一个（见 README 第 71 行）")


if __name__ == "__main__":
    alive = check_service()
    rows = check_accounts()
    if alive:
        try_login(rows)
