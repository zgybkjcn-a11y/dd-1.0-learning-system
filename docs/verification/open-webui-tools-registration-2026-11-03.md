# Open WebUI Tools 隔离注册与原生加载证据

日期：2026-11-03（Asia/Shanghai）  
范围：隔离 Open WebUI 0.12.5 与隔离 Learning API；仅使用合成身份、合成学习记录和隔离密钥。

## 注册结果

在隔离 Open WebUI 容器 `dd-openwebui-isolated-20261103d` 中通过原生 `POST /api/v1/tools/create` 注册了 Tool `dd_learning_v1`（显示名 `DD Learning V1`）。注册记录的 manifest 为：

- `required_open_webui_version: 0.12.5`
- `version: 1.0.0`
- `has_user_valves: true`
- 11 个公开方法；没有把确认、提交答案或 nonce 消费暴露为独立的模型参数工具

Tool 只归属于隔离测试管理员用户，未授予其他用户或群组访问；没有读取或修改现有正式 Open WebUI 的 Tool、数据库或配置。

实例级 Valves 已配置为隔离服务地址 `http://learning-api:31010`、隔离适配器密钥、隔离 provider/issuer。密钥值不写入本报告。该 Tool 的 per-user `UserValves` 已为合成用户配置学习者选择；共享环境不依赖 `DD_ACCOUNT_ID` 或 `DD_LEARNER_ID` 环境回退。

## 原生加载与执行

在容器内直接调用 Open WebUI 0.12.5 的 `open_webui.utils.tools.get_tools`，使用实际数据库中的 Tool 记录和宿主注入的 `__user__`，验证了以下结果：

- loader 返回的公开方法集合为：`get_attempt`、`get_mistakes`、`get_progress`、`get_review_tasks`、`list_learners`、`request_diagnosis`、`request_document_analysis`、`request_hint`、`request_variant`、`request_visual`、`start_trusted_interaction`。
- `__user__` 被 Open WebUI 从模型可见 schema 中过滤，并在调用时由宿主注入；模型传入的同名值不能覆盖宿主 subject。
- loader 自动读取实例 Valves，并注入 per-user `UserValves`；`list_learners` 和 `get_progress` 通过隔离服务返回结构化合成结果。
- 使用原生 loader 绑定合成 `__event_call__` 后，验证了 `submit_answer` 的 `input` 取消不会请求 challenge；接受后调用顺序为“读取题面 → input 回调 → submission challenge → answer 提交”。适配器返回安全状态，不回显原始答案、nonce 或 challenge id。
- 验证了 `confirm_import` 的 confirmation 取消不会创建 challenge；接受后调用顺序为“读取当前批次 revision 和候选 → confirmation 回调 → 带 `expected_batch_revision` 的 confirmation challenge → confirmations 提交”。回调消息包含服务端当前候选的题面、原始作答和人工证据，提交结果只返回安全计数。
- 验证了 `confirm_draft_interactively` 只使用服务端 `learning_drafts.content` 作为提交原文；合成回调接受后才创建 challenge，Tool 返回不含草稿原文、nonce 或 challenge id 的安全结果。未知测验资源的提交请求返回结构化错误，没有产生写入或成功语义。

## 隔离边界

Learning API 当前 `/health` 返回 HTTP 200、`schema_revision=6`；生产模式 `POST /internal/bootstrap` 返回 HTTP 404。Open WebUI 与 Learning API 共用隔离网络 `dd-openwebui-isolated-20261103d`，该网络 `internal=true`；Learning API 的 Docker inspect 显示 `31010/tcp` 没有宿主端口发布。现有正式 `open-webui` 容器和数据目录未参与该验证。

## 自动化与边界

本报告生成时本地确定性回归为 `pytest -q`：76 passed（服务 63、Tools 10、Open WebUI 兼容 3）；之后新增工作台回归，曾为 77 passed，最新全量为 78 passed（服务 64、Tools 11、Open WebUI 兼容 3）。`python3 -m compileall -q learning_service tests scripts` 通过。`tests/test_open_webui_compat.py` 仍保留源码加载和签名过滤回归，作为真实注册之外的快速反馈。

这份报告证明了隔离实例的真实 Tool 注册、原生 loader、Valves/UserValves 注入、宿主身份传递，以及使用合成服务响应的原生 `input`/`confirmation` 回调顺序和安全返回边界；它不证明真实浏览器点击、真实学生资料、真实 OCR/模型质量、正式环境切换或 T23 持续试用。Goal 继续保持 `active`。
