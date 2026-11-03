# 独立测验工作台 Chromium 验收

日期：2026-11-03（Asia/Shanghai）
结果：独立 `/ui` 合成浏览器闭环通过；不构成真实 Open WebUI、真实 provider 或真实学习者验收。

## 环境

- 使用临时目录、临时 SQLite 数据库、临时附件目录和随机 loopback 端口启动独立 Learning Service 与 worker；结束后进程和临时数据均已清理。
- 浏览器：Google Chrome，390×844 CSS px；另测 1280×900 CSS px。
- 数据为临时合成账号、学习者、已审核题目与合成答案。判分走本地确定性服务端 worker；没有配置外部模型/OCR/provider，也没有连接正式 Open WebUI 或正式数据。

## 浏览器实际流程

1. 在 `/ui` 启动独立测验并显示题面。
2. 刷新页面，工作台恢复同一 session 和 test item。
3. 请求提示，服务端状态记录 `assistance=hint`；session 响应不包含原始答案或答案键。
4. 提交答案。浏览器先以 `POST` 获取一次性 submission challenge，再以 `POST` 提交答案，收到 HTTP 202；worker 最终将 attempt 判为 `graded/correct`。因此前已暴露提示，服务端记录 `assessment_eligibility=0`。
5. 申请复核；浏览器显示申请成功，服务端保存一条复核申请，成绩仍由服务端维护。该流程同时发现并修复了成功提示被后续成绩刷新立即覆盖的问题。
6. 启动第二个未提交会话并取消；恢复读取显示 session 和 item 均为 `cancelled`。

受测请求结果：session 恢复读取 GET 200；submission challenge POST 200；答案 POST 202；复核申请 POST 202；取消 POST 200。运行期间无页面脚本异常。题面、session、attempt 与复核响应均未泄露 `answer_key_json` 或 `raw_answer`。

布局测量：390px 视口文档宽度 390px，1280px 视口文档宽度 1280px，均无横向溢出。浏览器截图：[browser-test-workbench-2026-11-03.png](browser-test-workbench-2026-11-03.png)。

## 验收边界

这证明当前独立服务 `/ui` 的本地测验工作台可以启动、恢复、记录提示、提交、等待并读取服务端判分、申请复核和取消未提交会话。它不能替代隔离 Open WebUI 聊天发起的真实模型 tool call、浏览器 `input`/`confirmation` 最终可信回调、真实 provider/OCR、整卷人工标注质量或 T23 真实试用；这些仍按 `docs/goal/BLOCKERS.md` 保持未完成。
