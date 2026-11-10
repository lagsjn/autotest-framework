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

    def send(self, payload):
        """直发任意请求体（数据驱动专用）：用于造"空值/缺字段/空请求体"这种
        login() 造不出的畸形请求。路径封装在本类，用例层只传 payload 不碰路径
        """
        return self.post(self.LOGIN_PATH, json=payload)

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
        防御型：data 在不同分支下类型不一样——成功=dict、身份错(401)=null、
        参数错(400)=list（实测探出）；非 dict 一律当"没有 token"，不能直接 .get 炸栈
        """
        data = (body or {}).get("data")
        if not isinstance(data, dict):
            return None
        return data.get("access_token")
