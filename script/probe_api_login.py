"""
接口自动化前置侦察脚本：登录接口 + 登录后 API 流量抓取（2026-11-08）
- 目的：UI 点"登录"按钮后，背后其实是一个 HTTP 请求（POST /xxx/login）。
  接口自动化要先知道：接口地址、请求方法、请求体字段名、返回体结构（token 在哪个字段）
- 原理：Edge 开启 enable-logging + "Log"=2（DevTools 协议的性能日志），
  driver.performance_logs 里会记录浏览器发出的每个网络请求（Network.requestWillBeSent 事件），
  从中筛出 API 请求，把 method/url/postData 打出来——不用手动 F12 抓包
- 铁律：只"看"不"点"——登录之后的所有 API 只登记清单，不发任何写操作请求
- 运行：& ".venv\\Scripts\\python.exe" "script\\probe_api_login.py"
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.edge.options import Options

from config import LOGIN_URL, USERNAME, PASSWORD
from pages.login_page import LoginPage


def collect_api_logs(driver, since_idx):
    """
    从性能日志里提炼 API 请求清单
    - 性能日志是一条条 DevTools 事件，type=Network 的才是网络请求
    - requestWillBeSent = "浏览器正要发请求"，含 method/url/requestPostData（请求体原文）
    - 返回值：(请求列表, 新日志游标)，游标用于增量采集不重复
    """
    logs = driver.get_log("performance")
    seen = []
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
        except (KeyError, json.JSONDecodeError):
            continue
        if msg.get("method") != "Network.requestWillBeSent":
            continue
        info = msg["params"]["request"]
        url = info["url"]
        # 过滤静态资源：只关心走接口的请求（路径含 api，或不是图片/js/css）
        if any(url.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".svg", ".ico", ".woff", ".woff2")):
            continue
        if url.startswith("chrome://") or url.startswith("devtools://"):
            continue
        seen.append({
            "method": info["method"],
            "url": url,
            "post": info.get("postData", ""),
        })
    return seen, since_idx + len(logs)


def main():
    edge_options = Options()
    edge_options.add_argument('--ignore-certificate-errors')
    # Edge 新版驱动（156 实测）已关掉 goog:loggingPrefs，改走 ms:loggingPrefs 键
    edge_options.set_capability("ms:loggingPrefs", {"performance": "INFO"})
    driver = webdriver.Edge(options=edge_options)
    driver.maximize_window()
    try:
        driver.get(LOGIN_URL)
        login = LoginPage(driver)
        # 点击前记游标，登录后采集增量——登录请求就在这段增量里
        _, cursor = collect_api_logs(driver, 0)  # 先把页面加载噪音清掉
        login.login(USERNAME, PASSWORD)
        assert login.is_login_success(), "前置失败：登录没成功"
        time.sleep(2)  # 侦察允许睡：等落地页的加载请求全部发完

        reqs, _ = collect_api_logs(driver, 0)
        print(f"\n{'='*70}\n登录链路共捕获 {len(reqs)} 个请求\n{'='*70}")
        for i, r in enumerate(reqs, 1):
            print(f"[{i}] {r['method']} {r['url']}")
            if r["post"]:
                body = r["post"][:500]
                print(f"    请求体: {body}")

        # 再登记登录后首页的 API 清单（只读请求，为后续"课程列表接口"探路）
        curls = sorted({r["url"] for r in reqs if "/api" in r["url"].lower()})
        print(f"\n{'='*70}\n其中走 /api 的接口地址清单（去重）\n{'='*70}")
        for u in curls:
            print("  ", u)
        print("\n侦察完毕：把输出贴回来，一起定登录接口和返回结构，再写 api 层。")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
