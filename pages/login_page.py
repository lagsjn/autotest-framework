from selenium.webdriver.common.by import By

from base.base_page import BasePage
from config import TIMEOUT


class LoginPage(BasePage):
    # ========== 元素定位器：统一写在这里，后续改XPATH只改这里 ==========
    # 账号输入框
    username_input = (By.XPATH, '//input[@autocomplete="username"]')
    # 密码输入框
    password_input = (By.XPATH, '//input[@autocomplete="current-password"]')
    # 登录按钮：用 HTML 语义属性 type="submit"（表达"这是提交按钮"的业务含义）
    # 不用 mt-2/w-full/!h-11 这种 Tailwind 原子类，那是纯样式，改 UI 必挂
    login_btn = (By.CSS_SELECTOR, "button[type='submit']")
    # 顶部提示条的文案容器（Element Plus 组件）
    # 实测：容器 id 是 message_1/message_2...自增的，写死必定挂，所以用组件库的语义类名
    toast_msg = (By.CSS_SELECTOR, '.el-message__content')
    # 密码框右侧的明文切换图标（Element Plus show-password 渲染出的 <i>，实测唯一）
    eye_icon = (By.CSS_SELECTOR, '.el-input__password')

    def login(self, username, password):
        """登录动作：输入账号密码，点击登录"""
        self.input_text(self.username_input, username)
        self.input_text(self.password_input, password)
        self.click_element(self.login_btn)

    def is_login_success(self, timeout=TIMEOUT):
        """
        登录是否成功：以"登录页的账号输入框消失"为依据
        为什么不看 URL？这是个 Vue 单页应用（SPA），登录后不一定传统跳转，
        页面上元素在不在，比地址栏更可靠

        反向用例请传短 timeout（如 3）：明知不该成功，没必要等满 10 秒
        """
        return self.is_element_absent(self.username_input, timeout)

    def start_watch_toast(self):
        """开始监听提示条——必须在点登录之前调用，否则白听
        self.toast_msg 是 (By.CSS_SELECTOR, '.el-message__content') 这个元组，
        [1] 取出来的就是后面那个选择器字符串，JS 里只能用字符串选择器
        """
        self.watch_appear(self.toast_msg[1])

    def wait_toast_texts(self, timeout=5):
        """拿点击后出现过的所有提示文案（列表）；真没提示就是空列表"""
        return self.wait_watched_texts(timeout)

    def get_password_type(self):
        """读密码框当前的 type：password=密文，text=明文
        为什么能拿它做断言？因为 type 是"会变的状态"，状态正好用来验证行为对不对
        """
        return self.get_attr(self.password_input, "type")

    def click_eye(self):
        """点击小眼睛图标"""
        self.click_element(self.eye_icon)
