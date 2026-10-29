from selenium.webdriver.common.by import By
from base.base_page import BasePage


class CoursePage(BasePage):
    # 进入课程的按钮
    enter_course_btn = (By.XPATH, '//*[@id="app"]/div[2]/div[2]/main/div/div[3]/div[1]/button/span[2]/div')
    # 左侧菜单父项（需要鼠标悬浮）
    menu_main = (By.XPATH, '//*[@id="app"]/div[2]/div[2]/main/div/nav/ul/li[1]/button/span[1]')
    # 上课工作台子菜单
    workbench_btn = (By.XPATH, '//*[@id="app"]/div[2]/div[2]/main/div/nav/ul/li[1]/div/div/button[2]/span/span[1]')

    def enter_course(self):
        """点击进入课程"""
        self.click_element(self.enter_course_btn)

    def open_workbench(self):
        """悬浮主菜单，再点击上课工作台"""
        self.move_to_element(self.menu_main)
        self.click_element(self.workbench_btn)
