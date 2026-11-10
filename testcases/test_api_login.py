"""
登录模块接口自动化用例（第一批）
- 分层：本文件只写"发哪个接口 + 断言返回对不对"，怎么发请求交给 api/ 层
- 绿级用例（默认跑）：正确登录、带 token 查课程、无 token 被拒——都不触发账号失败计数
- 红级用例（默认排除）：错误密码登录会累计锁定，打成 negative 且强制走废弃账号，
  治理策略和 UI 层 test_login.py 完全一致（同一红线不能两头漏）
"""
import allure
import pytest

from config import USERNAME, PASSWORD, HAS_RED, RED_USERNAME, RED_PASSWORD


@allure.feature("登录模块-接口")
@allure.story("正常登录返回 token")
@pytest.mark.smoke
def test_api_login_success(login_api):
    """正确账号密码：HTTP 200 + 业务码 0 + data 里有可用 token"""
    resp = login_api.login(USERNAME, PASSWORD)

    # 多维度断言（E2E 断言规范）：状态码 + 业务码 + 关键字段，缺一不可
    assert resp.status_code == 200, f"登录应返回 200，实际 {resp.status_code}：{resp.text[:200]}"
    body = resp.json()
    assert body.get("code") == 0, f"业务码应为 0（成功），实际 {body.get('code')}：{body.get('message')}"

    token = login_api.extract_token(body)
    assert token, f"登录成功但 data.access_token 为空：{resp.text[:200]}"
    # token 是 JWT（三段点分字符串），能大致确认"拿到的是真票据不是一串废话"
    assert token.count(".") == 2, f"access_token 不像 JWT 格式：{token[:40]}"
    # 顺带核对返回的用户身份就是登录的那个账号
    assert body["data"]["user"]["username"] == USERNAME, \
        f"返回的用户不是 {USERNAME}：{body['data']['user'].get('username')}"


@allure.feature("登录模块-接口")
@allure.story("错误账号被拒绝")
def test_api_login_not_exist_user(login_api):
    """不存在的账号：HTTP 401 + 业务码 40104（实测）
    安全：走 config 里的假账号 NOT_EXIST 思路——用一个不存在的名，绝不碰真实账号，
    不会累计任何真人账号的失败次数，所以是绿级
    """
    resp = login_api.login("t_not_exist_9999", "whatever_000")

    assert resp.status_code == 401, f"不存在账号应返回 401，实际 {resp.status_code}"
    body = resp.json()
    assert body.get("code") == 40104, f"业务码应为 40104（账号或密码错误），实际 {body.get('code')}"
    assert not login_api.extract_token(body), "登录失败了却还发得出 token（鉴权有漏洞！）"


@allure.feature("登录模块-接口")
@allure.story("带 token 能查课程列表")
@pytest.mark.smoke
def test_api_courses_with_token(course_api, api_token):
    """接口自动化最典型的链路：登录取 token（fixture 已备好）-> 鉴权头 -> 业务接口
    断言只读列表拿到 200 + 业务码 0 + items 是列表，不改动任何数据
    """
    resp = course_api.list_courses(token=api_token)

    assert resp.status_code == 200, f"带 token 查课程应 200，实际 {resp.status_code}：{resp.text[:200]}"
    body = resp.json()
    assert body.get("code") == 0, f"业务码应为 0，实际 {body.get('code')}"
    items = body.get("data", {}).get("items")
    assert isinstance(items, list), f"data.items 应是列表，实际类型 {type(items)}：{resp.text[:200]}"


@allure.feature("登录模块-接口")
@allure.story("无 token 访问被拒")
def test_api_courses_without_token_denied(course_api):
    """安全回归：不带 Authorization 头直接查课程，服务端应拒绝（401）
    这条专门守"鉴权是否真的生效"——数据没被读走之前，先证明门是锁着的。
    不触发账号失败计数（压根没走登录），绿级
    """
    resp = course_api.list_courses(token=None)  # BaseApi 见 token 为空就不塞鉴权头

    assert resp.status_code == 401, \
        f"无 token 访问课程列表本应被拒（401），实际 {resp.status_code}——接口没做鉴权，越权风险！"


@allure.feature("登录模块-接口")
@allure.story("错误密码被拒绝")
@pytest.mark.negative
@pytest.mark.skipif(not HAS_RED, reason=".env 未配置 TEST_RED_*（废弃账号），negative 用例跳过：防止锁主账号")
def test_api_login_wrong_password_negative(login_api):
    """错误密码：HTTP 401 + 业务码 40104
    ⚠ 有副作用：真实账号密码错误会计入登录失败次数（够 5 次锁号），
    所以强制走废弃账号（RED_*），且默认被 -m 'not negative' 排除
    跑法：python -m pytest -m negative
    """
    resp = login_api.login(RED_USERNAME, RED_PASSWORD + "_wrong")

    assert resp.status_code == 401, f"错误密码应返回 401，实际 {resp.status_code}"
    body = resp.json()
    assert body.get("code") == 40104, f"业务码应为 40104，实际 {body.get('code')}"
    assert not login_api.extract_token(body), "密码错了还发得出 token（鉴权有漏洞！）"


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
