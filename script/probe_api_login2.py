"""
接口自动化侦察脚本第2步：脱离浏览器，直接用 requests 直发登录接口（2026-11-08）
- 目的：登录接口地址/请求体已在 probe_api_login.py 确认（POST /api/v1/auth/login），
  但性能日志只记录"发出去的请求"，不含"返回的内容"——
  token 在哪个字段、错误密码返回什么码，都要靠这次直发确认
- 意义：这一次请求成功 = 接口自动化路线正式打通（浏览器只是幌子，服务器才是正主）
- 铁律：只发 1 次正确登录 + 1 次错误登录（错误密码用 WRONG_PASSWORD，
  不存在账号才踩锁定红线，密码错不锁号——与 UI 负向用例同一结论）
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_api_login2.py"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import urllib3

from config import BASE_URL, USERNAME, PASSWORD, WRONG_PASSWORD

# 被测系统是自签 HTTPS 证书（浏览器强退出来的），这里关掉"未校验证书"的告警噪音
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def show(tag, resp):
    """把一次 HTTP 往返的关键信息打全：状态码 + 返回体结构"""
    print(f"\n{'='*60}\n[{tag}]\n{'='*60}")
    print(f"HTTP 状态码: {resp.status_code}")
    try:
        data = resp.json()  # 按 JSON 解析返回体；解析失败说明返回的不是 JSON
    except ValueError:
        print("返回体不是 JSON，前 300 字符：", resp.text[:300])
        return None
    print("返回体 JSON：")
    import json
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
    return data


def main():
    login_url = f"{BASE_URL}/api/v1/auth/login"
    print("接口地址：", login_url)

    # ① 正确账号密码：看返回结构，找 token 住哪个字段
    resp = requests.post(
        login_url,
        json={"username": USERNAME, "password": PASSWORD},
        verify=False,   # 自签证书，跳过校验（仅测试环境适用！生产严禁）
        timeout=10,
    )
    data = show("正确登录", resp)

    # ② 错误密码：看失败时服务器怎么表达（状态码？业务码？message 文案？
    #    这决定接口层负向用例断言什么）
    resp2 = requests.post(
        login_url,
        json={"username": USERNAME, "password": WRONG_PASSWORD},
        verify=False,
        timeout=10,
    )
    show("错误密码登录", resp2)

    # ③ 如果 ① 拿到了 token，试一发"带 token 访问课程列表"——
    #    这就是接口自动化最典型的链路：登录取 token -> 鉴权头 -> 业务接口
    if isinstance(data, dict):
        token = _find_token(data)
        if token:
            print(f"\n找到 token（字段路径见上），试访问课程列表：")
            resp3 = requests.get(
                f"{BASE_URL}/api/v1/courses",
                params={"page": 1, "page_size": 100},
                headers={"Authorization": f"Bearer {token}"},
                verify=False,
                timeout=10,
            )
            show("带 token 查课程列表", resp3)
        else:
            print("\n返回体里没找到明显 token 字段，等贴结构人工判")


def _find_token(data):
    """在嵌套 dict 里广度找 token 类字段（token / access_token / accessToken）"""
    queue = [data]
    while queue:
        node = queue.pop(0)
        if isinstance(node, dict):
            for k, v in node.items():
                if k.lower() in ("token", "access_token", "accesstoken", "authorization") \
                        and isinstance(v, str) and len(v) > 20:
                    print(f"  token 所在字段名: {k}")
                    return v
                if isinstance(v, (dict, list)):
                    queue.append(v)
        elif isinstance(node, list):
            queue.extend(x for x in node if isinstance(x, (dict, list)))
    return None


if __name__ == "__main__":
    main()
