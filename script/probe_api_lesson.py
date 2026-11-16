r"""
上课流程·建讲次与状态机侦察（动态实测）：2026-11-15
目的（接口地图 docs/上课流程接口地图.md 留的唯一卡点）：
  摸清 POST /courses/{course_id}/lessons 建讲次的请求体字段，以及
  lesson 状态机 draft →(start)→ ongoing →(end)→ ended 三步的真实返回。
手段（全程零风险，只在自建沙箱课上操作）：
  ① 先 GET 演示课 14 的 lessons 看真实讲次长什么样（只读，抄字段名）；
  ② 自建 AT-* 沙箱课，对它的 lessons 空 body 试建 → 读 400 字段校验明细，
     按明细逐轮补字段，直到 200（后端会亲口告诉我缺哪几个字段，不凭空猜）；
  ③ 拿到 draft 讲次 id 后：GET 详情看 status 字段名 → POST start 断言变 ongoing
     → POST end 断言变 ended（都在沙箱讲次上，不碰真实 104）。
红线：绝不 GET/PATCH/POST 真实课堂（演示课 14、ongoing 104）的写接口；
      造的沙箱课收尾无条件归档。
运行：& ".venv\Scripts\python.exe" "script\probe_api_lesson.py"
"""
import os
import sys
import json
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows 默认 GBK，防打印崩
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, USERNAME, PASSWORD
from api.base_api import BaseApi
from api.login_api import LoginApi
from api.course_api import CourseApi

# 只读参考用的演示课 id（已下课的历史课，读它不写它）
DEMO_COURSE_ID = 14


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


def items_of(body):
    d = data_of(body)
    if not d:
        return []
    it = d.get("items")
    return it if isinstance(it, list) else []


def main():
    api = BaseApi(BASE_URL)
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    print(f"老师 token 已取得（{token[:12]}...）")

    # ---------- 0. 只读参考：真实讲次长什么样（抄字段名，不写演示课） ----------
    ref = show(f"0-1 GET /courses/{DEMO_COURSE_ID}/lessons 演示课讲次（只读参考）",
               api.get(f"/courses/{DEMO_COURSE_ID}/lessons", token=token,
                       params={"page": 1, "page_size": 5}))
    ref_items = items_of(ref)
    if ref_items:
        print(f"\n    讲次字段名：{sorted(ref_items[0].keys())}")
        print(f"    样例：{ {k: ref_items[0].get(k) for k in ('id','seq','title','name','status','course_id','start_time','end_time','scheduled_at','date') if k in ref_items[0]} }")

    # ---------- 1. 自建沙箱课 ----------
    course_name = f"AT-API-{time.strftime('%m%d%H%M%S')}"
    body = show(f"1-1 POST /courses 建沙箱课 {course_name}",
                CourseApi().create_course(token, course_name))
    d = data_of(body)
    if not d or not d.get("id"):
        print("    >>> 沙箱课没建出来，后面免谈")
        return
    cid = d["id"]
    print(f"    沙箱课 id={cid}")

    try:
        # ---------- 2. 空 body 建讲次，读 400 校验明细（后端亲口告知缺哪些字段） ----------
        resp = api.post(f"/courses/{cid}/lessons", token=token, json={})
        show("2-1 POST /courses/{id}/lessons  body={} 探字段", resp)
        # 空 body 常见三种结果：①400 带字段错误列表(最理想) ②404 说明路径不对 ③200 全默认值

        # ---------- 3. 按后端明说补齐：必填 title/week_no/weekday/period（seq 非必填） ----------
        ref0 = ref_items[0] if ref_items else {}
        guesses = [
            {"title": "AT 沙箱讲次",
             "week_no": ref0.get("week_no", 1) if isinstance(ref0, dict) else 1,
             "weekday": ref0.get("weekday", 3) if isinstance(ref0, dict) else 3,
             "period": ref0.get("period", "78") if isinstance(ref0, dict) else "78"},
        ]
        created = None
        for i, g in enumerate(guesses):
            resp = api.post(f"/courses/{cid}/lessons", token=token, json=g)
            body = show(f"3-{i+1} POST lessons  body={json.dumps(g, ensure_ascii=False)}", resp, keep=500)
            if resp.status_code == 200 and (body or {}).get("code") == 0:
                created = data_of(body)
                print(f"    >>> 命中！请求体字段 = {json.dumps(g, ensure_ascii=False)}")
                break
        if not created or not created.get("id"):
            print("\n    >>> 建讲次始终没成功，把上面 400 明细发我，下轮按字段名补")
            return
        lid = created.get("id")
        print(f"    新建讲次 id={lid} status={created.get('status')}")

        # ---------- 4. GET 详情确认 status 字段与初始值 ----------
        det = show(f"4-1 GET /lessons/{lid} 讲次详情（看初始 status）",
                   api.get(f"/lessons/{lid}", token=token))
        dd = data_of(det) or created
        print(f"    详情 status={dd.get('status')}")

        # ---------- 5. start：draft → ongoing ----------
        st = show(f"5-1 POST /lessons/{lid}/start  body={{}}",
                  api.post(f"/lessons/{lid}/start", token=token, json={}))
        show(f"5-2 GET /lessons/{lid} 看 start 后 status",
             api.get(f"/lessons/{lid}", token=token), keep=400)

        # ---------- 6. end：ongoing → ended ----------
        show(f"6-1 POST /lessons/{lid}/end 无 body",
             api.post(f"/lessons/{lid}/end", token=token))
        en = show(f"6-2 GET /lessons/{lid} 看 end 后 status",
                  api.get(f"/lessons/{lid}", token=token), keep=400)
        ed = data_of(en)
        print(f"\n    >>> 状态机定性：建后={dd.get('status')}  start后见5-2  end后={ed.get('status') if ed else '?'}")
    finally:
        print("\n===== 侦察收尾：归档沙箱课 =====")
        try:
            show(f"F DELETE /courses/{cid} 归档沙箱课",
                 CourseApi().archive_course(token, cid), keep=200)
        except Exception as e:
            print(f"    !!! 归档失败，请手动归档 id={cid} name={course_name}: {e}")


if __name__ == "__main__":
    main()
