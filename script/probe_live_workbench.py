"""L4 侦察·任务2:真实开一节沙箱课,进课堂页 dump 实时工作台全貌。

背景:2026-11-04 旧记录里的"十项子导航"(tp-bc-sub-btn 族)是开课期间才渲染的
内容,平时 DOM 里不存在,只能真的 start 一节沙箱讲次才能看到。
⚠ 讲次 id 绝不按旧记忆取(同一天体检发现旧 id=41 已易主),必须由
  probe_live_precheck.py 当场新建后传进来。

分两步侦察(只读 DOM,不点任何会改数据的按钮):
  第一步 GET /lessons/<id> 落点页,dump 所有可见交互元素
  第二步 若顶部/侧边出现子导航(含 sub 字样的 class),逐项记录文案与选中态
收尾:finally 里 end + archive,沙箱不过夜。

用法: python script/probe_live_workbench.py <lesson_id> <course_id>
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import config
from api.course_api import CourseApi
from api.lesson_api import LessonApi
from api.login_api import LoginApi
from pages.login_page import LoginPage
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait

LESSON_ID = int(sys.argv[1]) if len(sys.argv) > 1 else None
COURSE_ID = int(sys.argv[2]) if len(sys.argv) > 2 else None
assert LESSON_ID and COURSE_ID, "用法: python script/probe_live_workbench.py <lesson_id> <course_id>"

# 把页面上所有"看得见的可交互元素"倒出来(跟 probe_l4_console_v2 同一把手枪)
JS_DUMP = """
return [...document.querySelectorAll('a,button,input,[role=tab],[class*=tab],[class*=sub],[class*=btn]')]
  .filter(e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0)
  .map(e => ({
    tag: e.tagName.toLowerCase(),
    type: e.getAttribute('type') || '',
    text: (e.innerText || e.value || e.getAttribute('placeholder') || '').trim().slice(0, 30),
    aria: e.getAttribute('aria-label') || '',
    cls: (typeof e.className === 'string' ? e.className : '').slice(0, 60),
    active: e.getAttribute('aria-selected') || e.className.includes('active') ||
            e.className.includes('selected') || '',
    href: (e.getAttribute('href') || '').slice(0, 60),
  }));
"""

# 页面全部标题类文本:h1-h4 + 语义上的区块头,看工作台信息架构
JS_HEADINGS = """
return [...document.querySelectorAll('h1,h2,h3,h4,[class*=title],[class*=header] span')]
  .filter(e => e.getBoundingClientRect().width > 0)
  .map(e => (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 40))
  .filter(Boolean).slice(0, 40);
