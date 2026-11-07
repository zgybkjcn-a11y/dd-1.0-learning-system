# DD-1.0 V1 会话交接：provider、费用、认证与固定源码候选

日期：2026-11-04（Asia/Shanghai）。工作目录：`/home/deniskorfei/projects/open-webui`；分支 main。**这是 P0 之后的 provider 本地工程交接；后续复用部署规划从[新交接](HANDOFF-SESSION-2026-11-04-OPENWEBUI-REUSE.md)进入。** 保留本文件、P0、续篇和原交接的历史证据。

## 当前结论

真实模型调用仍被本轮限制禁止，P1 没有条件启动。本轮从可独立推进的工程项继续，完成诊断/变式 HTTP adapter、持久用量/费用控制、服务端浏览器会话与固定源码包准备。没有真实模型/OCR、真实学生资料外发、生产部署或试用。

- 当前源码 schema **9**：新增 008 provider 台账、009 browser sessions；OpenAPI **61 paths / 22 schemas**。
- P0 `dd-learning-p0-20261104` 仍运行原 **schema 7 / 56 paths** 快照；三服务 running，API/WebUI healthy、internal=true、无宿主端口。本轮只读元数据，未更新源码/私有配置/Tool 或重跑 P0。新源码与旧实例现在存在预期差异。
- 默认三个 provider 仍 mock，OCR/模型外发开关为 0、费用预算为 0。非默认的两个 OpenAI 兼容 ID 现有可调用 HTTP 的实现；其他未知 ID 仍降级，不再将这两项写成只有占位工厂。
- 本轮 **102 项聚焦通过（67 + 21 + 14）**；此前 **101 passed** 仍是旧全量基线。本轮未跑全量、四格式持久化或未变更的 Compose preflight。
- Chromium 390px/1280px 会话工作台合成链路通过，全部网页 URL 被本地 ASGI 拦截；不等同实际登录网关/TLS、Open WebUI 模型 tool call 或最终可信回调。
- 29 文件源码候选已生成并校验，包含既有未提交改动；image_digest=null，未构建、签名、提交/push、发布或部署。
- Goal API 起点 null；仓库 blocked，26 项状态保留，T04/T05/T23 blocked，T24–T26 deferred。不创建或 complete Goal。

## 已完成的本地实现

| 对应任务 | 实现 | 证据 |
| --- | --- | --- |
| T05/T13 | `openai-compatible-diagnosis-v1`，最小证据、JSON schema、知识点/逐字引用、澄清、安全降级、配置模型/提示词元数据、证据修订拒绝和 worker 结果复用 | `learning_service/model_providers.py`、`app.py`；`tests/test_model_providers.py` |
| T05/T14 | `openai-compatible-variant-v1`，审核母题与学习者/目标/整数域/单位范围，已有数轴模板参数，程序重建题干/答案，拒绝迟到/撤销审核；仅 job 草稿 | 同上；无实际审核发布投放 |
| T05/T21 | `UsageLedger` 逐请求预留金额、累计/UTC 日/单次金额、日/分钟次数、并发、持久暂停、用量估算与管理员对账；腾讯同样受控 | `provider_usage.py`、`providers.py`、migration 008、模型/腾讯回归 |
| T03/T06/T07/T16/T20 | 独立签名短声明→既有绑定→不透明会话，Secure/HttpOnly/CSRF/Origin、数据库角色、服务器学习者选择、退出/恢复撤销；`/ui` 会话模式 | `browser_auth.py`、migration 009、`tests/test_browser_auth.py`、浏览器 JSON |
| T02/T22 | 旧库/恢复迁移至 9；恢复撤销会话/暂停 provider/保留占用；固定源码包与未填生产配置模板 | `backup.py`、`prepare_learning_release.py`、打包回归、`docs/releases/` |

详细报告：[`provider-auth-release-local-2026-11-04.md`](../verification/provider-auth-release-local-2026-11-04.md) 与对应 JSON；浏览器：[`browser-auth-local-2026-11-04.json`](../verification/browser-auth-local-2026-11-04.json)。协议/费率/控制说明：[`PROVIDER_CONFIGURATION.md`](../PROVIDER_CONFIGURATION.md)。

费用接口仅管理员可用：GET `/api/v1/admin/provider-calls`（待对账优先）、POST `/api/v1/admin/provider-control`、POST `/api/v1/admin/provider-calls/{call_id}/reconcile`。metrics 源码 tracked=true，但没有真实费用；申报 token 是估算，对账来源是管理员账单引用。每次重试保留自己的预留，未知/中断占用不自动释放，运行中 reserved 不可直接对账；synthetic_http 不能登记为真实账单。金额/用量超额会暂停后续请求。恢复副本 reserved→unknown 且保留金额，实际账单时点与现场停止/恢复仍待验证。

诊断/变式一直 needs_review/草稿，无自动批准、入库、判分或投放。变式只支持已有 `signed_number_subtraction` 整数模板，母题需明确 parameters；本轮协议实现不构成选定真实模型或新的学科范围。

## 可审阅候选与运行边界

