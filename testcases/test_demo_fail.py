"""
故意的失败演习：验证"失败 -> 截图 -> 钉进报告"整条链路通不通。
平时用例全绿，永远看不到失败报告长什么样；等真挂了再第一次学看失败报告，
等于在最慌乱的时候学新操作——所以要在最不着急的时候演练一次。
这个文件验证完就可以删（或留着当链路自检脚本）。
"""


def test_demo_fail_with_screenshot(driver):
    driver.get("https://www.baidu.com")
    assert "autotest" in driver.title, "演习用假断言：故意让它失败"