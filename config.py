"""
全局配置：把"会变的东西"集中放这里
敏感信息（系统地址/账号/密码）从 .env 文件读，代码里不落真值
.env 已被 .gitignore 拉黑，永不进仓库 —— 别人拿到代码找你要 .env.example
"""
import os

from dotenv import load_dotenv

load_dotenv()  # 把项目根目录的 .env 加载进环境变量

# ============ 敏感配置：只存在于 .env，缺失就直接报错（fail fast） ============
BASE_URL = os.getenv("TEST_BASE_URL")
USERNAME = os.getenv("TEST_USERNAME")
PASSWORD = os.getenv("TEST_PASSWORD")
if not all([BASE_URL, USERNAME, PASSWORD]):
    raise RuntimeError(
        "缺少敏感配置：请复制 .env.example 为 .env 并填入真实值（该文件不进 git）"
    )

# ============ 扩展身份：可选资源，缺失不炸场（缺值处理分级） ============
# 学生号 demo_student（L5 跨端）与废弃老师号 demo_deprecated（negative/红级专用）由老师批复。
# 密码只住 .env（git 拉黑），代码里只读取、不落真值。
# 和主账号的区别：主账号缺失 raise 终止全场（所有用例的根基）；
# 扩展账号缺失只把对应能力标成 False，让依赖它的用例 skipif 跳过——
# 可选资源不该阻塞主干启动（优雅降级）
STUDENT_USERNAME = os.getenv("TEST_STUDENT_USERNAME")
STUDENT_PASSWORD = os.getenv("TEST_STUDENT_PASSWORD")
# 学生端独立入口：同一系统不同端口（实测 2026-11-07：8081老师/8082学生/8084管理）
STUDENT_BASE_URL = os.getenv("TEST_STUDENT_BASE_URL")
RED_USERNAME = os.getenv("TEST_RED_USERNAME")
RED_PASSWORD = os.getenv("TEST_RED_PASSWORD")
HAS_STUDENT = bool(STUDENT_USERNAME and STUDENT_PASSWORD and STUDENT_BASE_URL)
HAS_RED = bool(RED_USERNAME and RED_PASSWORD)

LOGIN_URL = f"{BASE_URL}/login"
# 学生端登录地址：只在 HAS_STUDENT 为 True 时被 L5 用例使用
STUDENT_LOGIN_URL = f"{STUDENT_BASE_URL}/login" if STUDENT_BASE_URL else None

# ============ 等待时间（秒） ============
# 显式等待最多等多久。太小->网络一慢就误报失败；太大->失败用例卡很久
TIMEOUT = 10

# ============ 非敏感测试数据：留在代码里无妨 ============
# 故意用来测"登录失败"的错误密码
WRONG_PASSWORD = "wrong_pwd_000"
# 负向用例专用：一个不存在的账号（避免误伤真实账号）
NOT_EXIST_USER = "t_not_exist_9999"

# 测试环境里固定存在的课程（环境事实，非机密；E2E 用例按课程名锁定卡片）
COURSE_NAME = "大数据技术与原理"

# ============ 调试开关 ============
# True ：用例跑完不关浏览器（方便肉眼查页面），只适合调试单条用例
# False：正常关闭（跑全量、跑 CI 必须用这个）
# 为什么不能一直 True？detach 会让 Edge / msedgedriver 进程残留，
# 用例一多就资源争抢，出现"某条 ERROR、重跑又好了"的偶发问题
BROWSER_DEBUG = False