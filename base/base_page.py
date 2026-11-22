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

    def wait_text_not_empty(self, locator, timeout=TIMEOUT):
        """
        等元素文本"渲染就绪"（非空）再返回文本；超时返回空串（不报错）
        治的是 Vue 异步渲染竞态：DOM 节点先挂上、文字后填充，
        presence 判据会抢在文字出现前返回，此时 .text 是空串
        与 get_text_or_none 的区别：那个只等"节点在不在"，这个等"文字到没到"
        """
        def _ready(d):
            try:
                t = d.find_element(*locator).text.strip()
            except Exception:
                return ""
            return t or False  # 空串当 False，让 until 继续轮询直到文字渲染出来
        try:
            return WebDriverWait(self.driver, timeout).until(_ready)
        except TimeoutException:
            return ""

    # 内容级锚点专用 JS：逐元素算“净文本”（从文本来源上剪掉导航门牌子树）
    _JS_HAS_VISIBLE_TEXT = """
    const want = arguments[0];
    const EXCLUDE = 'a.llink';   // 只排“巡览入口卡片”本身：那是别页的门牌
    const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
    const nodes = [...document.querySelectorAll('body *')].filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 2 && r.height > 2;      // 只看看得见的
    });
    // 倒序遍历：先算完子再算父，父的净文本直接拿子算好的结果拼
    // clean 同时干两件事：存净文本 + 记录“这个元素可见”（不在表里=不可见，其文字不计）
    const clean = new Map();
    for (let i = nodes.length - 1; i >= 0; i--) {
        const e = nodes[i];
        if (e.closest(EXCLUDE)) { clean.set(e, ''); continue; }   // 整棵子树置空
        let s = '';
        for (const c of e.childNodes) {
            if (c.nodeType === 3) { s += c.textContent; }
            else if (c.nodeType === 1 && clean.has(c)) { s += ' ' + clean.get(c); }
        }
        clean.set(e, norm(s));
    }
    return nodes.some(e => clean.get(e).includes(want));
    """

    def has_visible_text(self, text, timeout=3):
        """
        判断页面内容区有没有“看得见的文字”含指定文案（内容级证据，不是框架级证据）
        这个判据经了四轮实测修正，每一轮都是被真跑出来的失败逼着改的：
        【坑一 太宽→假绿】XPath contains 会命中整页祖先：<body> 的 innerText 天然含全部子孙文字，
          什么文案都“找得到”，断言永远为真。
        【坑二 太严→误报】只比叶子节点会漏：带图标按钮 <button><i></i>发布随堂测</button> 的文字
          是 button 的匿名文本节点，button 有子元素不算叶子，文字又不在任何叶子上 → 真在页上却判没找到。
        【坑三 门牌污染→锚点不独占】manage 页命中了“课堂质量报告/班级学情报告”，溯源发现它们挂在
          span.llink__title < a.llink < div.hub，是页面底部跳转卡片的标题，天然等于目标页名。
        【坑四 排除门牌后壳子往上爬】2026-11-22 实测：把 a.llink/[class*=hub] 排掉后判定完全没变（A/B 对照：
          门牌元素 46 个、变化 0 项）。因为 innerText 天生包含子孙文字：hub 被排了，但它的祖先
          <main>/<div id=app>/<body> 都没被排，它们的 innerText 照样含那段文字，于是壳子往上挪了一层。
          → “找最深命中节点”这个层级方案在需要排除子树的场景里本质失效。
        现在的做法换了维度：不再挑“哪个元素最深”，而是给每个元素算一份**净文本**——
        拼接时遇到被排除的子树直接跳过，所以祖先的净文本里根本不会出现门牌文字。
        好处：既不需要靠“最深”防祖先冒充（文本层面已经干净），又自然兼容坑二的匿名文本节点。
        【坑五 排除范围写宽→把本页内容一起排掉】2026-11-22 实测：当时 EXCLUDE 写成 'a.llink, [class*=hub]'，
        两个报告页修好了，但 manage 页命中数直接掉到 0/13（连自己的“布置作业”都找不到）——
        因为【管理随堂测与作业】是个枢纽页，整个主体就装在 div.hub 里，[class*=hub] 把内容区一并排掉了。
        → 有了净文本算法后只需排 a.llink 本身（门牌子树跳过，祖先拼出的净文本自动干净）。
        教训：排除范围要“最小必要”，宁窄勿宽；而且必须拿 A/B 对照看“变化了哪几项”，
        只看“最终绿不绿”永远发现不了自己把真内容误杀了。
        为什么要等（timeout）：Vue 异步渲染，DOM 骨架先挂、文字后填，立刻查会误报“文案不存在”
        适用：确认“到的确实是这一页”（本页独有的表头名/标题/按钮文字）
        不适用：文案本身随数据变（如“第 5 讲”“全部 50”）——那类要断结构不断内容
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script(self._JS_HAS_VISIBLE_TEXT, text)
            )
            return True
        except TimeoutException:
            return False

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
