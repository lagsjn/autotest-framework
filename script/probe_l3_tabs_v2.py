r"""
L3 页签重侦察（新版 UI，只读）：a.cb__tab 的 URL 形态和选中态判据到底是什么？—— 2026-11-14
- 为什么要重侦察：L3 四条用例的数据（TAB_CASES）来自 probe_tabs.py 在旧版 UI 的实测
  （2026-11-01：BUTTON.tp-bc-sub-btn + ?tab=materials 查询参数式路由）。
  11-14 界面改版实锤（§13.5）：tp-bc-sub-btn 全族已死，页签换成 a.cb__tab（<a> 路由链接）。
  <a> + router-link 意味着 URL 很可能变成路径式（/courses/14/xxx），
  但也可能仍带 ?tab= 参数——形态不实测就不能写进断言，这是纪律。
- 顺带要拿到的情报：
  ① 每个页签的 text / href（预判路由形态）
  ② 逐个点击后的真实 URL（router-link 可能改写 href，眼见为实）
  ③ 选中态判据：旧版是 class 含 is-active，新版 dump 里见过 is-on 和
     router-link-active——到底用哪个断言，点击后当场比对
  ④ 默认页签是哪个（旧版是"课表排期"，dump 显示新版默认像是"概览"，实测确认）
- 手段：纯导航巡礼，只点页签切换，不碰任何写操作按钮，看完即关。
- 运行：& ".venv\Scripts\python.exe" "script\probe_l3_tabs_v2.py"
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


def tab_snapshot(driver):
    """把当前所有页签的 (文字, class, href) 打出来，key 去重防重复渲染行"""
    tabs = driver.find_elements(By.CSS_SELECTOR, "a.cb__tab")
    rows = []
    for t in tabs:
        rows.append((t.text.strip().replace("\n", " ")[:12],
                     (t.get_attribute("class") or "").strip(),
                     t.get_attribute("href")))
    return rows


def main():
    edge_options = Options()
    # 与 conftest._make_browser 对齐：自签证书不忽略的话停在警告页等不到登录框
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，侦察终止"

        # 复用已适配的入场链路：点卡片 -> （若落当前讲次页）面包屑扳回详情页
        course = CoursePage(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(course.enter_course_btn))
        course.enter_course()
        url = course.wait_url_matches(r"/courses/\d+")
        assert url, f"没到详情页，停在：{driver.current_url}"
        print(f"详情页 URL: {url}")

        # 等页签栏渲染就绪再抢跑（Vue 异步填充，presence 只代表节点挂上）
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.cb__tab")))
        time.sleep(2)

        print("\n===== ① 初始快照（进详情页默认态）=====")
        for text, cls, href in tab_snapshot(driver):
            print(f"  {text:14} | {cls:70} | {href}")

        # ② 逐个点击：记下点击前 URL，点完等 URL/渲染变化再记录
        #    "设置"页可能带表单，但只看不存，仍属绿级只读
        names_to_try = []
        for text, _, _ in tab_snapshot(driver):
            names_to_try.append(text)
        print(f"\n===== ② 逐一点页签：{names_to_try} =====")
        for name in names_to_try:
            tab = (By.XPATH, f"//a[contains(@class,'cb__tab')][contains(text(),'{name.split()[0]}')]")
            try:
                driver.get(url)  # 每次都从详情页裸 URL 出发，排除上一条残留状态
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.cb__tab")))
                time.sleep(1)
                before = driver.current_url
                course.click_element(tab)
                for _ in range(20):
                    if driver.current_url != before:
                        break
                    time.sleep(0.5)
                after = driver.current_url
                # 点击后各页签的 class（找选中态判据：is-on? router-link-active?）
                hit = [f"({t}, {'is-on' in c and 'is-on' or ''}"
                       f"{'router-link-active' in c and ' RLA' or ''})"
                       for t, c, _ in tab_snapshot(driver)]
                print(f"  [{name}] {before}  ->  {after}")
                print(f"      点击后各页签态: {' '.join(hit)}")
            except Exception as e:
                print(f"  [{name}] 点击失败: {type(e).__name__}: {str(e)[:80]}")

        print("\n判读要点：URL 形态（?tab= 参数式 or /courses/14/xxx 路径式 or 不变）"
              "决定 TAB_CASES 的 expect_url；选中态 class 决定 is_tab_active() 的判据。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
