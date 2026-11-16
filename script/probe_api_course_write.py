r"""
写接口实测侦察（第三轮）：建课 → 详情 → 学生加入 → 成员 → 归档，全链路走 HTTP —— 2026-11-11
- 前置结论（来自 probe_api_bundle.py 静态侦察，非猜测）：
    POST   /courses                建课（请求体字段本脚本实测，JS 里是 post("/courses", e) 看不清）
    GET    /courses/{id}           课程详情
    POST   /courses/join           学生凭码加入，body={"invite_code": "..."}（JS 里明文抄到）
    GET    /courses/{id}/members   班级成员
    DELETE /courses/{id}           清单里没有 "archive" 字样，UI 的"归档课程"极可能映射到这条 → 本脚本站队定性
    DELETE /courses/{id}/permanent 永久删除 = 红线，本脚本绝不触碰
- 副作用控制（为什么敢在这里写数据）：
    ① 只操作本脚本自己新建的课（课程名 AT-API-<时间戳>，唯一、可认、可丢）；
    ② 绝不拿演示课"大数据技术与原理"做写操作（那是别人在用的数据）；
    ③ 结尾无条件归档自己造的课，跑完环境干净；
    ④ 一次只造一门，失败也不批量重试（避免残留一堆课）。
- 运行：& ".venv\Scripts\python.exe" "script\probe_api_course_write.py"
"""
import os
import sys
import json
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows 默认 GBK，防打印崩
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, STUDENT_BASE_URL, USERNAME, PASSWORD,
                    STUDENT_USERNAME, STUDENT_PASSWORD, HAS_STUDENT)
from api.base_api import BaseApi
from api.login_api import LoginApi

COURSE_API = "/courses"


