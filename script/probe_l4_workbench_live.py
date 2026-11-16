r"""
L4' 实时工作台侦察（只读）：用户手动点了"上课"，现在这门课有真实的 ongoing 讲次，
趁这个窗口把"实时工作台"这套 UI 抓清楚——上轮 probe_l4_console_v2.py 只能抓到 ended
回放页（7 个 llink 子页面），实时工作台当时不可见，一直没侦察成（§13.5 待办①留到今天）。
- 时效性：这个窗口过了就得等下次再开课，所以本脚本优先跑，晚点再做笔记归档类工作。
- 除了拿"新工作台长什么样"，还要顺手排查一件更要紧的事：现在卡片落点从 ended 回放页
  变成 ongoing 实时页，L2/L3/L4 已有用例是否会被这个状态变化顶红——
  ① CoursePage.enter_course() 靠面包屑 a.ui-head__crumb 扳回详情页，这个面包屑在
     实时工作台页还存在吗？（不存在=L2/L3 入场链路即刻受影响，不是"以后"的事）
  ② test_console_e2e.py 断言的 7 个 a.llink 巡览入口，在实时态下还在吗？
     （不在=L4 回放用例现在就会红，属"环境状态变化"这一档，不是界面改版）
- 要拿到的情报：
  ① 卡片落点 URL + 页面类型（是不是 /lessons/<id>，还是别的实时路径）
  ② 落点页有没有面包屑（决定 ① 的风险要不要马上处理）
  ③ 实时工作台的子导航/功能分区锚点全 dump（找"签到/点名/大屏/弹幕"这套到底住哪）
  ④ 旧抽屉 el-drawer 在实时态是不是又回来了（回放页实测是 0 命中）
  ⑤ 选中态判据：给子导航逐个点一遍前，先 dump class，别乱点写操作按钮
- 安全边界：只导航、只查看、只 dump DOM 属性；"下课/发布/开始上课/签到确认"这类
  真正会改动课堂状态的按钮一个都不点（那是黄级写操作，且会影响你正在上的这节课）。
- 运行：& ".venv\Scripts\python.exe" "script\probe_l4_workbench_live.py"
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


def dump_interactive(driver, label, limit=80):
    """dump 当前页可见的 <a>/<button>：tag | class | 文字 | href 尾段"""
    print(f"\n===== {label} =====")
    els = driver.find_elements(By.CSS_SELECTOR, "a, button")
    shown = 0
    for e in els:
        try:
            if not e.is_displayed():
                continue
            cls = (e.get_attribute("class") or "").strip()
            txt = (e.text or "").strip().replace("\n", " ")[:30]
            href = (e.get_attribute("href") or "")
            href_tail = href.replace("https://demo.test-env.local:8081", "") if href else ""
            if not txt and not cls:
                continue
            print(f"  {e.tag_name:6} | {cls[:55]:55} | {txt:30} | {href_tail[:36]}")
            shown += 1
            if shown >= limit:
                print(f"  ...（截断，共超过 {limit} 个）")
                break
        except Exception:
            pass  # SPA 重渲染导致元素失效，跳过
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

        course = CoursePage(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(course.enter_course_btn))

        # ① 直接点卡片（不调 enter_course，它会把 lessons 落点扳回详情页，看不到实时态）
        course.click_element(course.enter_course_btn)
        for _ in range(20):
            if "/lessons/" in driver.current_url or "/courses/" in driver.current_url:
                break
            time.sleep(0.5)
        landing = driver.current_url
        print(f"① 卡片落点（有 ongoing 讲次后）: {landing}")
        is_live_landing = "/lessons/" in landing
        time.sleep(3)  # 等实时页异步渲染（工作台通常比普通页多一层数据加载）

        # ② 面包屑还在不在（决定 L2/L3 的 enter_course 扳回逻辑现在是否还成立）
        crumbs = driver.find_elements(By.CSS_SELECTOR, "a.ui-head__crumb")
        vis_crumbs = [c for c in crumbs if c.is_displayed()]
        print(f"\n② 落点页面包屑 a.ui-head__crumb: 共 {len(crumbs)} 个，可见 {len(vis_crumbs)} 个")
        for c in vis_crumbs:
            print(f"    text={c.text.strip()!r} href={c.get_attribute('href')}")
        if not vis_crumbs:
            print("    ⚠ 没找到面包屑——CoursePage.back_to_course_btn 在实时态可能失效，"
                  "L2/L3 入场链路存在被这次状态变化顶红的风险，需要马上验证")

        # ③ 抽屉还在不在（回放页实测 0 命中，实时态是否又出现）
        drawer = driver.find_elements(By.CSS_SELECTOR, ".el-drawer, .el-overlay-drawer")
        print(f"\n③ el-drawer 命中: {len(drawer)} 个，可见: {[d.is_displayed() for d in drawer]}")

        dump_interactive(driver, "④ 落点页（实时态）可见交互元素全 dump——工作台功能分区锚点在这找")

        # ⑤ 候选子导航族逐个 dump class，看选中态/结构（只读，不点击）
        for probe_cls in ("tp-bc-sub-btn", "ui-shell__tab", "cb__tab", "llink",
                          "[class*='workbench']", "[class*='sub-nav']", "[class*='tab']"):
            found = driver.find_elements(By.CSS_SELECTOR, probe_cls)
            vis = [f for f in found if f.is_displayed()]
            print(f"\n⑤ {probe_cls}: 共 {len(found)} 个，可见 {len(vis)} 个")
            for f in vis[:15]:
                print(f"    {(f.get_attribute('class') or '')[:75]:75} "
                      f"text={(f.text or '').strip()[:20]!r}")

        # ⑥ 顺带查：上轮 L4 回放用例的 7 个 a.llink 巡览入口，在实时态还在不在
        print("\n⑥ 旧回放用例的 7 个 a.llink 入口，实时态存活检查：")
        replay_names = ["出勤明细", "本讲评分", "学生提问", "讨论记录",
                        "课堂质量报告", "课后学情报告", "管理随堂测与作业"]
        for name in replay_names:
            hit = [e for e in driver.find_elements(
                By.XPATH, f"//a[contains(@class,'llink')][contains(normalize-space(),'{name}')]")
                if e.is_displayed()]
            print(f"    {name!r}: {'在' if hit else '不在/不可见'}")

        print("\n判读要点：②决定 L2/L3 是否已被这次开课顶红（要立刻回归确认）；"
              "④⑤ 是实时工作台新用例的原始素材；⑥ 决定 test_console_e2e.py 现在跑会不会红。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
