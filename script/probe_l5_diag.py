"""
L5 侦察插曲：demo_student 登录失败一次性诊断（2026-11-07）
纪律：失败计数按账号记，只跑一次，绝不连续重试防锁号
手段：复用登录页的 MutationObserver toast 埋点（点击前监听），抓失败提示文案 + 截图
运行：& ".venv\\Scripts\\python.exe" "script\\probe_l5_diag.py"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.edge.options import Options

from config import LOGIN_URL, STUDENT_USERNAME, STUDENT_PASSWORD
from pages.login_page import LoginPage

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def main():
    print(f"提交账号：{STUDENT_USERNAME!r}（密码不打印）")
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.start_watch_toast()  # 必须在点登录之前埋监听
        login.login(STUDENT_USERNAME, STUDENT_PASSWORD)
        texts = login.wait_toast_texts(timeout=6)
        print(f"toast 抓到的提示文案：{texts}")
        print(f"登录后 URL：{driver.current_url}")
        print(f"登录是否成功：{login.is_login_success(timeout=3)}")
        driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_diag.png"))
        print(f"现场截图：{os.path.join(SHOT_DIR, 'probe_l5_diag.png')}")
        print("\n定性参考：'账号或密码错误'->账密有一项不对；'账号不存在'->用户名不对；没提示但没跳转->其他原因")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
