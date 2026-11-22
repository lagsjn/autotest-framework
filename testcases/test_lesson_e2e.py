"""
接口层·上课状态机 E2E：建沙箱课 → 建讲次(draft) → 开始上课(ongoing) → 下课(ended) → 归档收尾
这是"上课流程"新增功能在接口层的主干覆盖（UI 实时课堂强驱动、计时器/WebSocket 时序易 flaky，
不适合做主断言；接口层把状态流转钉成客观事实，稳、快、可重复）。
定位依据全部来自实测（2026-11-15 script/probe_api_lesson.py）：
  - 建讲次必填 title/week_no/weekday/period；返回体即带 id 与 status=draft
  - draft →(start)→ ongoing →(end)→ ended
  - 硬性约束：同一老师同时只能有一节 ongoing，冲突时 start → 409/40903
  - 硬性约束：未开始的讲次 end → 400/40003
副作用纪律（为什么默认被 -m 排除）：
  ① 会真实建沙箱课 + 讲次（名字 AT-API-<时间戳> 唯一可认），绝不碰演示课 14 / 真实课堂 104；
  ② 收尾无条件归档课程（讲次随课程一起留档），中途断言挂了也照样清理；
  ③ 清理包 try/except：finally 抛异常会盖掉主流程真实失败原因；
  ④ 绝不调互动写接口（签到/点名/下课红线），状态机只走 start/end 两个受控动作。
正向链路的现实情况：测试账号（T老师）若被手动"临时调课"开了真实 ongoing 讲次，
  start 会撞 409——这不是产品 bug，是"同一老师只能有一节在做"的正确规则，
  故用例把 409 识别为"环境被真实课堂占用"并 skip，而不是 fail（换空闲账号/先下课即可跑通）。
"""
import logging
import time

import allure
import pytest

from config import HAS_STUDENT  # noqa: F401  （预留：后续跨端学情用例需要，当前链路不依赖）


def _data(resp):
    """取返回体 data 并挡类型坑：成功=dict、参数错=list、拒绝=null"""
    data = (resp.json() or {}).get("data") if resp.text else None
    return data if isinstance(data, dict) else None


def _status(resp):
    """从讲次接口返回体里读 status（data.status），data 非 dict 时返回 None"""
    return (_data(resp) or {}).get("status")


def _make_sandbox_course(course_api, token):
    """建一门唯一命名的 AT-* 沙箱课，返回 (course_id, course_name)；建不出来当场 assert"""
    name = f"AT-API-{time.strftime('%m%d%H%M%S')}"
    resp = course_api.create_course(token, name)
    assert resp.status_code == 200, f"建沙箱课应 200，实际 {resp.status_code}：{resp.text[:300]}"
    data = _data(resp)
    assert data and data.get("id"), f"沙箱课没拿到 id：{resp.text[:300]}"
    return data["id"], name


