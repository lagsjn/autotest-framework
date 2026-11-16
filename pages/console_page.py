from selenium.webdriver.common.by import By

from base.base_page import BasePage


class ConsolePage(BasePage):
    """
    课堂回放页（当前讲次）页面对象（侦察来源：script/probe_l4_console_v2.py 实测 2026-11-14）

    产品形态已随 11-14 界面改版重排（业务流程地图 §13.5）：
    - 旧版"课堂工作台十项子导航"（tp-bc-sub-btn：签到/大屏/点名…）在当前 UI 里已不可见，
      实时工作台推测只在真实开课/模拟上课期间存在——待以后侦察，本对象先不管
    - 新版点课程卡片直达 /lessons/<id> 课后回放主页，巡览功能改成 7 个路径式子页面
      （/attendance、/scoreboard、/questions、/discussions、/quality-report、
      /class-report、/manage），入口是 a.llink 真链接
    - 旧 drawer_close_btn 删除依据：新版回放页 el-drawer 实测 0 命中，抽屉机制已不存在
    - 旧 back_to_course_btn（tp-nav-menu__home）删除依据：0 命中；回详情页统一走
      CoursePage.back_to_course_btn（面包屑），不在两个页面对象里维护同一锚点
    """

    # 回放页巡览入口家族：a.llink（文字=功能名+一行说明，如"出勤明细 逐个改出勤状态"，
    # 用 contains 前缀名匹配；同名文字也挂在 rv-link/el-button 上，class 把范围锁死在 llink 族）
    @staticmethod
    def lesson_link(name):
        return (By.XPATH,
                f"//a[contains(@class,'llink')][contains(normalize-space(),'{name}')]")

    # 页面框架地标：顶部面包屑（新版所有页面都有；证明 SPA 框架渲染完成、没掉出站外）
    crumb_marker = (By.CSS_SELECTOR, "a.ui-head__crumb")
