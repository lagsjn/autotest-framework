"""
登录业务接口：只管"登录这个动作"，怎么发请求交给 BaseApi
路径与字段全部来自实测（script/probe_api_login.py、probe_api_login2.py）
"""
from api.base_api import BaseApi
from config import USERNAME, PASSWORD


class LoginApi(BaseApi):
    LOGIN_PATH = "/auth/login"

    def login(self, username: str, password: str):
        """POST 登录，返回原始 requests 响应（用例层自己断言状态码/字段）"""
        return self.post(self.LOGIN_PATH, json={"username": username, "password": password})

    def login_and_get_token(self, username: str = USERNAME, password: str = PASSWORD) -> str:
        """一步到位拿 token，给"需要登录态"的接口用例当前置（对标 UI 的登录态复用）
        拿不到就当场报错——前置失败要第一时间喊出来，别让下游用例拿 None 去发请求
        """
        resp = self.login(username, password)
        assert resp.status_code == 200, f"登录接口前置失败：HTTP {resp.status_code} {resp.text[:200]}"
        token = self.extract_token(resp.json())
        assert token, f"登录成功但没取到 token：{resp.text[:200]}"
        return token

    @staticmethod
    def extract_token(body: dict):
        """从登录返回体里抠 access_token：data.access_token（实测结构）
        失败返回体里 data 是 null（键在、值为空），所以不能直接 .get("data", {})
        ——那会拿到 None 再 .get 就炸。用 `or {}` 把 None 也兼平成空字典
        """
        data = (body or {}).get("data") or {}
        return data.get("access_token")