@allure.feature("接口E2E-上课状态机")
@allure.story("讲次 draft→ongoing→ended 全生命周期")
@pytest.mark.lesson_e2e
def test_lesson_lifecycle_e2e(course_api, lesson_api, api_token):
    """正向主干：建课→建讲次(draft)→start(ongoing)→end(ended)，每步断言打在 status 上
    遇到 409（老师已有其它 ongoing 真实课堂）→ 判为环境占用，skip 而非 fail
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None
    started = False
    archived = False

    try:
        with allure.step(f"建讲次：POST /courses/{course_id}/lessons（draft）"):
            resp = lesson_api.create_lesson(
                api_token, course_id,
                title="AT 沙箱讲次", week_no=1, weekday=3, period="78",
            )
            assert resp.status_code == 200, \
                f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            data = _data(resp)
            assert data and data.get("id"), f"建讲次没拿到 id：{resp.text[:300]}"
            lesson_id = data["id"]
            assert data.get("status") == "draft", \
                f"新建讲次初始状态应为 draft，实际 {data.get('status')}"

        with allure.step(f"开始上课：POST /lessons/{lesson_id}/start（draft→ongoing）"):
            resp = lesson_api.start_lesson(api_token, lesson_id)
            if resp.status_code == 409:
                # 不是产品缺陷，是"同一老师同时只能有一节 ongoing"的正确规则被真实课堂触发
                msg = (resp.json() or {}).get("message", "")
                pytest.skip(
                    f"测试老师已有进行中的真实课堂，正向链路需空闲环境（先下课或换账号再跑）：{msg}"
                )
            assert resp.status_code == 200, \
                f"开始上课应 200，实际 {resp.status_code}：{resp.text[:300]}"
            started = True
            assert _status(lesson_api.get_lesson(api_token, lesson_id)) == "ongoing", \
                "start 后 status 应变为 ongoing"

        with allure.step(f"下课：POST /lessons/{lesson_id}/end（ongoing→ended）"):
            resp = lesson_api.end_lesson(api_token, lesson_id)
            assert resp.status_code == 200, \
                f"下课应 200，实际 {resp.status_code}：{resp.text[:300]}"
            assert _status(lesson_api.get_lesson(api_token, lesson_id)) == "ended", \
                "end 后 status 应变为 ended"
    finally:
        # started 兜底：万一 start 成功但后续断言挂了，讲次处于 ongoing——先补 end 再归档，
        # 不给环境留"上着课"的僵尸讲次（end 失败只留痕不上抛，避免盖掉主流程真实失败）
        if lesson_id and started:
            if _status(lesson_api.get_lesson(api_token, lesson_id)) == "ongoing":
                with allure.step("收尾：主流程失败但已 start，补一步下课"):
                    try:
                        lesson_api.end_lesson(api_token, lesson_id)
                    except Exception as e:
                        logging.getLogger("autotest").warning(f"[补下课失败 id={lesson_id}] {e}")
        if course_id and not archived:
            with allure.step("收尾：归档自建沙箱课（讲次随之留档）"):
                try:
                    course_api.archive_course(api_token, course_id)
                    archived = True
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")
                    allure.attach(f"{e}\n待手动归档：id={course_id} name={course_name}",
                                  name="清理失败留痕",
                                  attachment_type=allure.attachment_type.TEXT)


@allure.feature("接口E2E-上课状态机")
@allure.story("未开始的讲次禁止下课（400/40003）")
@pytest.mark.lesson_e2e
def test_end_before_start_rejected(course_api, lesson_api, api_token):
    """负向规则：draft 讲次直接 end 应被拒（400/40003 "未开始的课堂不能下课"）
    不受"老师是否空闲"影响，永远可跑——是状态机最稳的一条守卫断言
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None

    try:
        with allure.step(f"建讲次（draft）id 待用"):
            resp = lesson_api.create_lesson(
                api_token, course_id,
                title="AT 未开始讲次", week_no=1, weekday=3, period="78",
            )
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")
            assert _status(lesson_api.get_lesson(api_token, lesson_id)) == "draft"

        with allure.step(f"未 start 直接 end：POST /lessons/{lesson_id}/end 应被拒"):
            resp = lesson_api.end_lesson(api_token, lesson_id)
            assert resp.status_code == 400, \
                f"未开始的讲次下课应被拒(400)，实际 {resp.status_code}：{resp.text[:300]}"
            assert (resp.json() or {}).get("code") == 40003, \
                f"业务码应为 40003(未开始的课堂不能下课)，实际={(resp.json() or {}).get('code')}"
            # 拒了之后状态必须还是 draft（不能把拒掉的课悄悄置成别的态）
            assert _status(lesson_api.get_lesson(api_token, lesson_id)) == "draft", \
                "被拒的下课后讲次状态应仍是 draft"
    finally:
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")
                    allure.attach(f"{e}\n待手动归档：id={course_id} name={course_name}",
                                  name="清理失败留痕",
                                  attachment_type=allure.attachment_type.TEXT)


