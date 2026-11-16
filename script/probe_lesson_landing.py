r"""
侦察：点课程卡片落到"当前讲次页"（/lessons/<id>）之后，页面上到底有什么导航元素？—— 2026-11-14
- 为什么要这个脚本：UI 适配方案 A 需要在落点页点"返回课程"回详情页，
  用的定位器是 L4 侦察来的 tp-nav-menu__home（那是从"课堂工作台"页抄的）。
  真跑 L2 时发现落点页上找不到这个按钮（click_element 超时）——
  不猜、不瞎试，把落点页的候选元素实拍回来再定定位器。
- 手段：只读巡礼。登录 -> 点卡片 -> 等落点 -> dump（不点任何有副作用的按钮，看完即关）。
- 运行：& ".venv\Scripts\python.exe" "script\probe_lesson_landing.py"
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
from pages.login_page import LoginPage
from pages.course_page import CoursePage

# 候选筛选：class 含 nav/home/back/lesson 的元素 + 可见文字含"返回/课程/退出"的按钮
CANDIDATE_CSS = "button, a, [class*='nav'], [class*='home'], [class*='back']"


def main():
    edge_options = Options()
    # 这两项必须和 conftest._make_browser 对齐：环境是自签证书，
    # 不加 --ignore-certificate-errors 会停在浏览器证书警告页，永远等不到登录框
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    driver.implicitly_wait(0)
    try:
        driver.get(LOGIN_URL)   # 登录页直达（同 conftest），BASE_URL 在已登录态下会跳到列表页
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，侦察终止"

        course = CoursePage(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(course.enter_course_btn))
        course.click_element(course.enter_course_btn)

        # 等落点（SPA 滞后于点击），最多 10 秒
        for _ in range(20):
            url = driver.current_url
            if "/lessons/" in url or "/courses/" in url:
                break
            time.sleep(0.5)
        print(f"落点 URL: {url}")
        if "/lessons/" not in url:
            print("这次没落到当前讲次页（没有 ongoing 讲次？），侦察目的未达成")
            return

        time.sleep(3)  # 等这页自己的异步渲染落地，别抢跑
        print(f"页面标题: {driver.title}")

        # 1) dump 候选导航元素：tag/class/文字/是否可见
        els = driver.find_elements(By.CSS_SELECTOR, CANDIDATE_CSS)
        print(f"\n===== 候选元素 {len(els)} 个（tag | class | 可见 | 文字前30字）=====")
        seen = set()
        for e in els:
            try:
                cls = (e.get_attribute("class") or "").strip()
                txt = (e.text or "").strip().replace("\n", " ")[:30]
                tag = e.tag_name
                key = (tag, cls, txt)
                if key in seen:
                    continue
                seen.add(key)
                print(f"{tag:8} | {cls[:60]:60} | {e.is_displayed()!s:5} | {txt}")
            except Exception:
                pass  # 元素在 dump 过程中被 SPA 重渲染干掉，跳过即可

        # 2) 专门看一眼 L4 那个 home 按钮在这页存不存在（DOM 里有但不可见也算情报）
        home = driver.find_elements(By.CSS_SELECTOR, "[class*='tp-nav-menu__home']")
        print(f"\ntp-nav-menu__home 命中: {len(home)} 个",
              [h.tag_name for h in home])

        # 3) 面包屑/返回类文字的按钮全列出来（找"返回课程"到底长什么样）
        back_ish = [e for e in els if any(
            k in (e.text or "") for k in ("返回", "回课程", "课程详情", "退出"))]
        print(f"文字含'返回/退出'的: {len(back_ish)} 个")
        for e in back_ish:
            print(f"  -> <{e.tag_name} class={(e.get_attribute('class') or '')[:60]}> "
                  f"text={e.text.strip()[:30]!r} visible={e.is_displayed()}")

        # 4) 二阶段：真点面包屑验证回退落点（导航动作零副作用，点了不对就重进）
        #    新 UI 面包屑 = a.ui-head__crumb（"课程" / 课程名 两级），
        #    猜：点课程名那级应回 /courses/<id>，点"课程"那级应回列表页
        crumbs = driver.find_elements(By.CSS_SELECTOR, "a.ui-head__crumb")
        print(f"\n===== 面包屑候选 {len(crumbs)} 个 =====")
        for i, c in enumerate(crumbs):
            print(f"  crumb[{i}] text={c.text.strip()[:30]!r} "
                  f"href={c.get_attribute('href')}")
        if crumbs:
            # 从最后一级（课程名）试起：它的语义最接近"返回详情"
            target = crumbs[-1]
            print(f"\n试点 crumb[{len(crumbs)-1}] text={target.text.strip()[:30]!r}")
            target.click()
            for _ in range(20):
                if driver.current_url != url:
                    break
                time.sleep(0.5)
            print(f"点击后 URL: {driver.current_url}")
            # 再验证详情页地标还在不在（新 UI 下 tp-bc-sub-btn 那族可能也换了）
            wb = driver.find_elements(By.CSS_SELECTOR, "[class*='tp-']")
            print(f"详情页上残留 tp-* 元素: {len(wb)} 个（为 0 则页签定位器全部重侦察）")
            sub = driver.find_elements(By.CSS_SELECTOR, ".tp-bc-sub-btn")
            print(f"tp-bc-sub-btn 命中: {len(sub)} 个")
            # 新 UI 下页签候选：把所有含 tab 的 class 打出来供改写定位器用
            tabs = driver.find_elements(By.CSS_SELECTOR, "[class*='tab']")
            seen2 = set()
            print(f"\n===== 含'tab'的候选 {len(tabs)} 个 =====")
            for t in tabs:
                cls = (t.get_attribute("class") or "").strip()
                txt = (t.text or "").strip().replace("\n", " ")[:20]
                if (cls, txt) in seen2:
                    continue
                seen2.add((cls, txt))
                print(f"  {t.tag_name:6} | {cls[:60]:60} | {t.is_displayed()!s:5} | {txt}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