"""


def main():
    ok = True
    # ── 0. 接口 start(红级,只对当场新建的沙箱讲次) ──────────────
    tok = LoginApi().login_and_get_token()
    lh = LessonApi()
    r = lh.start_lesson(tok, LESSON_ID)
    print(f"[start] HTTP {r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        print("start 失败,不进浏览器(不制造半开状态)"); sys.exit(1)

    options = Options()
    options.add_argument("--ignore-certificate-errors")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Edge(options=options)
    driver.set_window_size(1680, 950)
    wait = WebDriverWait(driver, 15)
    try:
        # ── 1. UI 登录(与用例同一套凭据/入口) ──────────────────
        login = LoginPage(driver)
        # LoginPage 没有 open(),登录页地址由 config.LOGIN_URL 供给(同 conftest)
        login.open_url(config.LOGIN_URL)
        login.login(config.USERNAME, config.PASSWORD)
        assert login.is_login_success(), "UI 登录失败,不进课堂页"
        print("[登录后]", driver.current_url)

        # ── 2. 直接 URL 进课堂页(SPA 按 id 渲染,不依赖课程卡入口) ──
        # 页面地址就是 config.BASE_URL(接口同源不同路径,/api/v1 由 BaseApi 拼)
        url = f"{config.BASE_URL}/lessons/{LESSON_ID}"
        driver.get(url)
        time.sleep(3)
        print("[课堂页 URL]", driver.current_url)
        print("[标题栏]", driver.title)

        # ── 3. 落地全页截图 ──────────────────────────────────
        driver.save_screenshot("log/probe_live_landing.png")

        # ── 4. dump 交互元素 + 区块标题 ────────────────────────
        els = driver.execute_script(JS_DUMP) or []
        print(f"\n===== 可见交互元素 {len(els)} 个 =====")
        seen = set()
        for e in els:
            key = (e["tag"], e["text"], e["cls"][:40])
            if key in seen:
                continue
            seen.add(key)
            mark = " [选中]" if e["active"] in ("true", "True", "1") else ""
            print(f"  [{e['tag']}] '{e['text']}' class='{e['cls']}'"
                  f" href='{e['href']}'{mark}")

        heads = driver.execute_script(JS_HEADINGS) or []
        print("\n===== 区块标题 =====")
        for h in heads:
            print("  #", h)

        # ── 5. 子导航专项:找 class 含 sub 的容器,数它的项 ──────
        print("\n===== 含 'sub' 字样的元素(子导航候选) =====")
        for e in els:
            if "sub" in e["cls"].lower():
                print(f"  [{e['tag']}] '{e['text']}' class='{e['cls']}'")

        # ── 6. 若 topbar 有返回/退出按钮,记录它(巡览用例的退出按钮来源) ──
        print("\n===== 含 '返回|退出|下课|结束' 文案的元素 =====")
        for e in els:
            if any(k in (e["text"] + e["aria"]) for k in ("返回", "退出", "下课", "结束")):
                print(f"  [{e['tag']}] '{e['text']}' aria='{e['aria']}' class='{e['cls']}'")

        # ── 7. 第二轮:点「回到上课模式」进大屏再 dump ──────────
        # 落点页只是管理视角(页上自述"在别的设备上课时，这里看不到"),
        # 旧记录的十项子导航如果还在,应在大屏层。该按钮无 href(纯前端路由),
        # 零数据副作用;【按住下课】那个才是真改数据的,绝对不碰。
        btns = driver.find_elements(By.XPATH, "//button[contains(.,'回到上课模式')]")
        if not btns:
            print("\n[大屏] 没找到「回到上课模式」按钮,跳过第二轮")
        else:
            btns[0].click()
            time.sleep(3)
            print("\n===== 大屏层 URL =====", driver.current_url)
            driver.save_screenshot("log/probe_live_mode.png")
            els2 = driver.execute_script(JS_DUMP) or []
            print(f"===== 大屏可见交互元素 {len(els2)} 个 =====")
            seen2 = set()
            for e in els2:
                key = (e["tag"], e["text"], e["cls"][:40])
                if key in seen2:
                    continue
                seen2.add(key)
                mark = " [选中]" if e["active"] in ("true", "True", "1") else ""
                print(f"  [{e['tag']}] '{e['text']}' class='{e['cls']}'{mark}")
            heads2 = driver.execute_script(JS_HEADINGS) or []
            print("\n===== 大屏区块标题 =====")
            for h in heads2:
                print("  #", h)
    except Exception as e:
        ok = False
        print("!!! 侦察失败:", repr(e)[:300])
        try:
            driver.save_screenshot("log/probe_live_error.png")
        except Exception:
            pass
    finally:
        driver.quit()
        # ── 收尾:下课 + 归档,沙箱不过夜(清理失败要大声说,不能静默) ──
        try:
            r2 = lh.end_lesson(tok, LESSON_ID)
            print(f"[收尾·end] HTTP {r2.status_code} {r2.text[:120]}")
        except Exception as e:
            ok = False
            print(f"[收尾·end] 失败 需人工处理 沙箱讲次{LESSON_ID}: {e!r}")
        try:
            r3 = CourseApi().archive_course(tok, COURSE_ID)
            print(f"[收尾·archive] HTTP {r3.status_code}")
        except Exception as e:
            ok = False
            print(f"[收尾·archive] 失败 需人工处理 沙箱课程{COURSE_ID}: {e!r}")
    sys.exit(0 if ok else 1)


main()
