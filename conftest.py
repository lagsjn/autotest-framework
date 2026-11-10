import logging
import os
import re
import sys
from datetime import datetime

import allure
import pytest

from selenium import webdriver
from selenium.webdriver.edge.options import Options

from config import (
    LOGIN_URL, BROWSER_DEBUG, USERNAME, PASSWORD, BASE_URL,
    STUDENT_LOGIN_URL, STUDENT_BASE_URL, STUDENT_USERNAME, STUDENT_PASSWORD,
)
from pages.login_page import LoginPage
from api.login_api import LoginApi
from api.course_api import CourseApi

# log 目录专门放运行产物：日志 + 失败截图（以后不提交到 git）
LOG_DIR = os.path.join(os.path.dirname(__file__), "log")
SHOT_DIR = os.path.join(LOG_DIR, "screenshot")
LOG_FILE = os.path.join(LOG_DIR, "test.log")


def _setup_logger():
    """全局 logger：控制台 + 文件双写
    为什么配在 conftest？它是 pytest 的框架入口，在这里配一次，
    所有用例、所有钩子都用 logging.getLogger("autotest") 拿同一个对象
    """
    lg = logging.getLogger("autotest")
    if lg.handlers:  # 防止重复添加 handler -> 同一条日志打印两遍（新手高频坑）
        return lg
    lg.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    # mode="w"：每次跑全量前清掉上次日志，防止新旧混着看不出问题
    file_h = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_h.setFormatter(fmt)
    lg.addHandler(console)
    lg.addHandler(file_h)
    return lg


logger = _setup_logger()


def _make_browser():
    """统一造一个配好选项的 Edge 实例（多处 fixture 复用，避免重复 = 改一处全生效）
    为什么抽出来？老师/学生两个 session 级 fixture + function 级 driver 都要
    同样走一遍"忽略自签证书 + 调试时不关窗 + 最大化"，复制三处将来必漏改
    """
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    if BROWSER_DEBUG:
        # 只在调试时开：跑完不关浏览器，方便你看页面
        # 正式跑/CI 必须把 config.py 里的 BROWSER_DEBUG 改成 False，否则进程会残留
        edge_options.add_experimental_option("detach", True)
    dr = webdriver.Edge(options=edge_options)
    dr.maximize_window()
    return dr


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    pytest 钩子：每条用例的每个阶段结束后都会被调用一次
    现在做两件事：每条用例记一行结果日志；失败的自动截图留证据
    为什么用钩子而不是每条用例自己写？
    因为那是 100 条用例的重复劳动；框架层写一次，所有用例自动生效
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    logger.info(f"[{report.outcome.upper()}] {item.name}")
    if report.failed:
        # 两条路都认：function 级的 driver，或 session 级复用的 logged_in_driver
        dr = item.funcargs.get("driver") or item.funcargs.get("logged_in_driver")
        if dr is None:
            return
        os.makedirs(SHOT_DIR, exist_ok=True)
        # 中文参数会被 pytest 转义成 \u7b7e 这种写法，反斜杠在 Windows 里是路径分隔符
        # 会把文件名变成不存在的子目录（WinError 3），所以先把非法字符替换掉
        safe_name = re.sub(r'[\\/:*?"<>|]', "_", item.name)
        path = os.path.join(SHOT_DIR, f"{safe_name}_{datetime.now():%H%M%S}.png")
        try:
            dr.save_screenshot(path)
            logger.info(f"[失败自动截图] {path}")
            # 把截图作为附件钉进 allure 报告：看报告的人不用再去翻 log 目录
            allure.attach.file(
                path,
                name=f"{item.name} 失败现场",
                attachment_type=allure.attachment_type.PNG,
            )
            # 日志也钉进去：失败前后的运行留痕跟着用例走，一封报告=完整案卷
            with open(LOG_FILE, encoding="utf-8") as f:
                allure.attach(f.read(), name="运行日志",
                              attachment_type=allure.attachment_type.TEXT)
        except Exception as e:  # 截图本身挂了不能再把用例报告带坏
            logger.warning(f"[截图失败] {e}")