@allure.feature("接口E2E-上课流程")
@allure.story("新建讲次自带默认播放流程模板")
@pytest.mark.lesson_e2e
def test_lesson_flow_default_template(course_api, lesson_api, api_token):
    """新功能覆盖：GET /lessons/{id}/flow 断默认流程模板结构
    新建的 draft 讲次未由老师自定义过，flow 应回系统默认模板（实测：steps=[signin...end]、saved=False）。
    断言逐层打在实测结构上（不只是 200）：data 是 dict、steps 是非空 list、每步带 kind、首尾为 signin/end。
    本用例只读 flow、不 start（不依赖老师是否空闲，永远可跑）；但仍建了课+讲次，故归 lesson_e2e 写标。
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None

    try:
        with allure.step("建讲次（draft）作为 flow 只读样本"):
            resp = lesson_api.create_lesson(
                api_token, course_id,
                title="AT 流程样本", week_no=1, weekday=3, period="78",
            )
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")

        with allure.step(f"读 flow：GET /lessons/{lesson_id}/flow 断默认模板结构"):
            resp = lesson_api.get_flow(api_token, lesson_id)
            assert resp.status_code == 200, f"读 flow 应 200，实际 {resp.status_code}：{resp.text[:300]}"
            assert (resp.json() or {}).get("code") == 0, "读 flow 业务码应为 0"
            data = _data(resp)
            assert data, f"flow 返回体 data 应为 dict，实际={resp.text[:200]}"
            assert data.get("lesson_id") == lesson_id, \
                f"flow 回显的 lesson_id 应与请求一致，实际={data.get('lesson_id')}"
            steps = data.get("steps")
            assert isinstance(steps, list) and steps, \
                f"新建讲次应带非空默认流程模板，实际 steps={steps!r}"
            kinds = [s.get("kind") for s in steps if isinstance(s, dict)]
            assert all(s.get("kind") for s in steps if isinstance(s, dict)), \
                f"每个流程步骤都应带 kind 字段，实际 kinds={kinds}"
            assert kinds[0] == "signin" and kinds[-1] == "end", \
                f"默认模板首步应为 signin、末步应为 end，实际={kinds}"
            assert isinstance(data.get("saved"), bool), \
                f"saved 应为布尔（实测新建未自定义讲次为 False），实际={data.get('saved')!r}"
    finally:
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")
                    allure.attach(f"{e}\n待手动归档：id={course_id} name={course_name}",
                                  name="清理失败留痕",
                                  attachment_type=allure.attachment_type.TEXT)


def _flow_kinds(lesson_api, token, lesson_id):
    """读 flow 取 steps 的 kind 列表（带类型防御：拿不到就当空，不当 200 同义词）"""
    data = _data(lesson_api.get_flow(token, lesson_id)) or {}
    steps = data.get("steps")
    if not isinstance(steps, list):
        return None, data.get("saved")
    return [s.get("kind") for s in steps if isinstance(s, dict)], data.get("saved")


@allure.feature("接口E2E-上课流程")
@allure.story("保存自定义流程真落库（saved false→true）")
@pytest.mark.lesson_e2e
def test_lesson_flow_save_persists(course_api, lesson_api, api_token):
    """正向写场景：PUT flow 后 GET 回读断状态迁移真落库
    新建 draft 讲次默认 saved=False（未自定义）→ PUT 回传自身 steps → 回读应变 saved=True。
    断“回读变 true”而非只断 PUT 200：后者只能证明接口回了话，前者才证明流程真持久化了
    （写操作最怕响应说成功、数据没动）。steps 内容不变（只验证保存动作本身）。
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None

    try:
        with allure.step("建讲次（draft）并读默认 flow（应 saved=False）"):
            resp = lesson_api.create_lesson(
                api_token, course_id, title="AT 流程保存", week_no=1, weekday=3, period="78")
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")
            kinds, saved = _flow_kinds(lesson_api, api_token, lesson_id)
            assert saved is False, f"新建讲次默认应 saved=False，实际={saved}"
            base_steps = _data(lesson_api.get_flow(api_token, lesson_id)).get("steps")

        with allure.step("PUT flow 回传自身 steps → 预期服务端落库并把 saved 置 true"):
            resp = lesson_api.put_flow(api_token, lesson_id, {"steps": base_steps})
            assert resp.status_code == 200, \
                f"PUT flow 应 200，实际 {resp.status_code}：{resp.text[:300]}"
            assert (resp.json() or {}).get("code") == 0, "PUT flow 业务码应为 0"

        with allure.step("GET 回读断保存真落库：saved 变 true、steps 不变"):
            kinds2, saved2 = _flow_kinds(lesson_api, api_token, lesson_id)
            assert saved2 is True, \
                f"PUT 后回读应 saved=True（实测服务端自动置位），实际={saved2}——保存未落库"
            assert kinds2 == kinds, f"回传自身 steps 不应改变步骤序列，实际={kinds2}"
    finally:
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")


