"""
接口端到端串联（API E2E）：登录 → 建课 → 查详情 → 学生加入 → 学生列表 → 班级成员 → 归档
和 UI 的 L5 是同一条业务链路，区别是全程不发一个浏览器请求：
  UI L5  花 30 秒开两个 Edge、等动画、找按钮；本用例几秒跑完，且每一步断言都打在数据结构上
定位依据全部来自实测（script/probe_api_bundle.py + probe_api_course_write*.py），不是照手册推的：
  建课只要 name；返回体直接给 id 与 invite_code；重复加入幂等；归档=软删；归档后旧码 404/40401
副作用纪律（为什么默认被 -m "not api_e2e" 排除）：
  ① 会真实建一门课，课程名 AT-API-<时间戳> 唯一可认；
  ② 收尾无条件归档（本项目的清理手段=软删），中途断言挂了也照样清理；
  ③ 清理调用包 try/except：finally 里抛异常会盖掉主流程真实失败原因（L5 踩过的坑）；
  ④ 绝不调用 DELETE /courses/{id}/permanent（永久删除不可恢复）。
"""
import logging
import time

import allure
import pytest

from config import HAS_STUDENT, STUDENT_USERNAME


def _data(resp):
    """取返回体的 data，并挡住"类型会变"这一类坑（实测：成功=dict，参数错=list，拒绝=null）
    不是 dict 就返回 None，让调用方去 assert，而不是在这里 .get 炸一个 AttributeError
    """
    data = (resp.json() or {}).get("data") if resp.text else None
    return data if isinstance(data, dict) else None


def _items(resp):
    """从分页接口返回体里取 items（同样带类型防御：data 不是 dict 时视为拿不到）"""
    data = _data(resp)
    if not data:
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


