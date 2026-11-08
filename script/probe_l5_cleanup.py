"""
L5 收尾侦察③ + 孤儿课清理（2026-11-08）
背景：首跑发现"创建课程"提交后系统自动跳详情页并弹"排课"引导；且遗留一门 AT-L5-* 孤儿课
本脚本一次干三件事（都只针对自建 AT-L5-* 课，安全）：
  1) 进 AT-L5 课详情页，定位"邀请码"元素（供用例从详情页读码，不必回列表）
  2) 点右上角"更多"(tp-course-more-btn)，列出可见菜单项，确认"归档课程"定位
  3) 点"归档课程"，抓二次确认框结构（el-message-box / el-popconfirm），完成归档清理孤儿课
运行：& ".venv\\Scripts\\python.exe" "script\\probe_l5_cleanup.py"
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import time

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

from config import LOGIN_URL, BASE_URL, USERNAME, PASSWORD

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def dump_invite_code_area(driver):
    """详情页里含'邀请码'的元素 + 就近正则抠码"""
    hits = driver.execute_script("""
        const out = [];
        document.querySelectorAll('*').forEach(el => {
            if (el.children.length === 0) {
                const t = (el.textContent || '').trim();
                if (t.includes('邀请码') && t.length < 40)
                    out.push({text: t, cls: (el.className||'').toString().slice(0,60)});
            }
        });
        return out.slice(0, 8);
    """)
    return hits


def dump_visible_menu_items(driver):
    return driver.execute_script("""
        const items = [];
        document.querySelectorAll('.el-dropdown-menu__item').forEach(el => {
            if (el.offsetWidth || el.offsetHeight)
                items.push((el.textContent||'').trim().slice(0,16));
        });
        return items;
    """)


def dump_dialog(driver):
    """归档点击后可能弹的确认框：报告容器类名 + 内部按钮文本"""
    return driver.execute_script("""
        const out = [];
        document.querySelectorAll('.el-message-box, .el-popconfirm, .el-dialog, [role="dialog"]').forEach(el => {
            if (!(el.offsetWidth || el.offsetHeight)) return;
            const btns = [...el.querySelectorAll('button')].map(b => (b.textContent||'').trim());
            out.push({cls: (el.className||'').toString().slice(0,60),
                      text: (el.textContent||'').trim().slice(0,60), btns: btns});
        });
        return out;
    """)


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        from pages.login_page import LoginPage
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "demo_teacher 登录失败"

        # 找 AT-L5 孤儿课卡片（按文字前缀，不写死时间戳）
        driver.get(BASE_URL)
        time.sleep(2)
        orphan = driver.find_elements(
            By.XPATH, "//button[contains(@class,'tp-spot')][contains(., 'AT-L5')]")
        print(f"列表里 AT-L5 卡片数量：{len(orphan)}")
        if not orphan:
            print("没有 AT-L5 孤儿课（可能已被处理），仅做详情页归档流程侦察：需手动指定")
            return
        card = orphan[0]
        card_name = re.search(r'(AT-L5-\d+)', card.text)
        print(f"孤儿课名：{card_name.group(1) if card_name else '?'}")
        print(f"卡片文字快照：{card.text!r}")

        # 进详情页
        card.click()
        time.sleep(2)
        print(f"\n【详情页】URL：{driver.current_url}")
        print("含'邀请码'的元素：")
        for h in dump_invite_code_area(driver):
            print(f"  {h['text']!r} cls={h['cls']!r}")

        # 点"更多"⋯
        more = driver.find_element(By.CSS_SELECTOR, "button.tp-course-more-btn")
        more.click()
        time.sleep(1)
        print("\n【更多菜单·可见项】")
        for it in dump_visible_menu_items(driver):
            print(f"  {it!r}")
        driver.save_screenshot(os.path.join(SHOT_DIR, "cleanup_menu.png"))

        # 点"归档课程"
        archive_item = driver.find_element(
            By.XPATH, "//li[contains(@class,'el-dropdown-menu__item')][contains(normalize-space(),'归档课程')]")
        archive_item.click()
        time.sleep(1.5)
        print("\n【点归档后·弹层/确认框】")
        for d in dump_dialog(driver):
            print(f"  cls={d['cls']!r} text={d['text']!r} btns={d['btns']}")
        driver.save_screenshot(os.path.join(SHOT_DIR, "cleanup_confirm.png"))

        # 尝试点确认框主按钮（若有），完成归档清理
        clicked = False
        for sel in [".el-message-box__btns button.el-button--primary",
                    ".el-popconfirm button.el-button--primary",
                    ".el-dialog__footer button.el-button--primary"]:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            vis = [b for b in btns if b.is_displayed()]
            if vis:
                print(f"\n点确认主按钮：{sel} -> {vis[0].text!r}")
                vis[0].click()
                clicked = True
                break
        if not clicked:
            print("\n没找到可见的确认主按钮——可能归档无需二次确认，或按钮形态特殊，看 cleanup_confirm.png 定性")
        time.sleep(2)
        driver.save_screenshot(os.path.join(SHOT_DIR, "cleanup_after.png"))

        # 回列表验证是否已归档
        driver.get(BASE_URL)
        time.sleep(2)
        still = driver.find_elements(By.XPATH, "//button[contains(@class,'tp-spot')][contains(., 'AT-L5')]")
        print(f"\n归档后列表里 AT-L5 卡片数量（默认全部筛选）：{len(still)}")
        body = driver.find_element(By.TAG_NAME, "body").text
        print(f"归档后页面是否含'已归档'：{'已归档' in body}")
        print("\n侦察+清理完毕。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
