# DD-1.0 V1 会话交接：P0 执行与生产就绪缺口

日期：2026-11-04（Asia/Shanghai）。运行状态最后只读复核：16:17。工作目录：`/home/deniskorfei/projects/open-webui`；分支：`main`。

**后续续跑入口已更新为 [`HANDOFF-SESSION-2026-11-04-PROVIDERS.md`](HANDOFF-SESSION-2026-11-04-PROVIDERS.md)。** 下文是本文件生成时的 P0/schema 7 历史。后续源码已实现诊断/变式/费用/会话，升至 schema 9/契约 61/22，P0 保持原快照；不要无变更重跑本文件验证，或沿用其“当前源码一致”描述来验收新代码。

**下文保留 P0 会话生成时的交接。** 旧 `HANDOFF-SESSION-2026-11-04.md` 与 `HANDOFF-SESSION-2026-11-04-CONTINUATION.md` 保留历史实现和证据，不覆盖。P0 会话完成本地隔离准备及 P2 空规范，之后只评估生产就绪，没有生产部署、真实 API 调用、真实学生资料外发或试用启动。

## 1. 当前结论

- 新隔离 project `dd-learning-p0-20261104` 的 API、worker、Open WebUI 当前运行；API/Open WebUI healthy，无宿主端口发布，使用新命名卷和 internal 网络。
- 当前候选已实测 Learning API schema revision 7、Open WebUI 0.12.5、源码指纹/完整 OpenAPI 一致、原生 loader 11 方法、合成身份/UserValves、停止/恢复。
- 可用模型在 P0 检查时为 0，配置仍 offline、OpenAI/Ollama 关闭；没有真实模型发起的聊天 tool call 或最终浏览器可信回调，也没有宿主浏览器入口。
- P2 是空标注规范、5 份零记录 CSV 和 2 份空 JSON；没有脱敏整卷、人工参考、审核人、验收阈值或质量结果。
- **生产就绪复核新增明确工程缺口：真实诊断/变式 provider 仍未实现，外部费用统计/金额控制未完成；独立工作台还需正式认证和入口联调。不能把这些都写成“只差凭据”。**
- Goal API 最后返回 `goal: null`；仓库 Goal 状态仍 `blocked`。所有 T 任务状态未提升，不创建或完成 Goal。
- 当前源码、测试和原配置保留；最近全量 **101 passed** 是此前基线。本会话没有重跑四格式持久化或全量 pytest。

## 2. 本会话做了哪些任务

| 工作 | 做到哪里 | 证据/产物 |
| --- | --- | --- |
| 承接已有 V1 | 读取交接、台账、QA、Git/Goal；保留未提交改动 | STATUS、TASKS；Goal API 为 null |
| 外部条件复核 | 查到两个旧隔离实例停止、退出码 255；有限日志不足判断原因 | `docs/verification/external-gates-recheck-2026-11-04.md` |
| 详细后续计划 | 固定 P0–P7 的依赖、工作量、交付物与通过标准 | `NEXT-TASK-PLAN-2026-11-04.md` |
| P0 旧版本核对 | 停止状态下复制 SQLite 主文件/存在的 WAL/SHM，随后仅查询副本；旧库实测 revision 6，旧 Tool hash 不同 | P0 报告；临时检查副本 |
| P0 新候选环境 | 仅白名单构建上下文、缓存固定基底，创建独立 API/worker/Open WebUI | `scripts/prepare_isolated_runtime.py` |
| P0 API/边界/契约 | health、bootstrap 404、无受信上下文 401、跨学习者 404、全源码 hash/完整 OpenAPI 一致 | `scripts/isolated_runtime_probe.py` |
| P0 当前 Tool | 仅在新实例注册当前源码/临时 Valves/UserValves；原生 loader 11 方法及身份读取通过 | `scripts/isolated_tool_probe.py` |
| P0 停止/恢复 | 新环境 stop → resume；API/契约及未重新注册的 Tool 读取通过；start 拒绝覆盖已有资源 | P0 MD/JSON 报告 |
| P2 空参考集规范 | 原文、作答、五类判定、区域/跨页、集合拆分、覆盖与阈值签核规范；模板无样本 | `docs/quality/` |
| 生产就绪评估 | 列出真实接入/质量、正式认证、发布物、费用/监控、备份恢复和使用准入缺口 | 本文件第 5 节；DECISIONS/BLOCKERS/TASKS |

