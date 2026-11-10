"""
课程业务接口：这轮只做只读的"课程列表"（GET /courses），零副作用
写操作（建课/归档）等接口层跑稳、账号锁定红线研究清楚后再加
路径与参数来自实测（浏览器登录后自动发的 GET /api/v1/courses?page=1&page_size=100）
"""
from api.base_api import BaseApi


class CourseApi(BaseApi):
    COURSES_PATH = "/courses"

    def list_courses(self, token: str, page: int = 1, page_size: int = 100):
        """带 token 查课程列表。token 由 LoginApi.login_and_get_token 提供
        返回原始响应，用例层断言状态码 + 列表内容
        """
        return self.get(
            self.COURSES_PATH,
            token=token,
            params={"page": page, "page_size": page_size},
        )
