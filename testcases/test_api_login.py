"""
登录模块接口自动化用例
- 分层：本文件只写"发哪个接口 + 断言返回对不对"，怎么发请求交给 api/ 层
- 数据驱动：拒绝类场景的输入与预期外置 data/api_login.yaml，新增一条只加一行数据
- 绿级用例（默认跑）：正确登录、参数校验拒绝、不存在账号拒绝、带/无 token 查课程
- 红级用例（默认排除）：错误密码登录会累计锁定，打成 negative 且强制走废弃账号
"""
import allure
import pytest

from config import USERNAME, PASSWORD, HAS_RED, RED_USERNAME, RED_PASSWORD
from data import load_data


def _reject_params(section):
    """api_login.yaml 的一段 -> pytest.mark.parametrize 参数列表
    每行喂 4 个值：用例编号 + 请求体 + 预期HTTP码 + 预期业务码 + 预期文案关键词
    “一行数据 = 一条独立用例”就靠这个函数把 YAML 行翻译成 pytest 参数
    """
    return [
        pytest.param(d["case_id"], d["payload"],
                     d["expect_status"], d["expect_code"], d["expect_msg"],
                     id=d["case_id"])
        for d in load_data(section, "api_login.yaml")
    ]


# 参数校验拒绝数据（绿级：不碰真实账号、不会造成失败计数）
PARAM_INVALID_DATA = _reject_params("param_invalid")
# 身份验证拒绝数据（绿级：走不存在的幽灵账号）
AUTH_REJECT_DATA = _reject_params("auth_reject")


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
@allure.story("参数校验拒绝")
@pytest.mark.parametrize("case_id,payload,expect_status,expect_code,expect_msg", PARAM_INVALID_DATA)
def test_api_login_param_invalid(login_api, case_id, payload, expect_status, expect_code, expect_msg):
    """空值/缺字段/空请求体：请求本身不合法，服务端参数校验关拦下
    预期（400/40001）来自实测，全在 YAML 里；本函数只写一套通用断言逻辑
    “新增一种非法输入 = 只加一行 YAML”就是这个用例的价值
    """
    resp = login_api.send(payload)

    body = resp.json() if resp.text else {}
    # 三维度断言（数据驱动：预期值都从参数来，不写死）
    assert resp.status_code == expect_status, \
        f"[{case_id}] 请求体{payload} 应回 HTTP {expect_status}，实际 {resp.status_code}：{resp.text[:200]}"
    assert body.get("code") == expect_code, \
        f"[{case_id}] 业务码应为 {expect_code}，实际 {body.get('code')}"
    assert expect_msg in (body.get("message") or ""), \
        f"[{case_id}] message 应含{expect_msg!r}，实际 {body.get('message')!r}"
    # 参数不合法的请求绝不该吐 token
    assert not login_api.extract_token(body), f"[{case_id}] 参数校验都没过却发出了 token（鉴权混乱！）"


@allure.feature("登录模块-接口")
@allure.story("身份验证拒绝")
@pytest.mark.parametrize("case_id,payload,expect_status,expect_code,expect_msg", AUTH_REJECT_DATA)
def test_api_login_auth_reject(login_api, case_id, payload, expect_status, expect_code, expect_msg):
    """参数合法但账号查无此人：身份验证关拒绕（401/40104）
    安全：走 config 里的假账号 {not_exist}，失败记在幽灵账号头上，伤不到真人、不锁号，绿级
    这条与上一条拉开“400 vs 401”的分界：一个是请求不合法，一个是请求合法但身份不对
    """
    resp = login_api.send(payload)

    body = resp.json()
    assert resp.status_code == expect_status, \
        f"[{case_id}] 应回 HTTP {expect_status}，实际 {resp.status_code}：{resp.text[:200]}"
    assert body.get("code") == expect_code, \
        f"[{case_id}] 业务码应为 {expect_code}，实际 {body.get('code')}"
    assert expect_msg in (body.get("message") or ""), \
        f"[{case_id}] message 应含{expect_msg!r}，实际 {body.get('message')!r}"
    assert not login_api.extract_token(body), f"[{case_id}] 登录失败却还发得出 token（鉴权有漏洞！）"


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
