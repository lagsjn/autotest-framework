"""
L5 跨端链路：老师建课 → 读邀请码 → 学生凭码加入 → 断言学生可见
架构里程碑：本用例第一次同时驱动两个浏览器会话——
  fresh_page（老师 8081，session 级登录态复用）+ fresh_student_page（学生 8082）
副作用分级：建课🟡、加入🟡（均为写操作）；课程名带 AT-L5-<时间戳> 前缀唯一可辨
运行方式：默认 addopts 已排除 l5，需专门 `pytest -m l5` 才执行；不进冒烟/常规回归
清理：建课提交会自动跳详情页+弹排课引导，create_course 已强制回列表；收尾自动归档（详情页更多→归档课程→el-message-box 确定）
"""
import logging
import time

import allure
import pytest

from config import HAS_STUDENT, STUDENT_BASE_URL
from pages.course_page import CoursePage
from pages.student_page import StudentPage

# 两条门同时挂：没配学生端就整条跳过；即使配了也只在显式 -m l5 时才执行
pytestmark = [
    pytest.mark.skipif(not HAS_STUDENT,
                       reason="未配置学生端账号/入口（TEST_STUDENT_*），跳过跨端用例"),
    pytest.mark.l5,
]


@allure.feature("跨端模块")
@allure.story("L5 老师建课-学生加入")
def test_l5_teacher_create_student_join(fresh_page, fresh_student_page):
    # 唯一课程名：时间戳保证每次新建、可重跑（加入不可逆，复用旧课第二次必挂）
    course_name = f"AT-L5-{time.strftime('%m%d%H%M%S')}"
    teacher = CoursePage(fresh_page)
    student = StudentPage(fresh_student_page)

    teacher.create_course(course_name)  # 先建课：建成功之后才需要清理
    try:
        with allure.step(f"老师端：确认课程 {course_name} 已创建"):
            assert teacher.is_element_visible(teacher.course_card(course_name)), \
                "建课后课程卡片没出现"

        with allure.step("老师端：从课程卡片读取邀请码"):
            code = teacher.read_invite_code(course_name)
            assert code, f"未能从课程卡片解析出【{course_name}】的邀请码"

        with allure.step(f"学生端：用邀请码 {code} 加入课程"):
            student.open_join_page()
            student.join_by_code(code)

        with allure.step("学生端：回到我的课程，断言已加入"):
            student.driver.get(STUDENT_BASE_URL)
            assert student.is_in_my_courses(course_name), \
                f"学生加入后'我的课程'仍看不到 {course_name}"
    finally:
        # 收尾：无论中间断言成败，都把本次自建的课归档（黄级写操作，仅针对 AT-L5-*）
        # 为什么放 finally：不让"用例失败"变成"环境残留垃圾课"——清理必须无条件执行
        # 为什么又包 try/except：清理本身若报错，不能盖掉 try 里最初的真实失败原因
        # （否则 pytest 只报 finally 的异常，你永远猜不到主流程到底哪步挂了）
        with allure.step("收尾：老师端归档本次自建课程"):
            try:
                teacher.archive_course(course_name)
            except Exception as e:
                logging.getLogger("autotest").warning(
                    f"[L5 清理失败，可能残留课程 {course_name}，需手动归档] {e}")
