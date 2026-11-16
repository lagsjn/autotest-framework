r"""
UI 回归前置检查（preflight，只读）：现在跑 UI 用例环境状态对不对？—— 2026-11-14
- 为什么需要这个脚本：L2/L3/L4 这 15 条 UI 用例的动作会点进"当前讲次"页和课堂控制台。
  环境事实（2026-11-15 二次纠正）：demo_teacher 是纯测试老师号，上下课都是自己的测试操作，
  不存在"干扰真实课堂"的问题。演示课若残留一节 ongoing 讲次（往往是手动/用例开课后忘了下），
  点课程卡片的落点会随之变化——但实测（104 ongoing 时 15 条 UI 仍全绿）证明 L2/L3/L4 页面对象
  早已靠面包屑回位（enter_course() 用 back_to_course_btn）把落点差异消化掉了，**不会集体红**。
  所以本脚本只是"环境是否贴近真实"的提醒，不是硬阻断；跑前看一眼心里有数即可。
  （旧的"有 ongoing 则卡片落当前讲次页→L2/L3/L4 集体红"是早期未适配时的推断，已被实测推翻，
   且卡片落点也非简单"ongoing 优先"——104 ongoing 时卡片实际落在已下课的上一讲，具体路由规则待复核。）
- 手段：纯 GET 读接口，拿 config 里 UI 用例锁定的那门演示课（COURSE_NAME）的课堂列表，
  看有没有 status='ongoing' 的讲次。不发任何写请求，不点任何按钮。
- 判读：
    GO     = 该课无 ongoing 课堂 → UI 回归可以直接跑
    NO-GO  = 有 ongoing 课堂     → 先把这节残留讲次处理掉（界面上结束该讲）再跑 UI；
             或者等 L2/L3/L4 锚点适配完成后无视（断言兼容两种落点）
- 运行：& ".venv\Scripts\python.exe" "script\preflight_ui.py"
  退出码：GO=0 / NO-GO=1（这样以后 CI 或批处理能直接 `if ($LASTEXITCODE -ne 0) { ... }` 卡住）
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, USERNAME, PASSWORD, COURSE_NAME
from api.base_api import BaseApi
from api.course_api import CourseApi
from api.login_api import LoginApi


def items_of(resp):
    """取分页 items，带类型防御（同一字段在校验错误分支下是 list，不是 dict）"""
    data = (resp.json() or {}).get("data") if resp.text else None
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def main():
    token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    courses = CourseApi(BASE_URL)

    # UI 用例是靠课程名锁定卡片的（config.COURSE_NAME），所以前置检查也只盯这门课
    hit = [c for c in items_of(courses.list_courses(token)) if c.get("name") == COURSE_NAME]
    if not hit:
        print(f"NO-GO：找不到 UI 用例锁定的课程【{COURSE_NAME}】——环境里这门课没了或被改名，"
              f"先人工确认再跑（界面/数据正在开发修改中，这种情况也算预期内变更）")
        return 1

    course = hit[0]
    if course.get("status") == "archived":
        print(f"NO-GO：课程【{COURSE_NAME}】(id={course['id']}) 已归档，"
              f"归档后不可排课授课，UI 主干用例（进入详情页/工作台）必然失败")
        return 1

    lessons = items_of(courses.get(f"/courses/{course['id']}/lessons", token=token,
                                   params={"page": 1, "page_size": 30}))
    ongoing = [l for l in lessons if l.get("status") == "ongoing"]

    # 状态分布打出来：顺带能看出"点卡片会落到哪"（当前讲次=ongoing 优先，没有则是最近一期）
    dist = {}
    for l in lessons:
        dist[l.get("status")] = dist.get(l.get("status"), 0) + 1
    print(f"课程【{COURSE_NAME}】id={course['id']} 共 {len(lessons)} 个讲次，状态分布={dist}")

    if ongoing:
        o = ongoing[0]
        print(f"\n*** 提示：第 {o.get('seq')} 讲 (lesson id={o['id']}, {o.get('slot_label')}) 处于 ongoing 状态 ***")
        print("    这是残留的测试课堂（demo_teacher 是纯测试号，上下课都是自己的测试操作）。")
        print("    实测 L2/L3/L4 已适配落点，有这节残留一般不会集体红；但仍建议下掉，让环境贴近真实。")
        # 别用 emoji：Windows 控制台默认 GBK 码页，emoji 会打成乱码，判读命令的输出要保证人人看得清
        print("    处置：去界面上把这一讲下课，重跑本脚本确认 GO；不想动也可直接跑 UI（页面对象会消化落点）。")
        return 1

    print("GO：该课没有 ongoing 讲次，UI 回归可以直接跑。")
    print("     注意：negative / l5 / api_e2e 三组写操作标签仍按默认排除，需要时显式 -m 才跑。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
