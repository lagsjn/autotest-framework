r"""
接口清单侦察（第二轮：从前端 JS 包里抄路径）—— 2026-11-11
- 上一轮结论：系统没暴露 OpenAPI 文档（/openapi.json /docs 回的是首页 HTML，前端兜底路由）。
- 本轮换路线：前端是打包出来的 JS（Vue 单页应用）。所有接口路径最终都必须以字符串形式
  写在 JS 里（比如 "/courses"、"/auth/login"），否则浏览器不知道该往哪发请求。
  所以"下载 JS 包 + 正则检索"就等于把系统的接口清单抄出来，全程只读、零副作用。
  （这叫静态代码侦察，是接口测试里补文档缺口的常规手段，不是攻击手段）
- 下一步：拿到路径清单后，再单独写第三个脚本实测写接口的请求体字段。
- 运行（默认老师端 8081）：& ".venv\\Scripts\\python.exe" "script\probe_api_bundle.py"
- 换学生端：  & ".venv\\Scripts\\python.exe" "script\probe_api_bundle.py" student
- 只扒单个 chunk（不过滤关键词、把该文件所有调用点全抄）：
  & ".venv\\Scripts\\python.exe" "script\probe_api_bundle.py" teacher course-CfoxDUa0.js
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows 默认 GBK，防打印崩
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import urllib3

from config import BASE_URL, STUDENT_BASE_URL, API_PREFIX

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 命令行参数：第1个参=选哪一端（老师/学生），第2个参=只扒那个 chunk 文件名
which = (sys.argv[1] if len(sys.argv) > 1 else "teacher").lower()
BASE = (STUDENT_BASE_URL if which == "student" else BASE_URL).rstrip("/")
ONLY = sys.argv[2] if len(sys.argv) > 2 else None
print(f"目标端：{BASE}")

s = requests.Session()
s.verify = False

# 感兴趣的关键词：这次 E2E 要用的四个动作都在这几类里
KEYWORDS = ("course", "archiv", "join", "enroll", "invite", "member", "class",
            "lesson", "auth", "user", "student", "teacher")


def fetch(url):
    resp = s.get(url, timeout=20)
    return resp.status_code, resp.text


def find_assets(html, base):
    """从首页 HTML 里抠出 JS / CSS 资源地址（<script src="/assets/xxx.js">）"""
    out = []
    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', html):
        src = m.group(1)
        out.append(src if src.startswith("http") else f"{base}{src}")
    # 现代打包工具还会用 <link rel="modulepreload"> 预加载 JS，一并收进来
    for m in re.finditer(r'<link[^>]+href=["\']([^"\']+\.js)[^"\']*["\']', html):
        href = m.group(1)
        out.append(href if href.startswith("http") else f"{base}{href}")
    return out


def scan(text, origin, bucket, keep_all=False):
    """检索【HTTP 调用点】：形如  xxx.post("/courses", {name:e})  /  xxx.get(`/courses/${t}`)
    只盯调用点而不是裸路径字符串，原因：裸 "/courses" 可能是前端路由（页面地址），
    带 .get/.post 的才是后端接口；顺带把整行调用抄下来，请求体字段就写在第二个参数里
    keep_all=True：关掉关键词过滤（扒单个业务 chunk 时用，一个不漏全抄）
    """
    pat = re.compile(
        r'''[\w$.\]]{1,20}\.(get|post|put|patch|delete)\s*\(\s*['"`]([^'"`]{2,80})['"`]''',
        re.I)
    for m in pat.finditer(text):
        method, path = m.group(1).upper(), m.group(2)
        low = path.lower()
        if not low.startswith("/"):
            continue  # 相对拼路的（如 "courses/"+id）单独看，先滤掉噪音
        if API_PREFIX.lower() in low:
            path = path.replace(API_PREFIX, "")  # 前缀写在 axios baseURL 里的另一种写法
        if not any(k in low for k in KEYWORDS) and not keep_all:
            continue
        # 上下文多截一点：请求体字段（第二个参数）就在后面
        ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 30):m.end() + 160])
        bucket.setdefault(f"{method} {path}", []).append((origin, ctx))


def dump_chunk(name):
    """只扒一个 chunk：不过滤关键词，把里面所有接口调用点全抄出来（找具体请求体字段用）"""
    url = f"{BASE}/assets/{name}"
    st, body = fetch(url)
    print(f"[{name}] HTTP {st}，{len(body)} 字节")
    if st != 200:
        return
    bucket = {}
    scan(body, name, bucket, keep_all=True)
    print(f"\n===== {name} 共 {len(bucket)} 个调用点（全部，未过滤）=====")
    for key in sorted(bucket):
        print(f"\n{key}")
        for origin, ctx in bucket[key][:3]:
            print(f"  ...{ctx}...")


def main():
    if ONLY:
        dump_chunk(ONLY)
        return
    status, html = fetch(BASE)
    print(f"[首页] {BASE_URL}/ -> HTTP {status}，{len(html)} 字节")
    assets = find_assets(html, BASE)
    print(f"[资源] 首页挂出 {len(assets)} 个 JS：")
    for a in assets:
        print(f"  {a}")
    # 二次校验：首页 HTML 里没写 chunk 名时，至少保证主包先扫
    print(f"[首页] 内容开头：{html[:120]!r}")

    # 异步 chunk 递归扒：Vite 打包会把每个页面切成单独文件，建课/归档那些调用就在里面
    queue = list(assets)
    seen = set()
    bucket = {}
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        name = url.rsplit("/", 1)[-1]
        st, body = fetch(url)
        if st != 200 or not body:
            continue
        print(f"[扫描] {name}（{len(body)} 字节）")
        scan(body, name, bucket)
        # 从当前文件里再找下一层 chunk 引用（两种写法：./Xxx.js 与 "assets/Xxx.js"）
        for cm in set(re.findall(r'[\'"`./]*([\w\-\.]{4,60}\.js)[\'"`]', body)):
            fn = cm.rsplit("/", 1)[-1]
            if "vue-" in fn or "element-" in fn or "axios-" in fn:
                continue
            queue.append(f"{BASE}/assets/{fn}")
    
    print(f"\n===== 检索到 {len(bucket)} 个接口调用点 =====")
    for key in sorted(bucket):
        hits = bucket[key]
        print(f"\n{key}   （命中 {len(hits)} 处）")
        for origin, ctx in hits[:3]:
            print(f"  [{origin}] ...{ctx}...")


if __name__ == "__main__":
    main()
