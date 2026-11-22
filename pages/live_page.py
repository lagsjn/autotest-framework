"""实时工作台页面对象（侦察来源：script/probe_live_workbench.py 实测 2026-11-22）

产品形态（本次侦察坐实，替代 2026-11-04 旧记录里的"十项子导航"）：
  开课后老师端"正在上课"分两层——
  【管理视角】/lessons/<id>：面包屑 + 上课卡（开始时间/已签到/回到上课模式/按住下课）
             + 四个 a.llink 门牌（出勤明细/学生提问/讨论记录/管理随堂测与作业），
             与课后回放页同一族组件（回放页本质是"课后版实时页"）
  【大屏模式】/lessons/<id>/live：点「回到上课模式」进入（纯前端路由，零数据副作用）。
             步骤条 button.lv-step 的项数与文案 = GET /lessons/<id>/flow 的 steps
             （默认模板 signin→intro→end 渲染为 签到→课程导入→下课；
              当前步 class 带 is-cur，未到步带 is-next）——这条对应关系就是
              test_lesson_live.py 跨层断言的靶子。

定位器纪律：
  - class 名一律用实测值（lv-step / ui-hold / llink / live-card__cta），改版即红，红了先看
    重跑侦察脚本再动定位器；
  - 「按住下课」（ui-hold，aria=按住下课（按住确认））是长按确认交互：
    Selenium 的 click() 按下即松开、满足不了"按住若干秒"，本对象只把它当"存在性断言"用，
    **任何用例都不许点击它**——真点下去等于把沙箱课堂中途下课，状态就乱了。
"""
from selenium.webdriver.common.by import By

from base.base_page import BasePage


class LiveLessonPage(BasePage):

    # ========== 管理视角层（/lessons/<id>） ==========
    # 侧栏"正在上课"徽标：开课期间全局存在，是"真的开上课了"的 UI 侧证据
    live_badge = (By.CSS_SELECTOR, "button.ui-live")

    # 下课按钮（只断存在，绝不点击，理由见文件头定位器纪律）
    hold_end_btn = (By.XPATH, "//button[contains(@class,'ui-hold')]")

    # 进大屏的入口按钮：落点页上有两个同文案按钮（侧栏徽标、上课卡 primary 主按钮），
    # 用 live-card__cta 把范围锁死在上课卡那个，不随侧栏改版漂移
    enter_live_btn = (By.XPATH,
                      "//button[contains(@class,'live-card__cta')][contains(.,'回到上课模式')]")

    # 四个功能门牌（与 ConsolePage.lesson_link 同一族组件、同一写法：
    # 文字=功能名+一行说明，用 contains 前缀名匹配）
    @staticmethod
    def lesson_link(name):
        return (By.XPATH,
                f"//a[contains(@class,'llink')][contains(normalize-space(),'{name}')]")

    # ========== 大屏层（/lessons/<id>/live） ==========
    # 流程步骤条全家（数量随 flow 的 steps 变化，不写死三个）
    lv_steps = (By.CSS_SELECTOR, "button.lv-step")
    # 当前步：class 组合 lv-step is-cur（实测 start 后停在 signin=「签到」）
    lv_current_step = (By.CSS_SELECTOR, "button.lv-step.is-cur")
    # 大屏上的长按下课（xl 号），同样只可断存在不可点击
    lv_hold_end_btn = (By.XPATH, "//button[contains(@class,'lv-hold')]")
    # 「下一步」按钮：文案自带状态（实测"下一步 进入 课程导入"），用来交叉验证当前步的下一步
    lv_next_btn = (By.CSS_SELECTOR, "button.lv-next")

    def step_labels(self):
        """按页面顺序取全部步骤条按钮文案（跨层断言的主数据源）
        为什么返回列表而不是逐个在页面对象里断：断言属于用例层，
        页面对象只负责"把证据完整取出来"——和接口层方法返回原始 resp 同一分工
        """
        return [el.text.strip().replace("\n", " ")
                for el in self.driver.find_elements(*self.lv_steps)]

    def current_step_label(self):
        """当前步文案；is-cur 一个都不命中时返回 None，让用例自己 assert 出真相"""
        els = self.driver.find_elements(*self.lv_current_step)
        return els[0].text.strip().replace("\n", " ") if els else None
