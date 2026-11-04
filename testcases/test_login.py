import allure
import pytest

from config import USERNAME, PASSWORD, HAS_RED
from data import load_data
from pages.login_page import LoginPage


# ============ 参数化数据：全部外置到 data/login.yaml（数据驱动） ============
# 只有数据变了 -> 改 yaml；只有跑法逻辑变了 -> 改这里，两者互不干扰
def _params(section, marks=()):
    """yaml 的一段 -> pytest.mark.parametrize 的参数列表
    每条数据带 3 样：输入(username,password) + 预期(expect)
    expect 用 get 兜底：space_trim 这类不校验文案的组可以不写
    """
    if not isinstance(marks, (list, tuple)):
        marks = [marks]  # 传进来一个光杆标签？包成列表再往下走
    return [
        pytest.param(d["username"], d["password"], d.get("expect", ""),
                     id=d["case_id"], marks=list(marks))
        for d in load_data(section)
    ]



# A. 前端校验类：空值被前端拦下，不发请求、不计失败次数，可放心反复跑
FRONT_VALIDATE_DATA = _params("front_validate")
# B. 后端拒绝类：真实发请求、计入失败次数，够 5 次锁账号 → negative，默认不跑
BACKEND_REJECT_DATA = _params("backend_reject", marks=pytest.mark.negative)
# C1. 前后空格：实测系统 trim → 登录成功，无副作用
SPACE_TRIM_DATA = _params("space_trim")
# C2. 中间空格：不 trim → 登录失败并计失败次数 → negative
SPACE_REJECT_DATA = _params("space_reject", marks=pytest.mark.negative)

@allure.feature("登录模块")
@allure.story("正常登录")
def test_login_success(driver):
    """正向用例：正确的账号密码，应该能进入系统
    注意：账号被锁定期间这条也会失败，跑之前确认账号状态
    """
    login = LoginPage(driver)
    login.login(USERNAME, PASSWORD)

    # assert 条件, "失败时要打印的话"
    # 【重点】逗号后面那句一定要写：以后晚上跑回归挂了几十条，
    # 全靠这句话一眼看出是哪一步、哪个预期没满足
    assert login.is_login_success(), "登录失败：点击登录后登录页表单没有消失（账号被锁或密码被拒）"

@allure.feature("登录模块")
@allure.story("空值前端校验")
@pytest.mark.parametrize("username,password,expect", FRONT_VALIDATE_DATA)
def test_login_front_validate(driver, username, password, expect):
    """LOGIN-F-002 系列：空值提交，前端应拦下并给出预期提示"""
    login = LoginPage(driver)
    login.start_watch_toast()  # 【顺序关键】先埋监听，再触发点击
    login.login(username, password)

    # 反向用例用短等待：明知不该成功，等 3 秒就够，不必等满 10 秒
    assert not login.is_login_success(timeout=3), "空值输入竟然登录成功了（前端校验形同虚设！）"

    msgs = login.wait_toast_texts(timeout=5)
    assert msgs, "输入被拦下了但系统没有任何提示（用户不知道少了什么）"
    # 预期跟着数据走：每条数据自己的 expect 关键词必须出现在某条提示里
    assert any(expect in m for m in msgs), f"提示里没出现预期关键词{expect!r}：{msgs}"


@allure.feature("登录模块")
@allure.story("后端拒绝非法账号密码")
@pytest.mark.negative
@pytest.mark.skipif(not HAS_RED, reason=".env 未配置 TEST_RED_*（废弃账号），negative 用例跳过：防止锁主账号")
@pytest.mark.parametrize("username,password,expect", BACKEND_REJECT_DATA)
def test_login_backend_reject(driver, username, password, expect):
    """LOGIN-F-003/005 系列：账号或密码不对，后端应拒绝
    ⚠ 有副作用：计入登录失败次数——数据已指向废弃账号（demo_deprecated），主账号不沾
    跑法：python -m pytest -m negative
    """
    login = LoginPage(driver)
    login.start_watch_toast()
    login.login(username, password)

    assert not login.is_login_success(timeout=3), f"账号={username!r} 竟然登录成功，后端校验有漏洞"

    msgs = login.wait_toast_texts(timeout=5)
    assert msgs, "登录被拒绝却没有任何提示（用户会以为页面卡住了）"
    # 预期文案由数据驱动（expect 字段）：不同失败分支文案不同——
    # 密码错误/账号不存在 → "账号或密码错误"；全空格 → 走长度校验分支"长度不足"。
    # 此前断言写死文案，与数据文件构成两个事实源，解冻首日就自相矛盾（2026-11-04 复盘）
    assert any(expect in m for m in msgs), f"提示里没出现预期关键词{expect!r}：{msgs}"

@allure.feature("登录模块")
@allure.story("账号前后空格应被trim")
@pytest.mark.parametrize("username,password,expect", SPACE_TRIM_DATA)
def test_login_username_space_trimmed(driver, username, password, expect):
    """LOGIN-F-004 系列：账号前后带空格，系统应 trim 后正常登录（实测已确认的行为）
    登录成功不会产生失败计数，无副作用
    """
    login = LoginPage(driver)
    login.login(username, password)

    # 预期是"能登录成功"，断言就必须写成功；写成"必须有提示"就把用例判反了
    assert login.is_login_success(), f"账号 {username!r} 没被 trim，登录失败了（行为回归或系统改了实现）"

@allure.feature("登录模块")
@allure.story("账号中间空格应被拒绝")
@pytest.mark.negative
@pytest.mark.skipif(not HAS_RED, reason=".env 未配置 TEST_RED_*（废弃账号），negative 用例跳过：防止锁主账号")
@pytest.mark.parametrize("username,password,expect", SPACE_REJECT_DATA)
def test_login_username_space_rejected(driver, username, password, expect):
    """LOGIN-F-004 系列：账号中间带空格，系统不 trim，应登录失败并给统一提示
    ⚠ 有副作用：计入登录失败次数，数据已指向废弃账号
    """
    login = LoginPage(driver)
    login.start_watch_toast()
    login.login(username, password)

    assert not login.is_login_success(timeout=3), f"账号 {username!r} 中间空格竟然登录成功，后端匹配逻辑有问题"

    msgs = login.wait_toast_texts(timeout=5)
    assert msgs, "登录被拒绝却没有任何提示（用户会以为页面卡住了）"
    assert any(expect in m for m in msgs), f"提示里没出现预期关键词{expect!r}：{msgs}"

@allure.feature("登录模块")
@allure.story("密码明文切换交互")
def test_login_password_eye_toggle(driver):
    """LOGIN-I-002：点密码框右侧图标，密文/明文可切换
    这条不提交登录，不会消耗失败次数，也不依赖账号对不对，所以最安全
    """
    login = LoginPage(driver)
    login.input_text(login.password_input, PASSWORD)

    # 预期1：刚进页面是密文
    assert login.get_password_type() == "password", "初始应为密文，实际不是 password"

    # 预期2：点一下变明文
    login.click_eye()
    assert login.get_password_type() == "text", "点小眼睛后应变成明文 text"

    # 预期3：再点一下回密文（把开关测完整，只测一个方向等于只测了一半）
    login.click_eye()
    assert login.get_password_type() == "password", "再次点击应回到密文 password"


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])