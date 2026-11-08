"""
L5 前置侦察脚本：老师端建课表单 + 邀请码显示结构勘查（2026-11-07）
- 任务：①打开"创建课程"弹窗，登记表单字段（课程名称/学期/简介 + 提交/取消按钮），不提交；
        ②在现有课程卡片上勘查"邀请码"是怎么显示的（L5 用例要从卡片读邀请码传给学生端）
- 铁律：建课弹窗只开不提交（提交=写操作造数据）；"重置邀请码"绝不点（会让旧码立即失效）
- 手册情报（老师端操作手册 v2.0 §2.2/2.3）：
  课程列表右上角"创建课程"→弹窗，字段 课程名称(必填)/学期(可选)/简介(可选)；
  创建成功后系统自动生成邀请码显示在课程卡片上；卡片有"复制邀请码"按钮
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_l5_teacher.py"
"""
import os
import sys

# Windows 控制台默认 GBK，页面特殊符号会崩打印，强制 UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

from config import LOGIN_URL, USERNAME, PASSWORD, COURSE_NAME
from pages.login_page import LoginPage
from pages.course_page import CoursePage
from script.probe_console import probe_page_structure

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def dump_inputs(driver):
    """登记当前所有 input/textarea 的特征（找建课表单字段就看 placeholder/类型）"""
    return driver.execute_script("""
        const out = [];
        document.querySelectorAll('input, textarea').forEach(el => out.push({
            tag: el.tagName, type: el.type || '', placeholder: el.placeholder || '',
            maxlength: el.getAttribute('maxlength'),
            visible: !!(el.offsetWidth || el.offsetHeight),
        }));
        return out;
    """)


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "demo_teacher 登录失败"

        course = CoursePage(driver)
        assert course.is_element_exist(course.enter_course_btn, timeout=10), "课程列表没找到课程卡片"

        # 第一站：课程列表页——找"创建课程"入口 + 看现有卡片的邀请码怎么显示
        probe_page_structure(driver, "老师端课程列表")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        print(f"\n页面含'创建课程'：{'创建课程' in body_text}")
        print(f"页面含'邀请码'字样：{'邀请码' in body_text}")

        # 邀请码显示结构：抓含"邀请码"文字附近的小片段，供 L5 用例定位
        code_snippet = driver.execute_script("""
            const hits = [];
            document.querySelectorAll('*').forEach(el => {
                const t = (el.textContent || '').trim();
                if (el.children.length === 0 && /邀请码|复制/.test(t) && t.length < 30) {
                    hits.push({text: t, class: (el.className||'').toString().slice(0,50)});
                }
            });
            return hits.slice(0, 15);
        """)
        print("含'邀请码/复制'的叶子元素（定位器情报）：")
        for h in code_snippet:
            print(f"  {h['text']!r}  class={h['class']!r}")

        # 第二站：打开创建课程弹窗（只开不提）
        create_btn = (By.XPATH, "//button[contains(., '创建课程')]|//button[contains(., '新建课程')]")
        from base.base_page import BasePage
        bp = BasePage(driver)
        if bp.is_element_visible(create_btn, timeout=3):
            bp.click_element(create_btn)
            time.sleep(2)
            print(f"\n打开建课弹窗后 URL：{driver.current_url}")
            probe_page_structure(driver, "创建课程弹窗")
            print("建课弹窗 input/textarea：")
            for it in dump_inputs(driver):
                if it["visible"]:
                    print(f"  <{it['tag']}> type={it['type']!r} placeholder={it['placeholder']!r} "
                          f"maxlength={it['maxlength']}")
            driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_create.png"))
            print(f"建课弹窗截图：{os.path.join(SHOT_DIR, 'probe_l5_create.png')}")
            # 取消/关闭弹窗，绝不提交
            cancel = (By.XPATH, "//button[contains(., '取消')]|"
                                "//button[contains(@class,'el-dialog__headerbtn')]|"
                                "//i[contains(@class,'el-dialog__close')]")
            if bp.is_element_visible(cancel, timeout=2):
                bp.click_element(cancel)
                print("已取消建课弹窗（未提交，不造数据）")
            else:
                print("⚠ 没找到取消按钮——请人工确认弹窗关闭方式，用例里要能安全退出")
        else:
            print("\n没找到'创建课程'入口，看课程列表截图定性")
            driver.save_screenshot(os.path.join(SHOT_DIR, "probe_l5_teacher.png"))

        print("\n侦察完毕：只开弹窗看字段、没提交建课、没碰重置邀请码。输出贴回来做 L5 用例设计。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
