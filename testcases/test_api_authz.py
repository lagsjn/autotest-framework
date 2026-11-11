"""
接口鉴权 / 越权矩阵用例（安全测试）
预期全部来自实测侦察 script/probe_api_authz.py 与 probe_api_authz2.py（2026-11-10）：
  - 无 token        -> 401 / code 40101 "未登录或缺少凭证"
  - 伪造(篡改)token -> 401 / code 40103 "凭证无效"（服务器真校验 JWT 签名）
  - 学生 token 调 /courses -> 200，但返回的是学生自己的选课范围，
    看不到老师的私有课（数据隔离 OK，非越权）
判读原则：越权看"返回数据有没有越过身份边界"，不能只看 HTTP 码
"""
import allure
import pytest

from config import HAS_STUDENT


@allure.feature("接口安全-鉴权矩阵")
@allure.story("伪造 token 被拒")
def test_api_forged_token_denied(course_api, api_token):
    """把真 token 末尾改乱再发：签名对不上，服务器应识别为"凭证无效"(401/40103)
    这条守的是"系统不会只认 token 存在与否、而是真的验签"——防伪造票据越权
    """
    forged = api_token[:-6] + "XXXXXX"  # 篡改签名片段，构造一张"长得像但无效"的票据
    resp = course_api.list_courses(token=forged)

    assert resp.status_code == 401, f"伪造 token 应被拒(401)，实际 {resp.status_code}——可能没验签，伪造可通行！"
    body = resp.json()
    assert body.get("code") == 40103, f"业务码应为 40103(凭证无效)，实际 {body.get('code')}"


@allure.feature("接口安全-鉴权矩阵")
@allure.story("缺失 token 被拒")
def test_api_missing_token_denied(course_api):
    """完全不带 Authorization 头：应 401 且业务码 40101(未登录/缺凭证)
    与"伪造"(40103)区分开——缺凭证 vs 凭证无效，是两个不同的拒绝原因码
    """
    resp = course_api.list_courses(token=None)

    assert resp.status_code == 401, f"无 token 应被拒(401)，实际 {resp.status_code}"
    body = resp.json()
    assert body.get("code") == 40101, f"业务码应为 40101(未登录或缺少凭证)，实际 {body.get('code')}"


@allure.feature("接口安全-越权矩阵")
@allure.story("学生 token 读不到老师私有课")
@pytest.mark.skipif(not HAS_STUDENT, reason=".env 未配置 TEST_STUDENT_*（学生端），越权数据隔离用例跳过")
def test_api_student_courses_data_isolation(course_api, api_token, api_student_token):
    """垂直越权判读（数据边界，非状态码）：
    学生 token 调 GET /courses 会返回 200（该接口按身份给数据，不按角色拦），
    但返回的必须是"学生自己的选课范围"——老师自己的私有课（如老师自建、学生未加入的课）不能出现在学生列表里。
    正确判据：存在"老师可见、学生不可见"的课 -> 老师没把自己的完整视图泄给学生。
    （注：不能反过来断言"学生看到的必须是老师看到的子集"——学生合法加入了其他老师的课，
    那些课本就不在 demo_teacher 视图里，与隔离无关；这是一个错误的隔离模型，实测把它纠了出来）
    """
    t_body = course_api.list_courses(token=api_token).json()
    s_body = course_api.list_courses(token=api_student_token).json()

    t_ids = {c["id"] for c in (t_body.get("data") or {}).get("items", [])}
    s_ids = {c["id"] for c in (s_body.get("data") or {}).get("items", [])}

    assert t_ids, "前置异常：老师端课程列表为空，无法对比数据边界"
    # 核心隔离断言：老师应有学生看不到的私有课（否则就是泄了老师全集给学生）
    private = t_ids - s_ids
    assert private, (
        f"学生可见集合包含了老师可见全集(学生={sorted(s_ids)} 老师={sorted(t_ids)})，"
        "怀疑 /courses 未按身份隔离——学生越权看到老师私有课"
    )


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
