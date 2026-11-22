r"""
性能测试入门第一版：压「健康检查」接口。

为什么从它开始：这个接口只读、不写数据库、不需要登录 token，
压坏了也没有任何副作用，是零风险的工具练手对象。

运行（在项目根目录 D:\Test Learn\autotest 下）：
    & ".venv\Scripts\locust.exe" -f perf\locustfile_health.py --headless -u 20 -r 10 -t 30s --csv log\perf_health

参数含义（本次必须记住的四个）：
    --headless  不开浏览器界面，结果直接打印在终端（适合脚本化和存档）
    -u 20       虚拟用户数（User）：同时有 20 个"假用户"在不断发请求
    -r 10       孵化速率（Spawn Rate）：每秒新上线 10 个虚拟用户，2 秒到 20 个
    -t 30s      持续时间：跑 30 秒后自动停止
    --csv X     把结果导出成 X_statistics.csv / X_failures.csv / X_exceptions.csv
"""

from locust import HttpUser, between, task


class HealthUser(HttpUser):
    """一个虚拟用户 = 一个持续不断地访问健康检查接口的客户端。"""

    # 压测目标写在类属性里，命令行就不用每次重复 --host
    host = "http://127.0.0.1:8000"

    # 两次请求之间的停顿（秒）。between(0.1, 0.3) = 每次随机停 0.1~0.3 秒再发下一个请求。
    # 为什么要停顿：真实用户不会 0 间隔地疯狂点按钮。不停顿测出来的是"理论最大压力"，
    # 而不是"真实用户产生的压力"，这是性能测试里非常常见的错误设置。
    wait_time = between(0.01, 0.05)

    @task
    def health(self):
        # self.client 是 locust 内置的 HTTP 客户端，它会自动记录这次请求的耗时和成败，
        # 所以我们什么都不用写，locust 就知道该统计什么。
        self.client.get("/api/v1/health")
