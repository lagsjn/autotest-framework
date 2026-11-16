"""
端到端冒烟用例（第一站）：课程列表 → 点课程卡片 → 抵达课程详情页
定位器侦察结论（2026-10-31，2026-11-14 随改版更新）：
- 卡片是 <button class="tp-spot">，用 config.COURSE_NAME 的文字锁定身份
- 该课有进行中/已结束讲次时，点卡片落当前讲次页 /lessons/<id>（产品设计）；
  CoursePage.enter_course() 内部靠面包屑扳回详情页，用例层断言仍锁 /courses/<数字id>
- ⚠ SPA 路由切换滞后于点击：URL 断言前必须智能等待（首跑就栽在抢跑上）
- 落地地标（2026-11-14 改版后）：课程专属页签栏 nav.cb__tabs（概览/课表/…），
  旧地标"进入上课工作台"按钮已随界面改版消失
"""
import allure
import pytest

from pages.course_page import CoursePage


@allure.feature("课程模块")
@allure.story("端到端：进入课程")
@pytest.mark.smoke
def test_e2e_enter_course(fresh_page):
    course = CoursePage(fresh_page)

    # 出发前确认起点：目标课程卡片可见
    assert course.is_element_exist(course.enter_course_btn, timeout=10), \
        "起点不对：课程列表找不到目标课程卡片"

    course.enter_course()

    # 到站断言 1：等 URL 跳到 /courses/<数字id>（enter_course 已保证把
    # "落错站（当前讲次页）"扳回详情页，这里断言不放宽）
    final_url = course.wait_url_matches(r"/courses/\d+")
    print("进入课程后的真实 URL：", final_url or fresh_page.current_url)
    assert final_url, \
        f"点击后未跳转到课程详情页，停在：{fresh_page.current_url}"

    # 到站断言 2：详情页地标元素出现（2026-11-14 改版：页签栏取代旧工作台按钮）
    assert course.is_element_exist(course.detail_tabs_nav, timeout=10), \
        "详情页没有课程页签栏地标（页面没加载对？又改版了？）"
