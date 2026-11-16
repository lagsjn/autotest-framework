r"""
上课流程·flow 读接口侦察（只读，零副作用）：2026-11-15
背景：被测系统新增"添加上课流程"功能，大屏(/lessons/{id}/live)播的就是这个 flow
      （一节课的播放步骤清单）。接口地图靠静态扒包知道有 GET/PUT/DELETE /lessons/{id}/flow，
      但 flow 的返回结构（步骤怎么组织、字段叫什么）静态猜不准 → 必须动态实测一手。
纪律（这次只做只读，绝不写）：
  - 只 GET，不发任何 PUT/POST/DELETE。
  - 拿"已下课的演示讲次"当样本（数据稳定、不会有人在上课），不碰正在进行的课堂。
  - 顺带对比：draft 讲次（我们自建沙箱）的 flow 长啥样——但本脚本不创建，只读现有的。
运行：& ".venv\Scripts\python.exe" "script\probe_api_flow.py"
"""
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, USERNAME, PASSWORD, COURSE_NAME
from api.base_api import BaseApi
from api.login_api import LoginApi
from api.course_api import CourseApi
from api.lesson_api import LessonApi


def show(tag, resp, keep=1200):
    print(f"\n### {tag}")
    print(f"    -> HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        print(f"    [非 JSON，前200] {resp.text[:200]}")
        return None
    print("    " + json.dumps(body, ensure_ascii=False, indent=2)[:keep].replace("\n", "\n    "))
    return body


def items_of(body):
    data = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return []
    it = data.get("items")
    return it if isinstance(it, list) else []


def main():
    api = BaseApi(BASE_URL)
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    print(f"老师 token 已取得（{token[:12]}...）")

    # 1. 定位演示课 id（config.COURSE_NAME 就是 UI 用例锁的那门）
    courses = CourseApi().list_courses(token)
    hit = [c for c in items_of(courses.json()) if c.get("name") == COURSE_NAME]
    if not hit:
        print(f"未找到演示课【{COURSE_NAME}】，无法取样")
        return
    cid = hit[0]["id"]
    print(f"演示课【{COURSE_NAME}】id={cid}")

    # 2. 取该课的讲次，按状态分类，优先拿 ended 的当只读样本
    lessons = items_of(LessonApi().list_lessons(token, cid).json())
    by_status = {}
    for l in lessons:
        by_status.setdefault(l.get("status"), []).append(l)
    print(f"讲次状态分布：{{{', '.join(f'{k}:{len(v)}' for k, v in by_status.items())}}}")

    # 3. 对 ended / draft / ongoing 各取一个样本，只读 GET /lessons/{id}/flow 对比结构
    samples = []
    for st in ("ended", "draft", "ongoing"):
        if by_status.get(st):
            samples.append((st, by_status[st][0]["id"]))

    for st, lid in samples:
        show(f"[{st}] GET /lessons/{lid}/flow", api.get(f"/lessons/{lid}/flow", token=token))
        # flow 顶层结构看一眼：是 list 还是 dict？步骤项里有哪些字段？
        body = api.get(f"/lessons/{lid}/flow", token=token).json()
        data = (body or {}).get("data")
        if isinstance(data, list) and data:
            print(f"    -> data 是 list，首项字段名：{sorted(data[0].keys()) if isinstance(data[0], dict) else type(data[0]).__name__}")
        elif isinstance(data, dict):
            print(f"    -> data 是 dict，字段名：{sorted(data.keys())}")
            # 有的实现把步骤塞在 dict 的某个 list 字段里
            for k, v in data.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    print(f"       dict.{k} 是 list，首项字段：{sorted(v[0].keys())}")


if __name__ == "__main__":
    main()
