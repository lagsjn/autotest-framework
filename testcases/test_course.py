"""
课程模块冒烟用例：验证"登录态复用"这套提速机制本身
两条用例都只"看"不"点"，零副作用，可反复跑
"""
import allure

from pages.course_page import CoursePage


@allure.feature("课程模块")
@allure.story("课程列表加载")
def test_enter_course_button_exists(logged_in_driver):
    """登录后课程页应出现「进入课程」按钮（证明：登录态真的被继承到了）"""
    course = CoursePage(logged_in_driver)
    assert course.is_element_exist(course.enter_course_btn, timeout=10), \
        "登录后没看到进入课程按钮（登录态失效/页面改版/绝对XPath定位器过期）"


@allure.feature("课程模块")
@allure.story("课程列表加载")
def test_enter_course_button_text(logged_in_driver):
    """按钮不光要在，还得有非空文案（同一次登录态，第二条用例零成本复用）"""
    course = CoursePage(logged_in_driver)
    text = course.wait_text_not_empty(course.enter_course_btn, timeout=10)
    assert text, "进入课程按钮存在但文案为空（渲染异常）"

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