本会话没有修改 `learning_service` 核心源码、现有测试或 `.env.example`；新增的是隔离准备脚本、规范、报告和进度文档。没有提交/push 本会话改动。

此前已完成的四格式错题内容持久化是承接基线：PNG/PDF/DOCX/XLSX 确认后列表/详情、`content_json`、来源、人工 judgment 与 active 复习卡有回归。报告为 `docs/verification/mistake-import-content-persistence-2026-11-04.md`；不重新实现或无变更重跑。

## 3. T01–T26 当前进度

以 `TASKS.json` 为准，状态不等同整个 V1 已正式验收：

| 状态 | 任务 | 当前含义 |
| --- | --- | --- |
| verified | T01、T02、T06、T07、T08、T11、T15、T17、T19 | 已有本地/隔离确定性证据；对应真实入口边界仍按 QA 保留 |
| implemented | T03、T09、T10、T12、T13、T14、T16、T18、T20、T21、T22 | 业务实现已有，真实接入、人工质量、工程缺项或外部故障仍未满足 |
| blocked | T04、T05、T23 | 分别缺真实标注集/人工参考、真实 provider 许可与条件、真实试用条件 |
| deferred | T24、T25、T26 | 后续范围，用户未扩大范围时不启动 |

P0/P2 是执行计划标签，不新增或替代 T 编号。P0 通过只扩大 T03/T20/T22 本地准备证据；P2 空模板不解除 T04 阻塞。

## 4. 当前环境、文件和可用命令

### 新环境

- project：`dd-learning-p0-20261104`
- 容器：`dd-learning-p0-20261104-learning-api-1`、`dd-learning-p0-20261104-learning-worker-1`、`dd-learning-p0-20261104-open-webui-1`
- 网络：`dd-learning-p0-20261104_learning-internal`，internal=true
- 数据卷：`dd-learning-p0-20261104_dd_learning_data`、`dd-learning-p0-20261104_dd_openwebui_data`
- 运行目录：`/tmp/dd-p0-20261104/runtime/`
- 运行目录最后复核仍存在，`compose.private.json` 为 0600；包含临时凭据，**不得打印、提交、上传或当作生产配置/长期凭据备份**。
- 当前项目源文件 hash 与 P0 候选快照最后复核一致。

完整版本/指纹和结果见 [`p0-isolated-runtime-2026-11-04.md`](../verification/p0-isolated-runtime-2026-11-04.md) 与对应 JSON。OpenAPI 为 56 paths / 20 schemas，完整内容一致；依赖为 fastapi 0.136.1、uvicorn 0.44.0、pydantic 2.12.5、python-multipart 0.0.26、Pillow 12.1.1、PyMuPDF 1.27.2.2。

需要相应检查或恢复时才执行，当前运行正常且无相关变化时不重复跑整套 P0：

```bash
python3 scripts/prepare_isolated_runtime.py verify --run-dir /tmp/dd-p0-20261104/runtime
python3 scripts/prepare_isolated_runtime.py check-tools --run-dir /tmp/dd-p0-20261104/runtime
python3 scripts/prepare_isolated_runtime.py stop --run-dir /tmp/dd-p0-20261104/runtime
python3 scripts/prepare_isolated_runtime.py resume --run-dir /tmp/dd-p0-20261104/runtime
```

`start` 只用于尚无资源的新 project；当前 project 已存在，要恢复使用 `resume`。脚本会拒绝非空 prepare 目录、已有 project 的 start 和临时 Compose hash 漂移；不要删除/覆盖资源或偷偷更新 hash 绕过保护。P1 若获准使用新模型配置，先形成新的可审阅配置和边界验证。

若 `/tmp` 运行文件已经消失，不猜测凭据、不重新创建同名 project 覆盖既有卷。需恢复现存环境时按实际状态处理，或选择新目录/新 project 做 disposable 准备。

### 旧环境与构建限制

旧 `dd-learning-isolated-api-20261103d`、`dd-openwebui-isolated-20261103d` 仍停止，原卷/Tool 保留。退出原因未知。SQLite 检查副本不包含完整附件/配置恢复集合，不能称完整备份或恢复成功。

