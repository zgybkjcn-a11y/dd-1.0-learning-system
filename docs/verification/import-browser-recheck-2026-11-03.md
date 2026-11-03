# 整卷导入复核浏览器复验

日期：2026-11-03（Asia/Shanghai）
结果：独立 `/ui` Chromium 合成导入闭环通过；不构成真实资料、OCR/provider、Open WebUI 组合或真实学习者验收。

## 环境与范围

- 临时 SQLite、附件目录、loopback 端口和独立 API/worker；运行结束后临时进程和数据保留在 `/tmp` 供审阅，不连接正式 Open WebUI 或正式数据。
- 浏览器：Google Chrome，390×844 和 1280×900 CSS px。
- 两张合成 PNG 页面；`mock-document-v1` 只生成确定性页级候选，未执行真实 OCR/视觉识别。
- 账号、学习者、目标、人工复核人和文件内容均为合成值。

## 实际闭环

1. 以同一账号/学习者上传两份资料，创建整卷批次并启动异步分析。
2. 读取批次、两个候选和两个来源原页预览；批次状态为 `awaiting_review`，页面处理为 2/2，失败页为 0。
3. 对第一个候选保存人工 `incorrect`、目标和非空复核证据；请求为 `PATCH`，响应 HTTP 200，revision 从 1 变为 2。
4. 选择该候选，完成二次确认提示；浏览器以 `POST` 获取 confirmation challenge，再以 `POST` 提交确认，响应 HTTP 202。
5. 读取错题本，显示 `active` 错题。临时数据库对账为：2 个 `import_items`，其中 1 个 `confirmed/incorrect`、1 个 `needs_review/undetermined`；1 条 `import_judgments`、1 条 `mistake_sources` 和 1 条 `mistake_entries`。

受测业务请求均成功：上传 `201`（2 次）、创建批次 `201`、分析 `202`、候选/批次/来源读取 `200`、复核 `200`、confirmation challenge `200`、确认 `202`、错题本 `200`。运行期间无页面异常、控制台错误或失败请求；确认对话框包含候选摘要和人工复核边界。

布局测量：390px 视口的 `document.scrollWidth` 和 `body.scrollWidth` 均为 390px，溢出元素为空；1280px 视口 `document.scrollWidth` 为 1280px，`body.scrollWidth` 为 1120px。截图：[import-browser-recheck-2026-11-03.png](import-browser-recheck-2026-11-03.png)。

## 验收边界

该运行证明独立服务的上传→整卷分析→来源回查→人工复核→可信批量确认→错题本链路和窄屏布局可运行。合成页面不能证明真实 OCR/分题质量、人工学科标注、真实 provider、Open WebUI 模型发起的 tool call、最终浏览器可信回调或 T23 真实试用；这些仍按 `docs/goal/BLOCKERS.md` 保持未完成。
