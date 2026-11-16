r"""
L4' 实时工作台侦察 第三轮（只读）：/lessons/<id>/live 这条路径里到底有什么？—— 2026-11-15
- 用户证言：点"临时调课，现在开课"（li__force/next__force 按钮）之后，浏览器地址栏是
  https://demo.test-env.local:8081/lessons/104/live ——多了一个 /live 尾段，跟前两轮的
  /lessons/<id>（不带 live）是两套不同页面，这就是我们要找的真·实时工作台入口。
- 不写死 104：lesson id 是这堂课的临时 id，用户下次再点"临时调课，现在开课"会是别的数字。
  用 preflight_ui.py 同款 API 查询：拿演示课当前 status='ongoing' 的讲次 id，动态拼 URL，
  这样这个脚本以后还能复用（比死记一个 lesson id 稳）。
- 要拿到的情报（跟前两轮"报表壳"侦察不同的地方：这次页面内容应该是功能面板，不是数据展示）：
  ① 可见交互元素全 dump（a/button），重点找"签到/点名/大屏/弹幕/提问/讨论/评分"这套工具面板的锚点
  ② 候选子导航族（tp-bc-sub-btn / ui-shell__tab / 其它新命名）逐个探测命中数 + class 原样打回
  ③ 选中态判据：这轮先只 dump 不点（怕点到"下课/发布/签到确认"这类真写操作），
     下一轮如果需要断言选中态，再单独设计"安全点击序列"
  ④ el-drawer：第一轮报表页是 0 命中，实时页是不是又出现了（旧版工作台有此机制）
- 安全边界：本脚本全程不 click 任何按钮，只 driver.get 直达 + 只读 dump DOM；
  哪怕 /live 页面上有"下课"按钮，也不碰。
- 运行：& ".venv\Scripts\python.exe" "script\probe_l4_workbench_live3.py"
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

from config import BASE_URL, LOGIN_URL, USERNAME, PASSWORD, COURSE_NAME
from api.base_api import BaseApi
from api.course_api import CourseApi
from api.login_api import LoginApi
from pages.login_page import LoginPage


def items_of(resp):
    data = (resp.json() or {}).get("data") if resp.text else None
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def find_ongoing_lesson_id():
    """用 API 找演示课当前 ongoing 的讲次 id（跟 preflight_ui.py 同一套只读查询）"""
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    courses = CourseApi(BASE_URL)
    hit = [c for c in items_of(courses.list_courses(token)) if c.get("name") == COURSE_NAME]
    if not hit:
        return None
    lessons = items_of(courses.get(f"/courses/{hit[0]['id']}/lessons", token=token,
                                   params={"page": 1, "page_size": 30}))
    ongoing = [l for l in lessons if l.get("status") == "ongoing"]
    return ongoing[0]["id"] if ongoing else None


def dump_interactive(driver, label, limit=120):
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
            print(f"  {e.tag_name:6} | {cls[:55]:55} | {txt:34} | {href_tail[:36]}")
            shown += 1
            if shown >= limit:
                print(f"  ...（截断，共超过 {limit} 个）")
                break
        except Exception:
            pass
    print(f"  可见交互元素合计展示 {shown} 个")


def main():
    lesson_id = find_ongoing_lesson_id()
    if not lesson_id:
        print("没查到 ongoing 讲次——课堂可能已经下课了，或者这门课现在没有进行中的讲次。")
        print("请先在界面上重新点一次'临时调课，现在开课'，再跑本脚本。")
        return
    print(f"API 查到当前 ongoing 讲次 lesson id = {lesson_id}（不写死，动态拼 URL）")

    live_url = f"{BASE_URL}/lessons/{lesson_id}/live"

    edge_options = Options()
    edge_options.add_argument("--ignore-certificate-errors")
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        # 先走一次正常登录拿会话 cookie，再直达 /live（不能跳过登录直接 get live_url，会跳回登录页）
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，侦察终止"

        driver.get(live_url)
        for _ in range(20):
            if "/live" in driver.current_url:
                break
            time.sleep(0.5)
        print(f"\n① 直达实时工作台 URL: {driver.current_url}")
        time.sleep(3)  # 等这套工具面板的异步渲染（一般比报表页重，可能有 WebSocket 拉实时数据）

        drawer = driver.find_elements(By.CSS_SELECTOR, ".el-drawer, .el-overlay-drawer")
        print(f"\n② el-drawer 命中: {len(drawer)} 个，可见: {[d.is_displayed() for d in drawer]}")

        dump_interactive(driver, "③ 实时工作台可见交互元素全 dump")

        print("\n④ 候选子导航/工具栏族逐个探测命中数：")
        for probe_cls in ("tp-bc-sub-btn", "ui-shell__tab", "cb__tab", "llink",
                          "[class*='sub-btn']", "[class*='tool']", "[class*='panel__nav']",
                          "[class*='menu-item']", "button.el-button--primary"):
            found = driver.find_elements(By.CSS_SELECTOR, probe_cls)
            vis = [f for f in found if f.is_displayed()]
            print(f"  {probe_cls}: 共 {len(found)} 个，可见 {len(vis)} 个")
            for f in vis[:15]:
                print(f"      {(f.get_attribute('class') or '')[:75]:75} "
                      f"text={(f.text or '').strip()[:22]!r}")

        print("\n判读要点：③④ 拿到锚点后决定要不要新建 WorkbenchPage（跟报表用的 "
              "ConsolePage 分开，因为这是两套不同产品形态，不是同一页面的不同状态）。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
