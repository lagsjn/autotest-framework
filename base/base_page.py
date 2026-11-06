import re
import time

from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

from config import TIMEOUT


class BasePage:
    def __init__(self, driver):
        self.driver = driver
        # 统一从配置读超时，不要在每个页面里写死数字
        self.wait = WebDriverWait(self.driver, TIMEOUT)

    def get_element(self, locator):
        """等待元素可点击，返回元素对象，locator是元组 (By.XPATH, "xxx")"""
        return self.wait.until(EC.element_to_be_clickable(locator))

    def is_element_exist(self, locator, timeout=2):
        """
        判断元素在 timeout 秒内是否出现，只返回 True/False，不抛异常
        用途：断言"该出现的出现了"或"该消失的消失了"
        为什么单独写一个？因为 get_element 找不到元素会直接报 TimeoutException，
        而我们要的是"拿个布尔值去 assert"，两者职责不同
        注意：presence 判据是"DOM 里有"，不可见的预渲染元素（如没弹出的抽屉按钮）也算存在；
        要"看得见才算数"请用 is_element_visible
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def is_element_visible(self, locator, timeout=2):
        """
        判断元素在 timeout 秒内是否"可见"（存在 + 不隐藏），True/False，不抛异常
        和 is_element_exist 的区别：visibility 要求元素真的渲染出来（有尺寸、没被 display:none）
        适用：探测弹窗/抽屉这种"组件可能预挂在 DOM 上但并没显示"的浮层
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def is_element_absent(self, locator, timeout=TIMEOUT):
        """
        等元素消失：元素一消失马上返回 True，等满 timeout 还在则返回 False
        适用："点完提交后某个东西应该不见"这类断言
        为什么不用 is_element_exist 反着推？因为"判断不存在"必须等满整个超时时间，很浪费
        而 invisibility 是"一满足就提前返回"，效率高很多

        为什么要把 timeout 开成参数？因为正向和反向用例的等法完全不同：
          正向（元素真的会消失）：等满 10 秒也不浪费，一没就返回
          反向（元素根本不会消失）：等满 10 秒是纯浪费，给 2~3 秒就够了
        一条反向用例省 7 秒，50 条反向用例省 6 分钟——等待时间是用例设计的一部分
        """
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.invisibility_of_element_located(locator)
            )
        except TimeoutException:
            return False

    def input_text(self, locator, text):
        """输入文本"""
        ele = self.get_element(locator)
        ele.clear()
        ele.send_keys(text)

    def get_text_or_none(self, locator, timeout=3):
        """
        等元素出现后取它的文本；timeout 内没等到就返回空字符串（不报错）
        适用：提示/弹层这种"可能出现也可能不出现、而且会自动消失"的东西
        为什么要单独包一个 try？因为不包的话，提示没弹出来时会直接抛异常，
        报错信息是 TimeoutException，看不出到底是"提示没出现"还是"文案不对"
        """
        try:
            ele = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            return ele.text.strip()
        except TimeoutException:
            return ""

    def click_element(self, locator):
        """
        点击元素（被遮挡时自动重试）
        为什么要重试：登录后首次进页有入场动画，动画层会短暂盖住按钮，
        报 ElementClickInterceptedException（元素找到了也可点，只是按下那一瞬间被盖住）；
        为什么重新 find：重试间隔里 DOM 可能刷新，旧元素对象会 stale（失效）
        """
        ele = self.get_element(locator)
        for _ in range(3):
            try:
                ele.click()
                return
            except ElementClickInterceptedException:
                time.sleep(1)
                ele = self.get_element(locator)
        ele.click()  # 兜底：重试完还挂就抛出真实错误，不掩盖问题

    def get_attr(self, locator, name):
        """
        等元素出现并读它的属性值（断言状态用）
        注意：每次都要重新找元素再读，因为状态一变，旧元素对象可能已失效（stale）
        """
        ele = self.wait.until(EC.presence_of_element_located(locator))
        return ele.get_attribute(name)

    def move_to_element(self, locator):
        """鼠标悬浮到元素（对应你ActionChains悬浮菜单）"""
        ele = self.get_element(locator)
        action = ActionChains(self.driver)
        action.move_to_element(ele).perform()

    def open_url(self, url):
        self.driver.get(url)

    def wait_url_matches(self, pattern, timeout=TIMEOUT):
        """
        等 URL 匹配某个正则模式（SPA 路由切换滞后于点击，必须等而不是抢跑）
        匹配到返回当前 URL；等满 timeout 没等到返回 None（不抛异常，让用例自己 assert）
        为什么不用 time.sleep？固定睡眠两头亏：页面快了你白等，页面慢了你照样挂；
        智能等待是"一满足就提前返回"，又快又稳
        """
        rx = re.compile(pattern)
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: rx.search(d.current_url)
            )
        except TimeoutException:
            return None
        return self.driver.current_url

    # ============ 瞬时元素（toast）专用：埋点监听 ============
    # 轮询是"事后查岗"，1.5 秒就消失的提示很容易错过；
    # 改成点击前先用 MutationObserver 埋监听，元素一出现当场把文本存走
    def watch_appear(self, css_selector):
        """在"触发那个动作"之前调用！注入 JS 监听器"""
        self.driver.execute_script("""
        const sel = arguments[0];
        window.__watched = [];
        if (window.__watched_obs) { window.__watched_obs.disconnect(); }
        const grab = (node) => {
            if (node.nodeType !== 1) { return; }
            if (node.matches && node.matches(sel)) {
                window.__watched.push(node.textContent.trim());
            }
            if (node.querySelectorAll) {
                node.querySelectorAll(sel).forEach(e => window.__watched.push(e.textContent.trim()));
            }
        };
        const obs = new MutationObserver(list => list.forEach(m => m.addedNodes.forEach(grab)));
        obs.observe(document.body, {childList: true, subtree: true});
        window.__watched_obs = obs;
        """, css_selector)

    def wait_watched_texts(self, timeout=TIMEOUT):
        """等监听器抓到内容，返回出现过的文本列表（去重）；一直接不到则返回空列表"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: len(d.execute_script("return window.__watched || []")) > 0
            )
        except TimeoutException:
            pass
        return self.driver.execute_script(
            "return (window.__watched || []).filter((v, i, a) => a.indexOf(v) === i)"
        )

    def maximize_window(self):
        self.driver.maximize_window()

# 新增：等待元素可见，专门给断言用（判断元素是否存在）
    def wait_element_visible(self, locator):
        return self.wait.until(EC.visibility_of_element_located(locator))
