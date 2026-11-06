"""
L4 课堂控制台只读巡礼（🟢 绿级）
安全边界（业务流程地图 §12 定性表）：只点 tp-bc-sub-btn 子导航和关抽屉，
面板内部的 下课/发布测验/立即发布/编辑/AI生成 一律不碰——红黄级元素
侦察结论（probe_console.py 2026-11-04）：
- 进入工作台为同页跳转，URL=/lessons/<数字id>，断言用正则不写死 id
- 子导航十项，默认"控制台"激活（is-active）
- 进入时可能自带打开状态的抽屉，先关闭再巡礼
"""
import allure
import pytest

from pages.course_page import CoursePage
from pages.console_page import ConsolePage

# "控制台"放最后：其余九个面板都巡完再回默认面板，顺带验证"回得去"
SUB_TABS = ["签到", "大屏", "点名", "弹幕", "提问", "讨论", "评分",
            "质量报告", "课后报告", "控制台"]

# 冒烟只选一条代表巡礼项（标签贴在单个参数上，不是整个函数）：
# 全贴会把冒烟集从 5 条膨胀到 15 条，失去"每次构建快速把关"的意义；
# 选"控制台"：默认就在它上面，再点一次还能验证"选中态不丢+回得去"
SMOKE_TAB = "控制台"
TAB_PARAMS = [pytest.param(t, marks=pytest.mark.smoke) if t == SMOKE_TAB else t
              for t in SUB_TABS]


def _enter_workbench(fresh_page):
    """入场链路全绿级：列表 -> 课程详情（老师已确认进工作台安全）-> 处理抽屉"""
    course = CoursePage(fresh_page)#先进去课程页面
    assert course.is_element_exist(course.enter_course_btn, timeout=10), \
        "起点不对：课程列表找不到目标课程卡片"
    course.enter_course()
    assert course.wait_url_matches(r"/courses/\d+"), "进不去课程详情页"

    course.click_element(course.workbench_entry_btn)
    console = ConsolePage(fresh_page)
    assert console.wait_url_matches(r"/lessons/\d+"), \
        f"点了进入工作台但未到达 /lessons/<id>，停在：{fresh_page.current_url}"

    # 抽屉现场快照是打开态；出现就关掉（短等待探测：2 秒没看见就认为没弹）
    # 注意必须用 visibility（看得见）而不是 presence（DOM 里有）：
    # 抽屉没弹时关闭按钮也预挂在 DOM 上，presence 会误报存在然后去点它，等死 10 秒
    if console.is_element_visible(console.drawer_close_btn, timeout=2):
        console.click_element(console.drawer_close_btn)
    return console


@allure.feature("课堂模块")
@allure.story("L4 控制台只读巡礼")
@pytest.mark.parametrize("tab_name", TAB_PARAMS)
def test_l4_console_tour(fresh_page, tab_name):
    console = _enter_workbench(fresh_page)

    with allure.step(f"点击子导航：{tab_name}"):
        console.click_element(console.sub_btn(tab_name))

    with allure.step("断言该面板自证选中态"):
        assert console.is_sub_active(tab_name), f"子导航【{tab_name}】没挂 is-active"

    with allure.step("断言仍停留在课堂（切面板不应跳走）"):
        assert console.wait_url_matches(r"/lessons/\d+"), \
            f"点【{tab_name}】后跳离了课堂：{fresh_page.current_url}"
