"""真实业务场景压测第一弹：压「登录」接口。

为什么这个脚本比 health 重要（本轮核心知识点）
--------------------------------------------------
health 是 **I/O 等待型**：查一次数据库就把 CPU 让出去，所以单进程能撑到 364 req/s。
登录要跑 bcrypt.checkpw，rounds=12 = 4096 轮哈希迭代，实测 685ms 全烧在 CPU 上，
这叫 **CPU 密集型接口**。它能不能"靠并发变快"，取决于 bcrypt 这个 C 扩展
在校验时是否**释放 GIL**（GIL = CPython 的全局解释器锁，同一时刻只允许一个线程
执行 Python 字节码；C 扩展主动释放后，其他线程才能真正并行）：
    释放   -> 20 个核真并行，吞吐随用户数近线性上涨，直到 CPU 打满（约 29 req/s 量级）
    不释放 -> 用户加到 200 也照样排队，吞吐钉死在 1/0.685 ≈ 1.46 req/s
本轮压测就是用数据回答这个问题，而不是猜。

三个必须提前知道的风险
--------------------------------------------------
1) 压测会把本机 CPU 打满（压测机与被测机是同一台笔记本），期间电脑会明显变卡、
   风扇狂转，先保存其他工作；出现整机无响应就 Ctrl+C 停掉，这不算测试失败。
2) 严禁压「错误密码」：失败会累加 账号失败计数字段，达阈值写 锁定时间字段 直接锁号，
   号一锁后续全部 401，整轮数据作废。
   （源码 Utils/Auth/password.py 的 dummy_verify 说明：连"账号不存在"都要跑一次假校验
     来对齐响应耗时，防的是用时序差异枚举账号——所以错误路径同样烧 CPU，但会污染账号状态。）
3) HTTP 200 不等于登录成功：本系统业务码在响应体 code 字段（0 才是成功）。
   所以必须用 catch_response 自己判定，否则"业务全失败"会被统计成"零失败"。

运行（梯度：10 -> 20 -> 40，时长统一 60 秒）
--------------------------------------------------
& ".venv\Scripts\locust.exe" -f perf\locustfile_login.py --headless -u 10 -r 5  -t 60s --csv log\perf_login_u10
& ".venv\Scripts\locust.exe" -f perf\locustfile_login.py --headless -u 20 -r 5  -t 60s --csv log\perf_login_u20
& ".venv\Scripts\locust.exe" -f perf\locustfile_login.py --headless -u 40 -r 10 -t 60s --csv log\perf_login_u40
"""
import os

from dotenv import load_dotenv
from locust import HttpUser, between, task

# 账号密码只从 .env 读（.env 已在 .gitignore 里）：压测脚本要能公开，凭据不能写在代码里
load_dotenv()

USERNAME = os.getenv("PERF_USERNAME")
PASSWORD = os.getenv("PERF_PASSWORD")


class LoginUser(HttpUser):
    host = os.getenv("PERF_API_BASE", "http://127.0.0.1:8000")
    # 停顿压到最小：找 CPU 密集型接口的吞吐上限，停顿越大越测不出上限
    wait_time = between(0.01, 0.05)

    @task
    def login(self):
        with self.client.post(
            "/api/v1/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            name="/auth/login [POST]",   # 报表里的接口名，短一点便于和 health 对比
            catch_response=True,         # 拿到判定权，自己决定算成功还是失败
            timeout=30,                  # 超过 30 秒判失败：防止排队无限堆积把整轮拖死
        ) as resp:
            if resp.status_code != 200:
                # 把状态码写进失败原因，报表里能一眼区分是超时、5xx 还是被限流
                resp.failure(f"HTTP {resp.status_code}")
                return
            try:
                body = resp.json()
            except Exception as exc:
                resp.failure(f"响应非 JSON：{type(exc).__name__}")
                return
            data = body.get("data")
            if body.get("code") != 0 or not (isinstance(data, dict) and data.get("access_token")):
                # 业务码非 0 或没拿到 token —— 这就是"HTTP 200 但登录失败"的情况
                resp.failure(f"业务失败 code={body.get('code')} msg={body.get('message')}")
                return
            resp.success()
