r"""
上课流程·kind 白名单动态验证（只在自建沙箱 draft 讲次上探）：2026-11-15
背景：静态扒包（probe_flow_kinds_bundle.py）已见 LessonLinkCard-DuuWYVJg.js 里的步骤构造器：
      kind 取值 slides/quiz/discussion/demo（+固定头尾 signin/end），courseware 已实测非法。
      JS 里还零散出现过 rollcall/ask/ppt/plan/homework/bank/sign_in/lesson-plan/question-bank
      等字符串，但它们可能属于别的界面（备课清单、AI工具），必须拿后端裁决。
手段（两轮拿全白名单）：
  轮1 批量：steps = [signin] + 每个候选一条 + [end]，一次 PUT。
      已实测 400 的 data 是"字段错误 list"（如 steps.1.kind）——若后端一次收齐所有错误，
      出错下标=非法候选，没出错下标=合法；若只报 1 条则怀疑"遇错即停"，转轮2。
  轮2 逐条兜底：每候选单独 PUT [signin, 候选, end]，200=合法、400=非法，同时记录非 kind
      字段的报错（能顺带摸出每种步必填什么，如 quiz 是否必填 quiz_id）。
红线：只在自建沙箱讲次操作；结尾归档沙箱课。
运行：& ".venv\Scripts\python.exe" "script\probe_api_flow_kinds.py"
"""
import os
import re
import sys
import json
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, USERNAME, PASSWORD
from api.base_api import BaseApi
from api.login_api import LoginApi
from api.course_api import CourseApi
from api.lesson_api import LessonApi

# 候选池：静态包命中的 + 已知锚点（signin/end sanity、courseware 应仍被拒）
CANDIDATES = [
    "signin", "end",                      # 已知合法，当对照
    "courseware",                         # 已知非法，当对照
    "slides", "quiz", "discussion", "demo",   # 构造器直接证据
    "rollcall", "ask", "discuss", "ppt", "plan", "homework", "bank",
    "question-bank", "lesson-plan", "sign_in", "ai-ppt", "danmaku",
]

# 一把步骤对象的完整字段壳（照 GET 基线里 signin 步的结构抄，内容位全 null）
def make_step(kind):
    return {"kind": kind, "courseware_id": None, "courseware_name": None,
            "page_from": None, "page_to": None, "quiz_id": None, "quiz_title": None,
            "quiz_status": None, "topic": None, "demo_job_id": None, "demo_title": None,
            "missing": False}


