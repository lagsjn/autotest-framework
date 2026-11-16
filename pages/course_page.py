import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from config import COURSE_NAME, TIMEOUT, BASE_URL
from base.base_page import BasePage


class CoursePage(BasePage):
    # 课程列表页的课程卡片（DevTools 实地侦察：卡片整体是 <button class="tp-spot">，
    # 课程名在内层 div；按"按钮内含课程名文字"定位，不依赖 DOM 层数与顺序）
    # 旧绝对 XPath '//*[@id="app"]/div[2]/.../span[2]/div' 已弃用：前端加一层 div 就全挂
    enter_course_btn = (By.XPATH, f"//button[.//div[contains(text(), '{COURSE_NAME}')]]")

    # 当前讲次页（/lessons/<id>）顶部的面包屑"课程名"那级（probe_lesson_landing.py 实测 2026-11-14）：
    # 真 <a> 链接，href 直接指向 /courses/<id>，可读文字=课程名，比图标 class 稳定
    # ⚠ 旧定位器 tp-nav-menu__home 已随 11-14 界面改版消失（整站 class 从 tp-* 换成 ui-*/cb-*）
    back_to_course_btn = (By.XPATH, f"//a[contains(@class,'ui-head__crumb')][contains(text(), '{COURSE_NAME}')]")

    # 课程详情页的绿色地标按钮：既是"到站"断言的依据，也是下一站（工作台）的入口
    # ⚠ 2026-11-14 重跑发现详情页改版：这个文字的地标已不在（L4 入场链路需随改版重侦察）
    workbench_entry_btn = (By.XPATH, "//button[contains(., '进入上课工作台')]")

    # 详情页新地标（probe_lesson_landing.py 实测 2026-11-14）：课程专属页签栏
    # "概览/课表/备课资源/学情/成员/设置"，旧名 tp-bc-sub-btn 那族已被它替代；
    # 用它做"到站"断言：列表页/当前讲次页都没有这条栏，只有详情页有
    detail_tabs_nav = (By.CSS_SELECTOR, "nav.cb__tabs")

    # ============ L3：课程详情页页签（probe_l3_tabs_v2.py 实测 2026-11-14，随界面改版重写） ============
    # 旧 BUTTON.tp-bc-sub-btn 全族已死；新页签是 <a class="cb__tab">（router-link 真链接）
    # 实测情报（写进断言前必须拿到）：
    #   URL 形态混用：课表=?tab=lessons、学情=?tab=analytics、成员=?tab=members（参数式，
    #   相对裸 URL 必变）；备课资源=/resources、设置=/settings（路径式）；默认页签=概览（裸 URL）
    #   选中态判据：只有 is-on 打在真正选中的那一个上；router-link-active 会同时挂在多个
    #   前缀匹配的子路由页签上（实测在课表页时概览也带它），用它判会误报——继续只认 is-on
    # ⚠ 成员页签文字是"成员 50"（带实时人数），定位必须用 starts-with 前缀匹配，
    #   写死全文字会随人数变化升空
    def tab_btn(self, name):
        """按页签前缀文字锁定页签（定位器工厂，同 course_card 的套路）"""
        return (By.XPATH,
            f"//a[contains(@class,'cb__tab')][starts-with(normalize-space(),'{name}')]")

    def click_tab(self, name, expect_url_re):
        r"""点页签并等 URL 落位，返回匹配到的 URL（没等到返回 None，让用例自己 assert）
        为什么把"点+等"打包进页面对象：URL 切换滞后于点击（SPA 老坑），
        每条用例各写一遍等待迟早有人漏；方法语义=业务动作"切到某页签"
        expect_url_re 随数据传入：改版后 URL 形态混用（?tab= 与 /xxx 并存），
        形态是"测什么"的数据，不是"怎么点"的逻辑，留在 TAB_CASES 里维护
        注：概览页"无害空点"（点了 URL 不变）时等待会超时返回 None，
        用例里的 expect_url_re 写 r"/courses/\d+$" 会再等一轮——多花几秒不出错，
        不值得为此写特判分支增加复杂度
        """
        self.click_element(self.tab_btn(name))
        return self.wait_url_matches(expect_url_re)

    def enter_course(self):
        r"""点击目标课程卡片，保证最终抵达课程详情页 /courses/<id>
        环境定性（2026-11-11，11-14 纠正）：该课有 ongoing 讲次时，点卡片落的是
        "当前讲次页" /lessons/<id>（产品设计，非缺陷）。不在每条用例里各写一遍分支，
        而是把落点差异消化在导航方法内部——页面对象的职责是提供业务动作
        （"进入课程"），不是"盲点一下按钮"；调用方的到站断言仍锁 /courses/\d+ 不放宽。
        """
        self.click_element(self.enter_course_btn)
        # SPA 路由切换滞后于点击：先等"两种落点之一"出现，再决定要不要补救
        landed = self.wait_url_matches(r"/courses/\d+|/lessons/\d+")
        if landed and "/lessons/" in landed:
            self.click_element(self.back_to_course_btn)   # 当前讲次页 -> 返回课程详情页
            self.wait_url_matches(r"/courses/\d+")

    def is_tab_active(self, tab_name):
        """
        问页面：这个页签现在是不是选中态？
        依据：选中页签的 <a> class 里只会出现 is-active（旧版实测）或 is-on（11-14 新版实测），
        两个都认——前端再改版换了状态类名时，这里改一行就能兼容，且用例层无感；
        为什么不认 router-link-active：实测它会同时挂在多个前缀匹配的子路由页签上，判不准
        为什么每次重新 find：DOM 刷新后旧元素对象会 stale（失效），读到的还是历史快照
        """
        class_attr = self.get_attr(self.tab_btn(tab_name), "class") or ""
        return "is-active" in class_attr or "is-on" in class_attr

    # ============ L5：老师建课 + 读邀请码（侦察 probe_l5_teacher.py 实测 2026-11-07） ============
    # "创建课程"入口：课程列表右上角（文字含"创建课程"）
    create_course_btn = (By.XPATH, "//button[contains(., '创建课程')]")
    # 建课弹窗"课程名称"框：弹窗内唯一带 maxlength=128 的 input
    # 为什么用 maxlength 不用 placeholder？该框 placeholder 是空的；列表页搜索框也是 input，
    # 但只有课程名称框带 maxlength=128，靠这个稳定属性锁定，不依赖 DOM 层数/顺序
    course_name_input = (By.XPATH, "//input[@maxlength='128']")
    # 弹窗内"创建"提交：限定在 el-dialog 容器内、文字正好是"创建"
    # （列表页那个"创建课程"按钮文字也包含"创建"，用 normalize-space()='创建' 精确排除）
    create_submit_btn = (By.XPATH,
        "//div[contains(@class,'el-dialog')]//button[normalize-space()='创建']")
    create_cancel_btn = (By.XPATH,
        "//div[contains(@class,'el-dialog')]//button[normalize-space()='取消']")

    def course_card(self, name):
        """按课程名锁定课程卡片（老师/学生端卡片同为 button.tp-spot，名在内层 div）
        写成"定位器工厂"方法而不是写死一条 XPath：课程名是运行时才知道的唯一名，
        当参数传进来才能复用——和 L4 的 sub_btn(name) 同款套路
        """
        return (By.XPATH,
            f"//button[contains(@class,'tp-spot')][.//div[contains(text(), '{name}')]]")

    def create_course(self, name):
        """打开建课弹窗 -> 填课程名称 -> 点"创建"提交
        实测坑（probe_l5_cleanup 2026-11-08）：提交后系统会自动跳进课程详情页
        并弹"排课"引导——不回到列表，后续"列表卡片"定位器就全落空；
        所以提交后主动 driver.get(BASE_URL) 强制回列表（丢弃排课引导，我们不排课）
        """
        self.click_element(self.create_course_btn)
        self.input_text(self.course_name_input, name)
        self.click_element(self.create_submit_btn)
        # 提交后强制回列表：让后续 course_card / read_invite_code 的列表定位器成立
        self.open_url(BASE_URL)

    def read_invite_code(self, name, timeout=TIMEOUT):
        """从课程卡片文字里正则抠出邀请码（卡片文字形如"…邀请码S75CJX"）
        为什么不点"复制邀请码"去读剪贴板：Selenium 读系统剪贴板跨浏览器很麻烦，
        而邀请码本就明文印在卡片上——用页面文字提取是"数据跨页面传递"的稳妥做法
        抠不到返回 None（让调用方去 assert，而不是抛异常掩盖"到底哪一步没出现"）
        """
        try:
            card = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(self.course_card(name)))
        except TimeoutException:
            return None
        m = re.search(r'邀请码\s*([A-Z0-9]{6,8})', card.text)
        return m.group(1) if m else None

    # ============ L5 收尾：归档自建课程（侦察 probe_l5_archive*.py 实测 2026-11-08） ============
    # 归档入口不在列表卡片上，而在课程详情页一个圆形"更多"按钮的下拉菜单里
    course_more_btn = (By.CSS_SELECTOR, "button.tp-course-more-btn")
    # 下拉菜单里的"归档课程"项（同菜单还有"重置邀请码/删除课程"，靠文字精确区分）
    archive_menu_item = (By.XPATH,
        "//li[contains(@class,'el-dropdown-menu__item')][contains(normalize-space(),'归档课程')]")
    # 二次确认可能弹（归档不可逆）：el-message-box 或 el-popconfirm 两种常见形态的主按钮
    confirm_msgbox_btn = (By.CSS_SELECTOR, ".el-message-box__btns button.el-button--primary")
    confirm_pop_btn = (By.XPATH,
        "//div[contains(@class,'el-popconfirm') or contains(@class,'el-popper')][not(contains(@style,'display: none'))]"
        "//button[contains(@class,'el-button--primary')]")

    def _confirm_dialog_if_any(self, timeout=2):
        """归档大概率弹二次确认；两种常见弹层都试一下，命中就点主按钮
        为什么写防御式？弹层形态没实地抓到（不能拿演示课试点归档），
        所以"有则处理、无则跳过"，让首跑真机来定性到底弹哪种
        """
        for btn in (self.confirm_msgbox_btn, self.confirm_pop_btn):
            if self.is_element_visible(btn, timeout=timeout):
                self.click_element(btn)
                return True
        return False

    def archive_course(self, name):
        """清理：进该课程详情页 -> 点"更多" -> 点"归档课程" -> 处理二次确认
        归档单向不可逆（仅置"已归档"，不影响已有课件/记录），所以只对 AT-L5-* 自建课调用
        绝不点同菜单里的"重置邀请码"（旧码立即失效）与"删除课程"（不可恢复）
        """
        self.click_element(self.course_card(name))          # 进详情页
        self.wait_url_matches(r"/courses/\d+")
        self.click_element(self.course_more_btn)            # 展开课程"更多"下拉
        self.click_element(self.archive_menu_item)          # 点"归档课程"
        return self._confirm_dialog_if_any()                # 有确认就点，返回是否点过
