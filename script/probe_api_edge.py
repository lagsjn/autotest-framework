"""
接口数据驱动前置侦察：探测登录接口对"边界输入"的真实返回（2026-11-10）
- 为什么要侦察：数据驱动要把"每种输入 -> 预期返回"写进 YAML，
  预期必须来自实测，不能拍脑袋。UI 层空值是前端拦截、请求根本不发；
  接口层没有前端，空/超长/缺字段的请求会直打后端，返回码未知 -> 必须探
- 安全：只用"不存在账号 + 空值 + 缺字段"，绝不拿 demo_teacher 主账号试错（避开锁定红线）
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_api_edge.py"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.login_api import LoginApi


def run_case(api, tag, payload):
    """发一种边界输入，打印"实际返回"，供填 YAML 预期用
    payload 直接是请求体 dict（可能故意缺字段），用 request 而非 login() 以造缺字段场景
    """
    resp = api.post(LoginApi.LOGIN_PATH, json=payload)
    try:
        body = resp.json()
        code = body.get("code")
        msg = body.get("message")
    except ValueError:
        code = msg = "<返回体不是 JSON>"
    print(f"[{tag}] 请求体={payload}")
    print(f"    -> HTTP {resp.status_code} | code={code} | message={msg!r}\n")


def main():
    api = LoginApi()
    # 逐个场景：字段名沿用接口约定 username/password
    run_case(api, "空账号", {"username": "", "password": "x"})
    run_case(api, "空密码", {"username": "t_not_exist_9999", "password": ""})
    run_case(api, "都空", {"username": "", "password": ""})
    run_case(api, "缺password字段", {"username": "t_not_exist_9999"})
    run_case(api, "缺username字段", {"password": "x"})
    run_case(api, "空请求体", {})
    run_case(api, "不存在账号有值", {"username": "t_not_exist_9999", "password": "whatever"})
    print("侦察完毕：把上面每行的 HTTP状态码/code/message 抄进 data/api_login.yaml 当预期。")


if __name__ == "__main__":
    main()