def show(tag, resp, keep=900):
    print(f"\n### {tag}")
    print(f"    -> HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        print(f"    [非 JSON] {resp.text[:200]}")
        return None
    print("    " + json.dumps(body, ensure_ascii=False, indent=2)[:keep].replace("\n", "\n    "))
    return body


def data_of(body):
    d = (body or {}).get("data") if isinstance(body, dict) else None
    return d if isinstance(d, dict) else None


def err_fields(body):
    """把 400 的 data 归一成 ['steps.1.kind', ...] 字符串列表
    data 形态实测：可能是错误 dict 列表（[{field,message}]），也可能再包一层 {errors:[...]}
    """
    d = (body or {}).get("data") if isinstance(body, dict) else None
    if isinstance(d, dict):
        # 再往里找一层常见的列表字段
        for v in d.values():
            if isinstance(v, list):
                d = v
                break
    out = []
    if isinstance(d, list):
        for it in d:
            if isinstance(it, str):
                out.append(it)
            elif isinstance(it, dict):
                out.append(str(it.get("field") or it.get("loc") or it))
    elif isinstance(d, str):
        out.append(d)
    return out


def kind_bad_indexes(fields):
    """从字段错误里抠出 kind 步下标"""
    return {int(m.group(1)) for f in fields for m in [re.search(r"steps\.(\d+)\.kind", f)] if m}


def main():
    api = BaseApi(BASE_URL)
    lessons = LessonApi(BASE_URL)
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    print(f"老师 token 已取得（{token[:12]}...）")

    # 1. 建沙箱课 + draft 讲次
    course_name = f"AT-KIND-{time.strftime('%m%d%H%M%S')}"
    cb = show("1-1 POST /courses 建沙箱课", CourseApi().create_course(token, course_name), keep=200)
    cid = (data_of(cb) or {}).get("id")
    if not cid:
        print("沙箱课没建成，退出")
        return
    lb = show("1-2 POST /courses/{id}/lessons 建 draft 讲次",
              lessons.create_lesson(token, cid, title="AT kind白名单探", week_no=1, weekday=3, period="78"),
              keep=200)
    lid = (data_of(lb) or {}).get("id")
    if not lid:
        print("讲次没建成，退出")
        CourseApi().archive_course(token, cid)
        return
    print(f"沙箱课 id={cid} 讲次 id={lid}")

    verdict = {}   # kind -> "OK" / "BAD" / ("BAD:" + 报错字段)
    try:
        # 2. GET 基线（拿信封结构照抄，只换 steps）
        base = show(f"2-1 GET /lessons/{lid}/flow 基线", api.get(f"/lessons/{lid}/flow", token=token), keep=500)
        base_data = data_of(base) or {}

        # 3. 轮1 批量：signin + 每候选一条 + end
        steps = [make_step("signin")] + [make_step(k) for k in CANDIDATES] + [make_step("end")]
        body = dict(base_data)
        body["steps"] = steps
        body["saved"] = True
        resp1 = api.put(f"/lessons/{lid}/flow", token=token, json=body)
        r1 = show(f"3-1 PUT flow 批量 {len(CANDIDATES)} 候选", resp1, keep=1500)
        fields = err_fields(r1)
        bad = kind_bad_indexes(fields)
        print(f"\n    轮1 字段错误 {len(fields)} 条：{fields[:30]}")
        hint_ok = 0
        if resp1 is not None and resp1.status_code == 400 and len(bad) > 1:
            # 后端一次报全：下标 i+1 对应 CANDIDATES[i]
            for i, k in enumerate(CANDIDATES):
                if i + 1 in bad:
                    verdict[k] = "BAD"
                else:
                    verdict[k] = "OK?"   # 加问号：轮1 过了校验，但没逐条确认，兜底轮会转实
            hint_ok = sum(1 for v in verdict.values() if v == "OK?")
            print(f"    轮1 判读：报错 {len(bad)} 个下标 → 初判非法 {len(bad)}，未报错 {hint_ok}")

        # 4. 轮2 逐条：凡轮1 没判成非法的 + 怀疑遇错即停时全部重测
        to_one_by_one = [k for k in CANDIDATES if verdict.get(k) != "BAD"] if hint_ok else CANDIDATES
        if hint_ok == 0 and len(bad) <= 1:
            to_one_by_one = CANDIDATES   # 疑似遇错即停，全部逐条
        print(f"\n===== 轮2 逐条验证 {len(to_one_by_one)} 个候选 =====")
        for k in to_one_by_one:
            one = dict(base_data)
            one["steps"] = [make_step("signin"), make_step(k), make_step("end")]
            one["saved"] = True
            resp = api.put(f"/lessons/{lid}/flow", token=token, json=one)
            f2 = err_fields(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None)
            if resp.status_code == 200:
                verdict[k] = "OK"
                print(f"  {k:<15} -> {resp.status_code} OK")
            else:
                bad_here = any("kind" in x for x in f2)
                verdict[k] = "BAD" if bad_here else f"BAD-FIELDS {f2}"
                print(f"  {k:<15} -> {resp.status_code} {verdict[k]}")
                # 关键：字段列表为空时把原始响应体打出来，看 400 到底长什么样
                if not f2:
                    print(f"      原始体: {resp.text[:400]}")

        # 5. 回读确认：合法项最后再整体 PUT 一次，GET 看步数是否真的落库
        good = [k for k, v in verdict.items() if v == "OK" and k not in ("signin", "end")]
        print(f"\n===== 结论汇总 =====")
        for k in CANDIDATES:
            print(f"  {k:<15} {verdict.get(k, '?')}")

        # 4.5 轮3：轮2 里 kind 过了但被更深校验拒的内容步，补齐各自内容字段再试，
        #     验证假设"slides/quiz/discussion/demo 必需对应内容字段非空"（静态包里
        #     构造器实证：这几类步建的时候必然带 id/topic，只有 rollcall 不带）
        filled = {
            "slides": {"courseware_id": 1, "courseware_name": "AT课件", "page_from": 1, "page_to": 3},
            "quiz": {"quiz_id": 1, "quiz_title": "AT随堂测", "quiz_status": "done"},
            "discussion": {"topic": "AT讨论题"},
            "demo": {"demo_job_id": 1, "demo_title": "AT演示"},
        }
        suspect = [k for k in to_one_by_one if str(verdict.get(k, "")).startswith("BAD-FIELDS") and k in filled]
        if suspect:
            print(f"\n===== 轮3 补齐内容字段重试 {suspect} =====")
            for k in suspect:
                st = make_step(k)
                st.update(filled[k])
                one = dict(base_data)
                one["steps"] = [make_step("signin"), st, make_step("end")]
                one["saved"] = True
                resp = api.put(f"/lessons/{lid}/flow", token=token, json=one)
                f3 = err_fields(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None)
                mark = "OK-FILLED" if resp.status_code == 200 else f"STILL-400 {f3 or resp.text[:300]}"
                print(f"  {k:<15} -> {resp.status_code} {mark}")
                if resp.status_code == 200:
                    verdict[k] = "OK"
                    good.append(k)

        if good:
            def step_for(k):
                st = make_step(k)
                if k in filled:
                    st.update(filled[k])
                return st
            final = dict(base_data)
            final["steps"] = [make_step("signin")] + [step_for(k) for k in good] + [make_step("end")]
            final["saved"] = True
            show("5-1 PUT 仅合法自定义步", api.put(f"/lessons/{lid}/flow", token=token, json=final), keep=300)
            after = show("5-2 GET 回读", api.get(f"/lessons/{lid}/flow", token=token), keep=1500)
            kinds = [s.get("kind") for s in (data_of(after) or {}).get("steps", []) if isinstance(s, dict)]
            print(f"    回读 kinds={kinds}（期望 signin+{good}+end 全在）")
    finally:
        print("\n===== 侦察收尾：归档沙箱课 =====")
        try:
            show(f"F DELETE /courses/{cid}", CourseApi().archive_course(token, cid), keep=150)
        except Exception as e:
            print(f"    !!! 归档失败，请手动归档 id={cid} name={course_name}: {e}")


if __name__ == "__main__":
    main()
