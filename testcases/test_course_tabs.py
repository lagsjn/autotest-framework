"""
L3 只读巡礼用例：课程详情页页签遍历（🟢 绿级，无任何写入，见业务流程地图 §7）
侦察情报来源：script/probe_l3_tabs_v2.py 实测（2026-11-14，随界面改版重写；
旧版 probe_tabs.py 2026-11-01 的 tp-bc-sub-btn/?tab=materials 情报已随改版作废）
- 页签 = a.cb__tab（router-link 真链接），定位器工厂 CoursePage.tab_btn(name)
- URL 形态混用（实测）：?tab=lessons/analytics/members 参数式 + 裸 URL 默认页（概览）；
  本轮不纳入 /resources、/settings 两个新页签：菜单文字"成员 50"证明人数会变，
  同理 /resources 里可能出现"备课资源 3"这种带计数文字，前缀匹配需随实跑验证，
  先把四个老对应用例恢复绿，新页签覆盖另开一轮补
- 断言双保险：① 等 URL（治 SPA 路由滞后，禁 sleep）② 页签自证 is-on/is-active
- 每个页签一条独立用例（parametrize 数据驱动）：fresh_page 保证各自从列表页重新出发
- ⚠ 页签名与旧版对应关系（菜单重命名）：课表排期→课表、学情看板→学情、
  班级成员→成员；"资料归档(materials)"已被"备课资源(/resources)"取代，故本轮只剩四条
"""
import allure
import pytest

from pages.course_page import CoursePage

# (页签前缀名, 预期 URL 正则)
# 正则里的 $ 是锚点："必须以……结尾"——裸 /courses/14 才算过，
# 万一 ?tab=xxx 残留没被洗掉，$ 立刻抓现行
TAB_CASES = [
    pytest.param("课表", r"tab=lessons", id="lessons"),
    pytest.param("学情", r"tab=analytics", id="analytics"),
    pytest.param("成员", r"tab=members", id="members"),
    pytest.param("概览", r"/courses/\d+$", id="overview-default"),
]


def _enter_course_detail(fresh_page):
    r"""L2 已验证的入场链路，打包成步助（step helper）：列表 → 点卡片 → 到详情页
    （enter_course 内部已把"落当前讲次页"的分支消化掉，这里照旧锁 /courses/\d+）"""
    course = CoursePage(fresh_page)
    assert course.is_element_exist(course.enter_course_btn, timeout=10), \
        "起点不对：课程列表找不到目标课程卡片"
    course.enter_course()
    assert course.wait_url_matches(r"/courses/\d+"), \
        f"进不去课程详情页，停在：{fresh_page.current_url}"
    # 页签栏是详情页地标，等它出现再动手（防 Vue 异步渲染抢跑）
    assert course.is_element_exist(course.detail_tabs_nav, timeout=10), \
        "详情页页签栏没出现（页面没加载对？又改版了？）"
    return course


@allure.feature("课程模块")
@allure.story("L3 页签只读巡礼")
@pytest.mark.smoke
@pytest.mark.parametrize("tab_name,expect_url", TAB_CASES)
def test_l3_tab_tour(fresh_page, tab_name, expect_url):
    course = _enter_course_detail(fresh_page)

    with allure.step(f"点击页签：{tab_name}"):
        # 概览这条点下去是"无害空点"（进详情页它就默认激活），
        # 换来四条用例同一个动作模型，不为此单独写分支
        final_url = course.click_tab(tab_name, expect_url)

    with allure.step(f"等 URL 落到预期：{expect_url}"):
        assert final_url, \
            f"点了【{tab_name}】但 URL 不符预期，停在：{fresh_page.current_url}"

    with allure.step(f"断言【{tab_name}】自证选中态"):
        # 先等 URL 再查选中态：URL 变了说明前端这一轮渲染大概率完成，
        # 此刻读状态不易读到"切换进行中"的中间态
        assert course.is_tab_active(tab_name), \
            f"URL 已到站但【{tab_name}】没挂选中态类——页面状态机不同步？值得提 bug"
