# Web UI 自动化测试框架（pytest + Selenium + Allure）

基于真实业务系统（私有环境）搭建的 POM 分层自动化框架，覆盖「用例设计 → 数据驱动 → 执行提速 → 失败留证 → 报告输出」完整链路。

## 技术栈
Python 3.14 · Selenium 4 · pytest 9 · Allure · Edge WebDriver

## 核心能力
- **POM 分层**：base（等待/交互封装）→ pages（定位器与页面动作）→ testcases（纯断言逻辑）
- **数据驱动**：用例输入与预期（expect）全部外置 YAML，新增用例不改代码
- **登录态复用**：session 级 fixture 共享登录态 + function 级"页面归位"，兼顾速度与隔离
- **瞬时提示可靠捕获**：MutationObserver 点击前埋点，解决 2 秒自动消失 toast 的漏抓问题（flaky 治理）
- **失败证据链**：pytest 钩子自动截图 + 运行日志，作为附件嵌入 Allure 报告
- **副作用隔离**：有账号污染风险的用例打 negative 标签，默认执行自动排除
- **配置安全**：敏感信息经 .env 注入（不入仓库），缺失时 fail-fast 报错

## 快速开始
```text
1. pip install -r requirements.txt
2. 复制 .env.example 为 .env，填入测试环境地址与账号
3. pytest testcases\test_login.py -v        # 跑默认用例
4. pytest -m negative                        # 跑有副作用用例（需废弃账号）
5. allure serve allure-results               # 查看可视化报告