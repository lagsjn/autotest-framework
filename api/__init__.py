"""
接口自动化包（API 层）：对应 UI 层里的 pages/base 分层思想
- base_api.py：所有接口的公共底座（建会话、拼地址、带 token、发请求、记日志）
- login_api.py / course_api.py：具体业务接口，只关心"路径 + 参数"
分层目的和 UI 一样：把"怎么发请求"沉淀到基类，把"发哪个请求"上提到业务对象，
用例层（testcases/test_api_*.py）只写"断言返回对不对"，读起来像自然语言
"""