def show(tag, resp, keep=800):
    """打印一行 HTTP 概要 + 精简返回体（结构化数据要看得见，不能只看状态码）"""
    print(f"\n### {tag}")
    print(f"    -> HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        print(f"    [非 JSON] {resp.text[:200]}")
        return None
    print("    " + json.dumps(body, ensure_ascii=False, indent=2)[:keep].replace("\n", "\n    "))
    return body


def pick(data, *keys):
    """从返回体里挑几个关键字段看一眼（详情字段名要靠这个定，不能瞎写）"""
    if not isinstance(data, dict):
        return None
    return {k: data.get(k) for k in keys if k in data}


def data_items(body):
    """从列表返回体里取 items，带类型防御
    实测坑（本脚本 114 行踩过）：data 不永远是 dict——正常=dict、
    分页参数超限时（page_size=200）=list（装字段校验错误明细）。
    同一个字段类型随分支变，取值必须先验类型，否则 AttributeError 把后面步骤全带走
    """
    data = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def main():
    api = BaseApi(BASE_URL)
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    print(f"老师 token 已取得（{token[:12]}...）")

    # ---------- 0. 基线：现有课程列表长什么样（拿字段名 + 记录原有 id，后面好比对）----------
    body = show("0-1 GET /courses 老师原始列表（只看第一条的结构）",
                api.get(COURSE_API, token=token, params={"page": 1, "page_size": 5}))
    items = data_items(body)
    if items:
        print(f"\n    列表项字段名：{sorted(items[0].keys())}")
        print(f"    样例：{pick(items[0], 'id', 'name', 'status', 'invite_code', 'code', 'teacher_id', 'member_count')}")

    # ---------- 1. 建课：先按 UI 只填一门名字试（后端会告诉我还缺什么字段）----------
    name = f"AT-API-{time.strftime('%m%d%H%M%S')}"
    resp = api.post(COURSE_API, token=token, json={"name": name})
    body = show(f"1-1 POST /courses  body={{'name': '{name}'}}", resp)
    if resp.status_code != 200:
        print("\n    >>> 建课被拒，看上面错误明细补字段（400 的 data 通常是字段错误列表）")
        return
    data = (body or {}).get("data") or {}
    cid, icode = data.get("id"), (data.get("invite_code") or data.get("code"))
    print(f"\n    新建课程 id={cid} 邀请码={icode} status={data.get('status')}")
    if cid is None:
        print("    >>> 返回体里没有 id，需要从列表里按课程名反查（下面自动兜底）")
        lst = api.get(COURSE_API, token=token, params={"page": 1, "page_size": 100}).json()
        hit = [c for c in data_items(lst) if c.get("name") == name]
        print(f"    反查命中：{pick(hit[0], 'id', 'name', 'status', 'invite_code') if hit else '没有，说明建课没落库'}")
        return

    try:
        # ---------- 2. 详情：字段名断言的依据全在这一步 ----------
        d = show(f"2-1 GET /courses/{cid} 课程详情", api.get(f"{COURSE_API}/{cid}", token=token))
        print(f"\n    详情字段名：{sorted((d or {}).get('data', {}).keys())}")
        print(f"    详情里邀请码字段：{pick((d or {}).get('data') or {}, 'invite_code', 'code', 'status', 'teacher_id')}")

        # ---------- 3. 学生凭码加入（写操作，加的是 demo_student 自己）----------
        if HAS_STUDENT and icode:
            stu_api = BaseApi(STUDENT_BASE_URL)
            stu_token = LoginApi(STUDENT_BASE_URL).login_and_get_token(STUDENT_USERNAME, STUDENT_PASSWORD)
            show(f"3-1 POST /courses/join body={{'invite_code': '{icode}'}} 学生端",
                 stu_api.post(f"{COURSE_API}/join", token=stu_token, json={"invite_code": icode}))
            sb = show("3-2 GET /courses 学生列表里有没有这门课",
                      stu_api.get(COURSE_API, token=stu_token, params={"page": 1, "page_size": 100}))
            s_items = data_items(sb)
            print(f"\n    学生列表含本课：{any(c.get('id') == cid for c in s_items)}  "
                  f"（学生共 {len(s_items)} 门，本课名 {name}）")
            mm = show(f"3-3 GET /courses/{cid}/members 班级成员（老师视角）",
                      api.get(f"{COURSE_API}/{cid}/members", token=token,
                              params={"page": 1, "page_size": 20}))
            print(f"\n    成员结构：{json.dumps((mm or {}).get('data'), ensure_ascii=False)[:400]}")
        elif not HAS_STUDENT:
            print("\n[跳过] .env 未配学生端，加入/成员两步不测")

        # ---------- 4. 归档语义定性：DELETE 到底是软删(归档)还是硬删 ----------
        ar = show(f"4-1 DELETE /courses/{cid} 归档候选", api.delete(f"{COURSE_API}/{cid}", token=token))
        after = show(f"4-2 DELETE 之后再 GET /courses/{cid}（看是 404/报错，还是 status=archived）",
                     api.get(f"{COURSE_API}/{cid}", token=token), keep=400)
        print(f"\n    >>> 定性依据：4-2 若 HTTP 200 且 status 变了 -> 软删(归档)；"
              f"若 404/业务码报错 -> 记录已不可读，需再看列表里是否彻底消失")
        # 归档后老师列表里还在吗（分页上限实测为 100，超了 data 会变 list）
        lst2 = api.get(COURSE_API, token=token, params={"page": 1, "page_size": 100}).json()
        still = [c for c in data_items(lst2) if c.get("id") == cid]
        print(f"    归档后老师列表里还在吗：{bool(still)}  {pick(still[0], 'id', 'name', 'status') if still else ''}")
        # 归档后学生能不能再加入同一门（预期失败，手册规则：已归档课程加入失败）
        if HAS_STUDENT and icode:
            show("4-3 归档后学生再 POST /courses/join 同一码（预期被拒）",
                 BaseApi(STUDENT_BASE_URL).post(
                     f"{COURSE_API}/join",
                     token=LoginApi(STUDENT_BASE_URL).login_and_get_token(STUDENT_USERNAME, STUDENT_PASSWORD),
                     json={"invite_code": icode}))
    finally:
        print("\n===== 侦察收尾：本次造的课已在第 4 步归档；若中途异常退出，请手动归档 " + name + " =====")


if __name__ == "__main__":
    main()
