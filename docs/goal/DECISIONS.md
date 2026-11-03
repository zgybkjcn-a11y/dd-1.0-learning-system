# DD-1.0 决策记录

## G0 / 2026-11-02

- 学习服务使用独立 FastAPI 进程、SQLite/WAL 和独立附件目录；不导入 `open_webui.*`、不写 `data/webui.db`，Open WebUI 只通过薄适配器调用。
- 默认数据目录为 `learning_data/`，部署时固定为 `/var/lib/dd-learning`；正式 `data/` 不挂载到学习服务。
- V1 只正式接入 `signed_number_subtraction`；数学参数和终点由程序计算，素材默认提供静态回退。
- 未配置受信适配器密钥时，非开发模式拒绝业务请求；内部 bootstrap/seed/worker 端点在生产不可见。
- 所有最终确认、答案提交和复习晋阶需要服务端挑战、nonce、资源 revision 和一次性消费；Agent 白名单不包含这些动作。
- 真实 OCR/模型/学生资料/付费调用不因本地模拟通过而标记完成。

## D1 / 2026-11-02

- 多页 PDF 的原始上传继续作为不可变 `source_document` 资产；每页渲染为独立私有 `source_page` 资产并通过 `source_pages.asset_id` 回查。这样页级区域、备份和删除生命周期不依赖把一个 PDF 路径伪装成所有页面。
- `import_batches.answer_document_id` 通过向后兼容迁移持久化，保留参考答案与学生资料的学习者范围校验；本字段只记录来源，不把答案自动转为判定结果。
- 学习草稿确认以服务端 `learning_drafts.content_json` 为唯一原文；客户端可回显校验但不能替换，校验失败不消费一次性挑战。

## 当前偏差

- 早期运行环境中 `fastapi.testclient.TestClient` 对最小 FastAPI 曾挂起；2026-11-03 在临时目录复核 `/health` 已返回 200。该探针不改变确定性业务测试以直接路由函数、SQLite 约束和 worker 事务为主的安排，也不替代真实 Open WebUI HTTP/浏览器/Tools 回调验收。
- 当前分析 worker 生成“需复核”候选和页级区域，不宣称自动分题或学科判错质量；未提供真实标注集前不计算准确率。
- `/ui` 使用独立服务内的完整本地受信工作台，身份上下文通过请求头注入；它已由直接路由和独立 Compose 宿主 HTTP 回归覆盖，但不等同真实 Open WebUI UI。真实 Open WebUI 浏览器、Tools 注册和回调继续列为外部环境验收。

## D7 / 2026-11-03

- Tools 适配器将资源 ID 编码为单个 URL path segment，并保留服务返回的结构化 HTTP 错误；只有网络错误和超时映射为不可用，避免把权限/冲突/不存在误报成服务宕机。
- `start_trusted_interaction` 只允许固定的可信 UI challenge 操作，并且适配器不消费 nonce、不提交确认或答案。Agent 对同一动作只返回 `requires_trusted_ui` handoff；最终确认和答案提交仍必须由可信 UI 回调完成。
- Agent handoff 同时接受产品动作名 `confirm_draft_interactively`，由可信 UI 层映射到服务端的 `confirm_learning` challenge；该别名不增加 Agent 权限。
- 本地回归新增到 47 项；该证据验证隔离服务的安全边界，不提升为真实 Open WebUI Tools 注册、原生回调或真实 provider 验收。

## D8 / 2026-11-03

- migration 执行改为每个版本显式 `BEGIN IMMEDIATE`，DDL 与 `schema_migrations` 版本记录在同一事务；不使用会隐式提交的 `executescript()`。失败 migration 必须完整回滚并可在修复后重试；并发首次启动通过写锁串行化。该改动只增强独立 SQLite 启动/升级边界，不改变正式 Open WebUI 或生产数据库的未验证状态。
- 本地确定性回归更新为 49 项；迁移专测和并发初始化证据见 `docs/verification/migration-atomicity-2026-11-03.md`。

## D2 / 2026-11-02

