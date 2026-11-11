"""
越权矩阵侦察·第2步：对比"数据边界"而非只看状态码（2026-11-10）
- 上一步 probe_api_authz.py 发现学生 token 调 GET /courses 返回 200，
  但 200 不等于越权：得看返回的课程是不是"各自相关范围"、有没有串数据
- 这一步把老师/学生各自看到的课程 (id / 名字 / teacher_id / 邀请码) 打出来对比：
  · 若学生看到的是"自己加入的课"（与老师教的课基本不重叠或只含已加入的）→ 数据隔离 OK
  · 若学生能看到"自己根本没加入的别人的课"→ 水平/垂直越权，值得报缺陷
- 全程只读
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_api_authz2.py"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, STUDENT_BASE_URL, USERNAME, PASSWORD,
                    STUDENT_USERNAME, STUDENT_PASSWORD, HAS_STUDENT)
from api.login_api import LoginApi
from api.course_api import CourseApi


def dump_courses(label, token, base):
    """拿某身份在某端的课程列表，打印规模 + 前几门明细，便于对比数据边界"""
    resp = CourseApi(base_url=base).get("/courses", token=token, params={"page": 1, "page_size": 100})
    body = resp.json()
    items = (body.get("data") or {}).get("items") or []
    print(f"\n[{label}] HTTP {resp.status_code} | 共 {len(items)} 门课")
    for c in items[:8]:
        print(f"    id={c.get('id'):<4} teacher_id={c.get('teacher_id')} "
              f"invite={c.get('invite_code')} name={c.get('name')!r}")
    return {c.get("id") for c in items}


def main():
    t_token = LoginApi(base_url=BASE_URL).login_and_get_token(USERNAME, PASSWORD)
    teacher_ids = dump_courses("老师 token → 8081", t_token, BASE_URL)

    if not HAS_STUDENT:
        print("\n未配置学生端，跳过数据边界对比。")
        return
    s_token = LoginApi(base_url=STUDENT_BASE_URL).login_and_get_token(STUDENT_USERNAME, STUDENT_PASSWORD)
    stu_on_teacher = dump_courses("学生 token → 8081(老师端)", s_token, BASE_URL)
    stu_on_stu = dump_courses("学生 token → 8082(学生端)", s_token, STUDENT_BASE_URL)

    print("\n" + "=" * 50)
    print("数据边界对比：")
    print(f"  老师可见课程 id 集合：{sorted(teacher_ids)}")
    print(f"  学生在老师端可见课程 id：{sorted(stu_on_teacher)}")
    print(f"  学生在学生端可见课程 id：{sorted(stu_on_stu)}")
    leak = stu_on_teacher - stu_on_stu  # 学生在老师端看到、但学生端不该给的课=可疑越界
    print(f"  学生在老师端比学生端'多看到'的课(可疑越界)：{sorted(leak)}")
    print("判读：若上面差集非空，说明学生 token 在老师端读到了学生端不给的课=越权，值得报；"
          "若两端返回完全一致，则 /courses 对同一身份返回相同数据、无越权，只是鉴权按'登录'不'按角色'。")


if __name__ == "__main__":
    main()
