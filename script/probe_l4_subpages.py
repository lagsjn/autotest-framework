r"""
L4 回放页 7 个子页面「内容级地标」侦察（只读）—— 2026-11-22
为什么要侦察：现有 test_console_e2e.py 的 8 条用例只断两件事——①URL 落到 /lessons/<id>/<段>
②顶部面包屑 a.ui-head__crumb 存在。这两条都是**框架级**证据，不是**内容级**证据：
如果前端把这 7 个路由全指向同一个组件（配错路由/复制粘贴漏改），或者某页白屏报错但
框架仍渲染，用例照样全绿。这就是"假绿"——测试通过但什么都没测到。
本脚本要为每一页找回一个"只有这页才有"的文本锚点（表头名/卡片标题/专属按钮），
补进用例后，断言才真正锁住"到的是这一页"。

要拿到的四份情报（每页各一份）：
  ① 标题类文本：h1~h4 及 class 含 title/head 的元素文字
  ② 表格结构：th 表头文字（数据页最稳的内容锚点，不依赖具体数据行）
  ③ 专属控件文本：本页独有的按钮/标签（如"逐个改出勤状态"类）
  ④ 空态提示：.el-empty 的描述文字（沙箱/无数据时页面长什么样，决定用例能不能断数据行）
安全边界：全程只点导航链接与只读查看，不点任何写操作（布置/发布/标为请假/导出）。
运行：& ".venv\Scripts\python.exe" "script\probe_l4_subpages.py"
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

from config import BASE_URL, LOGIN_URL, USERNAME, PASSWORD
from pages.login_page import LoginPage
from pages.course_page import CoursePage
from pages.console_page import ConsolePage

# (入口文字, URL 尾段正则)：与 test_console_e2e.py 的 REPLAY_PARAMS 保持同源
SUB_PAGES = [
    ("出勤明细", "attendance"),
    ("本讲评分", "scoreboard"),
    ("学生提问", "questions"),
    ("讨论记录", "discussions"),
    ("课堂质量报告", "quality-report"),
    ("课后学情报告", "class-report"),
    ("管理随堂测与作业", "manage"),
]

# 一次性抓四类文本，返回 JSON 结构，省掉 7 页 × 4 次 find_elements 的往返
JS_COLLECT = """
const txt = e => (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
const vis = e => { const r = e.getBoundingClientRect();
                   return r.width > 2 && r.height > 2; };
const pick = (sel, cap) => [...document.querySelectorAll(sel)]
    .filter(vis).map(txt).filter(Boolean).slice(0, cap);
return {
  headings: pick('h1,h2,h3,h4,[class*=__title],[class*=card__head]', 12),
  ths:      pick('th, [class*=table__head] [class*=cell]', 16),
  buttons:  pick('button, a.el-button, [class*=rv-link]', 16),
  labels:   pick('[class*=tab], [class*=stat], [class*=kpi], [class*=label]', 12),
  empty:    pick('.el-empty, .el-empty__description, [class*=empty]', 4),
};
"""


def dump_page(driver, name, seg):
    print(f"\n{'=' * 70}\n【{name}】→ 期望 URL 尾段 /{seg}")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.ui-head__crumb")))
    except Exception:
        print("  ⚠ 面包屑都没出现（框架未渲染），本页无内容可采")
        return
    time.sleep(2.0)  # 等本页异步接口回来，否则抓到的是加载骨架
    print(f"  实际 URL: {driver.current_url.replace(BASE_URL, '')}")
    data = driver.execute_script(JS_COLLECT)
    for key in ("headings", "ths", "buttons", "labels", "empty"):
        vals = data.get(key) or []
        # 去重保序：同一文案在 DOM 里常出现多次（表头 + 列名重复）
        uniq = list(dict.fromkeys(vals))
        print(f"  {key:9}({len(uniq):2}): " + " | ".join(uniq[:10]))
    if not any(data.values()):
        print("  ⚠ 四类文本全空——本页可能纯靠 canvas/图表渲染，需另找锚点（截图）")


def main():
    options = Options()
    options.add_argument("--ignore-certificate-errors")
    driver = webdriver.Edge(options=options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，侦察终止"

        course = CoursePage(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(course.enter_course_btn))
        course.click_element(course.enter_course_btn)
        url = course.wait_url_matches(r"/lessons/\d+")
        assert url, f"点卡片没落到回放页，停在 {driver.current_url}"
        print(f"回放主页落点: {url.replace(BASE_URL, '')}")

        console = ConsolePage(driver)
        for name, seg in SUB_PAGES:
            link = console.lesson_link(name)
            if not console.is_element_exist(link, timeout=3):
                print(f"\n【{name}】⚠ 主页找不到这个入口，跳过（入口文案可能已改）")
                continue
            console.click_element(link)
            dump_page(driver, name, seg)
            # 回主页：用面包屑回上一级比 driver.back() 稳（SPA 历史栈不一定同步）
            driver.get(url)
            time.sleep(1.2)

        print(f"\n{'=' * 70}\n判读要点：每页挑一个「只有本页才有」的 th 或标题文案做内容锚点；"
              "\n若某页四列高度重合（尤其 buttons/labels 一样），说明多页共用同一组件，"
              "\n那正是需要单独取证的可疑点。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
