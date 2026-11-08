"""
L5 侦察插曲：探测学生端访问端口（2026-11-07）
背景：手册只说"不同访问端口"没给号；老师端是 8081，登录页副标题写着"老师端"
办法：对同一主机的常见端口发一次 HTTPS GET，看谁活着、谁的登录页带"学生端"字样
性质：只读探测，不提交任何表单，不产生业务数据
运行：& ".venv\\Scripts\\python.exe" "script\\probe_student_port.py"
"""
import os
import ssl
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL

# 待测端口：8081 当对照组（已知老师端）；其余是部署常用号
CANDIDATES = [8081, 8080, 8082, 8083, 8084, 8085, 8088, 5173, 3000, 8000, 9000]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE  # 自签证书环境，等同 --ignore-certificate-errors

host = urllib.parse.urlparse(BASE_URL).hostname


def probe(port):
    url = f"https://{host}:{port}/login"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "probe"})
        with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
            body = resp.read(65536).decode("utf-8", errors="ignore")
            mark = []
            for role in ("老师端", "学生端", "管理端"):
                if role in body:
                    mark.append(role)
            return f"活着 HTTP {resp.status}，页面角色字样：{mark or '未识别（SPA 外壳文字在 JS 里，需浏览器渲染）'}"
    except Exception as e:
        return f"不通：{type(e).__name__} {e}"


def main():
    print(f"主机：{host}")
    for p in CANDIDATES:
        print(f"  端口 {p}: {probe(p)}")
    print("\n说明：SPA 的'老师端/学生端'字样可能是 JS 渲染出来的，HTML 源码里抓不到很正常；"
          "\n哪个端口活着但源码没角色字样，就要再用浏览器打开定性。把输出贴回来。")


if __name__ == "__main__":
    main()
