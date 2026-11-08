"""
L5 前置侦察脚本：学生端页面结构勘查（2026-11-07）
- 任务：demo_student 登录后登记"我的课程"页结构；若"加入课程"入口存在，点进去看一眼表单（导航级，安全）
- 铁律：邀请码不填、"加入"按钮不点——加入课堂是写操作（🟡），定性留给用例设计阶段
- 手册情报（学生端操作手册 v2.0 §2.1/2.2）：
  "我的课程"右上角"加入课程" -> 加入页填 6 位邀请码 -> 识别后显示课程信息 -> 点"加入"提示"已加入"
  空态文案："还没有课程。右上角加入一门，就能看到课堂和课件"
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_l5_student.py"
"""
import os
import sys

# Windows 控制台默认 GBK，页面文字里的特殊符号（如 ▾）编不进 GBK 会直接报 UnicodeEncodeError
# 把标准输出强制成 UTF-8，编不了的字符用替代符，保证侦察脚本不因为打印而崩
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

from config import STUDENT_LOGIN_URL, STUDENT_USERNAME, STUDENT_PASSWORD
from pages.login_page import LoginPage
from script.probe_console import probe_page_structure

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def main():
    assert STUDENT_USERNAME and STUDENT_PASSWORD and STUDENT_LOGIN_URL, ".env 缺少 TEST_STUDENT_*，先配学生账号"
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(STUDENT_LOGIN_URL)  # 学生端独立入口（实测 8082，老师端提交会被拒"请使用学生端登录"）
        login = LoginPage(driver)
        login.login(STUDENT_USERNAME, STUDENT_PASSWORD)
        assert login.is_login_success(), "demo_student 登录失败（账号状态？登录页结构变了？）"
        print(f"学生端登录后 URL：{driver.current_url}")

        # 第一站：我的课程页（或落地页）——登记可交互元素清单 + 截图
        probe_page_structure(driver, "学生端落地页")
        driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_landing.png"))

        # 空态文案探测：手册说没课时显示"还没有课程"
        body_text = driver.find_element(By.TAG_NAME, "body").text
        print(f"\n页面含'还没有课程'空态文案：{'还没有课程' in body_text}")
        print(f"页面含'加入课程'字样：{'加入课程' in body_text}")

        # 第二站：加入课程入口（导航级动作，只看不提交）
        join_btn = (By.XPATH, "//button[contains(., '加入课程')]|//a[contains(., '加入课程')]")
        from base.base_page import BasePage
        bp = BasePage(driver)
        if bp.is_element_visible(join_btn, timeout=3):
            bp.click_element(join_btn)
            import time
            time.sleep(2)  # 侦察允许睡：等页面稳定
            print(f"\n点'加入课程'后 URL：{driver.current_url}")
            probe_page_structure(driver, "加入课程页")
            driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_join.png"))
            # 登记邀请码输入框特征（只读属性，不输入）
            inputs = driver.execute_script("""
                const out = [];
                document.querySelectorAll('input').forEach(el => out.push({
                    type: el.type, placeholder: el.placeholder || '',
                    maxlength: el.getAttribute('maxlength'),
                }));
                return out;
            """)
            print("加入页 input 清单（找 6 位邀请码框就看 maxlength/placeholder）：")
            for it in inputs:
                print(f"  type={it['type']!r} placeholder={it['placeholder']!r} maxlength={it['maxlength']}")
        else:
            print("\n没找到'加入课程'入口——可能已加入课程后入口形态变化，看截图定性")

        print("\n侦察完毕：只登录、浏览、进了加入页看表单，没填码没点加入。输出贴回来做 L5 用例设计。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
