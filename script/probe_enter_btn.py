"""
一次性诊断：test_enter_course_button_text 读到空文本的真因（2026-11-08）
只读，不点任何写操作。跑：& ".venv\\Scripts\\python.exe" "script\\probe_enter_btn.py"
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

from config import LOGIN_URL, BASE_URL, USERNAME, PASSWORD, COURSE_NAME

XPATHS = [
    ("旧: button含div含课程名", f"//button[.//div[contains(text(), '{COURSE_NAME}')]]"),
    ("新: tp-spot+div含课程名", f"//button[contains(@class,'tp-spot')][.//div[contains(text(), '{COURSE_NAME}')]]"),
    ("button直接contains课程名", f"//button[contains(., '{COURSE_NAME}')]"),
    ("tp-spot contains课程名", f"//button[contains(@class,'tp-spot')][contains(., '{COURSE_NAME}')]"),
]


def main():
    o = Options()
    o.add_argument('--ignore-certificate-errors')
    d = webdriver.Edge(options=o)
    d.maximize_window()
    try:
        d.get(LOGIN_URL)
        from pages.login_page import LoginPage
        lp = LoginPage(d)
        lp.login(USERNAME, PASSWORD)
        assert lp.is_login_success()
        d.get(BASE_URL)
        time.sleep(3)

        for label, xp in XPATHS:
            els = d.find_elements(By.XPATH, xp)
            print(f"\n[{label}] 命中 {len(els)} 个")
            for i, e in enumerate(els[:4]):
                try:
                    disp = e.is_displayed()
                    txt = (e.text or "").replace("\n", " | ")[:60]
                    cls = (e.get_attribute("class") or "")[:50]
                    print(f"   #{i} displayed={disp} class={cls!r} text={txt!r}")
                except Exception as ex:
                    print(f"   #{i} 读取异常 {ex}")

        # 打印第一张 tp-spot 卡片的内部标签结构，看课程名到底在 div 还是 span
        print("\n=== 大数据卡片内部结构（前 400 字 outerHTML）===")
        card = d.find_elements(By.XPATH, f"//button[contains(@class,'tp-spot')][contains(., '{COURSE_NAME}')]")
        if card:
            html = card[0].get_attribute("outerHTML") or ""
            print(html[:400])
    finally:
        d.quit()


if __name__ == "__main__":
    main()
