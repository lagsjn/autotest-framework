"""
学生端页面（L5 跨端：demo_student 走 8082）
侦察依据 probe_l5_student.py（2026-11-07 实测）：
- 登录后落地 /courses；底部导航"加入"→ /join；列表页右上角也有"加入课程"按钮(tp-cta)
- 加入页：邀请码框 placeholder='输入 6~8 位课程邀请码' maxlength=8；
          确认按钮文字"确认加入课程" class 含 tp-cta；返回按钮 tp-course-back
纪律：本页面只承载"凭邀请码加入"这条绿/黄级链路；二维码加入、剪贴板粘贴暂不驱动
"""
from selenium.webdriver.common.by import By

from base.base_page import BasePage
from config import TIMEOUT


class StudentPage(BasePage):
    # 进入"加入课程"页的入口（列表页右上角按钮，文字"加入课程"）
    join_entry_btn = (By.XPATH, "//button[contains(., '加入课程')]")
    # 加入页的邀请码输入框：用 placeholder 含"邀请码"锁定
    # 为什么不用精确 placeholder？文案里"6~8/6-8"这种符号口径易变，含关键词更稳
    code_input = (By.XPATH, "//input[contains(@placeholder, '邀请码')]")
    # 确认加入按钮（文字"确认加入课程"）
    confirm_join_btn = (By.XPATH, "//button[contains(., '确认加入课程')]")

    def course_card(self, name):
        """按课程名锁定"我的课程"里的课程卡片（学生端卡片同为 button.tp-spot，名在内层 div）
        与老师端 CoursePage.course_card 同款定位器工厂——同一套前端组件，选择器自然一致
        """
        return (By.XPATH,
            f"//button[contains(@class,'tp-spot')][.//div[contains(text(), '{name}')]]")

    def open_join_page(self):
        """从我的课程页点进"加入课程"页"""
        self.click_element(self.join_entry_btn)

    def join_by_code(self, code):
        """在加入页填邀请码 → 点"确认加入课程\""""
        self.input_text(self.code_input, code)
        self.click_element(self.confirm_join_btn)

    def is_in_my_courses(self, name, timeout=TIMEOUT):
        """学生"我的课程"里是否已出现该课程卡片（加入成功的断言依据）
        用 visibility（看得见）而非 presence（DOM 里有）：列表渲染中可能有占位假阳性
        """
        return self.is_element_visible(self.course_card(name), timeout)