@allure.feature("接口E2E-上课流程")
@allure.story("加一个合法自定义步并真落库（步数+1）")
@pytest.mark.lesson_e2e
def test_lesson_flow_add_valid_step_persists(course_api, lesson_api, api_token):
    """正向写场景（kind 白名单侦察铺的路）：在默认流程中插一个合法自定义步→回读步数+1。
    实测 kind 白名单共7个（signin/slides/quiz/discussion/demo/rollcall/end），其中只有 rollcall 不依赖
    任何外部资源（slides/quiz/demo 需真实课件/测验/演示 id，伪造会撞 40002“不存在或不属于”），
    故本用例选 rollcall（点名）做纯沙箱可自证的“加合法步”。
    断言不只看 PUT 200：独立 GET 回读才钉住“新步真落库”（比基准多一步、新 kind 在 end 之前、saved 变 true）。
    ⚠ 不断死默认模板的绝对内容：被测系统在开发中，2026-11-18 CI 抓到默认模板从
      [signin,end] 变成 [signin,intro,end]（产品迭代不是代码坏）——用例只钉“我插入的那一步”
      这个相对变化，环境现状以实读到为准，避免脆断言。
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None

    try:
        with allure.step("建讲次（draft）并读默认 flow 作基准（只断结构：首 signin、尾 end）"):
            resp = lesson_api.create_lesson(
                api_token, course_id, title="AT 加合法步", week_no=1, weekday=3, period="78")
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")
            base_steps = _data(lesson_api.get_flow(api_token, lesson_id)).get("steps")
            kinds0 = [s.get("kind") for s in base_steps if isinstance(s, dict)]
            assert kinds0 and kinds0[0] == "signin" and kinds0[-1] == "end", \
                f"默认流程首步应 signin、末步应 end，实际={kinds0}"

        with allure.step("PUT flow：在 end 前插一个合法自定义步 rollcall"):
            new_steps = list(base_steps)
            pos = next((i for i, s in enumerate(new_steps)
                        if isinstance(s, dict) and s.get("kind") == "end"), len(new_steps))
            new_steps.insert(pos, {"kind": "rollcall"})
            resp = lesson_api.put_flow(api_token, lesson_id, {"steps": new_steps})
            assert resp.status_code == 200, \
                f"加合法步 rollcall 应 200，实际 {resp.status_code}：{resp.text[:300]}"
            assert (resp.json() or {}).get("code") == 0, "PUT flow 业务码应为 0"

        with allure.step("GET 回读：比基准多一步 rollcall（插在 end 前）、saved 变 true"):
            kinds2, saved2 = _flow_kinds(lesson_api, api_token, lesson_id)
            assert kinds2 is not None, f"回读 steps 应可解析，实际={kinds2}"
            expected = kinds0[:pos] + ["rollcall"] + kinds0[pos:]
            assert kinds2 == expected, \
                f"回读步序应为基准插入 rollcall 后的 {expected}，实际={kinds2}"
            assert saved2 is True, \
                f"自定义后回读应 saved=True，实际={saved2}——新增步未真落库"
    finally:
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")


@allure.feature("接口E2E-上课流程")
@allure.story("非法步骤 kind 被枚举白名单拦截（400/40001）")
@pytest.mark.lesson_e2e
def test_lesson_flow_invalid_kind_rejected(course_api, lesson_api, api_token):
    """负向写场景：PUT flow 带非法 kind 应被枚举报拒（400/40001），且不落库
    实测 kind 是受限枚举（signin/end 合法，courseware 非法）；被拒后 data 是字段错误 list，
    再次坐实“返回体同一字段类型随分支变”——取值必须类型防御。回读 steps 应仍为默认两步（拒了不能存）。
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None

    try:
        with allure.step("建讲次（draft）"):
            resp = lesson_api.create_lesson(
                api_token, course_id, title="AT 非法流程", week_no=1, weekday=3, period="78")
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}"
            lesson_id = _data(resp).get("id")
            base_steps = _data(lesson_api.get_flow(api_token, lesson_id)).get("steps")

        with allure.step("PUT flow 插一个非法 kind 的步骤 → 应被拒 400/40001"):
            bad_steps = list(base_steps)
            bad_steps.insert(len(bad_steps) - 1, {"kind": "bogus_probe_kind"})
            resp = lesson_api.put_flow(api_token, lesson_id, {"steps": bad_steps})
            assert resp.status_code == 400, \
                f"非法 kind 应被参数校验拒(400)，实际 {resp.status_code}：{resp.text[:300]}"
            body = resp.json()
            assert body.get("code") == 40001, f"业务码应为 40001，实际={body.get('code')}"
            # 关键取证：参数错分支下 data 是 list（字段错误明细），不是 dict
            assert isinstance(body.get("data"), list), \
                f"参数校验错误的 data 应是 list，实际类型 {type(body.get('data')).__name__}"
            assert any("kind" in str(e.get("field", "")) for e in body["data"]), \
                f"应报错字段含 kind，实际={body['data']}"

        with allure.step("GET 回读：非法步应未落库，steps 仍是默认两步"):
            kinds2, _ = _flow_kinds(lesson_api, api_token, lesson_id)
            assert "bogus_probe_kind" not in (kinds2 or []), \
                f"被拒的非法步不应落库，实际 steps={kinds2}"
    finally:
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")


