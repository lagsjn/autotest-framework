"""
L5 收尾侦察②：定位课程详情页"归档/删除"下拉菜单的触发器（只读，2026-11-08）
上一步已确认入口：详情页 el-dropdown 内有 '归档课程'(el-dropdown-menu__item) + '删除课程'(tp-menu-danger)
本步目标：找到点开这个下拉的触发按钮（class/text），并列出展开后的全部菜单项
安全红线：只点 el-dropdown 触发器（仅让菜单显形）；绝不点 '归档课程'/'删除课程' 本体；菜单看完按 ESC 收起
运行：& ".venv\\Scripts\\python.exe" "script\\probe_l5_archive2.py"
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from config import LOGIN_URL, USERNAME, PASSWORD, COURSE_NAME

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def dump_dropdown_triggers(driver):
    """找所有 el-dropdown 触发器，报告其文本/class/所在区域，供用例定位'更多'入口"""
    return driver.execute_script("""
        const out = [];
        document.querySelectorAll('.el-dropdown, [class*="dropdown__trigger"], [class*="tp-menu"]').forEach(el => {
            const trig = el.querySelector('.el-dropdown__trigger, [class*="trigger"]') || el;
            out.push({
                cls: (el.className || '').toString().slice(0, 70),
                trigText: (trig.textContent || '').trim().slice(0, 20),
                trigCls: (trig.className || '').toString().slice(0, 70),
                visible: !!(el.offsetWidth || el.offsetHeight),
            });
        });
        return out.slice(0, 15);
    """)


def dump_menu_items(driver):
    """展开后列出下拉菜单里所有项（文本+class），标注是否危险项"""
    return driver.execute_script("""
        const items = [];
        document.querySelectorAll('.el-dropdown-menu__item, [class*="tp-menu"]').forEach(el => {
            const t = (el.textContent || '').trim();
            if (t) items.push({text: t.slice(0, 20), cls: (el.className||'').toString().slice(0,60),
                                visible: !!(el.offsetWidth||el.offsetHeight)});
        });
        return items.slice(0, 20);
    """)


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        from pages.login_page import LoginPage
        from pages.course_page import CoursePage
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "demo_teacher 登录失败"

        course = CoursePage(driver)
        assert course.is_element_exist(course.enter_course_btn, timeout=10), "没找到卡片"
        course.enter_course()
        time.sleep(2)
        print(f"详情页 URL：{driver.current_url}")

        print("\n【触发器清单】")
        for t in dump_dropdown_triggers(driver):
            print(f"  cls={t['cls']!r}\n     trigText={t['trigText']!r} trigCls={t['trigCls']!r} visible={t['visible']}")

        # 点开第一个 el-dropdown 触发器（仅让菜单显形，不点危险项）
        print("\n【点开下拉后菜单项】")
        try:
            trig = driver.find_element(By.CSS_SELECTOR, ".el-dropdown .el-dropdown__trigger, .el-dropdown")
            trig.click()
            time.sleep(1)
            for it in dump_menu_items(driver):
                print(f"  {it['text']!r} cls={it['cls']!r} visible={it['visible']}")
            driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_dropdown_open.png"))
        except Exception as e:
            print(f"  点开失败：{e}")
        finally:
            # 收起菜单，避免停在展开态
            try:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass

        print("\n侦察完毕：只点开下拉看菜单，未点'归档课程'/'删除课程'本体。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
