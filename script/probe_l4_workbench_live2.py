r"""
L4' 实时工作台侦察 第二轮（只读）：真正的"签到/点名/大屏"控制台入口到底在哪？—— 2026-11-15
- 上一轮 probe_l4_workbench_live.py 实测：点课程卡片落的 /lessons/103 页面 tp-bc-sub-btn/
  ui-shell__tab/cb__tab 全部 0 命中，看到的还是 /lessons/<id> 那套 llink 报表壳（只是
  数据实时了，出现"还有44位未签到""标为请假"这类按钮）——说明"上课中"不等于卡片落点
  会自动换成一个完全不同的实时控制台页面，真正的工作台入口可能是另一条独立路径。
- 常见产品模式：老师开课后，界面上通常有一处专门的"正在上课，点击进入课堂"入口，
  大概率住在这两个地方，本脚本都要查：
  ① /today（左侧栏"今天"）：当日课程列表，进行中的课一般置顶且给一个显眼的进入按钮
  ② 课程详情页"课表"页签（?tab=lessons）：讲次列表里"进行中/ongoing"那条卡片挂的按钮，
     跟 ended 讲次的"查看回放"类按钮文字/链接很可能不一样
- 安全边界：只读，找到可疑入口只 dump 它的 href/class/文字，不点击"下课/发布/开始上课"
  这类真正改变课堂状态的按钮；进入新页面本身（点导航链接）是绿级只读操作，可以做。
- 运行：& ".venv\Scripts\python.exe" "script\probe_l4_workbench_live2.py"
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import LOGIN_URL, BASE_URL, USERNAME, PASSWORD
from pages.login_page import LoginPage
from pages.course_page import CoursePage


def dump_interactive(driver, label, limit=80):
    print(f"\n===== {label} =====")
    els = driver.find_elements(By.CSS_SELECTOR, "a, button")
    shown = 0
    for e in els:
        try:
            if not e.is_displayed():
                continue
            cls = (e.get_attribute("class") or "").strip()
            txt = (e.text or "").strip().replace("\n", " ")[:34]
            href = (e.get_attribute("href") or "")
            href_tail = href.replace(BASE_URL, "") if href else ""
            if not txt and not cls:
                continue
            print(f"  {e.tag_name:6} | {cls[:52]:52} | {txt:34} | {href_tail[:34]}")
            shown += 1
            if shown >= limit:
                print(f"  ...（截断，共超过 {limit} 个）")
                break
        except Exception:
            pass
    print(f"  可见交互元素合计展示 {shown} 个")


def main():
    edge_options = Options()
    edge_options.add_argument("--ignore-certificate-errors")
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，侦察终止"

        # ① 先去 /today（不走课程卡片，那是已知答案的路径）
        driver.get(f"{BASE_URL}/today")
        time.sleep(3)
        print(f"① 今天页 URL: {driver.current_url}")
        dump_interactive(driver, "①b 今天页可见交互元素——找'正在上课/进入课堂'类入口", limit=100)

        # 找 href 里带非 /courses /lessons /today 常规前缀的可疑路径（可能是新的实时课堂专属路由）
        print("\n①c 今天页里 href 不像常规报表/详情页的链接（候选新入口）：")
        seen_hrefs = set()
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = (a.get_attribute("href") or "").replace(BASE_URL, "")
            if href and href not in seen_hrefs and a.is_displayed():
                if not any(href.startswith(p) for p in ("/courses", "/today", "/assistant", "/login")):
                    seen_hrefs.add(href)
                    print(f"    href={href!r} text={a.text.strip()[:24]!r} class={a.get_attribute('class')!r}")

        # ② 课表页签里"进行中"讲次卡片挂的按钮
        course = CoursePage(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(course.enter_course_btn))
        course.click_element(course.enter_course_btn)
        landed = course.wait_url_matches(r"/courses/\d+|/lessons/\d+")
        if landed and "/lessons/" in landed:
            course.click_element(course.back_to_course_btn)
            course.wait_url_matches(r"/courses/\d+")
        course.click_element(course.tab_btn("课表"))
        assert course.wait_url_matches(r"tab=lessons"), "课表页签没跳过去"
        time.sleep(2)
        print(f"\n② 课表页签 URL: {driver.current_url}")
        dump_interactive(driver, "②b 课表页签——ongoing 讲次卡片挂的按钮/链接", limit=100)

        print("\n②c 课表页签里所有 href 含 /lessons/ 的链接（区分 ongoing vs ended 卡片文案）：")
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/lessons/']"):
            if a.is_displayed():
                href = (a.get_attribute("href") or "").replace(BASE_URL, "")
                print(f"    href={href!r} text={a.text.strip()[:30]!r} class={a.get_attribute('class')!r}")

        print("\n判读要点：①c 若出现一个跟 /lessons/<id> 不同的新路径（比如 /teach/ /live/ /class/），"
              "那才是真·实时工作台入口；②c 用来对比 ongoing 卡片跟 ended 卡片挂的链接是不是同一个。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
