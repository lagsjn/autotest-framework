"""
端到端冒烟用例（第一站）：课程列表 → 点课程卡片 → 抵达课程详情页
定位器侦察结论（2026-10-31）：
- 卡片是 <button class="tp-spot">，用 config.COURSE_NAME 的文字锁定身份
- 点击后 URL 变为 /courses/<数字id>，断言用正则不写死 id
- ⚠ SPA 路由切换滞后于点击：URL 断言前必须智能等待（首跑就栽在抢跑上）
- 落地地标：绿色"进入上课工作台"按钮
- "正在上课"状态提示：工作台入口的副作用未评估，本用例暂不点进第二站
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

    # 到站断言 1：等 URL 跳到 /courses/<数字id>（最多等 10 秒，一到就往下走）
    final_url = course.wait_url_matches(r"/courses/\d+")
    print("进入课程后的真实 URL：", final_url or fresh_page.current_url)
    assert final_url, \
        f"点击后 10 秒内未跳转到课程详情页，停在：{fresh_page.current_url}"

    # 到站断言 2：详情页地标元素出现
    assert course.is_element_exist(course.workbench_entry_btn, timeout=10), \
        "详情页没有'进入上课工作台'地标按钮（页面没加载对？）"
