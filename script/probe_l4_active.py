"""
L4 补充侦察：子导航"选中态"判据勘查（2026-11-05）
背景：test_console_e2e 验收时【大屏】【点名】断言 is-active 挂不上，
     但失败截图显示面板其实切过去了 -> 怀疑 1)is-active 是竞态晚到 2)选中态另有标记
本脚本任务：对十个子导航逐个"点击前快照 class -> 点击 -> 轮询 class 变化"，
     拿到选中态的第一手定性证据（也顺带验证点击后是否跳离 /lessons）
安全边界：只点 tp-bc-sub-btn（与正式用例同一绿级白名单），面板内部一律不碰
运行：& ".venv\\Scripts\\python.exe" "script\\probe_l4_active.py"
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

from config import LOGIN_URL, USERNAME, PASSWORD, COURSE_NAME, BASE_URL
from pages.login_page import LoginPage
from pages.course_page import CoursePage
from pages.console_page import ConsolePage

SUB_TABS = ["签到", "大屏", "点名", "弹幕", "提问", "讨论", "评分",
            "质量报告", "课后报告", "控制台"]


def dump_sub_classes(driver):
    """抓十个子导航按钮当前的 class 列表（JS 一次性抓全，避免逐个 find 的时差）"""
    return driver.execute_script("""
        const out = {};
        document.querySelectorAll('button.tp-bc-sub-btn').forEach(el => {
            out[el.textContent.trim().replace(/\\s+/g, ' ')] = el.className;
        });
        return out;
    """)


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        # 入场链路：与正式用例完全一致的绿级路线
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "前置失败：登录没成功"

        course = CoursePage(driver)
        assert course.is_element_exist(course.enter_course_btn, timeout=10)
        course.enter_course()
        assert course.wait_url_matches(r"/courses/\d+")
        # 首次进场有入场动画：侦察允许睡 3 秒，模拟"页面完全静止"后的世界
        time.sleep(3)
        course.click_element(course.workbench_entry_btn)
        console = ConsolePage(driver)
        assert console.wait_url_matches(r"/lessons/\d+"), "进不去工作台"

        # 抽屉：用可见性判据（正式用例已改），有就关
        if console.is_element_visible(console.drawer_close_btn, timeout=2):
            console.click_element(console.drawer_close_btn)

        print(f"\n默认状态（刚进工作台）子导航 class：")
        for text, cls in dump_sub_classes(driver).items():
            print(f"  {text!r}: {cls}")

        for tab in SUB_TABS:
            print(f"\n{'='*60}\n>>> 点击【{tab}】")
            before = dump_sub_classes(driver)
            console.click_element(console.sub_btn(tab))
            # 轮询 8 秒：盯住该按钮 class 什么时候出现 is-active（或其它变化）
            changed_at = None
            after = before
            for i in range(16):
                time.sleep(0.5)
                after = dump_sub_classes(driver)
                hit = [c for k, c in after.items() if tab in k and "is-active" in c]
                if hit:
                    changed_at = (i + 1) * 0.5
                    break
            print(f"  URL: {driver.current_url}")
            if changed_at is not None:
                print(f"  is-active 在点击后约 {changed_at:.1f}s 挂上（=> 断言必须等待，不能抢跑）")
            else:
                print(f"  等满 8s 仍未见 is-active！该按钮最终 class 快照：")
            for k, v in after.items():
                mark = "  <== 目标按钮" if tab in k else ""
                old = next((bv for bk, bv in before.items() if tab in bk), None) if tab in k else None
                if tab in k:
                    print(f"    {k!r}: {v}{mark}\n    （点击前: {old}）")
                elif v != before.get(k):
                    print(f"    {k!r}: {v}（class 有变化，点击前: {before.get(k)}）")

        print("\n侦察完毕。把上面输出贴回来定性：选中态标记 + 挂上耗时 + 是否有跳离 /lessons。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
