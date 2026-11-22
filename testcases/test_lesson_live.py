"""
实时工作台 · 跨层 E2E：建沙箱 → start 开课 → UI 断"管理视角层" → 进大屏断
"步骤条 = flow 接口数据" → 收尾 end + 归档。

这条用例是项目里第一条【跨层交叉断言】：同一份业务数据（上课流程 steps），
接口层从 GET /flow 拿，UI 层从大屏步骤条 button.lv-step 拿，两边对账。
它能查出两类单端用例都查不出的 bug：
  ① 接口返回对但前端没渲染对（组件接错数据源、字段改名前端没跟上）；
  ② 前端渲染对但它压根没接口取数、写死了模板（接口换数据 UI 不动）。
单端各断各的，两头各自"自洽"就都绿，中间断了没人知道——这就是交叉断言的价值。

定位器与渲染对应关系全部来自 2026-11-22 实测（script/probe_live_workbench.py，
证据 log/probe_live_workbench2.out + 截图 log/probe_live_landing.png / probe_live_mode.png）：
  - 管理视角 /lessons/<id>：侧栏 ui-live 徽标、四个 a.llink 门牌、ui-hold 长按下课
  - 大屏 /lessons/<id>/live：lv-step 步骤条 = flow.steps（signin→签到 intro→课程导入 end→下课），
    当前步 is-cur，start 后停在第一步；lv-next 文案自带下一步名（"下一步 进入 课程导入"）
副作用纪律（为什么默认被 -m 排除，为什么单开 live 标而不蹭 lesson_e2e）：
  ① 红级写：会真 start 开课（lesson_e2e 里 start 后立刻 end、不碰 UI；本用例开课期间
     还要开浏览器逛两层，页面存在时间更长，影响面不同，标也分开挂）；
  ② 沙箱课名 AT-LIVE-<时间戳> 唯一可认，绝不碰演示课/真实课堂；
  ③ 「回到上课模式」是纯前端路由按钮才允许点；「按住下课」只断存在、任何路径都不点；
  ④ finally 兜底：主流程挂了也先补 end 再归档，全部包 try/except——finally 抛异常
     会盖掉主流程真实失败原因（项目三大坑之一）。
环境不满足时 skip 而非 fail：老师号已有其它 ongoing 课堂 → start 409，同 lesson_e2e 口径。
"""
import logging
import time

import allure
import pytest

from config import BASE_URL
from pages.live_page import LiveLessonPage

# kind → 大屏步骤条文案映射。依据是侦察 dump 的实测对应关系，不是猜的；
# 默认模板之外若出现新 kind，下面的断言会当场红并带出映射表——提示要么改版要么数据变了，
# 这是有意设的"绊线"：宁可红得明白，不许悄悄跳过
_KIND_LABEL = {"signin": "签到", "intro": "课程导入", "end": "下课"}

# 管理视角层的四个门牌（与回放页同一族组件，名字取自实测文案前缀）
_LLINK_NAMES = ["出勤明细", "学生提问", "讨论记录", "管理随堂测与作业"]


def _data(resp):
    """取返回体 data 并挡类型坑：成功=dict、参数错=list、拒绝=null（同 lesson_e2e）"""
    data = (resp.json() or {}).get("data") if resp.text else None
    return data if isinstance(data, dict) else None


def _status(resp):
    return (_data(resp) or {}).get("status")