原始 Dockerfile 的离线构建未成功；最终方案先核对缓存基底的锁定依赖，再在 network=none 构建中复制当前源码。学习服务缓存基底为 `sha256:14ea733a5100079b01bfe5be218fb8a55732451858dc656b9d6cb3b3b7b5ef49`；Open WebUI 固定缓存镜像为 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd`。不宣称原始 Dockerfile 无缓存全新构建通过。

构建上下文只复制 17 个白名单文件，没有把仓库根直接交给 Docker，没有读取根目录禁读文件。

## 5. 还有哪些未做

| 缺项 | 对应任务 | 下一步及条件 |
| --- | --- | --- |
| 真实聊天 tool call 与最终浏览器可信回调 | T03/T16/T18/T20 | 在获准测试模型和受控浏览器入口下验证成功、取消/120 秒超时、刷新/断线、修订/重放和跨学习者拒绝；不能用 loader/合成 callback 替代 |
| 真实诊断/变式适配器代码 | T05/T13/T14 | `learning_service/providers.py:527` / `:533` 的工厂仅支持 mock，其他 ID 返回 `UnconfiguredProvider`；先补连接配置、请求/响应 schema、引用/范围校验、超时与安全降级，再做获准实测 |
| 真实 OCR/模型调用 | T05，关联 T09/T13/T14 | 腾讯 `QuestionSplitOCR` 已有实现，但没有真实调用；需独立凭据、明确许可、预算/调用上限、endpoint/出网及资料范围 |
| 实际外部调用统计/金额控制 | T05/T21 | `learning_service/app.py:1467` 仍返回 `external_calls.tracked=false`；Agent 步数/时间预算不等于金额控制，需统计、限额/停用、重试/限流和费用对账 |
| 真实资料与人工质量 | T04/T09/T10/T12/T13/T14 | 空模板尚无数据；需脱敏整卷、逐题边界/转写/作答/参考判定、审核人、题型覆盖与冻结验收规则 |
| 正式登录/学习者绑定/入口 | T03/T16/T20/T22 | `/ui` 是本地验收工作台，客户端 account/learner 头不能替代生产认证；需真实登录后端/受信网关、审核权限及上传/今日任务/错题本/测验入口；密钥留在服务端 |
| 固定生产发布物与配置 | T22 | 审阅既有未提交改动并固定候选版本/镜像 digest；形成独立交付与生产配置，不依赖 `/tmp` 临时凭据，不照搬 P0 offline/关闭持久化设置，不顺便重置既有 WebUI 配置或轮换原密钥 |
| 实际生产架构故障、容量/监控 | T21/T22 | 当前 SQLite/本地附件已有本机故障证据；按实际架构确定容量、磁盘/队列/告警与 provider 网络恢复。外部 DB/对象存储不使用时需明确范围决策，不自行消掉未验收项或无故引入新架构 |
| 完整生产备份与切换恢复 | T22 | 冻结写入、排空 worker、制作新的一致性备份；副本恢复/数据对账/耗时、维护窗口与失败处理。只换镜像或开放写入后覆盖旧快照不能声称无损 |
| 真实试用及扩大开放 | T23 | 参与者/监护人同意、使用/外发范围、保留删除规则、人工抽检、预算与启动授权；连续 7–14 自然日真实观察后人工复核，可在预发布环境进行 |

本会话用户询问了生产前置工作，属于就绪咨询，**没有授权实际生产切换、真实 API、真实资料外发或新增付费调用**。受限“手动录入+人工复核”首发只是讨论选项，用户没有接受缩小首发范围；继续按完整 V1 台账执行，不自签缩减范围后完成。

## 6. 新会话下一步怎么继续

1. 先读本文件、STATUS/TASKS/BLOCKERS/DECISIONS、详细计划、P0 报告与 QA。旧两份交接作为历史依据。核对 Git/Goal、指定隔离容器元数据及候选源码变化，不重做已完成测试。
2. 若测试模型、明确调用许可和可信浏览器条件已到位，从 P1 真实模型 tool call/最终回调续验；当前条件尚未到位时，保留这项外部门槛。
3. **当前可独立推进的工程项：真实诊断/变式 provider 接口与实现、外部用量/费用限额控制、正式认证/入口和生产发布物准备。** 先明确选用协议/范围并复用现有 provider/权限/worker 架构；本地可用合成 HTTP 响应验证，不发真实请求、不自行编造模型连接/预算/质量结论。不能因缺真实调用许可把尚未实现的 adapter 当作已实现。
4. 资料/审核人到位后填充 P2 并冻结验收口径；provider 获准后 P3 受控冒烟；随后 P4 质量、P5 故障/兼容恢复、P6 准入、P7 真实试用。阶段间无依赖的准备工作可同期排期，默认单执行者，不自动启用子代理。
5. 只在相关实现/版本/状态变化、失败或未解决疑点时复验；四格式持久化和 P0 已通过证据复用。新增代码按风险做必要回归，实际报告与未满足门槛分别更新。

## 7. 持续约束与验证事实

- 保留全部未提交改动；不 reset、checkout、清理、覆盖用户文件，也不擅自提交/push。
- 不读取或修改根目录 `docker-compose.yml`、`batch_ingest.py`，不读取正式 WebUI 密钥库来替代授权。
- 腾讯 OCR 默认 `mock-document-v1`，`TENCENT_OCR_EXTERNAL_CALLS_ENABLED=0`；不调用真实模型/OCR API、不外发真实学生资料、不部署生产，除非后续用户明确改变对应限制并给出范围。
- 工具权限/网络权限放宽不等于真实调用或生产授权。当前环境允许网络和文件操作，业务授权限制仍有效。
- 本地 mock/合成资料、原生 loader、真实组件连接、人工质量与真实试用证据分开记录；不把任何局部证据写成正式 V1 验收通过。
- 不创建或完成 Goal；API 最近无活动目标，仓库 blocked。T24–T26 不扩大。

本会话实测通过：P0 内部 HTTP/源码/完整契约/原生 loader/停止恢复，3 个新增脚本编译，Compose 静态 preflight，空模板解析/零记录/阈值未签核、已有 project 覆盖拒绝、文档一致性和 diff-check。此前 P0 一致性统计为 149 条 evidence paths，后续新增代码缺项引用的统计以最新 checker 为准。

最近全量测试基线仍为此前 **101 passed**；本会话没有全量 pytest 或四格式聚焦重跑。不得把本文件生成时的只读核对称为重新完成 API/浏览器/质量验收。

## 8. 新会话续跑指令

在项目的新会话中粘贴：

```text
继续 DD-1.0 V1 学习服务任务。工作目录 /home/deniskorfei/projects/open-webui。
先读取 docs/goal/HANDOFF-SESSION-2026-11-04-P0.md，再按其要求读取旧交接、STATUS.md、TASKS.json、BLOCKERS.md、DECISIONS.md、NEXT-TASK-PLAN-2026-11-04.md、P0 验证报告与 QA 矩阵，核对 git status --short --branch 和当前 Goal API。
当前 P0 新隔离环境 dd-learning-p0-20261104 已完成本地准备：schema 7、Open WebUI 0.12.5、源码/完整契约、原生 loader/合成身份及停止恢复通过；模型数为 0，真实模型 tool call 和最终浏览器回调未验收。P2 只有空标注模板，101 passed 是此前基线，不重做四格式持久化或无变更重跑 P0。
从交接中的下一项可执行工作继续：条件齐备时优先 P1；未具备真实调用条件时，推进诊断/变式真实 provider 的本地接口实现、用量/费用限额控制和正式认证/发布准备。当前这两类 provider 非 mock 配置返回 UnconfiguredProvider，费用指标 tracked=false，不能写成只差凭据。
保留所有现有未提交改动，不 reset、checkout 或清理；不读取/修改根目录 docker-compose.yml、batch_ingest.py。不调用真实模型/OCR API、不发送真实学生资料、不部署生产；保持 OCR 默认 mock、外发关闭，不把 mock/合成/loader 证据当真实验收，不创建或 complete Goal。生产部署咨询未构成执行授权，T24–T26 保持 deferred。
更新真实实现、必要验证、任务证据/缺项与交接，默认单执行者，不启用子代理。
```

## 9. 本交接生成后的最终核对

文档一致性、入口/报告链接和 diff-check 通过：`tasks=26, evidence paths=152, backlog task rows=26, QA matrix rows=17, manifest path references=22, release authorization boundaries intact`。49 个进度文档之外的既有改动文件指纹与交接生成前一致；本次仅新增本文件并补充进度/缺项文档，源码、测试、配置和隔离脚本未改动。所有任务状态保留，原 unmet 内容保留并追加生产复核缺项。Goal API 最后读取仍为 `goal: null`。
