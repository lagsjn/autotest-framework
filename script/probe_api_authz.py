"""
越权矩阵前置侦察：摸清"不同身份 token × 不同端接口"的真实鉴权返回（2026-11-10）
- 目的：写越权用例前，必须先知道系统到底怎么做角色校验——
  学生 token 调老师接口是回 401 还是 403？伪造 token 呢？不能假设，要测出来
- 铁律：全程只读！GET 请求不改数据；绝不用低权限 token 去 POST 建课
  （万一没被拒就会凭空造出课程污染环境），写类越权留到读类结论清楚后再单独设计
- 身份来源：老师 demo_teacher(8081) / 学生 demo_student(8082)；成功登录不计失败次数，安全
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_api_authz.py"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import base64
import json

from config import (BASE_URL, STUDENT_BASE_URL, USERNAME, PASSWORD,
                    STUDENT_USERNAME, STUDENT_PASSWORD, HAS_STUDENT)
from api.login_api import LoginApi
from api.course_api import CourseApi


def jwt_role(token):
    """JWT 中间段是 base64 的 payload，解出来能看到 role（老师/学生身份写在票据里）"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # base64 补齐
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data.get("role"), data.get("username")
    except Exception as e:
        return f"<解析失败:{e}>", None


def probe(tag, api, path, token, params=None):
    """发一次只读 GET，打印身份+URL+返回码，供填越权用例预期"""
    resp = api.get(path, token=token, params=params or {})
    body = {}
    try:
        body = resp.json()
    except ValueError:
        pass
    who = jwt_role(token)[0] if token else "无token"
    print(f"[{tag}] 身份={who:<8} {resp.request.method} {resp.url}")
    print(f"    -> HTTP {resp.status_code} | code={body.get('code')} | msg={body.get('message')!r}\n")


def main():
    teacher = LoginApi(base_url=BASE_URL)          # 老师端 8081
    teacher_token = teacher.login_and_get_token(USERNAME, PASSWORD)
    print(f"老师 token 身份：{jwt_role(teacher_token)}\n")

    courses = CourseApi(base_url=BASE_URL)
    probe("老师token→老师/courses", courses, "/courses", teacher_token)

    # 伪造 token：把真 token 末尾改乱，模拟"客户端瞎编票据"
    forged = teacher_token[:-6] + "XXXXXX"
    probe("伪造token→老师/courses", courses, "/courses", forged)

    # 无 token（已知应 401，这里再采一次坐实矩阵完整性）
    probe("无token→老师/courses", courses, "/courses", None)

    if not HAS_STUDENT:
        print("\n未配置学生端（.env 缺 TEST_STUDENT_*），跳过垂直越权侦察。")
        return

    stu = LoginApi(base_url=STUDENT_BASE_URL)       # 学生端 8082 登录拿学生 token
    stu_token = stu.login_and_get_token(STUDENT_USERNAME, STUDENT_PASSWORD)
    print(f"学生 token 身份：{jwt_role(stu_token)}\n")

    # 垂直越权（只读探测）：学生 token 去调老师端(8081)的 /courses
    probe("学生token→老师端(8081)/courses", CourseApi(base_url=BASE_URL), "/courses", stu_token)
    # 反向：学生 token 调自己端(8082)的 /courses，作为"合法访问"对照组
    probe("学生token→学生端(8082)/courses", CourseApi(base_url=STUDENT_BASE_URL), "/courses", stu_token)
    # 反向越权：老师 token 调学生端(8082)的 /courses
    probe("老师token→学生端(8082)/courses", CourseApi(base_url=STUDENT_BASE_URL), "/courses", teacher_token)

    print("\n侦察完毕：把上面 HTTP/code 抄成越权用例预期（读类，安全）。")


if __name__ == "__main__":
    main()
