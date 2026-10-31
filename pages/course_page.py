from selenium.webdriver.common.by import By
from config import COURSE_NAME
from base.base_page import BasePage


class CoursePage(BasePage):
    # 课程列表页的课程卡片（DevTools 实地侦察：卡片整体是 <button class="tp-spot">，
    # 课程名在内层 div；按"按钮内含课程名文字"定位，不依赖 DOM 层数与顺序）
    # 旧绝对 XPath '//*[@id="app"]/div[2]/.../span[2]/div' 已弃用：前端加一层 div 就全挂
    enter_course_btn = (By.XPATH, f"//button[.//div[contains(text(), '{COURSE_NAME}')]]")

    # 课程详情页的绿色地标按钮：既是"到站"断言的依据，也是下一站（工作台）的入口
    # ⚠ 该课当前显示"正在上课"，点它有无副作用未评估，E2E 暂未放行到这一站
    workbench_entry_btn = (By.XPATH, "//button[contains(., '进入上课工作台')]")

    def enter_course(self):
        """点击目标课程卡片，进入课程详情页"""
        self.click_element(self.enter_course_btn)
