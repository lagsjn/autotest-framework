r"""
上课流程·flow 写接口侦察（只在自建沙箱 draft 讲次上探）：2026-11-15
目的：扒清 PUT /lessons/{id}/flow 的请求体结构与持久化语义，为"自定义流程"用例铺路。
手段（不凭空猜，让后端一步步告诉我们）：
  ① 自建 AT-* 沙箱课 + draft 讲次；
  ② GET flow 拿当前结构当基线（默认模板 [signin, end]、saved=false）；
  ③ 候选 PUT 逐轮试，每轮 PUT 后紧跟一次 GET 回读看是否生效：
     A. 原样把 GET 的 data 回传（验证信封 {lesson_id,saved,steps} 收不收）
     B. {steps: [...]} 只给 steps（很多实现只要 steps）
     C. saved=true + 中间插一步（看能否持久化 + 自定义步是否被接受）
     被拒就读 400 字段明细，据此收敛请求体。
红线：只在自建沙箱讲次操作，绝不 PUT 真实/演示讲次；结尾归档沙箱课。
运行：& ".venv\Scripts\python.exe" "script\probe_api_flow_write.py"
"""
import os
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


def brief_steps(flow_data):
    if not isinstance(flow_data, dict):
        return flow_data
    steps = flow_data.get("steps") or []
    return {"saved": flow_data.get("saved"),
            "kinds": [s.get("kind") for s in steps if isinstance(s, dict)]}


def main():
    api = BaseApi(BASE_URL)
    lessons = LessonApi(BASE_URL)
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    print(f"老师 token 已取得（{token[:12]}...）")

    # 1. 建沙箱课 + draft 讲次
    course_name = f"AT-API-{time.strftime('%m%d%H%M%S')}"
    cb = show("1-1 POST /courses 建沙箱课", CourseApi().create_course(token, course_name), keep=200)
    cid = (data_of(cb) or {}).get("id")
    if not cid:
        print("沙箱课没建成，退出")
        return
    lb = show("1-2 POST /courses/{id}/lessons 建 draft 讲次",
              lessons.create_lesson(token, cid, title="AT flow写探", week_no=1, weekday=3, period="78"),
              keep=200)
    lid = (data_of(lb) or {}).get("id")
    if not lid:
        print("讲次没建成，退出")
        CourseApi().archive_course(token, cid)
        return
    print(f"沙箱课 id={cid} 讲次 id={lid}")

    try:
        # 2. GET 基线
        base = show(f"2-1 GET /lessons/{lid}/flow 基线", api.get(f"/lessons/{lid}/flow", token=token))
        base_data = data_of(base)
        print(f"    基线概览：{brief_steps(base_data)}")

        # 3-A：原样回传 GET 的 data
        show("3-A PUT flow  原样回传 data", api.put(f"/lessons/{lid}/flow", token=token, json=base_data), keep=400)
        show("     回读", api.get(f"/lessons/{lid}/flow", token=token), keep=400)

        # 3-B：只给 steps
        steps_only = {"steps": (base_data or {}).get("steps", [])}
        show("3-B PUT flow  body={steps:[...]}", api.put(f"/lessons/{lid}/flow", token=token, json=steps_only), keep=400)
        show("     回读", api.get(f"/lessons/{lid}/flow", token=token), keep=400)

        # 3-C：saved=true + 中间插一步（用一个新 kind，看后端认不认自定义步）
        modified = json.loads(json.dumps(base_data))  # 深拷贝
        steps = modified.get("steps", [])
        # 在 signin 与 end 之间插一步（先试 kind="courseware"，不确定是否合法，看返回）
        insert = {"kind": "courseware", "courseware_id": None, "courseware_name": "AT 探测课件",
                  "page_from": None, "page_to": None, "quiz_id": None, "quiz_title": None,
                  "quiz_status": None, "topic": None, "demo_job_id": None, "demo_title": None,
                  "missing": False}
        # 插到 end 之前
        pos = next((i for i, s in enumerate(steps) if s.get("kind") == "end"), len(steps))
        steps.insert(pos, insert)
        modified["saved"] = True
        show("3-C PUT flow  插一步(courseware)+saved=true",
             api.put(f"/lessons/{lid}/flow", token=token, json=modified), keep=600)
        after = show("     回读（看插入的步有没有存下来）", api.get(f"/lessons/{lid}/flow", token=token), keep=800)
        print(f"    >>> 写后概览：{brief_steps(data_of(after))}")
    finally:
        print("\n===== 侦察收尾：归档沙箱课 =====")
        try:
            show(f"F DELETE /courses/{cid}", CourseApi().archive_course(token, cid), keep=150)
        except Exception as e:
            print(f"    !!! 归档失败，请手动归档 id={cid} name={course_name}: {e}")


if __name__ == "__main__":
    main()