候选本机目录：`learning_data/release-preparation/dd-v1-provider-auth-20261104/`（Git 忽略），含 `source.tar.gz`、`manifest.json`。源码集合 SHA-256：`974dc7e5dbd3b5fbee77b5559754a8c4b44004f092d36cac96371d6cc36ee335`；归档 SHA-256：`b01a718aac46eacdebffcdb5729265a516d8e7e1f27aa99ae2cca563a3472230`。校验已通过，无密钥/数据库/学生附件/禁读根文件；该包未签名，不是已构建或部署的发布物。

```bash
python3 scripts/prepare_learning_release.py verify --destination learning_data/release-preparation/dd-v1-provider-auth-20261104
```

源码改变后在新目录 prepare，不覆盖已有封包。现有 `docker-compose.learning.yml` 保留隔离 mock 基线，没有转发新增模型/会话参数；正式网关与运行配置还需实现/联调。原始 Dockerfile 无缓存构建仍未通过，不用旧缓存/P0 镜像冒充新 schema 9 镜像。

P0 私有配置仍在 `/tmp/dd-p0-20261104/runtime/compose.private.json`（0600），不得打印、提交或当长期生产凭据。不要对旧 P0 执行当前源码/新契约一致性 verify 并将差异写成意外故障，也不要修改旧 manifest hash 通过检查。要检验新代码组合，先准备新 run-dir/project 和独立卷，从当前固定候选构建；不重用旧 P0 卷/私有配置、不清理现存资源。P0 当前不需要恢复，原两个旧隔离实例仍保留。

## 下一项可执行工作与缺项

1. 先读本交接、STATUS/TASKS/BLOCKERS/DECISIONS、计划第 12 节、当前报告和 QA，再核对 Git/Goal 与候选/旧 P0 差异。已有通过项不无变更复验。
2. 若真实调用限制被明确改变且测试模型、许可和可信浏览器到位，优先 P1 实际模型 tool call/最终可信回调；覆盖接受、取消/120 秒超时、刷新/断线、修订/重放和跨学习者。loader、直接调用或本地 ASGI 不替代。
3. 否则继续可独立推进的缺项：**实际登录网关/身份绑定管理与入口、独立新运行配置/固定镜像、费用中断现场恢复/监控准备、变式人工审核发布准备**。当前会话模块不是登录后端，源码封包不是完整生产发布。需保留真实供应商协议/价格/账单与运行时网络的未验收边界。
4. 实际诊断/变式模型/端点尚未指定；真实 OCR/provider 仍需独立凭据、明确调用许可/资料范围、预算与可核实费率/账单。外发关闭时只做本地合成响应，不自行填价格或启用出网。
5. P2 仍是 5 份零记录 CSV/2 份空 JSON；脱敏整卷、人工转写/判定/母题、审核人与冻结阈值尚缺，T04 不提升。资料/许可到位后按 P3/P4，再按实际架构做 P5/P6/P7。
6. SQLite/本地附件不替代外部 DB/对象存储/provider 网络或生产容量/磁盘/队列/告警，不能自行去掉 QA 门槛；完整生产一致性备份/维护切换尚缺。T23 还需参与者/监护人同意、启动授权与 7–14 天真实观察。

## 持续约束

保留全部未提交改动，不 reset、checkout 或清理；不读取/修改根 `docker-compose.yml`、`batch_ingest.py`，不读取正式 WebUI 密钥库。OCR 默认 mock、外发关闭，不调用真实模型/OCR、发送真实学生资料或部署生产。不把合成/loader/ASGI、估算金额/管理员合成账单和空质量模板写成真实验收，不创建或 complete Goal。默认单执行者，本轮没有子代理。

## 本轮最终核对

文档一致性与 diff-check 通过：`tasks=26, evidence paths=194, backlog task rows=26, QA matrix rows=17, manifest path references=24, release authorization boundaries intact`。当前入口、计划、状态与 QA 中的 P0/schema 7/56 paths 描述已明确标为历史，当前源码仍为 schema 9/61 paths/22 schemas；本轮收尾没有再次运行 pytest、四格式持久化、浏览器或 P0 验证。

29 个白名单文件与固定 manifest 的逐文件 SHA-256 完全一致，归档与源码集合校验通过；上文两项 SHA 不变，image_digest=null。收尾只更新不属于封包白名单的进度/证据文档，未覆盖候选或构建新镜像。

会话起点 `/tmp/dd-v1-local-engineering-20261104-start.json` 记录的 58 个既有改动文件中，19 个有本轮有意修改，39 个指纹完全一致，0 个缺失；有意修改路径与对比结果保存在[机器报告](../verification/provider-auth-release-local-2026-11-04.json)的 `final_audit`。不读取或修改禁读根文件，未 reset、checkout、清理、提交或 push。

Markdown 本地链接、JSON、默认 mock/外发关闭/零预算及发布授权边界检查通过。26 项任务和 QA01–QA17 状态均保留，T04/T05/T23 blocked，T24–T26 deferred。Goal API 收尾只读结果仍为 `goal: null`，仓库 blocked；未创建或 complete Goal。

真实模型 tool call/最终可信回调、实际 provider/账单、真实资料/人工参考、登录网关/TLS/绑定管理、新镜像/运行配置、实际架构故障/完整恢复和真实试用仍按上节缺项推进；102 项聚焦通过及 Chromium ASGI 合成证据不作为真实验收。
