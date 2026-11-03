# DD-1.0 薄 Tools 接入说明

本文件描述隔离测试环境中的注册方式和边界。`learning_service/tools.py` 是唯一需要复制到 Open WebUI Tools 编辑器的适配器源码；学习服务业务逻辑、数据库、附件和迁移仍运行在独立 FastAPI 服务中。不要把 `docs/contracts/openapi-v1.json` 整体注册为模型工具，也不要把本适配器改成直接读写 `webui.db`。

## 隔离注册步骤

1. 在隔离 Open WebUI 测试账号的 Tools 编辑器中创建新 Tool，把 `learning_service/tools.py` 的完整内容粘贴进去。注册前审阅源码和顶层元数据，确认它只使用标准库与 Open WebUI 已有的 `pydantic`，不包含真实资料、密钥或生产地址。
2. 在该 Tool 的管理员 Valves 中设置：

   - `DD_LEARNING_BASE_URL`：隔离学习服务的内部地址，例如 `http://learning-api:31010`；
   - `DD_LEARNING_ADAPTER_SECRET`：与隔离学习服务 `LEARNING_ADAPTER_SECRET` 相同的临时值；
   - `DD_TRUSTED_PROVIDER`：固定为 `open-webui` 或隔离安装标识；
   - `DD_TRUSTED_ISSUER`：固定为该隔离安装的发行者标识；
   - `DD_TRUSTED_SUBJECT`：生产和真实多用户接入留空。它只为没有宿主用户上下文的本地合成探针保留。

   Open WebUI 会用 `Valves(**values)` 重建实例；适配器的 `Valves` 是 Pydantic 模型并保留实例级 `valves` 属性，因此管理员配置不会退回到源码默认值。
3. 运行时 Open WebUI 将服务端 `__user__` 注入声明了该保留参数的 Tool 方法。适配器只读取 `__user__['id']`（或兼容的 `user_id`）作为 `X-Trusted-Subject`，并与固定的 provider/issuer 一起由学习服务映射到自己的 `identity_bindings`。模型参数中同名或以 `__` 开头的字段不会覆盖宿主注入值。
4. 学习者上下文必须由受信 UI/服务端选择并以 `X-Learner-Id` 传递；服务端再次检查该账号的 `learner_access`。适配器支持 Open WebUI 的 per-user `UserValves.DD_LEARNER_ID` 作为受信选择；`DD_ACCOUNT_ID`、`DD_LEARNER_ID` 环境变量只用于本地隔离探针，不应配置在共享的正式 Open WebUI Tool 中。

## 暴露的方法和可信边界

适配器只暴露学习者列表、复习任务、错题/进度/作答读取，以及分析、诊断、变式、提示和数轴教学请求。`start_trusted_interaction` 固定允许 `confirm_import`、`confirm_learning`、`confirm_draft_interactively` 和 `submit_answer` 四种操作。它先从服务端按当前学习者重新读取权威资源，在 Open WebUI 原生 `__event_call__` 中发出 `confirmation` 或 `input` 事件；只有回调严格返回 `True` 或非空原始答案后，才按资源 revision 创建一次性 challenge 并提交。宿主事件声明 120 秒超时，适配器也对异步回调实施相同等待上限；取消、错误对象、异常、超时或缺少回调均 fail closed，不创建 challenge 或写入。Tool 返回值只保留安全状态、attempt/draft 标识和计数，不回显原始答案、nonce、challenge ID、确认集合或草稿原文。整卷导入不能用普通聊天输入替代原卷复核。

`tests/open_webui_harness.py` 仿真了当前 Open WebUI 的源码加载、实例级 Valves 注入、公共 callable 发现、保留参数过滤和宿主用户注入。`tests/test_open_webui_compat.py` 与 `tests/test_learning_tools.py` 使用假的 `urlopen`，不启动或写入正式 Open WebUI，不访问正式 provider，并断言资源路径编码、固定 challenge 路由、超时 fail-closed 和用户 subject 不可被模型参数替换。

## 隔离实例注册证据

2026-11-03 已在 disposable 隔离 Open WebUI 0.12.5 实例实际注册 Tool `dd_learning_v1`。原生 `open_webui.utils.tools.get_tools` 从数据库记录加载 Tool，返回 11 个公开方法，并验证实例 Valves、合成用户 UserValves、宿主 `__user__` subject、学习者读取，以及合成 `input`/`confirmation` 回调的取消、接受和 challenge 顺序。注册账号仅为隔离测试管理员，使用合成学习者和内部网络；未接触现有正式 Open WebUI 或其数据目录。完整证据见 `docs/verification/open-webui-tools-registration-2026-11-03.md`。

## 仍待真实验收

隔离注册与原生 loader/合成服务回调已通过；仍未验证真实模型发起的浏览器工具调用、真实浏览器组合及最终可信 UI 确认/答案提交回调，真实 OCR/模型 provider 也未接入；这些仍由 `docs/goal/BLOCKERS.md` 记录，需要明确测试账号、临时密钥、脱敏资料和授权后才能推进。不得以本地 harness、合成 `/ui` 或 mock provider 代替这些验收。