@pytest.fixture(scope="function")
def fresh_page(logged_in_driver):
    """每条用例拿到手之前，先把页面拽回系统入口（登录态还在，只是位置归零）
    治的就是"状态残留"：上一条用例逛到哪都不算数，下一条永远从同一起点出发
    """
    logger.info("==> 页面归位：重新打开系统入口")
    logged_in_driver.get(BASE_URL)
    return logged_in_driver

@pytest.fixture(scope="function")
def driver():
    logger.info("==> 启动浏览器（function 级）")
    dr = _make_browser()
    dr.get(LOGIN_URL)
    yield dr
    # yield后面：用例执行完之后执行
    logger.info("==> 关闭浏览器")
    dr.quit()

@pytest.fixture(scope="session")
def logged_in_driver():
    """session 级：整场 pytest 只开一次浏览器、只登录一次，登录态全员共享
    给"进去以后"的业务模块（课程/工作台）用；登录模块自己不许用
    前置失败（比如账号被锁）会让所有用它的用例集体阵亡——见讲解的连锁失败风险
    """
    logger.info("==> 启动老师端浏览器（session 级，登录态复用）")
    dr = _make_browser()
    dr.get(LOGIN_URL)
    login = LoginPage(dr)
    login.login(USERNAME, PASSWORD)
    assert login.is_login_success(), "登录态复用前置失败：正确账号密码没登进去（账号被锁？）"
    logger.info("==> 登录成功，登录态交给本会话所有用例共享")
    yield dr
    dr.quit()


@pytest.fixture(scope="session")
def logged_in_student():
    """session 级：整场只开一次学生端浏览器、只登录一次 demo_student（L5 跨端专用）
    这是本框架第一次"同一趟测试里并存两个身份"：
    老师端 logged_in_driver 走 8081，学生会话走 8082，各开各的、互不干扰
    前置失败（学生账号被锁/端口错）只波及用到它的跨端用例，不影响老师端主干
    """
    logger.info("==> 启动学生端浏览器（session 级，登录态复用）")
    dr = _make_browser()
    dr.get(STUDENT_LOGIN_URL)
    login = LoginPage(dr)
    login.login(STUDENT_USERNAME, STUDENT_PASSWORD)
    assert login.is_login_success(), "学生登录态前置失败：demo_student 没登进去（账号被锁？端口配错？）"
    logger.info("==> 学生登录成功，登录态交给跨端用例共享")
    yield dr
    dr.quit()


@pytest.fixture(scope="function")
def fresh_student_page(logged_in_student):
    """学生版页面归位：每条跨端用例开跑前把学生浏览器拽回学生端入口（登录态还在）
    和老师版 fresh_page 对称——起点一致，用例之间才互不串扰
    """
    logger.info("==> 学生页面归位：重新打开学生端入口")
    logged_in_student.get(STUDENT_BASE_URL)
    return logged_in_student


# ==================== 接口自动化 fixture ====================
@pytest.fixture(scope="function")
def login_api():
    """登录接口对象（function 级：无状态、成本低，每条用例各自 new 一个互不干扰）"""
    return LoginApi()


@pytest.fixture(scope="function")
def course_api():
    """课程接口对象"""
    return CourseApi()


@pytest.fixture(scope="session")
def api_token():
    """session 级：整场 pytest 只登录一次、只取一次 token，全项目接口用例共享
    对标 UI 的 logged_in_driver：前置失败（账号被锁/接口挂了）只影响需要登录态的接口用例，
    不波及 UI 用例（两套体系互不依赖，一边挂另一边照跑）
    """
    logger.info("==> 接口层：登录取 token（session 级，登录态复用）")
    token = LoginApi().login_and_get_token()
    logger.info("==> 接口层 token 已取得，交给本会话所有需要鉴权的用例")
    return token