# ---------- 流程结构规则（源码 normalize_steps 四条约束，2026-11-21 读 Service/lesson_flow_service.py）-----
# 设计要点（都是源码读出来的，不是猜的）：
# ① 四步构造都完全自持（自己写死 steps），不依赖环境当前默认模板内容——
#    默认模板在迭代中（CI 曾抓到 [signin,end]变[signin,intro,end]），依赖它会脆断；
# ② steps 只用 signin/intro/end 三种不引用外部资源的 kind，绕开课件/测验/演示的引用校验分支，
#     pure 沙箱可自证（滑入 slides/quiz 会先撞 40002“不存在或不属于”，测不到目标准则）；
# ③ “end 不在最后”靠把唯一的 end 移到首位构造，不能用“往中间插一个 end”：
#    源码 count(END)>1 的检查在 kinds[-1]!=END 之前，插两个会先命中“下课只能有一个”，测不到目标规则。
_FLOW_RULE_CASES = [
    pytest.param([{"kind": "signin"}, {"kind": "signin"}, {"kind": "end"}], "签到",
                 id="signin 重复"),
    pytest.param([{"kind": "signin"}, {"kind": "intro"}, {"kind": "intro"}, {"kind": "end"}], "导入",
                 id="intro 重复"),
    pytest.param([{"kind": "signin"}, {"kind": "end"}, {"kind": "end"}], "下课环节只能有一个",
                 id="end 重复"),
    pytest.param([{"kind": "end"}, {"kind": "signin"}], "最后",
                 id="end 不在末尾"),
]


