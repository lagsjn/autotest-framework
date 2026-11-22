r"""
L4 七个内容锚点的「互斥性」体检（只读）—— 2026-11-22
为什么跑这个：test_console_e2e.py 给 7 个子页面各配了专属文案锚点，8 条用例全绿。
但"我的页能查到自己文案"只证明了锚点存在，没证明锚点**排他**——
如果"生成记录"这种文案在 quality-report 和 class-report 两页都有，或者干脆七个页面
都渲染了同一批文字，那么路由把两页接反时用例照样绿，锚点等于白配（又是一个假绿）。
所以必须做一张矩阵：在每一个页面上，把全部 14 个锚点文案都查一遍，
看"只有本页命中"的专属锚点存在不存在。

判定标准（脚本自己给结论）：
  ✓ 通过：本页至少有一个锚点在其余 6 页全部不命中 → 该页可被唯一识别
  ⚠ 共享：某锚点在 ≥2 页命中 → 它只能证明"到了这一族页面"，不能识别具体页（不算错，但不能单用）
  ✗ 失效：某页 14 个锚点里没有任何一个是它独占的 → 该页无法识别，锚点要换

锚点定义直接 import 用例文件里的 REPLAY_PARAMS，不在脚本里重抄一份——
两处各写一遍，改一处忘另一处，体检就失去意义了（单源纪律）。
运行：& ".venv\Scripts\python.exe" "script\probe_anchor_exclusivity.py"
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
# 锚点单源：从用例文件取，避免脚本与用例各维护一份而互相不一致
from testcases.test_console_e2e import REPLAY_PARAMS

# 与 BasePage.has_visible_text 同一判据（“包含该文案的最深节点”+排除导航门牌区），但一次查多个文案，
# 省掉 7 页 × 14 次的轮询等待（未命中的文案每次都傻等满 timeout 会跑到天荒地老）
# ⚠ 两边判据必须一字不差：体检用的是宽判据、用例用的是严判据，那“体检通过”就保不住“用例有效”。
JS_MULTI = """
const wants = arguments[0];
const useExcl = arguments[1];   // A/B 对照开关：0=不排除导航区，1=排除
const EXCLUDE = 'a.llink';   // 只排门牌本身：[class*=hub] 会把 manage 这类枢纽页的整个内容区误杀
const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
const nodes = [...document.querySelectorAll('body *')].filter(e => {
    const r = e.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
});
// 与 BasePage 同一算法：算净文本而不是找最深节点
const clean = new Map();
for (let i = nodes.length - 1; i >= 0; i--) {
    const e = nodes[i];
    if (useExcl && e.closest(EXCLUDE)) { clean.set(e, ''); continue; }
    let s = '';
    for (const c of e.childNodes) {
        if (c.nodeType === 3) { s += c.textContent; }
        else if (c.nodeType === 1 && clean.has(c)) { s += ' ' + clean.get(c); }
    }
    clean.set(e, norm(s));
}
const out = {__hub: document.querySelectorAll(EXCLUDE).length};
for (const w of wants) { out[w] = nodes.some(e => clean.get(e).includes(w)); }
return out;
"""

PAGES = [
    {"name": v[0], "seg": v[1], "markers": v[2]}
    for v in (p.values for p in REPLAY_PARAMS)
]
ALL_MARKERS = sorted({m for p in PAGES for m in p["markers"]})

# 溯源：某个文案在本页命中了，但它并不是本页该有东西——找出那个“最深命中节点”
# 到底挂在什么元素上、祖先链是什么 class。不靠猜不靠改运气，让 DOM 自己交代。
JS_TRACE = """
const want = arguments[0];
const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
// 溯源故意“不排”导航区：它的任务就是把门牌文字揪出来并报告挂在哪个容器上
const all = [...document.querySelectorAll('body *')].filter(e => {
    const r = e.getBoundingClientRect();
    return r.width > 2 && r.height > 2 && norm(e.innerText).includes(want);
});
const leaf = all.filter(e => !all.some(o => o !== e && e.contains(o)));
return leaf.slice(0, 3).map(e => {
    const chain = []; let n = e;
    for (let i = 0; i < 6 && n && n.tagName; n = n.parentElement, i++) {
        const cls = String(n.className || '').split(/\\s+/).filter(Boolean).slice(0, 2).join('.');
        chain.push(n.tagName.toLowerCase() + (cls ? '.' + cls : ''));
    }
    return {text: norm(e.innerText).slice(0, 36), chain: chain.join('  <  ')};
});
"""


def main():
    options = Options()
    options.add_argument("--ignore-certificate-errors")
    driver = webdriver.Edge(options=options)
    driver.maximize_window()
    matrix = {}
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "登录失败，体检终止"

        course = CoursePage(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(course.enter_course_btn))
        course.click_element(course.enter_course_btn)
        url = course.wait_url_matches(r"/lessons/\d+")
        assert url, f"点卡片没落到回放页，停在 {driver.current_url}"
        print(f"回放页: {url.replace(BASE_URL, '')}；待检锚点 {len(ALL_MARKERS)} 个")

        console = ConsolePage(driver)
        for p in PAGES:
            if not console.is_element_exist(console.lesson_link(p["name"]), timeout=5):
                print(f"\n⚠ 【{p['name']}】入口找不到，本页跳过")
                matrix[p["name"]] = {}
                continue
            console.click_element(console.lesson_link(p["name"]))
            if not console.wait_url_matches(rf"/lessons/\d+/{p['seg']}$", timeout=10):
                print(f"\n⚠ 【{p['name']}】URL 未到站，停在 {driver.current_url}")
            time.sleep(2.5)  # 等本页接口数据回来，避免抓到加载中的半成品
            raw = driver.execute_script(JS_MULTI, ALL_MARKERS, False)
            got = driver.execute_script(JS_MULTI, ALL_MARKERS, True)
            hub_n = got.get("__hub")
            diff = [k for k in ALL_MARKERS if bool(raw.get(k)) != bool(got.get(k))]
            print(f"      [A/B] 本页导航门牌元素 {hub_n} 个；排除后判定变化的锚点: {diff}")
            matrix[p["name"]] = {k: bool(v) for k, v in got.items() if k != "__hub"}
            hit = [k for k, v in matrix[p["name"]].items() if v]
            print(f"\n【{p['name']}】命中 {len(hit)}/{len(ALL_MARKERS)}: {hit}")
            # 跨页命中必须当场溯源：它们就是“独占锚点”失效的污染源
            for k in [x for x in hit if x not in p["markers"]]:
                for t in driver.execute_script(JS_TRACE, k) or []:
                    print(f"      ↳ 本页不应出现“{k}”，实际挂在：{t['text']!r}")
                    print(f"        位置链：{t['chain']}")
            driver.get(url)
            time.sleep(1.5)

        # ---- 矩阵判读 ----
        print(f"\n{'=' * 74}\n锚点 | " + " | ".join(p["name"][:6] for p in PAGES))
        for m in ALL_MARKERS:
            row = ["  √  " if matrix[p["name"]].get(m) else "  ·  " for p in PAGES]
            print(f"{m:12} | " + " | ".join(row))

        print(f"\n{'=' * 74}\n逐页专属度判定：")
        bad = []
        for p in PAGES:
            if not matrix[p["name"]]:
                bad.append(p["name"])
                continue
            own = [m for m in p["markers"]
                   if matrix[p["name"]].get(m)
                   and not any(matrix[q["name"]].get(m)
                               for q in PAGES if q["name"] != p["name"] and matrix[q["name"]])]
            shared = [m for m in p["markers"]
                      if matrix[p["name"]].get(m) and m not in own]
            if own:
                print(f"  ✓ {p['name']:12} 独占锚点={own}  共享锚点={shared}")
            else:
                print(f"  ✗ {p['name']:12} 没有任何独占锚点！（命中项={list(shared)} 都在别页也出现）")
                bad.append(p["name"])
        print(f"\n结论：{'七页均可唯一识别' if not bad else '以下页面无法唯一识别，锚点需更换：' + str(bad)}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