- schema revision 3 增加导出 artifact 和删除生命周期字段/表；删除先写 tombstone 并停用学习者访问，再执行物理清理。清理失败保留错误状态，恢复时先迁移旧库再重放 tombstone，避免已删除资料重新公开。
- 文档、诊断和变式 provider 通过显式配置选择；默认 provider 是确定性 mock，只能产生 `needs_review` 并记录 `external_call=false`，不把本地回归当作真实 OCR/模型证据。
- 隔离 Compose 复验固定使用独立 project、卷、端口和合成身份；不挂载 Open WebUI 正式数据目录。生产模式不暴露 bootstrap，业务请求必须经过受信适配器身份。

## D3 / 2026-11-02

- 将 Playwright 证据明确归类为独立服务 `/ui` 的本地受信工作台验收：它覆盖上传、候选复核、可信确认和错题本的浏览器可操作性，但不提升为真实 Open WebUI UI/Tools 注册、真实 provider 或真实学生资料验收。
- 浏览器测试使用内存注入的合成 PNG 字节和独立 Compose project/卷/端口；测试结束保留独立卷证据并停止容器，不使用 `-v`，不影响现有 `open-webui`。

## D4 / 2026-11-02

- 管理员运行指标只提供按状态/类型的任务计数、队列年龄、过期租约、失败页比例、待复核/删除/幂等计数，并明确 `external_calls.tracked=false`；不伪造费用，也不返回学习者标识、原图、原答或 provider payload。
- 备份恢复在复制前拒绝非空目标，要求 manifest 文件集合与实际文件一致并逐文件校验；恢复后执行 SQLite `integrity_check`，失败时删除半恢复目录。过期 lease 的重领证据只证明确定性状态机，不替代真实进程 kill、对象存储或网络 provider 故障演练。

## D5 / 2026-11-03

- 维护准入由服务端 `_maintenance_gate` 统一计算：stage 5、到期、至少 3 个不同自然日的无提示独立正确、至少 2 个已审核变式以及距最近学习/提示/练习/教学素材暴露至少 30 个自然日。当前作答不会成为暴露；practice session 不产生晋阶，并返回可审计的 `eligible=false` 结果。
- `question_versions` 的变式元数据通过 migration 004 增加，旧版题库写入保持默认 `base` 兼容；本条记录的是 migration 005 之前的历史探针（schema revision 4），当前 schema revision 5 及复核申请以 D13 为准。

## D6 / 2026-11-03

- 本地 `/ui` 工作台继续作为独立服务的受信验收入口；为保证窄屏可操作性，控件采用 `box-sizing`、可收缩 flex 子项和状态文本任意断词。Google Chrome revision 4 浏览器证据确认 390px 与桌面视口均无横向溢出。该证据不改变真实 Open WebUI UI/Tools 仍待外部验收的边界。

## D9 / 2026-11-03

- provider/OCR/模型调用不得持有 SQLite writer transaction。分析 worker 在调用前只读取并固定批次/页快照，provider 返回后按页在短写事务中重新校验 job lease、批次 revision 和页面状态，再幂等写入候选；诊断同样在读证据与短写持久化之间调用 provider。第二连接写入回归和进程中断证据支持该边界。
- SQLite 连接在 WAL 协商前设置 busy timeout，并对启动期 `SQLITE_BUSY` 做 15 秒有界重试；这是独立隔离服务的启动可靠性增强，不代表真实生产数据库故障已完成验收。

## D10 / 2026-11-03

- 新增嵌入式 SQLite writer 进程中断回归：子进程在 WAL 写事务中被 `SIGKILL` 后，重开数据库执行 `integrity_check`，确认已提交数据保留、未提交数据回滚且后续写入成功。该证据覆盖 SQLite 文件的本机进程故障恢复，不覆盖外部数据库服务、网络文件系统、对象存储或跨主机故障。

## D11 / 2026-11-03