@allure.feature("接口E2E-上课流程")
@allure.story("流程结构规则被拒（400/40002语义层）")
@pytest.mark.lesson_e2e
@pytest.mark.parametrize("bad_steps,kw", _FLOW_RULE_CASES)
def test_flow_structure_rule_rejected(course_api, lesson_api, api_token, bad_steps, kw):
    """负向写场景（源码反推 predict-then-verify）：违反结构规则应 400 + 业务码 40002
    这条用例同时断两件事，都是源码读出来的预测，跑不过就说明我们对系统的理解有误：
      ① 码是 40002（PARAM_VALUE_ILLEGAL 语义层）而不是 40001（枚举层）——两者是同接口不同层；
      ② 报错形态与 40001 不同：40002 由 BizException 直接抛，data 默认 None（不是字段错误 list），
         提示语是中文人话（如“下课环节要放在最后”），所以这里断 message 含关键词、不断 data 是 list。
    被拒后必须回读确认没落库（拒了不能悄悄存）。
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None

    try:
        with allure.step("建讲次（draft）并读默认流程作基准"):
            resp = lesson_api.create_lesson(
                api_token, course_id, title="AT 结构规则", week_no=1, weekday=3, period="78")
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")
            base_kinds, _ = _flow_kinds(lesson_api, api_token, lesson_id)

        with allure.step(f"PUT 违规 steps（{[s['kind'] for s in bad_steps]}）→ 应 400/40002"):
            resp = lesson_api.put_flow(api_token, lesson_id, {"steps": bad_steps})
            assert resp.status_code == 400, \
                f"违反结构规则应 400，实际 {resp.status_code}：{resp.text[:300]}"
            body = resp.json() or {}
            # 断语义层码：40002 不是 40001（同一个接口上两层拦截，报的码代的是不同团队的责任层）
            assert body.get("code") == 40002, \
                f"业务码应为 40002(参数值非法)，实际={body.get('code')}：{resp.text[:300]}"
            assert kw in (body.get("message") or ""), \
                f"提示语应含“{kw}”，实际={body.get('message')!r}"
            # 形态预测：语义层报错带的是单条中文提示，data 默认 None（与 40001 的 list 形态不同）
            assert not isinstance(body.get("data"), list), \
                f"40002 的 data 不应是字段错误 list（那是 40001 的形态），实际={body.get('data')!r}"

        with allure.step("GET 回读：违规流程不应落库"):
            kinds2, _ = _flow_kinds(lesson_api, api_token, lesson_id)
            assert kinds2 == base_kinds, \
                f"被拒的 PUT 不应改变流程，基准={base_kinds}，实际={kinds2}"
    finally:
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")


@allure.feature("接口E2E-上课流程")
@allure.story("重置流程真丢弃自定义（DELETE 硬删）")
@pytest.mark.lesson_e2e
def test_lesson_flow_reset_restores_default(course_api, lesson_api, api_token):
    """正向写场景：自定义→重置→回读，断三步真落库而不是只看接口返 200
    源码依据 lesson_flow_service.reset_flow：调 delete_steps 硬删已存流程，再走 get_flow 现算默认。
    所以重置后的特征不是“saved=True 且内容等于默认”，而是 **saved 跳回 False**（保存记录被丢了）；
    这个区分是关键：若只看步序变默认，分不清“硬删后重算”和“复制了一份默认并覆盖”。
    用 rollcall 做自定义步（不依赖外部资源）。本用例全程 draft，不依赖老师是否空闲。
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None

    try:
        with allure.step("建讲次（draft）并读默认流程基准"):
            resp = lesson_api.create_lesson(
                api_token, course_id, title="AT 重置流程", week_no=1, weekday=3, period="78")
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")
            base_kinds, saved0 = _flow_kinds(lesson_api, api_token, lesson_id)
            # ⚠ 形状陷阱（本轮实测踩出来的）：_flow_kinds 返回的是 kind 字符串列表（读用的派生视图），
            # PUT 要的是对象列表 [{"kind":...},...]（写用的原始结构）；两者混用服务端直接 40001
            # “Input should be a valid dictionary or object”——这里必须另取一次 steps 原始 dict。
            base_steps = _data(lesson_api.get_flow(api_token, lesson_id)).get("steps")
            assert saved0 is False, f"新建讲次应 saved=False，实际={saved0}"

        with allure.step("先 PUT 自定义（插 rollcall）→ 回读 saved=True 且含 rollcall，把‘已保存’状态做出来"):
            pos = next((i for i, k in enumerate(base_kinds) if k == "end"), len(base_kinds))
            expected_kinds = base_kinds[:pos] + ["rollcall"] + base_kinds[pos:]
            new_steps = base_steps[:pos] + [{"kind": "rollcall"}] + base_steps[pos:]
            resp = lesson_api.put_flow(api_token, lesson_id, {"steps": new_steps})
            assert resp.status_code == 200, f"自定义 PUT 应 200，实际 {resp.status_code}：{resp.text[:300]}"
            kinds1, saved1 = _flow_kinds(lesson_api, api_token, lesson_id)
            assert saved1 is True and kinds1 == expected_kinds, \
                f"重置前应先自定义成功（saved=True），实际 saved={saved1} kinds={kinds1}"

        with allure.step("DELETE /flow 重置 → 断 saved 跳回 False 且自定义步硬删"):
            resp = lesson_api.reset_flow(api_token, lesson_id)
            assert resp.status_code == 200, \
                f"重置流程应 200，实际 {resp.status_code}：{resp.text[:300]}"
            assert (resp.json() or {}).get("code") == 0, "重置业务码应为 0"
            kinds2, saved2 = _flow_kinds(lesson_api, api_token, lesson_id)
            # 关键断言：重置是“丢弃保存”不是“写入默认”，所以 saved 必回 False
            assert saved2 is False, \
                f"重置后 saved 应回到 False（保存记录被硬删），实际={saved2}"
            assert "rollcall" not in (kinds2 or []), \
                f"重置后自定义步 rollcall 应消失，实际={kinds2}"
            assert kinds2 == base_kinds, \
                f"重置后应等于重置前的默认步序 {base_kinds}，实际={kinds2}"
    finally:
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")