@allure.feature("接口E2E-课程全生命周期")
@allure.story("老师建课到学生加入再到归档")
@pytest.mark.skipif(not HAS_STUDENT, reason=".env 未配置 TEST_STUDENT_*（学生端），接口 E2E 跳过")
@pytest.mark.api_e2e
def test_api_course_lifecycle_e2e(course_api, student_course_api, api_token, api_student_token):
    """七步串联：每一步都断在"接口给的客观事实"上，且下一步依赖上一步的产出（id/邀请码）
    这种"数据跨步骤传递"的写法是接口 E2E 的核心：一旦中间某步没真落库，后面立刻断不上
    """
    # 唯一课程名：系统实测允许同名课程，所以名字只是"给人看的标签"，锁定一律用 id
    course_name = f"AT-API-{time.strftime('%m%d%H%M%S')}"
    course_id = None
    archived = False

    with allure.step(f"老师端建课：POST /courses name={course_name}"):
        resp = course_api.create_course(api_token, course_name)
        assert resp.status_code == 200, \
            f"建课应 200，实际 {resp.status_code}：{resp.text[:300]}"
        body = resp.json()
        assert body.get("code") == 0, f"建课业务码应为 0，实际 {body.get('code')}：{body.get('message')}"
        data = _data(resp)
        assert data, f"建课成功却没有返回课程对象：{resp.text[:300]}"
        # 建课返回体就带主键和邀请码——后面六步全靠这两个值往下传
        course_id, invite_code = data.get("id"), data.get("invite_code")
        assert course_id, f"返回体没有 id，无法继续锁定本课：{resp.text[:300]}"
        assert data.get("status") == "active", \
            f"新建课程初始状态应为 active（进行中），实际 {data.get('status')}"
        assert invite_code and len(invite_code) == 6, \
            f"邀请码应为 6 位，实际 {invite_code!r}（手册规则：6 位邀请码）"

    try:
        with allure.step("老师端查详情：库里存的必须就是刚建的那门课"):
            resp = course_api.get_course(api_token, course_id)
            assert resp.status_code == 200, f"查详情应 200，实际 {resp.status_code}"
            detail = _data(resp) or {}
            # 三条一致性：建课返回的值 == 库里的值，防"返回体是临时对象、没真落库"
            assert detail.get("id") == course_id, f"详情 id 不匹配：{detail.get('id')}"
            assert detail.get("name") == course_name, \
                f"详情课程名不符：期望 {course_name!r} 实际 {detail.get('name')!r}"
            assert detail.get("invite_code") == invite_code, \
                f"详情邀请码与建课返回不一致：{detail.get('invite_code')!r} vs {invite_code!r}"

        with allure.step(f"学生端凭邀请码 {invite_code} 加入课程"):
            resp = student_course_api.join_course(api_student_token, invite_code)
            assert resp.status_code == 200, \
                f"学生加入应 200，实际 {resp.status_code}：{resp.text[:300]}"
            body = resp.json()
            assert body.get("code") == 0, f"加入业务码应为 0，实际 {body.get('code')}：{body.get('message')}"
            assert (_data(resp) or {}).get("id") == course_id, "加入返回的不是本课"

        with allure.step("学生端我的课程列表里必须出现本课（按 id 断，不按名字）"):
            resp = student_course_api.list_courses(api_student_token)
            ids = {c.get("id") for c in _items(resp)}
            assert course_id in ids, \
                f"学生列表看不到本课 id={course_id}（现有 ids={sorted(ids)}）——加入没生效？"

        with allure.step(f"老师端班级成员里必须有 {STUDENT_USERNAME}（加人的权威证据）"):
            resp = course_api.list_members(api_token, course_id)
            members = _items(resp)
            nos = [m.get("student_no") for m in members]
            assert STUDENT_USERNAME in nos, \
                f"成员表里没有 {STUDENT_USERNAME}（实际={nos}）——学生列表有课但成员没落库，数据不一致"
            joined = [m for m in members if m.get("student_no") == STUDENT_USERNAME]
            assert all(m.get("status") == "joined" for m in joined), \
                f"成员状态应为 joined，实际={[m.get('status') for m in joined]}"

        with allure.step("老师端归档本课（DELETE=软删，本项目清理手段）"):
            resp = course_api.archive_course(api_token, course_id)
            assert resp.status_code == 200, \
                f"归档应 200，实际 {resp.status_code}：{resp.text[:300]}"
            assert (_data(resp) or {}).get("status") == "archived", \
                f"归档返回体状态应为 archived，实际={(_data(resp) or {}).get('status')}"
            archived = True

        with allure.step("归档后详情仍可读到且状态为 archived（坐实是软删、不是删库）"):
            resp = course_api.get_course(api_token, course_id)
            assert resp.status_code == 200, \
                f"归档后详情应仍可读（软删），实际 {resp.status_code}：{resp.text[:200]}"
            assert (_data(resp) or {}).get("status") == "archived", \
                f"归档后状态应留档为 archived，实际={(_data(resp) or {}).get('status')}"

        with allure.step("归档后旧邀请码再加入必须被拒（404/40401，实测）"):
            resp = student_course_api.join_course(api_student_token, invite_code)
            assert resp.status_code == 404, \
                f"已归档课程加入应被拒(404)，实际 {resp.status_code}——归档失效，学生还能进已结束的课"
            assert (resp.json() or {}).get("code") == 40401, \
                f"业务码应为 40401(邀请码无效或课程不存在)，实际={(resp.json() or {}).get('code')}"
    finally:
        # 收尾：只要课建出来了就必须归档，不给环境留"进行中"的垃圾课
        # archived 标记避免重复 DELETE（同一门课第二次归档的行为没实测，不拿未实测行为当清理手段）
        if course_id and not archived:
            with allure.step("收尾：主流程失败也要归档自建课程"):
                try:
                    course_api.archive_course(api_token, course_id)
                except Exception as e:
                    # 只留痕不上抛：在这里抛异常会把 try 里第一条真实失败原因整个盖掉，
                    # 报出来的将是清理的错，你永远猜不到主流程到底哪步挂（L5 踩过的坑）
                    logging.getLogger("autotest").warning(
                        f"[api_e2e 清理失败，需手动归档 id={course_id} name={course_name}] {e}")
                    allure.attach(f"{e}\n待手动归档：id={course_id} name={course_name}",
                                  name="清理失败留痕",
                                  attachment_type=allure.attachment_type.TEXT)


@allure.feature("接口E2E-分页参数边界")
@allure.story("page_size 超限被参数校验拦截")
def test_api_page_size_over_limit(course_api, api_token):
    """绿级只读：page_size 上限实测 100，101 就该被参数校验关拦下（400/40001）
    为什么单独钉一条：这条把"同一字段类型会随分支变"的教训固化成断言——
    参数错时 data 是 list（字段错误明细），不是 dict，取值不做类型防御就会当场崩
    （本轮侦察脚本就是被 page_size=200 撞崩过一次）
    """
    resp = course_api.list_courses(api_token, page_size=101)

    assert resp.status_code == 400, \
        f"超限分页参数应被拒(400)，实际 {resp.status_code}：{resp.text[:200]}"
    body = resp.json()
    assert body.get("code") == 40001, f"业务码应为 40001(参数校验失败)，实际 {body.get('code')}"
    # 关键取证：错误分支下 data 是 list 且带着"哪个字段、错在哪"
    assert isinstance(body.get("data"), list), \
        f"参数校验错误的 data 应是字段错误列表，实际类型 {type(body.get('data')).__name__}"
    assert body["data"] and body["data"][0].get("field") == "page_size", \
        f"应指明出错字段是 page_size，实际={body['data']}"


if __name__ == "__main__":
    pytest.main(["-v", "-s", "-m", "api_e2e or not api_e2e", __file__])
