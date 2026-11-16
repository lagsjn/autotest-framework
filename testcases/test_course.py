"""
课程模块冒烟用例：验证"登录态复用"这套提速机制本身
两条用例都只"看"不"点"，零副作用，可反复跑
事故档案（2026-11-14 清理）：仓库里曾粘贴过一对同名的 fresh_page 版用例，
Python 后定义覆盖先定义，logged_in_driver 版从未被收集执行过，已删重名；
现存两条改用 fresh_page：同一个 session 浏览器（登录态照样复用，不增登录成本），
但每条用例前多一步"页面归位"——直接用 logged_in_driver 会停在上一条用例
遗留的页面（首跑就因此红：页面停在工作台找不到列表卡片），位置残留必须归零。
教训：函数重名 pytest 不报错只静默丢用例，改完必须 --co 核对条数（见记忆档案）
"""
import allure

from pages.course_page import CoursePage


@allure.feature("课程模块")
@allure.story("课程列表加载")
def test_enter_course_button_exists(fresh_page):
    """登录后课程页应出现「进入课程」按钮（证明：登录态真的被继承到了）"""
    course = CoursePage(fresh_page)
    assert course.is_element_exist(course.enter_course_btn, timeout=10), \
        "登录后没看到进入课程按钮（登录态失效/页面改版/绝对XPath定位器过期）"


@allure.feature("课程模块")
@allure.story("课程列表加载")
def test_enter_course_button_text(fresh_page):
    """按钮不光要在，还得有非空文案（同一次登录态，第二条用例零成本复用）"""
    course = CoursePage(fresh_page)
    text = course.wait_text_not_empty(course.enter_course_btn, timeout=10)
    assert text, "进入课程按钮存在但文案为空（渲染异常）"