@allure.feature("实时工作台")
@allure.story("flow 接口数据与大屏步骤条跨层一致")
@pytest.mark.live
def test_live_workbench_flow_matches_api(fresh_page, course_api, lesson_api, api_token):
    course_id, course_name, lesson_id = None, None, None
    started = False

    try:
        with allure.step("建沙箱课 + 讲次（AT-LIVE-<时间戳>，period 用枚举值 78）"):
            course_name = f"AT-LIVE-{time.strftime('%m%d%H%M%S')}"
            resp = course_api.create_course(api_token, course_name)
            assert resp.status_code == 200, \
                f"建沙箱课应 200，实际 {resp.status_code}：{resp.text[:300]}"
            course_id = _data(resp).get("id")
            assert course_id, f"沙箱课没拿到 id：{resp.text[:300]}"

            resp = lesson_api.create_lesson(
                api_token, course_id,
                title="AT 跨层断言讲次", week_no=1, weekday=3, period="78",
            )
            assert resp.status_code == 200, \
                f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")
            assert lesson_id, f"建讲次没拿到 id：{resp.text[:300]}"

        with allure.step("接口侧取证：GET /flow 拿默认流程 steps 的 kind 序列"):
            resp = lesson_api.get_flow(api_token, lesson_id)
            assert resp.status_code == 200, f"读 flow 应 200：{resp.text[:300]}"
            steps = (_data(resp) or {}).get("steps") or []
            kinds = [s.get("kind") for s in steps if isinstance(s, dict)]
            assert kinds, f"默认流程应非空，实际 steps={steps!r}"
            unknown = [k for k in kinds if k not in _KIND_LABEL]
            assert not unknown, \
                f"出现映射表之外的 kind {unknown}（系统改版加了新环节？重跑侦察脚本更新 _KIND_LABEL）"

        with allure.step(f"开课：POST /lessons/{lesson_id}/start（红级，仅沙箱）"):
            resp = lesson_api.start_lesson(api_token, lesson_id)
            if resp.status_code == 409:
                msg = (resp.json() or {}).get("message", "")
                pytest.skip(f"测试老师已有进行中的课堂，本用例需空闲环境：{msg}")
            assert resp.status_code == 200, \
                f"start 应 200，实际 {resp.status_code}：{resp.text[:300]}"
            started = True
            assert _status(lesson_api.get_lesson(api_token, lesson_id)) == "ongoing", \
                "start 后 status 应为 ongoing"

        live = LiveLessonPage(fresh_page)
        with allure.step(f"管理视角层：/lessons/{lesson_id} 断徽标+门牌+长按下课（只存在不点击）"):
            live.open_url(f"{BASE_URL}/lessons/{lesson_id}")
            assert live.is_element_exist(live.live_badge, timeout=10), \
                f"开课后侧栏应有『正在上课』徽标（当前 URL：{fresh_page.current_url}）"
            missing = [n for n in _LLINK_NAMES
                       if not live.is_element_exist(live.lesson_link(n), timeout=3)]
            assert not missing, f"管理视角层缺少功能门牌：{missing}"
            # 长按下课按钮只钉"它在页上"这一事实：真点它属于交互红线（见页面对象头注）
            assert live.is_element_exist(live.hold_end_btn, timeout=5), \
                "管理视角层应存在『按住下课』按钮"

        with allure.step("进大屏层：点『回到上课模式』（纯前端路由），等 URL 落到 /live"):
            live.click_element(live.enter_live_btn)
            url = live.wait_url_matches(r"/live$")
            assert url, f"没进大屏，停在：{fresh_page.current_url}"
            # 步骤条是 SPA 渲染主体，等当前步出现再取全量，防"节点未到先读空列表"
            live.wait_element_visible(live.lv_current_step)

        with allure.step("跨层对账①：lv-step 文案序列 == flow steps 的 kind 映射序列"):
            labels = live.step_labels()
            expected = [_KIND_LABEL[k] for k in kinds]
            assert len(labels) == len(expected), \
                f"步骤条数量与接口不符：UI={labels} vs API={expected}"
            for i, (got, want) in enumerate(zip(labels, expected)):
                assert want in got, f"第 {i + 1} 步文案不符：UI『{got}』里应含『{want}』"

        with allure.step("跨层对账②：start 后当前步(is-cur)=第一步『签到』，『下一步』文案预告第二步"):
            cur = live.current_step_label()
            assert cur == _KIND_LABEL[kinds[0]], \
                f"刚开课时当前步应为『{_KIND_LABEL[kinds[0]]}』，实际『{cur}』"
            next_text = live.get_element(live.lv_next_btn).text
            assert _KIND_LABEL[kinds[1]] in next_text, \
                f"『下一步』按钮应预告第二步『{_KIND_LABEL[kinds[1]]}』，实际文案：『{next_text}』"
            assert live.is_element_exist(live.lv_hold_end_btn, timeout=5), \
                "大屏层应存在长按下课（同样只断存在，不点击）"
    finally:
        # 兜底顺序：先补 end 再归档——课还 ongoing 时归档讲次会被状态守卫拒（同 lesson_e2e 口径）；
        # 清理异常只留痕不上抛，避免盖掉主流程真实失败原因
        if lesson_id and started:
            if _status(lesson_api.get_lesson(api_token, lesson_id)) == "ongoing":
                with allure.step("收尾：主流程失败但已开课，补一步下课"):
                    try:
                        lesson_api.end_lesson(api_token, lesson_id)
                    except Exception as e:
                        logging.getLogger("autotest").warning(f"[补下课失败 id={lesson_id}] {e}")
        if course_id:
            with allure.step("收尾：归档自建沙箱课（讲次随之留档）"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[live 清理失败，需手动归档 id={course_id} name={course_name}] {e}")
                    allure.attach(f"{e}\n待手动归档：id={course_id} name={course_name}",
                                  name="清理失败留痕",
                                  attachment_type=allure.attachment_type.TEXT)
