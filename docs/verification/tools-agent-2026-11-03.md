# Tools 与 Agent 可信交互回归证据

日期：2026-11-03

## 范围

本轮验证 `learning_service/tools.py` 薄适配器和受控 Agent 的可信交互边界。验证只覆盖本地确定性实现，不代表真实 Open WebUI Tools 注册、原生回调或真实 provider 已接通。

## 自动化结果

```text
pytest -q
47 passed in 16.79s (the focused report snapshot; the current full regression is 91 passed, including later migration, provider-boundary, WAL startup, Agent-action, SQLite process-recovery, test-workbench, trusted UI callback-timeout, Open WebUI compatibility and isolated Compose preflight regressions).

python3 -m compileall -q learning_service tests
passed
```

新增回归覆盖：

- 适配器转发 `X-Adapter-Secret`、账号/学习者和可信 provider/issuer/subject 头；JSON 请求体使用 UTF-8 编码并固定 15 秒超时。
- 资源 ID 按单个 URL path segment 编码，斜杠和空格不会改变资源路径边界。
- 结构化 HTTP 4xx/5xx 错误原样保留；非 JSON 响应限制为 500 字符的 `LEARNING_SERVICE_HTTP_ERROR`；网络错误和超时映射为 `LEARNING_SERVICE_UNAVAILABLE`。
- `start_trusted_interaction` 仅允许 `confirm_import`、`confirm_learning`、`confirm_draft_interactively` 和 `submit_answer`；缺少资源或未知 operation 在本地拒绝。
- Agent action 的 `start_trusted_interaction` 返回不含 nonce、challenge ID、原始答案或确认集合的 `requires_trusted_ui` handoff，不创建/消费 challenge、不提交确认、不提交答案。
- Open WebUI 薄 Tools 适配器另外通过原生 `input`/`confirmation` 回调重新读取并显示权威资源；用户接受后才创建并消费 challenge，Tool 返回不包含 nonce、challenge ID 或原始答案。隔离实例原生 loader 回调证据见 `open-webui-tools-registration-2026-11-03.md`，浏览器首页/Tools 页面读取证据见 `open-webui-browser-probe-2026-11-03.md`。

## 边界

测试使用假的 `urlopen` 和服务路由上下文。尚未进行真实 Open WebUI Tools 注册/回调、真实 OCR/模型调用或真实学生资料外发；这些仍按 `docs/goal/BLOCKERS.md` 的授权条件等待隔离环境和明确授权。
