r"""
课堂状态侦察（只读）：演示课"大数据技术与原理"底下到底有没有"上课中"的课堂 —— 2026-11-11
- 触发背景：全量回归 15 条 UI 用例集体失败，报错都是"点课程卡片后没跳到 /courses/{id}，
  停在 /lessons/100"。要判这两类原因里到底是哪一个：
    ① 我们的代码改坏了（api/ + conftest + pytest.ini 本轮确实动过公共模块）；
    ② 被测系统的业务状态变了（那门演示课现在有一堂活跃的课，点卡片直接被带进课堂）。
- 手段：纯 GET 读接口，把课程 id、课堂列表与每堂课的 status 抄出来对比，不改任何数据。
  绝不 POST /lessons/{id}/start 之类——那才是真去干扰课堂。
- 运行：& ".venv\Scripts\python.exe" "script\probe_api_lesson_state.py"
"""
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, USERNAME, PASSWORD, COURSE_NAME
from api.base_api import BaseApi
from api.login_api import LoginApi

C = "/courses"


def items_of(resp):
    """取 items，带类型防御（data 在校验错误分支下是 list，直接 .get 会崩）"""
    data = (resp.json() or {}).get("data") if resp.text else None
    if not isinstance(data, dict):
        print(f"    [注意] data 不是 dict，类型={type(data).__name__}：{str(data)[:200]}")
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def main():
    api = BaseApi(BASE_URL)
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)

    # 1. 演示课本身的 id 与状态（UI 用例就是靠课程名锁定这张卡片的）
    courses = items_of(api.get(C, token=token, params={"page": 1, "page_size": 100}))
    demo = [c for c in courses if c.get("name") == COURSE_NAME]
    print(f"课程总数={len(courses)}  匹配【{COURSE_NAME}】={len(demo)} 门")
    for c in demo:
        print(f"  id={c['id']}  status={c.get('status')}  invite={c.get('invite_code')}")

    for c in demo:
        cid = c["id"]
        # 2. 这门课的课堂列表：看有没有 status 是"上课中"的（UI 点卡片被带进 /lessons/100 的来源）
        lessons = items_of(api.get(f"{C}/{cid}/lessons", token=token,
                                   params={"page": 1, "page_size": 30}))
        print(f"\n课程 id={cid} 共 {len(lessons)} 个课堂")
        for l in lessons[:30]:
            print(f"  lesson id={l.get('id')} 第{l.get('lesson_no', l.get('no', '?'))}讲 "
                  f"status={l.get('status')!r} 标题={str(l.get('title'))[:24]!r}")
        active = [l for l in lessons if (l.get("status") or "") not in ("ended", "finished", "draft")]
        print(f"  非已结束/非草稿的课堂：{[(l.get('id'), l.get('status')) for l in active]}")

        # 3. 成员数：顺带确认这张卡片上有没有"正在上课"横幅所需的数据
        mem = api.get(f"{C}/{cid}/members", token=token, params={"page": 1, "page_size": 1})
        md = (mem.json() or {}).get("data") or {}
        print(f"  成员 total={md.get('total') if isinstance(md, dict) else '?'}")

    # 4. 单个课堂详情：/lessons/100 就是 UI 卡住时停住的那个地址，看它归属哪门课、什么状态
    r = api.get("/lessons/100", token=token)
    print(f"\nGET /lessons/100 -> HTTP {r.status_code}")
    d = (r.json() or {}).get("data") if r.status_code == 200 else None
    print("  " + json.dumps(d, ensure_ascii=False)[:500] if d else "  <无 data>")


if __name__ == "__main__":
    main()
