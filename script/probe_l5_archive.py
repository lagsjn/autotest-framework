"""
L5 收尾侦察：找"归档/结束课程"入口（2026-11-08，只读）
背景：手册说"已归档"=老师"已结束该课程"，但没写按钮在哪、叫什么；
     L5 用例建完课要能自动清理，先得拿到这个入口的精确定位器
安全红线（铁律）：
  - 只做只读动作：hover 卡片、打开"更多/⋯"菜单看项、进课程详情页逛
  - 绝不点击文字含 结束/归档/删除/下架 的按钮（不可逆写操作）
  - 绝不进"上课工作台"、绝不点"下课"
侦察目标：
  1) 课程卡片里/悬停后是否有"更多"或直接的"结束课程"按钮？class 是什么？
  2) 若有"更多"菜单，点开列出菜单项（不点其中危险项）
  3) 课程详情页里是否有"结束/归档课程"入口？
运行：& ".venv\\Scripts\\python.exe" "script\\probe_l5_archive.py"
"""
import os
import sys

# Windows 控制台默认 GBK，页面文字里的特殊符号（如 ▾）编不进会 UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from config import LOGIN_URL, USERNAME, PASSWORD, COURSE_NAME

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")

# 危险关键词：这些词命中的按钮，本次侦察一律不点
DANGER = ["结束", "归档", "删除", "下架", "停用"]


def find_candidates(driver):
    """全页搜含危险词/更多词的叶子元素，报告 文本/tag/class/是否可见——只看不点"""
    return driver.execute_script("""
        const kw = arguments[0];
        const hits = [];
        document.querySelectorAll('button, a, span, i, li').forEach(el => {
            const t = (el.textContent || '').trim();
            if (!t || t.length > 16) { return; }
            if (el.children.length > 0 && el.tagName !== 'BUTTON' && el.tagName !== 'A') { return; }
            for (const k of kw) {
                if (t.includes(k)) {
                    hits.push({text: t, tag: el.tagName,
                               cls: (el.className || '').toString().slice(0, 60),
                               visible: !!(el.offsetWidth || el.offsetHeight)});
                    break;
                }
            }
        });
        return hits.slice(0, 25);
    """, DANGER + ["更多", "管理", "设置"])


def dump_card_actions(driver):
    """把第一张'进行中'课程卡片内部的按钮全列出来（找隐藏操作）"""
    return driver.execute_script(f"""
        const name = arguments[0];
        const cards = [...document.querySelectorAll('button.tp-spot')];
        const card = cards.find(c => c.textContent.includes(name));
        if (!card) {{ return {{found:false}} }}
        const acts = [...card.querySelectorAll('button, a, i, span')]
            .filter(e => (e.textContent || '').trim() || e.className)
            .map(e => ({{
                text: (e.textContent || '').trim().slice(0, 16),
                tag: e.tagName, cls: (e.className || '').toString().slice(0, 50)
            }}));
        return {{found:true, cardClass: card.className.toString(), acts: acts.slice(0, 20)}};
    """, COURSE_NAME)


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        from pages.login_page import LoginPage
        from pages.course_page import CoursePage
        from base.base_page import BasePage
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "demo_teacher 登录失败"

        course = CoursePage(driver)
        assert course.is_element_exist(course.enter_course_btn, timeout=10), "课程列表没找到卡片"

        print("【第1步】课程列表页：全页搜危险词/更多词元素（只报告不点）")
        for h in find_candidates(driver):
            print(f"  <{h['tag']}> {h['text']!r} cls={h['cls']!r} visible={h['visible']}")

        print("\n【第2步】目标课程卡片内部结构（看有没有藏操作按钮/更多图标）")
        info = dump_card_actions(driver)
        print(f"  卡片找到={info.get('found')} 卡片class={info.get('cardClass')!r}")
        for a in info.get("acts", []):
            print(f"    <{a['tag']}> {a['text']!r} cls={a['cls']!r}")

        print("\n【第3步】悬停卡片后再次搜（有些操作 hover 才浮现）")
        card = driver.find_element(*course.course_card(COURSE_NAME))
        ActionChains(driver).move_to_element(card).perform()
        time.sleep(1)
        for h in find_candidates(driver):
            print(f"  <{h['tag']}> {h['text']!r} cls={h['cls']!r} visible={h['visible']}")
        driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_archive_card.png"))

        print("\n【第4步】进课程详情页逛（导航级，安全），搜归档/结束入口")
        course.enter_course()
        time.sleep(2)
        print(f"  进入后 URL：{driver.current_url}")
        for h in find_candidates(driver):
            print(f"    <{h['tag']}> {h['text']!r} cls={h['cls']!r} visible={h['visible']}")
        driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_archive_detail.png"))
        print(f"  详情页截图：{os.path.join(SHOT_DIR, 'probe_l5_archive_detail.png')}")

        print("\n侦察完毕：全程只 hover/浏览/搜索，未点任何危险按钮，未进工作台、未下课。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
