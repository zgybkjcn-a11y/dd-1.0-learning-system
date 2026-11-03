# Open WebUI Tools 兼容 harness 与隔离边界证据

日期：2026-11-03

本报告仅记录源码兼容 harness 的范围：源码加载、Valves 注入、方法发现、保留参数过滤和假的 HTTP 请求；它本身没有注册 Tool、读取 `webui.db`、发送学生资料或调用真实 provider。隔离实例实际注册与原生 loader 证据另见 `open-webui-tools-registration-2026-11-03.md`。

## 兼容实现

- `Tools` 实例在构造时拥有 `valves`，并以 Pydantic `Valves` 模型保存 `DD_LEARNING_BASE_URL`、适配器密钥、provider、issuer 和可选的本地 subject。宿主按 `Valves(**values)` 替换实例后，适配器从新实例读取配置。
- `UserValves.DD_LEARNER_ID` 可由宿主按用户注入，服务端仍会用 `learner_access` 再次校验；共享或正式配置不使用全局 `DD_ACCOUNT_ID`/`DD_LEARNER_ID` 环境回退。
- 所有公开方法将 `__user__` 声明为保留参数。宿主向模型生成签名时过滤该参数，调用时由服务端注入；适配器只把 user id 转为 `X-Trusted-Subject`，模型传入的同名字段不会覆盖它。
- harness 的 callable 发现与 Open WebUI `get_functions_from_tool` 一致：忽略以下划线开头的 helper，并排除 callable class。暴露方法集合固定为读取/请求操作和 `start_trusted_interaction`，没有确认、答案提交或 nonce 消费方法。
- 顶层源码元数据声明了 Tool 标题、版本和 `required_open_webui_version: 0.12.5`，可直接粘贴到隔离 Open WebUI Tools 编辑器审阅。

## 自动化证据

```text
pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py
13 passed (10 Tools adapter + 3 Open WebUI compatibility)

pytest -q
76 passed（63 service + 10 Tools + 3 Open WebUI compatibility；本报告生成时的快照，后续曾为 77 passed，最新全量回归为 78 passed）

python3 -m compileall -q learning_service tests
passed

OpenAPI runtime == docs/contracts/openapi-v1.json
55 paths / 19 schemas
```

`tests/open_webui_harness.py` 通过临时 Python module 执行适配器源码，模拟实例化和宿主注入；`tests/test_open_webui_compat.py` 进一步断言：

- Valves 替换后的 URL、密钥、provider/issuer 和宿主 user subject 正确转发；模型伪造的 `__user__` 被丢弃；UserValves 选择的 learner id 通过受信 header 转发。
- 顶层 Tool 元数据（标题、版本和 `required_open_webui_version`）可被宿主解析，且不会进入可调用方法清单。
- 所有 11 个暴露方法的 `__user__` 不出现在模型可见签名中，内部 helper 和 `Valves`/`UserValves` 类不出现在工具清单中。
- `start_trusted_interaction("submit_answer", ...)` 先重新读取题面并通过原生 `__event_call__` 发出 `input`；只有回调返回非空原始答案后才请求并提交一次性 challenge。模型可见结果不含原始答案、nonce 或 challenge ID；取消、错误对象、异常和缺少回调均返回结构化错误且不创建 challenge。`confirm_import`/`confirm_learning` 同样先显示服务端原文，严格接受原生 `confirmation` 后才创建并消费绑定 revision 的 challenge。
- 资源 id 中的斜杠仍编码为单一 URL path segment。

## 独立 Compose 探针

使用临时 project `dd-learning-toolscompat-20261103c`、端口 `32194`、临时密钥和独立卷执行：

```text
health = {"status":"ok","service":"learning-api","schema_revision":5,"version":"0.1.0"}
POST /internal/bootstrap       -> 404
GET  /api/v1/learners          -> 401 (无受信上下文)
GET  /api/v1/learners          -> 401 (未知 trusted identity)
```

探针结束后已执行 `docker compose down --volumes --remove-orphans`；临时容器、卷和网络均已清理，现有 `open-webui` 容器仍在运行且未触碰。

## 验收边界

这份报告只证明源码 harness 兼容性；隔离 Tool 注册、原生 loader 和合成 `input`/`confirmation` 回调顺序已由 `open-webui-tools-registration-2026-11-03.md` 验证。真实浏览器点击及其 WebSocket 回调、真实 OCR/模型与 T23 仍待验收；Goal 保持 `active`。
