"""
讲次（lesson）业务接口：建讲次 + 上课状态机三步（详情/开始/下课）
路径、请求体字段、返回结构、状态变化全部来自实测（2026-11-15 script/probe_api_lesson.py），不是猜的：
  - 建讲次 POST /courses/{id}/lessons 必填 title/week_no/weekday/period（seq 后端可默认），
    空 body 会被 400/40001 逐字段告知缺哪几个（实测踩出来的），首发返回体即带 id 与 status=draft
  - 状态机：draft →(POST /lessons/{id}/start)→ ongoing →(POST /lessons/{id}/end)→ ended
    start 无强制 body（实测 body={} 即可）；end 无 body
  - 两条硬性约束（实测拿到的返回，直接决定用例设计）：
      ① 同一老师同时只能有一个 ongoing 课堂：已有ongoing时 start → 409/40903
         "该老师已有正在上课的课堂（#X），请先下课后再开始另一节"
      ② 没开始的课不能下课：对 draft 直接 end → 400/40003 "未开始的课堂不能下课"
  - 平行还有一堆互动写接口（签到/点名/弹幕/随堂测…）见 docs/上课流程接口地图.md，
    都是改动真实课堂数据的红线，本类一律不封装、用例一律不碰
"""
from api.base_api import BaseApi


class LessonApi(BaseApi):
    def list_lessons(self, token: str, course_id: int, page: int = 1, page_size: int = 100):
        """GET /courses/{id}/lessons 某课程下的讲次列表
        每项 status 取值 draft/ongoing/ended（实测）；只读，用来查环境是否已有 ongoing 讲次
        """
        return self.get(f"/courses/{course_id}/lessons", token=token,
                        params={"page": page, "page_size": page_size})

    def create_lesson(self, token: str, course_id: int, title: str,
                      week_no: int, weekday: int, period: str, seq: int = None):
        """建讲次 POST /courses/{id}/lessons
        必填字段 title/week_no/weekday/period 是实测空 body 被 400 逐字段点出来的，缺一不可；
        seq 后端会默认（实测不传也能建成），做成可选参数
        ⚠ 黄级写操作：调用即在库中建一条 draft 讲次，仅在自建 AT-* 沙箱课下调用
        """
        payload = {"title": title, "week_no": week_no, "weekday": weekday, "period": period}
        if seq is not None:
            payload["seq"] = seq
        return self.post(f"/courses/{course_id}/lessons", token=token, json=payload)

    def get_lesson(self, token: str, lesson_id):
        """GET /lessons/{id} 讲次详情：状态机每一步都用它读 status 做权威断言"""
        return self.get(f"/lessons/{lesson_id}", token=token)

    def start_lesson(self, token: str, lesson_id):
        """开始上课 POST /lessons/{id}/start：draft → ongoing
        实测 body 传 {} 即可；若该老师已有别的 ongoing 课堂 → 409/40903（用例据此判环境）
        """
        return self.post(f"/lessons/{lesson_id}/start", token=token, json={})

    def end_lesson(self, token: str, lesson_id):
        """下课 POST /lessons/{id}/end：ongoing → ended
        实测无 body；对未开始的 draft 讲次调用 → 400/40003 "未开始的课堂不能下课"
        ⚠ 只对自建沙箱讲次调用，绝不用于真实课堂（真实 104 等属红线）
        """
        return self.post(f"/lessons/{lesson_id}/end", token=token)

    def get_flow(self, token: str, lesson_id):
        """读上课流程 GET /lessons/{id}/flow：返回大屏依次播的步骤清单
        实测返回结构 data={lesson_id, saved(bool), steps(list)}；每步含 kind
        （默认模板为 signin→end）+ courseware_id/quiz_id/topic 等内容位（未自定义时均 null）；
        saved=false 代表老师未改过默认流程。只读零副作用，适合做绿级断言
        """
        return self.get(f"/lessons/{lesson_id}/flow", token=token)

    def put_flow(self, token: str, lesson_id, body):
        """保存上课流程 PUT /lessons/{id}/flow
        实测（2026-11-15 script/probe_api_flow_write.py）：
          - 请求体传完整 {lesson_id,saved,steps} 或只传 {steps} 都收（信封宽松）；
          - 成功后 message="流程已保存"，且 saved 由服务端置 true（不认客户端传的 false）；
          - steps 里每项的 kind 是受限枚举：signin/end 合法，courseware 等非法值 → 400/40001，
            且 data 是字段错误 list（命中行如 steps.1.kind 取值不在允许范围内）。
        ⚠ 只对自建沙箱讲次调用（写操作）；不碰演示课/真实课堂的 flow
        """
        return self.put(f"/lessons/{lesson_id}/flow", token=token, json=body)
