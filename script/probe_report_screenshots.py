r"""给 README 拍 Allure 报告门面图（只拍汇总层，明细层一律不进）。

为什么用脚本拍而不是手工点：报告里固化了内网地址与真实账号（日志附件、参数化实参），
仓库已转公开，一张拍漏的图就是永久泄露。所以这里用代码把"能去哪些页面"钉死：
  1) Overview 总览（状态饼图、用例总数、趋势、耗时）
  2) Suites 套件列表（只有用例名与通过/失败状态）
脚本里没有任何点击用例名、展开 Log/Attachments/Parameters 的动作——做不到手滑。

前置：先起本地服务（静态 index.html 直接双击打不开，必须走 HTTP）
  & allure open allure-report
拿到形如 http://127.0.0.1:7160 的地址后：
  & ".venv\Scripts\python.exe" "script\probe_report_screenshots.py" http://127.0.0.1:7160/index.html

产出：assets/allure-overview.png、assets/allure-suites.png（这两张是要进仓库的公开资产）
"""
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets"

# 只允许访问这两个路由；#suites 是 Allure 的套件列表页
# needle：用页面文本判定“真渲染完了”的关键词（SPA 的 DOM 结构不好猜，文本最可靠）
PAGES = {
    "allure-overview.png": ("", ["OVERVIEW", "TESTS", "SUMMARY"]),
    "allure-suites.png": ("#suites", ["testcases", "test_"]),
}


def wait_for_text(driver, needles, timeout=40) -> bool:
    """轮询等页面出现任一关键词；Allure 是单页应用，路由切换后还要等异步拉数据"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = driver.find_element(By.TAG_NAME, "body").text.upper()
        if any(n.upper() in text for n in needles):
            return True
        time.sleep(1)
    return False


def shoot(base_url: str) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    # 容错：传人根地址或带 /index.html 的地址都行，统一归一成服务根地址
    root = base_url.rstrip("/")
    if root.endswith("/index.html"):
        root = root[: -len("/index.html")]

    options = Options()
    options.add_argument("--headless=new")      # 无头：不弹窗口，纯截图
    options.add_argument("--window-size=1600,1000")
    options.add_argument("--force-device-scale-factor=1")

    driver = webdriver.Edge(options=options)
    try:
        for filename, (route, needles) in PAGES.items():
            url = root + "/index.html" + route
            driver.get(url)

            # 等报告真正渲染出来：用页面文本判定，不猜 class 名
            if not wait_for_text(driver, needles):
                print(f"[警告] 没等到关键词 {needles}，仍然截图（人工核对后再用）")
            # 图表是二次绘制，再给一点时间，避免拍到半张白图
            time.sleep(3)

            target = OUT_DIR / filename
            driver.save_screenshot(str(target))
            print(f"[OK] {target}  <-  {driver.current_url}")

        # 顺手把页面上的统计数字打出来，供 README 措辞核对（只读文本，不点任何明细）
        driver.get(root + "/index.html")
        time.sleep(3)
        body = driver.find_element(By.TAG_NAME, "body").text
        for line in body.splitlines():
            if any(k in line.lower() for k in ("test", "pass", "fail", "broken", "duration")):
                print("  页面文本:", line.strip())
    finally:
        driver.quit()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法：python script/probe_report_screenshots.py http://127.0.0.1:<端口>")
    shoot(sys.argv[1])
