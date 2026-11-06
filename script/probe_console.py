"""
L4 前置侦察脚本：课堂控制台页面结构勘查（2026-11-02）
- 老师已确认（业务流程地图 §10-1）：随时可进工作台、与是否正在上课无关 → 进门动作=绿级
- 铁律：进门之后只"看"不"点"——签到/点名/发布测验等按钮在定性前全部按黄/红对待
- 新知识点：进入工作台可能开新标签页，Selenium 默认留在原标签页操作，
  必须先 window_handles 拿清单、switch_to.window 切焦点，否则查什么都"不存在"
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_console.py"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.edge.options import Options

from config import LOGIN_URL, USERNAME, PASSWORD, COURSE_NAME
from pages.login_page import LoginPage
from pages.course_page import CoursePage

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def probe_page_structure(driver, tag):
    """
    登记当前页面上的"可交互元素清单"：按钮/链接/页签，只读不点
    输出字段：tag 标签名、可见文字、class、是否禁用、aria 语义
    为什么把 disabled 也抓：禁用态=前端在告诉我们"现在这个操作不可用"，
    它背后就是业务规则（比如没开课时测验按钮灰着），是免费的需求文档
    """
    items = driver.execute_script("""
        const sel = 'button, a, [role="tab"], [role="button"]';
        const out = [];
        document.querySelectorAll(sel).forEach(el => {
            const text = (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 20);
            out.push({
                tag: el.tagName,
                text: text,
                class: (el.className || '').toString().slice(0, 60),
                disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
                href: el.getAttribute('href'),
            });
        });
        return out;
    """)
    print(f"\n{'='*60}\n[{tag}] 可交互元素清单（共 {len(items)} 个）\n{'='*60}")
    seen = set()  # 去重：同一文字+同一class的按钮只报一次，防刷屏
    for it in items:
        key = (it["tag"], it["text"], it["class"])
        if key in seen:
            continue
        seen.add(key)
        flag = " [禁用]" if it["disabled"] else ""
        href = f" -> {it['href']}" if it["href"] else ""
        print(f"  <{it['tag']}> {it['text']!r}{flag}{href}  class={it['class']!r}")
    return items


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        # 入场链路：登录 → 课程卡片 → 详情页（全部是 L2/L3 已验证的绿级动作）
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "前置失败：登录没成功（查账号状态）"

        course = CoursePage(driver)
        assert course.is_element_exist(course.enter_course_btn, timeout=10), \
            f"课程列表找不到：{COURSE_NAME}"
        course.enter_course()
        assert course.wait_url_matches(r"/courses/\d+"), "进不去课程详情页"

        # 进门：点"进入上课工作台"（老师已放行）。先记下原标签页，用于处理"新开页"情况
        old_handles = set(driver.window_handles)
        course.click_element(course.workbench_entry_btn)

        import time
        time.sleep(3)  # 侦察脚本允许睡：等新标签页稳定（正式用例严禁，用智能等待）
        new_handles = [h for h in driver.window_handles if h not in old_handles]
        if new_handles:
            driver.switch_to.window(new_handles[0])
            print(f"检测到新开标签页，已切换。共 {len(driver.window_handles)} 个标签页")
        else:
            print("没有新标签页，工作台在当前页内打开")

        print("工作台 URL：", driver.current_url)
        probe_page_structure(driver, "课堂控制台")

        shot = os.path.join(SHOT_DIR, "probe_console.png")
        driver.save_screenshot(shot)
        print(f"现场截图：{shot}")
        print("\n侦察完毕：只看了，没点任何功能按钮。输出贴回来做九功能定性。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
