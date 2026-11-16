r"""
上课流程·kind 白名单静态侦察（只读扒前端 JS 包）：2026-11-15
背景：PUT /lessons/{id}/flow 的 kind 是受限枚举（已实测 signin/end 合法、courseware 非法 400/40001）。
原理：页面模板渲染流程步骤选择器时，合法 kind 列表必然以字符串形式写在 JS 里
      （如 kind:"signin"、"quiz"、value:"discussion"），扒包就能把白名单抄出来。
手段：复用 probe_api_bundle.py 的递归爬 chunk 思路，但检索目标从"接口调用点"换成
      "kind 字符串上下文"——只打印命中点前后一段原文，人工判读。
红线：全程只读（GET 静态资源），不建数据、不动真实课。
运行：& ".venv\Scripts\python.exe" "script\probe_flow_kinds_bundle.py"
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows 默认 GBK，防打印崩
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import urllib3

from config import BASE_URL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = BASE_URL.rstrip("/")
s = requests.Session()
s.verify = False

# 已实测合法的 kind（作为锚点：搜到它，周围的数组/对象里大概率就是整份白名单）
ANCHORS = ("signin", "courseware", "quiz")


def fetch(url):
    resp = s.get(url, timeout=20)
    return resp.status_code, resp.text


def find_assets(html, base):
    """从首页 HTML 里抠出 JS 资源地址（<script src> 与 modulepreload）"""
    out = []
    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', html):
        src = m.group(1)
        out.append(src if src.startswith("http") else f"{base}{src}")
    for m in re.finditer(r'<link[^>]+href=["\']([^"\']+\.js)[^"\']*["\']', html):
        href = m.group(1)
        out.append(href if href.startswith("http") else f"{base}{href}")
    return out


def scan_kind(text, origin):
    """打印锚点命中点上下文；顺带把 kind: 或 kind 为 key 的字面量全抄出来"""
    hits = 0
    # ① kind 字面量：形如 kind:"xxx" / kind:'xxx'（打包后 key 不带引号居多）
    for m in re.finditer(r'''kind\s*[:=]\s*['"]([\w\-]{2,30})['"]''', text, re.I):
        ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 60):m.end() + 60])
        print(f"  [{origin}] KIND-LIT {m.group(1)}")
        print(f"      ...{ctx}...")
        hits += 1
    # ② 锚点字符串（"signin" 等）出现在任何位置
    for anchor in ANCHORS:
        for m in re.finditer(r'''['"]%s['"]''' % re.escape(anchor), text):
            lo = max(0, m.start() - 180)
            hi = min(len(text), m.end() + 260)
            ctx = re.sub(r"\s+", " ", text[lo:hi])
            print(f"  [{origin}] ANCHOR '{anchor}' @{m.start()}")
            print(f"      ...{ctx}...")
            hits += 1
            break  # 每个文件每条锚点只打第一处，防刷屏
    return hits


def main():
    status, html = fetch(BASE)
    print(f"[首页] {BASE} -> HTTP {status}")
    queue = find_assets(html, BASE)
    print(f"[资源] 首页挂出 {len(queue)} 个 JS")

    seen = set()
    total = 0
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        name = url.rsplit("/", 1)[-1]
        st, body = fetch(url)
        if st != 200 or not body:
            continue
        hits = scan_kind(body, name)
        print(f"[扫描] {name}（{len(body)} 字节）命中 {hits}")
        total += hits
        # 递归找下一层 chunk
        for cm in set(re.findall(r'[\'"`./]*([\w\-\.]{4,60}\.js)[\'"`]', body)):
            fn = cm.rsplit("/", 1)[-1]
            if "vue-" in fn or "element-" in fn or "axios-" in fn:
                continue
            queue.append(f"{BASE}/assets/{fn}")

    print(f"\n===== 共 {len(seen)} 个文件，{total} 处命中 =====")


if __name__ == "__main__":
    main()