- Agent 动作实现从占位成功语义改为服务端真实的学习者范围读取和持久化委托：整卷分析、诊断、变式、提示和数轴动作均受现有权限/版本/审核边界约束；诊断 provider 返回后再次校验 job lease，结果固定为 `needs_review`。允许清单中任何未实现分支显式返回 `AGENT_ACTION_NOT_IMPLEMENTED`，不写入成功步骤。
- Agent 不能消费可信挑战或提交最终确认/答案；四种可信操作只返回 `requires_trusted_ui` handoff。该实现通过本地回归，但不等于真实 Open WebUI 原生注册、回调或 provider 验收。

## D12 / 2026-11-03

- 生成并固定 `docs/contracts/openapi-v1.json` 作为 DD-1.0 V1 的版本化接口快照；由 `create_app().openapi()` 生成并检查 50 条路径、16 个 schema。运行时 `/openapi.json` 是来源，路由/模型变更需重新生成。契约不包含密钥、学生资料或生产地址，也不替代真实 Open WebUI Tools 注册验收。

## D13 / 2026-11-03

- migration 005 增加学习者隔离的 `review_requests` 表；页面修订采用完整页面集合和 `expected_revision` CAS，校验连续页序、合法旋转和资产归属，保留原始资料并使旧批次、候选、分析 job 失效。
- 复核申请按作答一条、幂等键同载荷重试/异载荷冲突、跨学习者拒绝；管理员或授权 reviewer 才能接单/裁决，关闭后禁止再次裁决。申请和裁决显式 `grade_unchanged=true`，不隐式改分。
- 导出、删除 tombstone、备份恢复重放纳入复核申请；新增页面修订、复核权限/幂等/成绩不变、删除与恢复生命周期回归，确定性全量结果为 59 passed；OpenAPI 快照更新为 53 paths / 19 schemas。
- revision 5 独立 Compose 使用临时密钥、项目、卷、端口和网络完成健康、生产 bootstrap 404、未受信业务 401、重启读取和清理探针；不改变真实 Open WebUI、真实 provider、人工标注和 T23 的外部验收边界。


## D14 / 2026-11-03

- 薄 Tools 适配器按当前 Open WebUI 0.12.5 的加载契约补齐实例级 Pydantic `Valves`、可选 per-user `UserValves.DD_LEARNER_ID` 和宿主注入的 `__user__`。subject 只来自服务端 user id；模型参数不能覆盖保留上下文。该改动只增强隔离兼容性，不把 Tool 变成业务实现或放宽服务端学习者授权。
- 新增 `tests/open_webui_harness.py` 与 `tests/test_open_webui_compat.py` 仿真源码加载、Valves 替换、公共方法发现和保留参数过滤；新增 `docs/OPEN_WEBUI_TOOLS_INTEGRATION.md` 与兼容证据报告。测试使用假的 HTTP 入口，未注册正式 Tool、未读写 `webui.db`、未调用真实 provider；真实注册/原生回调继续保持 T03/T20 阻塞。


## D15 / 2026-11-03

- 兼容 harness 增量回归后，当前确定性全量为 62 passed（服务 53、Tools/Open WebUI 兼容 9）；`compileall` 通过，OpenAPI runtime 与 `docs/contracts/openapi-v1.json` 均为 53 paths / 19 schemas 且内容一致。该数字只更新本地技术证据，不改变真实 Open WebUI 注册/回调、真实 provider、人工标注或 T23 的阻塞状态。

## D16 / 2026-11-03

- 完成文档一致性审计后，将 `docs/IMPLEMENTATION_BACKLOG.md` 顶部的“37 项测试、schema revision 3”明确标注为 2026-11-02 历史快照，并指向 `docs/goal/` 与 `docs/verification/` 的当前事实；当前本地结果写为 62 passed、schema revision 5。该修订只消除历史数字被误读为当前状态的歧义，不改变任何任务状态、外部阻塞或 Goal 完成门槛。

## D17 / 2026-11-03

