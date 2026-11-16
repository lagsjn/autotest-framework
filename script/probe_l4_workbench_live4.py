r"""
L4' 实时工作台侦察 第四轮：/lessons/<id>/live 落地页点"继续上课"之后才是真工具面板吗？—— 2026-11-15
- 上一轮（probe_l4_workbench_live3.py）实测：直达 /live 只拿到一个落地态——50 个学生姓名按钮
  （att__name is-btn）+ 两个大按钮"继续上课"（cls-btn--primary cls-btn--lg）/
  "打开老师后台"（cls-btn--lg），tp-bc-sub-btn/ui-shell__tab 全部 0 命中。
  说明这套实时工作台是"两段式"：先进落地态，点一个动作按钮才进真正的功能面板。
- 用户已明确授权：demo_teacher 是纯测试号，这堂课本来就是为侦察临时开的，点"继续上课"不算干扰真实课堂。
- 本脚本任务：
  ① 复现前三轮的直达 /live（用 API 查 ongoing lesson id，不写死）
  ② 点"继续上课"，记录：会不会跳新窗口（window_handles 数量变化）、URL 变不变、
     点完之后 tp-bc-sub-btn/ui-shell__tab 这套子导航是否现身
  ③ 现身了就 dump 每个子导航按钮的 text/class，找选中态标记（对照第三轮"is-on"经验）
  ④ 没现身（比如点了个寂寞，或者"继续上课"是恢复播放跟面板无关）：再试"打开老师后台"，
     同样先看 window_handles 变化——这个名字更像"另开一个管理面板窗口"，是旧版
     workbench_entry_btn 的继任者候选
- 安全边界：只点"继续上课"/"打开老师后台"这两个已经确认无真实副作用的按钮（用户已授权）；
  "下课/发布随堂测/签到确认提交"这类真正改动课堂数据的按钮，本轮依然不碰。
- 运行：& ".venv\Scripts\python.exe" "script\probe_l4_workbench_live4.py"
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
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    courses = CourseApi(BASE_URL)
    hit = [c for c in items_of(courses.list_courses(token)) if c.get("name") == COURSE_NAME]
    if not hit:
        return None
    lessons = items_of(courses.get(f"/courses/{hit[0]['id']}/lessons", token=token,
                                   params={"page": 1, "page_size": 30}))
    ongoing = [l for l in lessons if l.get("status") == "ongoing"]
    return ongoing[0]["id"] if ongoing else None


def dump_interactive(driver, label, limit=100):
    print(f"\n===== {label} =====")
    handles = driver.window_handles
    print(f"  当前窗口数: {len(handles)}，句柄: {handles}")
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


def probe_family(driver, label):
    print(f"\n----- {label} 子导航族命中检查 -----")
    for probe_cls in (".tp-bc-sub-btn", ".ui-shell__tab", ".cb__tab", ".llink",
                      "[class*='sub-btn']", "[class*='cls-']", "[class*='tool']"):
        found = driver.find_elements(By.CSS_SELECTOR, probe_cls)
        vis = [f for f in found if f.is_displayed()]
        if vis:
            print(f"  {probe_cls}: 共 {len(found)} 个，可见 {len(vis)} 个")
            for f in vis[:15]:
                print(f"      {(f.get_attribute('class') or '')[:80]:80} "
                      f"text={(f.text or '').strip()[:22]!r}")
        else:
            print(f"  {probe_cls}: 0 命中")


def main():
    lesson_id = find_ongoing_lesson_id()
    if not lesson_id:
        print("没查到 ongoing 讲次——请先在界面上重新点'临时调课，现在开课'再跑本脚本。")
        return
    print(f"ongoing lesson id = {lesson_id}")

    edge_options = Options()
    edge_options.add_argument("--ignore-certificate-errors")
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，侦察终止"

        driver.get(f"{BASE_URL}/lessons/{lesson_id}/live")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.cls-btn")))
        print(f"落地页 URL: {driver.current_url}")

        # ② 点"继续上课"
        btn = driver.find_element(By.XPATH, "//button[contains(@class,'cls-btn')][contains(text(),'继续上课')]")
        before_handles = set(driver.window_handles)
        btn.click()
        time.sleep(3)
        after_handles = set(driver.window_handles)
        new_handles = after_handles - before_handles
        print(f"\n② 点'继续上课'后：新窗口数 {len(new_handles)}，当前 URL: {driver.current_url}")
        if new_handles:
            driver.switch_to.window(new_handles.pop())
            print(f"   切到新窗口，URL: {driver.current_url}")
        dump_interactive(driver, "②b 点'继续上课'之后的可见交互元素")
        probe_family(driver, "②c")

        # 若还没找到子导航族，回到原窗口试"打开老师后台"
        found_any = any(
            driver.find_elements(By.CSS_SELECTOR, c)
            for c in (".tp-bc-sub-btn", ".ui-shell__tab", ".llink")
        )
        if not found_any:
            print("\n③ '继续上课'没带出子导航面板，尝试另一条路：'打开老师后台'")
            driver.get(f"{BASE_URL}/lessons/{lesson_id}/live")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.cls-btn")))
            before_handles = set(driver.window_handles)
            btn2 = driver.find_element(By.XPATH,
                                       "//button[contains(@class,'cls-btn')][contains(text(),'打开老师后台')]")
            btn2.click()
            time.sleep(3)
            after_handles = set(driver.window_handles)
            new_handles = after_handles - before_handles
            print(f"③ 点'打开老师后台'后：新窗口数 {len(new_handles)}，当前 URL: {driver.current_url}")
            if new_handles:
                driver.switch_to.window(new_handles.pop())
                print(f"   切到新窗口，URL: {driver.current_url}")
            dump_interactive(driver, "③b '打开老师后台'之后的可见交互元素")
            probe_family(driver, "③c")

        print("\n判读要点：找到 tp-bc-sub-btn 或新命名子导航族在哪一步出现，决定 WorkbenchPage "
              "要不要处理'两段式进入'（先点按钮才展开面板）和窗口切换。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
