"""
L3 只读巡礼用例：课程详情页四页签遍历（🟢 绿级，无任何写入，见业务流程地图 §7）
侦察情报来源：script/probe_tabs.py 实测（2026-11-01）
- 可点页签 = BUTTON.tp-bc-sub-btn（定位器已固化在 CoursePage）
- 路由型页签：点击后 URL 追加 ?tab=materials/analytics/members
- 课表排期是默认页签：激活态 = 裸 URL /courses/<id>，不带 tab 参数
- 断言双保险：① 等 URL（治 SPA 路由滞后，禁 sleep）② 页签按钮 class 自证 is-active
- 每个页签一条独立用例（parametrize 数据驱动）：fresh_page 保证各自从列表页重新出发
"""
import allure
import pytest

from pages.course_page import CoursePage

# (页签名, 定位器, 预期 URL 正则)
# 正则里的 $ 是锚点："必须以……结尾"——裸 /courses/14 才算过，
# 万一 ?tab=xxx 残留没被洗掉，$ 立刻抓现行
TAB_CASES = [
    pytest.param("资料归档", CoursePage.materials_tab_btn,
                 r"tab=materials", id="materials"),
    pytest.param("学情看板", CoursePage.analytics_tab_btn,
                 r"tab=analytics", id="analytics"),
    pytest.param("班级成员", CoursePage.members_tab_btn,
                 r"tab=members", id="members"),
    pytest.param("课表排期", CoursePage.schedule_tab_btn,
                 r"/courses/\d+$", id="schedule-default"),
]


def _enter_course_detail(fresh_page):
    """L2 已验证的入场链路，打包成步助（step helper）：列表 → 点卡片 → 到详情页"""
    course = CoursePage(fresh_page)
    assert course.is_element_exist(course.enter_course_btn, timeout=10), \
        "起点不对：课程列表找不到目标课程卡片"
    course.enter_course()
    assert course.wait_url_matches(r"/courses/\d+"), \
        f"进不去课程详情页，停在：{fresh_page.current_url}"
    return course


@allure.feature("课程模块")
@allure.story("L3 页签只读巡礼")
@pytest.mark.parametrize("tab_name,tab_btn,expect_url", TAB_CASES)
def test_l3_tab_tour(fresh_page, tab_name, tab_btn, expect_url):
    course = _enter_course_detail(fresh_page)

    with allure.step(f"点击页签：{tab_name}"):
        # 课表排期这条点下去是"无害空点"（进详情页它就默认激活），
        # 换来四条用例同一个动作模型，不为此单独写分支
        course.click_element(tab_btn)

    with allure.step(f"等 URL 落到预期：{expect_url}"):
        final_url = course.wait_url_matches(expect_url)
        assert final_url, \
            f"点了【{tab_name}】但 URL 不符预期，停在：{fresh_page.current_url}"

    with allure.step(f"断言【{tab_name}】自证选中态"):
        # 先等 URL 再查 is-active：URL 变了说明前端这一轮渲染大概率完成，
        # 此刻读状态不易读到"切换进行中"的中间态
        assert course.is_tab_active(tab_btn), \
            f"URL 已到站但【{tab_name}】没挂 is-active——页面状态机不同步？值得提 bug"
