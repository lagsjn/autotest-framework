"""
课程业务接口：只读列表 + E2E 链路四步（建课/详情/加入/成员/归档）
路径、请求体字段、返回结构全部来自实测，不是猜的：
  静态侦察 script/probe_api_bundle.py（从前端 JS 包里抄调用点）
  动态实测 script/probe_api_course_write.py 与 _write2.py（真发请求抄返回）
实测要点（2026-11-11）：
  - 建课请求体只要 name 一个字段就过（描述/学期等留空），返回体直接带 id 和 invite_code，
    所以"建完再查列表找 id"这一步是多余的，省掉
  - 邀请码字段名统一叫 invite_code（列表、详情、建课返回三处一致）
  - GET /courses 的 status 查询参数实测不生效（带不带都返回全集），过滤在前端做
    → 需要按状态筛数据时，调用方自己从 items 里挑，别指望 URL 参数
  - page_size 上限实测 100，超了回 400/40001 且 data 变成 list（字段校验错误明细）
  - "归档课程"在接口层是 DELETE /courses/{id}，实测是软删：返回体 status=archived、
    归档后详情仍可 GET 到；同清单里的 /permanent 才是真删（不可恢复），本项目一律不用
"""
from api.base_api import BaseApi


class CourseApi(BaseApi):
    COURSES_PATH = "/courses"

    def list_courses(self, token: str, page: int = 1, page_size: int = 100):
        """带 token 查课程列表。token 由 LoginApi.login_and_get_token 提供
        page_size 默认 100=实测上限，写更大会被参数校验拒（400/40001）
        返回原始响应，用例层断言状态码 + 列表内容
        """
        return self.get(
            self.COURSES_PATH,
            token=token,
            params={"page": page, "page_size": page_size},
        )

    def get_course(self, token: str, course_id):
        """查课程详情 GET /courses/{id}：E2E 里用它核对“建课返回的那门课就是库里存的那门课”"""
        return self.get(f"{self.COURSES_PATH}/{course_id}", token=token)

    def create_course(self, token: str, name: str):
        """建课 POST /courses，请求体只需 {"name": ...}（实测）
        ⚠ 黄级写操作：调用即落库，且系统允许同名课程——所以课程名要带时间戳保证唯一，
        并且断言一律用返回体里的 id 锁定，不要只按名字找（同名会找到别门课）
        """
        return self.post(self.COURSES_PATH, token=token, json={"name": name})

    def join_course(self, token: str, invite_code: str):
        """学生凭 6 位邀请码加入课程 POST /courses/join（实测 body 字段名=invite_code）
        实测两条行为，直接影响用例设计：
          ① 重复加入是幂等的（连发两次都回 200"加入成功"，成员表只有一条）→ 用例可重跑
          ② 课程归档后旧邀请码立刻失效 → 404/40401"邀请码无效或课程不存在"
        注意：本方法应通过学生端的 CourseApi 实例（base_url=STUDENT_BASE_URL）调用
        """
        return self.post(f"{self.COURSES_PATH}/join", token=token,
                         json={"invite_code": invite_code})

    def list_members(self, token: str, course_id: int, page: int = 1, page_size: int = 20):
        """班级成员 GET /courses/{id}/members：断言"谁真的加进来了"的权威数据源
        返回体 items 每项含 student_no / status（实测 status=joined）
        """
        return self.get(f"{self.COURSES_PATH}/{course_id}/members", token=token,
                        params={"page": page, "page_size": page_size})

    def archive_course(self, token: str, course_id: int):
        """归档 DELETE /courses/{id}：本项目的数据清理手段（软删，实测 status->archived）
        ⚠ 红线：只对自动化自己建的课（AT-* 前缀）调用；
          同族还有个 DELETE /courses/{id}/permanent 是永久删除，不可恢复，严禁出现在自动化里
        """
        return self.delete(f"{self.COURSES_PATH}/{course_id}", token=token)
