"""
接口层公共底座：把"怎么发 HTTP 请求"沉淀成一处，业务接口类只管"发哪个接口"
对标 UI 层的 base_page.py：那里集中封装等待/点击，这里集中封装会话/鉴权/日志
"""
import logging

import requests
import urllib3

from config import BASE_URL, API_PREFIX, TIMEOUT

# 被测系统是自签 HTTPS 证书（浏览器就是为这个才加 --ignore-certificate-errors）。
# requests 默认会校验证书、自签的直接报错拦下。关掉校验只适用于测试环境，生产严禁
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("autotest")


class BaseApi:
    """所有业务接口类的父类：建会话、拼绝对地址、统一带 token、发请求、记日志"""

    def __init__(self, base_url: str = BASE_URL):
        # 会话对象：复用底层 TCP 连接、自动维护 Cookie，比每次 requests.get 裸调更快更省
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = False  # 自签证书，全局关掉校验（子类都走这个会话）

    def _url(self, path: str) -> str:
        """把接口路径拼成绝对地址。path 传 /auth/login 这种"资源路径"，
        版本前缀 /api/v1 在这里统一补，业务类不用各写一遍（改前缀只改 config）
        """
        return f"{self.base}{API_PREFIX}{path}"

    def request(self, method: str, path: str, token: str = None, **kwargs):
        """发一次请求并把关键信息记进日志（日志和 UI 用例同一份，好排查）
        token 不为空就自动塞进 Authorization 头（Bearer 鉴权，抓包实测的格式）
        """
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = self._url(path)
        logger.info(f"[API] {method} {url}")
        resp = self.session.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
        # 只记一行概要，正文大不放日志（放日志会刷屏）；断言失败时用例自己贴 body
        logger.info(f"[API] <- {resp.status_code}")
        return resp

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)