@allure.feature("接口E2E-上课状态机")
@allure.story("下课后流程进入只读（400/40003）且重复下课幂等")
@pytest.mark.lesson_e2e
def test_flow_readonly_after_ended(course_api, lesson_api, api_token):
    """状态守卫：走完整条状态机到 ended 后，改流程的两条写入口（PUT/DELETE）都应及时拒
    源码依据 save_flow/reset_flow 开头都有：status==ENDED → STATE_NOT_ALLOWED(40003)
      “这一讲已经下课，流程不能再改”——两个入口守卫应一致，这本身就是要测的点
      （只改一处、漏另一处是这类守卫最常见的一致性缺陷）。
    同行附带断一条：router 注释写了 end “对已结束的课堂幂等成功”，所以重复 end 应仍是 200。
    依赖环境：需测试老师当下无其他 ongoing 课堂，否则 start 撞 409 → skip（不是产品 bug）。
    """
    course_id, course_name = _make_sandbox_course(course_api, api_token)
    lesson_id = None
    ended = False

    try:
        with allure.step("建讲次并跑到 ended（draft→ongoing→ended）"):
            resp = lesson_api.create_lesson(
                api_token, course_id, title="AT 下课只读", week_no=1, weekday=3, period="78")
            assert resp.status_code == 200, f"建讲次应 200，实际 {resp.status_code}：{resp.text[:300]}"
            lesson_id = _data(resp).get("id")
            base_steps = _data(lesson_api.get_flow(api_token, lesson_id)).get("steps")

            r = lesson_api.start_lesson(api_token, lesson_id)
            if r.status_code == 409:
                pytest.skip("测试老师已有进行中真实课堂，本用例需空闲环境（先下课或换账号）："
                            f"{(r.json() or {}).get('message', '')}")
            assert r.status_code == 200, f"start 应 200，实际 {r.status_code}：{r.text[:300]}"
            r = lesson_api.end_lesson(api_token, lesson_id)
            assert r.status_code == 200, f"end 应 200，实际 {r.status_code}：{r.text[:300]}"
            ended = True
            assert _status(lesson_api.get_lesson(api_token, lesson_id)) == "ended"

        with allure.step("重复 end：应幂等成功（源码声明），不是报错也不是 409"):
            r = lesson_api.end_lesson(api_token, lesson_id)
            assert r.status_code == 200, \
                f"已结束的讲次重复 end 应幂等 200，实际 {r.status_code}：{r.text[:300]}"
            assert _status(lesson_api.get_lesson(api_token, lesson_id)) == "ended", \
                "重复下课不应改变状态"

        with allure.step("ended 后 PUT flow：应被状态守卫拒 400/40003"):
            bad = [{"kind": "signin"}, {"kind": "rollcall"}, {"kind": "end"}]
            r = lesson_api.put_flow(api_token, lesson_id, {"steps": bad})
            assert r.status_code == 400, \
                f"下课后代改流程应 400，实际 {r.status_code}：{r.text[:300]}"
            body = r.json() or {}
            assert body.get("code") == 40003, \
                f"业务码应为 40003(当前状态不允许)，实际={body.get('code')}"

        with allure.step("ended 后 DELETE flow：另一入口守卫应一致，同样 400/40003"):
            r = lesson_api.reset_flow(api_token, lesson_id)
            assert r.status_code == 400, \
                f"下课后重置流程应同样被拒(400)，实际 {r.status_code}：{r.text[:300]}"
            assert (r.json() or {}).get("code") == 40003, \
                f"重置入口业务码也应为 40003，实际={(r.json() or {}).get('code')}"

        with allure.step("两个入口被拒后，流程应还是下课前的内容（拒了不能partial写入）"):
            kinds2, _ = _flow_kinds(lesson_api, api_token, lesson_id)
            base_kinds = [s.get("kind") for s in base_steps if isinstance(s, dict)]
            assert kinds2 == base_kinds, \
                f"被拒的写不应改变流程，下课基准={base_kinds}，实际={kinds2}"
    finally:
        # 本用例已走到 ended（或 start 前就挂）→ 不会有僵尸 ongoing；仅当 start 后、end 前异常才需补下课
        if lesson_id and not ended:
            try:
                if _status(lesson_api.get_lesson(api_token, lesson_id)) == "ongoing":
                    lesson_api.end_lesson(api_token, lesson_id)
            except Exception as e:
                logging.getLogger("autotest").warning(f"[补下课失败 id={lesson_id}] {e}")
        if course_id:
            with allure.step("收尾：归档自建沙箱课"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    logging.getLogger("autotest").warning(
                        f"[lesson_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")


if __name__ == "__main__":
    pytest.main(["-v", "-s", "-m", "lesson_e2e", __file__])
