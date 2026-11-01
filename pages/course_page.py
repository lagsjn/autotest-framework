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

    # ============ L3：课程详情页四个页签（侦察脚本 probe_tabs.py 实测 2026-11-01） ============
    # 真实可点的页签是 BUTTON.tp-bc-sub-btn（文字包在内层 span）；
    # 同名文字还出现在主导航菜单(tp-nav-menu)里——那是菜单项和"当前选中回显"，
    # 点错会弹出菜单而不是切页签，所以定位器必须用 class 把范围锁死在 sub-btn 这一族。
    # 纪律自查：语义标签(button) + 可读文字双条件；class 只做消歧，不写 DOM 层数
    schedule_tab_btn = (By.XPATH,
        "//button[contains(@class,'tp-bc-sub-btn')][.//span[contains(text(),'课表排期')]]")
    materials_tab_btn = (By.XPATH,
        "//button[contains(@class,'tp-bc-sub-btn')][.//span[contains(text(),'资料归档')]]")
    analytics_tab_btn = (By.XPATH,
        "//button[contains(@class,'tp-bc-sub-btn')][.//span[contains(text(),'学情看板')]]")
    members_tab_btn = (By.XPATH,
        "//button[contains(@class,'tp-bc-sub-btn')][.//span[contains(text(),'班级成员')]]")

    def enter_course(self):
        """点击目标课程卡片，进入课程详情页"""
        self.click_element(self.enter_course_btn)

    def is_tab_active(self, tab_btn):
        """
        问页面：这个页签现在是不是选中态？
        依据：选中页签的按钮 class 里会出现 is-active（前端自己标的状态，比截图肉眼靠谱）
        为什么每次重新 find？DOM 刷新后旧元素对象会 stale（失效），读到的还是历史快照
        """
        class_attr = self.get_attr(tab_btn, "class") or ""
        return "is-active" in class_attr