- 隔离验证继续以 `dd-learning-isolated-api-20261103d` 与 `dd-openwebui-isolated-20261103d` 为边界：Learning API schema revision 6、生产模式 bootstrap 关闭、API 无宿主端口且网络 `internal=true`。`dd_learning_v1` 已在隔离 Open WebUI 0.12.5 实例通过原生 `get_tools` loader 注册并完成 Valves/UserValves、宿主 subject 和可信 UI 回调探针。该证据只覆盖隔离注册与合成回调，不等同真实模型发起的浏览器 tool call、真实 provider、人工质量或 T23；Goal 继续保持 active。

## D18 / 2026-11-03（可信 UI 回调实现由 D19 记录的现状取代）

- 批量导入确认在创建和提交 challenge 前共享严格候选校验：item 必须属于当前学习者和批次、revision/状态有效、verdict 为 `incorrect` 或 `partial`、`verification_status=manual`、候选证据非空，并存在当前 revision 且 verdict/证据一致的人工 judgment。重复 ID、非法 revision、跨批次/跨学习者和失效 judgment 均拒绝；提交校验失败不会消费 challenge。
- `start_trusted_interaction` 不再把服务端 challenge 或 nonce 放入模型可见结果，也不向服务端申请 challenge。它只返回 nonce-free `requires_trusted_ui` handoff；可信工作台重新读取资源、展示原卷/题面并完成一次性 challenge 回调。该边界避免模型看到确认集合或学生原始答案，整卷确认不能被普通聊天输入冒充。该阶段实现后来由 D19 记录的 Open WebUI 原生 callback 适配器取代。

## D19 / 2026-11-03

- 核对当前 `learning_service/tools.py`、自动化回归和隔离 Open WebUI 注册内容后，确认 `start_trusted_interaction` 使用原生 `__event_call__` 执行 `input`/`confirmation`：适配器先读取并展示服务端原文，只有回调接受后才创建并消费一次性 challenge。challenge、nonce 和原始答案不进入模型可见结果；取消或缺少 callback 时不创建 challenge。D18 的 nonce-free `requires_trusted_ui` 描述是旧状态，已由当前实现取代。
- 本次仅对齐状态与证据文档；隔离浏览器首页和 Tools 页面已验收，真实模型 tool call/最终浏览器回调仍未验收。

## D20 / 2026-11-03

- 独立 `/ui` 的 Chromium 测验闭环纳入 T16/QA08 本地证据：临时数据库、合成身份与合成题目下完成启动、刷新恢复、提示、服务端判分、复核申请及取消；提示暴露后 `assessment_eligibility=false`，页面/接口不泄露原答案或答案键。challenge 和答案请求均为 POST，390px/1280px 无横向溢出。
- 浏览器实测发现复核申请成功状态被随后成绩刷新覆盖，已调整提示与刷新顺序并复验通过。该本地工作台证据不替代隔离 Open WebUI 真实模型 tool call、原生浏览器最终可信回调、真实 provider 或真实资料验收。

## D21 / 2026-11-03

- 在不触碰现有 Open WebUI 或既有隔离实例的前提下，用全新 Compose project `dd-learning-restore-check-20261103e` 实际完成 revision 6 镜像的干净启动、生产边界探针、合成账号/学习者授权与附件备份恢复、API 重启后状态读取，并清理临时容器/卷/网络。证据写入 `docs/verification/compose-isolation-2026-11-03-revision7.md`。该证据加强 T22/QA15 的本地恢复结论，但不改变真实 Open WebUI 浏览器组合、真实 provider、外部服务故障、人工标注或 T23 的待验收状态。

## D22 / 2026-11-03

- 原生 `__event_call__` 的异步 callback 受 120 秒等待上限约束，与 Open WebUI input/confirmation 事件声明的超时一致。超时、取消、异常或非肯定回调均 fail closed；在回调被接受前不创建或提交最终确认/答案 challenge。聚焦回归覆盖导入确认和答案提交两条路径，见 `docs/verification/trusted-ui-timeout-2026-11-03.md`。这是确定性适配器验证，不替代真实浏览器 callback 或模型发起的 Tool 调用。
