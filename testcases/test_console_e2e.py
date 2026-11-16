"""
L4 课堂回放页只读巡礼（🟢 绿级）—— 2026-11-14 随界面改版重写
侦察情报来源：script/probe_l4_console_v2.py 实测（旧 probe_console.py 2026-11-04 的
"工作台十项子导航"UI 已随改版不可见，实时工作台待开课后再侦察，见业务流程地图 §13.5）
- 入场：课程列表点演示课卡片，直达当前讲次回放页 /lessons/<id>（两次实测均直接落）
- 新版巡览模型：回放主页 + 7 个路径式子页面（a.llink 入口 -> /lessons/<id>/<段>），
  独立路由页面没有"选中态"可断，双保险改成 ①到站 URL 正则 ②页面框架地标（面包屑）
- 安全边界：只点导航链接；子页面内部（如 /manage 的布置/发布、出勤页的标为请假）
  一律不碰——那是黄级写操作
- 用例条数 10 -> 8（主页 1 + 巡礼站 7），--co 总数会相应减 2，属预期不是丢用例
"""
import allure
import pytest

from pages.course_page import CoursePage
from pages.console_page import ConsolePage

# (入口文字关键词, URL 尾段正则)
# 冒烟只选一条代表站（标签贴单个参数上）：选"出勤明细"——回放页最核心的数据面
REPLAY_PARAMS = [
    pytest.param("出勤明细", r"attendance", marks=pytest.mark.smoke, id="attendance"),
    pytest.param("本讲评分", r"scoreboard", id="scoreboard"),
    pytest.param("学生提问", r"questions", id="questions"),
    pytest.param("讨论记录", r"discussions", id="discussions"),
    pytest.param("课堂质量报告", r"quality-report", id="quality"),
    pytest.param("课后学情报告", r"class-report", id="class-report"),
    pytest.param("管理随堂测与作业", r"manage", id="manage"),
]


def _enter_replay(fresh_page):
    """入场：点课程卡片直达当前讲次回放页，返回 ConsolePage
    为什么不调 CoursePage.enter_course：那条路会把落点扳回课程详情页（给 L2/L3 用），
    本用例要的恰恰是"当前讲次页"这个落点本身
    """
    course = CoursePage(fresh_page)
    assert course.is_element_exist(course.enter_course_btn, timeout=10), \
        "起点不对：课程列表找不到目标课程卡片"
    course.click_element(course.enter_course_btn)
    url = course.wait_url_matches(r"/lessons/\d+")
    assert url, \
        f"点卡片没落到当前讲次回放页，停在：{fresh_page.current_url}（该课还有讲次吗？）"
    console = ConsolePage(fresh_page)
    assert console.is_element_exist(console.crumb_marker, timeout=10), \
        "回放页框架（面包屑）没渲染（页面没加载对？又改版了？）"
    return console


@allure.feature("课堂模块")
@allure.story("L4 回放页只读巡礼")
def test_l4_replay_landing(fresh_page):
    """落点主页：框架地标在 + 七个巡览入口齐全（缺一个都算红）"""
    console = _enter_replay(fresh_page)

    with allure.step("断言七个巡览入口全部可见"):
        # REPLAY_PARAMS 元素是 pytest.param(...) 包出来的 ParameterSet（values/marks/id 三字段的
        # NamedTuple），不是裸二元组；被 @pytest.mark.parametrize 用时 pytest 会自动拆 values，
        # 但这里是自己手写循环遍历，必须显式取 .values，否则直接解包会按 3 元组去拆 2 个变量报错
        missing = [name for name, _ in (p.values for p in REPLAY_PARAMS)
                   if not console.is_element_exist(console.lesson_link(name), timeout=3)]
        assert not missing, f"回放页缺少巡览入口：{missing}"


@allure.feature("课堂模块")
@allure.story("L4 回放页只读巡礼")
@pytest.mark.parametrize("link_name,url_seg", REPLAY_PARAMS)
def test_l4_replay_tour(fresh_page, link_name, url_seg):
    console = _enter_replay(fresh_page)

    with allure.step(f"点击巡览入口：{link_name}"):
        console.click_element(console.lesson_link(link_name))

    with allure.step(f"等 URL 落到 /lessons/<id>/{url_seg}"):
        # $ 锚点：必须正好停在这段路由，不能被重定向到别站
        final_url = console.wait_url_matches(rf"/lessons/\d+/{url_seg}$")
        assert final_url, \
            f"点了【{link_name}】但 URL 不符预期，停在：{fresh_page.current_url}"

    with allure.step("断言页面框架仍在（双保险：没跳出站、框架渲染完整）"):
        # 独立路由页没有页签式"选中态"可查，用面包屑证明真的渲染出了目标页框架；
        # 各子页面的内容级地标待后续侦察后再补强
        assert console.is_element_exist(console.crumb_marker, timeout=10), \
            f"URL 到站但【{link_name}】页框架没渲染（空白页/报错页？）"
