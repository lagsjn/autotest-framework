from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import TimeoutException

from base.base_page import BasePage
from config import TIMEOUT


class ConsolePage(BasePage):
    """
    课堂控制台页面对象（侦察来源：script/probe_console.py 实测 2026-11-04）
    - 进入方式：课程详情页点"进入上课工作台"，同页跳转（无新标签页）
    - URL 形态：/lessons/<数字id>（课堂，业务流程地图 §3 三级状态机的中间一级）
    """

    # 子导航：tp-bc-sub-btn 家族（与课程详情页签同组件族 -> 行为同为局部面板切换，🟢 只读）
    # 用 class 过滤把同名干扰排除在外：'签到进行中·46/50' 是 tp-spot 卡片、
    # '打开演示大屏' 是 el-button，都不属于 sub-btn，点不到也定位不到
    @staticmethod
    def sub_btn(name):
        return (By.XPATH,
                f"//button[contains(@class,'tp-bc-sub-btn')][contains(., '{name}')]")

    # 抽屉（从屏幕边缘滑出的浮层面板）关闭按钮：侦察现场显示进入时抽屉是打开的
    # 关闭一个浮层无业务副作用，🟢
    drawer_close_btn = (By.CLASS_NAME, "el-drawer__close-btn")

    # 返回课程详情（L4 的出口，🟢 导航）
    back_to_course_btn = (By.XPATH, "//button[contains(@class, 'tp-nav-menu__home')]")

    def is_sub_active(self, name, timeout=TIMEOUT):
        """
        子导航是否处于选中态（is-active，与 L3 页签同款判据）
        为什么必须轮询等待而不是立刻读：侦察实测（probe_l4_active.py 2026-11-05）
        is-active 是点击后约 0.5 秒才异步挂上的，点完立刻断言必竞态；
        等法=一挂上马上返回 True，等满 timeout 没挂上才返回 False，又快又稳
        """
        def active(driver):
            cls = driver.find_element(*self.sub_btn(name)).get_attribute("class") or ""
            return "is-active" in cls
        try:
            WebDriverWait(self.driver, timeout).until(active)
            return True
        except TimeoutException:
            return False
