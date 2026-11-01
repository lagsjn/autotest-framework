"""
L3 前置侦察脚本：课程详情页四个页签的 DOM 身份勘查（2026-10-31）
- 为什么要侦察再动手：写定位器前先弄清页签是什么标签（<a href>？role="tab"？普通 div？）
  情报决定定位器写法和断言升级方向（见 docs/业务流程地图.md §7 绿级 + 定位器纪律）
- 四个页签：课表排期 / 资料归档 / 学情看板 / 班级成员
- 副作用评估：页签切换是 🟢 绿级（只读、无后果），可以放心挨个点
- 定位器纪律：只"看一眼"，不改任何数据，也不写成正式用例
- 运行（项目根目录）：& ".venv\\Scripts\\python.exe" "script\\probe_tabs.py"
"""
import os
import sys

# 让 script/ 下也能 import 到项目根的 config、pages（跑脚本时工作目录不确定，路径自己拼绝对）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options

from config import LOGIN_URL, USERNAME, PASSWORD, COURSE_NAME
from pages.login_page import LoginPage
from pages.course_page import CoursePage

# L3 要巡礼的四个页签（来自管理/老师端手册 §课程详情页）
TABS = ["课表排期", "资料归档", "学情看板", "班级成员"]

SHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def probe_tab_identities(driver):
    """
    用 JS 在整页找"直接文字 = 页签名"的元素，打印它们的 DOM 身份
    为什么要取"直接文字"（只拼自己名下第一层文本节点）？
    因为外层容器（整条页签栏、整个页面 body）的"全部文字"也包含页签名，
    不按直接文字过滤会把每一层父辈都命中，情报噪音太大
    """
    hits = driver.execute_script("""
        const names = arguments[0];
        const out = [];
        document.querySelectorAll('*').forEach(el => {
            const ownText = Array.from(el.childNodes)
                .filter(n => n.nodeType === 3)          // 3 = 文本节点
                .map(n => n.textContent.trim())
                .join('');
            if (!names.includes(ownText)) { return; }
            out.push({
                text: ownText,
                tag: el.tagName,
                class: el.className,
                id: el.id,
                role: el.getAttribute('role'),
                ariaSelected: el.getAttribute('aria-selected'),
                href: el.getAttribute('href'),
                parentTag: el.parentElement ? el.parentElement.tagName : '',
                parentClass: el.parentElement ? el.parentElement.className : '',
            });
        });
        return out;
    """, TABS)
    print(f"\n{'='*60}\n页签 DOM 身份勘查（共 {len(hits)} 个候选元素）\n{'='*60}")
    for h in hits:
        for k, v in h.items():
            print(f"  {k:12s}: {v}")
        print("  " + "-" * 40)
    return hits


def walk_each_tab(driver):
    """
    挨个点页签，记录：点击前后 URL 变不变（页签是路由型还是纯局部刷新？）
    每个页签截一张现场图，供肉眼确认"内容区真的换了一块"
    """
    for name in TABS:
        before = driver.current_url
        # 文字定位先粗点一枪；正式定位器等勘查结果出来后再精修（侦察阶段不嫌糙）
        els = driver.find_elements(By.XPATH, f"//*[text()='{name}']")
        if not els:
            print(f"[{name}] 没找到可点元素，跳过")
            continue
        els[-1].click()
        import time
        time.sleep(2)  # 侦察脚本允许睡：只求看清变化，不追求效率，正式用例严禁这样写
        after = driver.current_url
        changed = "URL 变了" if after != before else "URL 没变（局部刷新型页签）"
        print(f"[{name}] 点击后：{changed}\n         before={before}\n         after ={after}")
        shot = os.path.join(SHOT_DIR, f"probe_tab_{name}.png")
        driver.save_screenshot(shot)
        print(f"         现场图：{shot}")


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        # 复用 L1/L2 已验证的入口链路：登录 → 课程卡片 → 详情页
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "前置挂了：登录没成功（账号被锁？查 L1 案底）"

        course = CoursePage(driver)
        assert course.is_element_exist(course.enter_course_btn, timeout=10), \
            f"课程列表找不到目标课程卡片：{COURSE_NAME}"
        course.enter_course()
        url = course.wait_url_matches(r"/courses/\d+")
        assert url, f"10 秒内没进到课程详情页，停在：{driver.current_url}"
        print("已抵达课程详情页：", url)

        probe_tab_identities(driver)
        walk_each_tab(driver)
        print("\n侦察完毕：把上面的输出发回来，我们据此定四个页签的正式定位器")
    finally:
        driver.quit()  # 侦察脚本必须收尸：不留残骸进程（见 BROWSER_DEBUG 注释里的教训）


if __name__ == "__main__":
    main()
