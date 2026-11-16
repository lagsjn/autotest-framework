r"""
L4 课堂控制台重侦察（新版 UI，只读）：入场入口、子导航锚点、选中态判据全换新了吗？—— 2026-11-14
- 为什么要重侦察：11-14 界面改版实锤（§13.5），console_page.py 整套锚点基于
  probe_console.py 2026-11-04 的实测（旧 tp-* 体系），子导航 tp-bc-sub-btn、出口
  tp-nav-menu__home 已随改版失效，L4 十条全红。不实测就重写=闭眼改，纪律不允许。
- 与 L3 侦察的不同：旧情报来自"实时课堂"（当时有 ongoing），而现在点卡片落的
  /lessons/<id> 是 ended 讲次的回放页——新版里"回放页"和"上课工作台"可能是两套 UI，
  本脚本两种状态都要取证，用例才能设计。
- 要拿到的五份情报：
  ① 点课程卡片的落点（哪一讲？URL 形态）
  ② 详情页（概览）上还有没有"进入课堂/工作台"类入口（文字+class 全 dump）
  ③ 课表页签（?tab=lessons）里讲次卡片挂着什么按钮（"查看/进入"类，可能是新入口）
  ④ /lessons/<id> 页的可见交互元素结构：子导航到底是不是 ui-shell__tab 族
     （上轮 dump 里那族是 display=False 的移动端 tabbar，桌面端子导航另有其人）
  ⑤ 选中态判据 + 出口锚点 + el-drawer 抽屉还在不在
- 安全边界：全程只导航、只切换查看，不点下课/发布/开始上课等任何写操作；
  只看不存，看完即关。
- 运行：& ".venv\Scripts\python.exe" "script\probe_l4_console_v2.py"
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

from config import LOGIN_URL, USERNAME, PASSWORD
from pages.login_page import LoginPage
from pages.course_page import CoursePage


def dump_interactive(driver, label, limit=60):
    """dump 当前页可见的 <a>/<button> 交互元素：tag | class | 文字 | href尾段"""
    print(f"\n===== {label} =====")
    els = driver.find_elements(By.CSS_SELECTOR, "a, button")
    shown = 0
    for e in els:
        try:
            if not e.is_displayed():
                continue
            cls = (e.get_attribute("class") or "").strip()
            txt = (e.text or "").strip().replace("\n", " ")[:26]
            href = (e.get_attribute("href") or "")
            href_tail = href.replace("https://demo.test-env.local:8081", "") if href else ""
            if not txt and not cls:
                continue
            print(f"  {e.tag_name:6} | {cls[:52]:52} | {txt:26} | {href_tail[:34]}")
            shown += 1
            if shown >= limit:
                print(f"  ...（截断，共超过 {limit} 个）")
                break
        except Exception:
            pass  # dump 途中被 SPA 重渲染干掉，跳过
    print(f"  可见交互元素合计展示 {shown} 个")


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')  # 自签证书，同 conftest
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，侦察终止"

        course = CoursePage(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(course.enter_course_btn))

        # ① 点卡片看落点（不动用 enter_course，它会把 lessons 落点扳回详情页）
        course.click_element(course.enter_course_btn)
        for _ in range(20):
            if "/lessons/" in driver.current_url or "/courses/" in driver.current_url:
                break
            time.sleep(0.5)
        landing = driver.current_url
        print(f"① 卡片落点: {landing}")
        time.sleep(2)  # 等这页异步渲染
        lessons_direct = "/lessons/" in landing
        if lessons_direct:
            dump_interactive(driver, "①b 落点页（/lessons）可见交互元素")
            # 抽屉探测（旧版进入时自带打开态抽屉）
            drawer = driver.find_elements(By.CSS_SELECTOR,
                                         ".el-drawer, .el-overlay-drawer")
            print(f"  el-drawer 命中: {len(drawer)} 个，"
                  f"可见: {[d.is_displayed() for d in drawer]}")

        # 回详情页，查新版入口在哪
        driver.get(landing.split("/lessons/")[0].split("/courses/")[0]
                   + "/courses/14" if ("/lessons/" in landing or "/courses/" in landing)
                   else landing)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.cb__tab")))
        print(f"\n② 详情页概览 URL: {driver.current_url}")
        dump_interactive(driver, "②b 详情页（概览）可见交互元素——找课堂/工作台入口", limit=80)

        # ③ 课表页签：讲次列表里每讲挂什么按钮
        course.click_element(course.tab_btn("课表"))
        assert course.wait_url_matches(r"tab=lessons"), "课表页签没跳过去"
        time.sleep(2)
        dump_interactive(driver, "③ 课表页签（?tab=lessons）——讲次卡片上的入口按钮", limit=90)

        # ④ 从课表页找"进入/查看课堂"类链接进 /lessons/<id>
        links = [a for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/lessons/']")]
        print(f"\n④a 课表页里 href 含 /lessons/ 的链接: {len(links)} 个")
        for a in links[:10]:
            print(f"    text={a.text.strip()[:20]!r} href={a.get_attribute('href')} "
                  f"visible={a.is_displayed()}")
        target = next((a for a in links if a.is_displayed()), None)
        if target:
            target.click()
            for _ in range(20):
                if "/lessons/" in driver.current_url:
                    break
                time.sleep(0.5)
            print(f"④b 进入课堂页: {driver.current_url}")
            time.sleep(3)  # 等控制台自己的异步渲染
            dump_interactive(driver, "④c 课堂页可见交互元素——子导航锚点全在这", limit=90)

            # ⑤ 选中态判据：找疑似子导航族元素，把 class 原样打回来比对
            for probe_cls in ("ui-shell__tab", "cb__tab", "el-tabs__item",
                              "[class*='sub']", "[class*='menu']"):
                found = driver.find_elements(By.CSS_SELECTOR, probe_cls)
                vis = [f for f in found if f.is_displayed()]
                if vis:
                    print(f"\n⑤ {probe_cls}: 共 {len(found)} 个，可见 {len(vis)} 个")
                    for f in vis[:12]:
                        print(f"    {(f.get_attribute('class') or '')[:70]:70} "
                              f"text={(f.text or '').strip()[:16]!r}")
        else:
            print("④ 课表页没找到可见的 /lessons/ 链接——入口可能在别处（今天页/课堂工具菜单）")

        print("\n判读要点：②③④确定 L4 新入场链路；④c+⑤ 定 console_page.py 重写的"
              "子导航定位器与选中态类名；抽屉情报决定 _enter_workbench 要不要保留关闭步骤。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
