"""
接口清单侦察（第一轮：先摸地图，不动数据）—— 2026-11-11
- 目的：API E2E 串联要用到 建课/详情/加入/归档 四个接口，路径和请求体字段现在还不清楚。
  硬猜有两个害处：①猜错路径打出一堆 404/405 日志噪音；②猜对写接口但字段不全，
  凭空造出半门课污染测试环境。所以先找系统的"接口说明书"。
- 说明书从哪来：这类后端（FastAPI/Swagger 家族）默认会把全部接口导出成一份 JSON，
  常见地址是 /openapi.json 或 /api/v1/openapi.json。拿到它 = 一次看清所有路径、方法、字段。
  （这属于"公开元数据探测"，是接口测试正常的路线调研，不是漏洞扫描）
- 铁律：本脚本全程只读（只有 GET，且只问文档地址，不碰任何业务写接口）。
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_api_schema.py"
"""
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows 默认 GBK，防打印崩
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib3

from config import BASE_URL, STUDENT_BASE_URL, API_PREFIX

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 候选地址：版本前缀内外都试；后端口顺序=先试无鉴权的通用约定位置
CANDIDATES = [
    "/openapi.json",
    f"{API_PREFIX}/openapi.json",
    "/api/openapi.json",
    "/docs",
    f"{API_PREFIX}/docs",
    "/swagger-ui.html",
    "/v2/api-docs",          # Spring Boot 老格式（万一后端不是 FastAPI）
]


def probe_one(base, path):
    """GET 一个候选文档地址，回一行结论；是 JSON 就返回解析结果，否则 None"""
    url = f"{base.rstrip('/')}{path}"
    try:
        resp = __import__("requests").get(url, timeout=10, verify=False)
    except Exception as e:
        print(f"    [异常] {url} -> {type(e).__name__}: {e}")
        return None
    ctype = resp.headers.get("content-type", "")
    print(f"    {url}  -> HTTP {resp.status_code} | {ctype[:40]} | {len(resp.text)} 字节")
    if resp.status_code == 200 and "json" in ctype.lower():
        try:
            return resp.json()
        except ValueError:
            pass
    return None


def summarize(schema):
    """把 OpenAPI JSON 缩成人类能读的接口清单，重点挑出课程相关的"""
    paths = schema.get("paths", {})
    print(f"\n===== 接口总清单：共 {len(paths)} 个路径 =====")
    for p in sorted(paths):
        for method in sorted(paths[p]):
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                print(f"  {method.upper():<6} {p}")

    print("\n===== 课程/加入/归档 相关路径的细节 =====")
    keys = ("course", "enroll", "join", "archive", "student", "class", "member")
    hit = [p for p in paths if any(k in p.lower() for k in keys)]
    for p in sorted(hit):
        for method, spec in sorted(paths[p].items()):
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            note = spec.get("summary") or spec.get("description") or "(无说明)"
            print(f"\n--- {method.upper()} {p}  说明：{note}")
            params = spec.get("parameters") or []
            for q in params:
                print(f"    query/path 参数: {q.get('name')} ({q.get('in')}) 必填={q.get('required')}")
            body = ((spec.get("requestBody") or {}).get("content") or {})
            for ctype, content in body.items():
                ref = (content.get("schema") or {}).get("$ref")
                print(f"    请求体 {ctype} schema={ref}")
                if ref:
                    name = ref.split("/")[-1]
                    comp = (schema.get("components", {}).get("schemas", {}) or {}).get(name, {})
                    props = comp.get("properties", {})
                    req = comp.get("required", [])
                    for fname, fval in props.items():
                        mark = "*" if fname in req else " "
                        print(f"      {mark} {fname}: {fval.get('type')} 默认={fval.get('default')} "
                              f"例={fval.get('example') or fval.get('examples')}")
    return hit


def main():
    for label, base in (("老师端 8081", BASE_URL), ("学生端 8082", STUDENT_BASE_URL)):
        if not base:
            continue
        print(f"\n########## {label}：{base} ##########")
        for path in CANDIDATES:
            schema = probe_one(base, path)
            if isinstance(schema, dict) and "paths" in schema:
                print(f"    *** 命中 OpenAPI 文档：{path}，标题={schema.get('info', {}).get('title')} ***")
                summarize(schema)
                return  # 一份够了，不必两端都扒
        print("    未拿到 JSON 接口文档（可能被关掉了），下一步改走『UI 操作 + 抓包』路线侦察。")

    print("\n结论：没有现成文档。改写第二个侦察脚本——用浏览器打开建课/加入/归档页面，"
          "从 Network 请求里抄真实路径与字段（只读抄录，不猜）。")


if __name__ == "__main__":
    main()
