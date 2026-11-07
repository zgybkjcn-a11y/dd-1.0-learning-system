# DD-1.0 V1 Goal 状态

2026-11-05 当前优先级：**两人数学测试版已部署**，一个现有家长账号切换七年级/二年级档案，14 道起步题、练习判分/恢复和手动错题本。用户已明确授权本家庭版生产上线；真实模型/OCR、学生资料外发和 Goal 写入仍禁止。设备根证书已安装并通过系统 TLS 校验，真实家长首次绑定仍待用户操作。复杂监控/完整恢复/商业化功能暂缓，不作为此次上线前置。下文旧批次的“未部署/禁止生产/下一步监控恢复”保留历史，仅在与本范围不冲突时适用。入口/首次使用/验证及运维见[家庭测试版交接](HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)。

2026-11-05 W08/W09补充：周期监控/去重提醒/容量/备份回执与独立失联检查已本地实现，21项新增聚焦和新隔离验证通过。SQL只读，但SQLite辅助文件需数据卷写权限；初次只读挂载失败证据保留。完整恢复七组件与顺序已设计，正式来源/秘密/RPO/RTO未填、合成回执不算真实备份。详见[监控与恢复计划报告](../verification/reuse-monitoring-recovery-plan-2026-11-05.md)。T/QA/W/Goal状态及执行限制保持。

2026-11-04 故障补充：新隔离组合已验证网关/API/WebUI停机隔离、认证WSS下退出与同Cookie恢复、主动SIGKILL137及合成库完整性；nginx解析/连接超时改为3秒，修改后故障请求约3秒返回。10项新增编排防护通过，六个测试容器最终退出0、卷保留；正式门槛/原137根因/T/QA/Goal状态不变。详见[故障报告](../verification/reuse-fault-isolation-2026-11-04.md)。

2026-11-04 停机补充：隔离停止工具现核对容器归属/固定ID、60秒宽限与实际退出码，非零/OOM/残留进程不能记为成功；新隔离WebUI冷启动及合成认证后正常停止，9项聚焦通过。原两次137原因未充分定位，正式负载/故障门槛保留。详见[停机报告](../verification/reuse-graceful-shutdown-2026-11-04.md)。


2026-11-04 第三批W07–W10：schema11/66/24、Tools1.1.0；独立sidecar/代理/秘密文件、固定基础OCI与16个hash依赖的50文件新源码候选/本地无缓存镜像、聚合告警及新隔离学习数据恢复已推进。实际结果与边界以[本轮交接](HANDOFF-SESSION-2026-11-04-W07-W10.md)和[工程报告](../verification/reuse-runtime-recovery-2026-11-04.md)为准。正式TLS/身份、聊天计费/网络/运维与完整架构恢复、模型最终原生回调/人工质量/试用仍缺，T/QA/Goal状态保留。


2026-11-04 第二批W04/W05/W06：当前schema11/契约66/24、Tools1.1.0，工作台/共享Tools/人工审核冻结版本已有本地实现和合成证据；89项主聚焦与19项有重叠契约复核通过，390/1280px合成浏览器通过。正式TLS/账号/Tools分享模型/最终原生回调、真实母题/人工质量、独立运行配置/新镜像与W07以后组合仍缺，T/QA状态不提升。详见[第二批历史交接](HANDOFF-SESSION-2026-11-04-W04-W06.md)与[工程报告](../verification/reuse-workbench-tools-review-2026-11-04.md)。旧P0/四格式没有重跑，未部署/真实调用/外发/Goal变更。

更新时间：2026-11-04

Goal：`01a19afc-30a8-78f3-aa59-e73e24ea4e84`（blocked）

Goal 工具当前运行状态：无活动目标（本轮 `get_goal` 返回 `goal: null`）。仓库任务状态仍为 `blocked`，表示真实验收前置条件缺失；未创建新 Goal，也未标记 `complete`。

最新会话交接入口：[`HANDOFF-SESSION-2026-11-04-W07-W10.md`](HANDOFF-SESSION-2026-11-04-W07-W10.md)；首批总结保留于[`HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md`](HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)，含任务/进度/缺项/下一步和可粘贴续跑指令；[第一批工程交接](HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)保留实施证据。用户已授权本地工程并确认沿用IP，目标 `https://172.19.116.53`（443）；现有HTTP53001部署没有改动。第一批网关/身份CLI/来源绑定/共享上下文及前缀基础已实现，schema10/契约61/22，74聚焦通过，390/1280px合成浏览器通过；W01输入部分固定、W02/W03本地证据、W04部分实现。正式账号/TLS/证书信任、HTTP策略、绑定清单、Tools/审核发布、独立运行配置/新镜像和真实验收仍缺。旧P0/schema7与29文件schema9候选保留；本轮未部署、真实调用或外发资料，T/QA/Goal状态保留。详见[工程报告](../verification/open-webui-reuse-engineering-2026-11-04.md)。

此前本地工程交接：[`HANDOFF-SESSION-2026-11-04-PROVIDERS.md`](HANDOFF-SESSION-2026-11-04-PROVIDERS.md)，记录诊断/变式、费用、会话和固定候选。P0/P2 历史入口 [`HANDOFF-SESSION-2026-11-04-P0.md`](HANDOFF-SESSION-2026-11-04-P0.md) 保留；Goal API 与仓库 blocked 分开记录。

此前provider本地工程（2026-11-04历史schema9）：已实现 OpenAI 兼容结构化诊断/变式 adapter、证据/引用/母题/范围与迟到校验、逐请求用量/保守费用预留和限额/暂停/对账、受信网关声明与服务端会话。新增 migration 008/009 后源码 schema 9，OpenAPI 61/22；29 文件固定源码候选已生成，image_digest=null，未构建或部署。67 项新增/provider/认证/打包回归 + 21 项相关服务 + 14 项 Tools/兼容共 102 聚焦通过，Chromium 合成会话工作台 390px/1280px 通过；不是全量或真实验收。当前源码 metrics tracked=true，P0 仍保持 schema 7/旧源码与旧指标，未更新/复验。真实 provider/计费、登录网关实现/目标环境、新镜像和真实质量/回调仍缺，不能写成只差凭据。证据见 [`provider-auth-release-local-2026-11-04.md`](../verification/provider-auth-release-local-2026-11-04.md)。

2026-11-04 前次只读复核（旧隔离实例）：Goal API 仍返回 `goal: null`；此前隔离 Learning API 与 Open WebUI 容器均为 `exited`、退出码 `255`，隔离网络仍为 `internal=true`。当次未启动容器或检查停止原因，不沿用历史 health 作为当前就绪结论。真实模型、浏览器回调、脱敏标注集、provider 授权和试用条件仍缺失；任务状态不变，已完成的四格式导入持久化测试没有重跑。证据见 `docs/verification/external-gates-recheck-2026-11-04.md`。

后续详细执行计划见 [`NEXT-TASK-PLAN-2026-11-04.md`](NEXT-TASK-PLAN-2026-11-04.md)：先核对/准备隔离环境，再补真实模型 tool call 与可信回调；标注集可同期准备，真实 provider、质量评估、故障恢复和试用分别按条件推进。计划编写时尚未执行；后续实际进度如下，TASKS/QA/Goal 状态以证据为准。

P0 执行进度（2026-11-04 历史快照）：本地隔离准备已完成并留证，P2 空标注规范已准备。旧实例仍停止，检查副本确认旧 schema 为 6、Tool 与当时源码不同；新 project `dd-learning-p0-20261104` 使用独立卷/internal 网络、无宿主端口，实测 Learning API schema 7、Open WebUI 0.12.5、完整契约及 P0 候选源码指纹一致、原生 loader 11 方法和合成身份/UserValves 通过，停止/恢复后复验通过。P0 报告完成时新环境保持运行，可用模型为 0，真实模型 tool call 和最终浏览器回调未执行。证据见 [`p0-isolated-runtime-2026-11-04.md`](../verification/p0-isolated-runtime-2026-11-04.md)；空规范见 [`docs/quality/README.md`](../quality/README.md)。所有 T 任务状态不变，T04/T05/T23 仍 blocked；101 passed 为此前基线，P0 阶段未重跑四格式或全量 pytest。

目标是独立学习服务的 V1 技术交付与隔离验收。正式上线、真实资料外发、付费调用和 T23 持续试用仍需各自授权与真实条件；T24–T26 deferred。

当前阶段：S1–S4 核心实现、隔离构建与自动化验收。

已完成并有本地证据：

- 独立 SQLite/WAL、迁移（含 001 旧库升级到 revision 7；新增复核申请表、Agent 预算时间、手动错题内容和 Office 文本提取字段）、账号/身份/学习者授权、附件目录、原件页记录和失败页状态。
- 整卷导入批次、逐页候选、五类判定、revision、可信挑战、批量确认、幂等和错题来源；手动录入错题、图片/PDF 原件候选复核，以及 DOCX/XLSX 结构化文本候选。
- 诊断待复核、学习记录确认、interval-v1 复习卡、正式题面、原始作答、服务端判分和一次调度事件。
- 数轴正式入口（`signed_number_subtraction`）、静态回退、受控 Agent 动作和薄 Tools 适配器。
- 独立 Docker/Compose、worker、备份/恢复工具和最近 101 项确定性服务/Tools/兼容测试（服务 76、Tools 11、Open WebUI 兼容 3、腾讯 OCR 边界 5、隔离 Compose preflight 6）；schema migration revision 已推进到 7。全新 Compose project 的干净启动、生产边界、合成账号/附件备份恢复和 API 重启持久性见 docs/verification/compose-isolation-2026-11-03-revision7.md；迁移失败回滚、修复后重试、WAL 协商重试和双进程并发初始化见 docs/verification/migration-atomicity-2026-11-03.md；SQLite writer 进程中断后的 WAL 完整性与继续写入见 docs/verification/database-process-recovery-2026-11-03.md。
- stage 5 维护准入已实现：独立正确自然日、审核变式、30 天暴露间隔、到期和 session mode 均由服务端证据判断；practice 作答不晋阶并返回明确的不准入证据。
- 新增隔离 Compose 静态 preflight：解析实际 Compose 配置并拒绝宿主端口、生产 bind mount、非 internal 网络、外部卷、真实 provider、开发模式及提权/namespace 旁路；不启动容器，6 项回归通过。报告：`docs/verification/compose-preflight-2026-11-03.md`。该检查不覆盖运行时防火墙或外部数据库/对象存储/provider 故障演练。
- 管理员 metrics 只返回聚合队列、失败页、复核、生命周期和幂等计数；已验证不包含学习者标识、原图、原始答案或 provider payload。
- 已在真实隔离子进程中验证 provider 外部调用期间 `SIGKILL` 后没有页面/候选业务写入，过期 worker lease 可重领，attempts 正确递增且候选/来源区域不重复；另以第二 SQLite 连接写入回归确认 provider 等待不持有 writer lock；备份恢复拒绝 manifest 漂移、校验和篡改和非空目标，并在恢复后执行 SQLite integrity_check。
- `/ui` 已接通完整本地受信工作台：账号/学习者上下文、上传、整卷批次、分析/取消、候选读取、候选判定/目标/证据复核和可信批量确认入口；本轮 Chromium 重新跑通上传两份合成资料→整卷分析→两页来源预览→人工判定/证据保存→可信确认→错题本，390px/1280px 均无页面横向溢出，数据库对账为 2 个候选、1 条 judgment、1 条错题来源和 1 条 active 错题，详见 `docs/verification/import-browser-recheck-2026-11-03.md`。独立测验工作台还完成启动、刷新恢复、提示、POST challenge/作答、最终服务端判分、复核申请和取消，提示暴露后资格保持 false，见 `docs/verification/browser-test-workbench-2026-11-03.md`。revision 6 独立 Compose 中的生产边界探针已完成。隔离 Open WebUI 0.12.5 已实际注册 `dd_learning_v1`，并用原生 loader、实例 Valves、per-user UserValves、宿主 `__user__` 和合成回调探针完成验证；trusted-header 登录与 Tools 页面读取也已完成。证据见 `docs/verification/compose-isolation-2026-11-03-revision6.md`、`docs/verification/open-webui-tools-registration-2026-11-03.md` 和 `docs/verification/open-webui-browser-probe-2026-11-03.md`。真实模型发起的浏览器 tool call、最终可信 UI 回调仍待验证。
- 多页 PDF 保留原 PDF，并为每页生成独立私有 PNG 资产、尺寸和页内容回查入口；页级资产已覆盖备份恢复和管理员删除后的不可回查生命周期；整卷批次持久化已校验的参考答案文档关联。
- 学习草稿确认幂等键强制、同键异载荷冲突保护，确认只接受服务端草稿原文（可选回显不一致会拒绝且不消费挑战）；整卷批次取消后迟到 worker 不得写成成功。
- 错题本新增 `POST /api/v1/mistakes/manual` 手动录入；图片/PDF 保留原件并生成待复核候选；`.docx`/`.xlsx` 先做本地 OOXML 文本提取，整份文档生成候选，人工整理、判定并确认后才进入错题本。`.doc`/`.xls`、嵌入扫描图片、复杂排版和公式语义暂不承诺。

- 最近全量验证：`pytest -q` 为 101 passed（服务 76、Tools 11、Open WebUI 兼容 3、腾讯 OCR 边界 5、隔离 Compose preflight 6），无失败；其中四种文件格式导入确认后的错题本列表/详情及 `mistake_entries.content_json` 对账见 `docs/verification/mistake-import-content-persistence-2026-11-04.md`。`pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py` 为 14 passed；`python3 -m compileall -q learning_service tests scripts`、`python3 scripts/verify_goal_consistency.py` 与 `git diff --check` 通过。此前 schema 7 基线的 OpenAPI runtime 与快照一致，为 56 paths、20 schemas；当前源码 61/22 见顶部本地工程记录。手动错题、DOCX/XLSX 提取、损坏 Office 文件、旧格式拒绝和 schema revision 7 迁移回归均在服务测试中覆盖。本轮新增异步原生 UI callback 120 秒等待上限，超时 fail closed；导入确认与答案提交的超时回归断言不会请求或提交 challenge，详见 `docs/verification/trusted-ui-timeout-2026-11-03.md`。两条 Chromium 合成工作台链路分别覆盖导入复核→错题本和测验恢复→提示→POST challenge/作答→服务端判分→复核/取消；页面无异常、请求失败和横向溢出，详细数据见对应报告。UI 更新顺序和 favicon 请求行为也在最新浏览器运行中复验。Tools 适配器的异步 HTTP 请求改用可回收的短生命周期 executor，避免重复 `asyncio.run()` 收尾挂起；聚焦与全量回归均通过。五类候选人工确认、错误来源、人工 judgment/证据边界、challenge 不消费和可信回调后才消费等回归继续通过。隔离 Compose revision 7 的 health 200、schema revision 7、POST bootstrap 404、无宿主端口和 internal 网络边界已验证。真实模型 tool call 与最终可信回调仍待 provider/授权。证据见 `docs/verification/trusted-ui-timeout-2026-11-03.md`、`docs/verification/browser-test-workbench-2026-11-03.md`、`docs/verification/import-browser-recheck-2026-11-03.md`、`docs/verification/import-confirmation-five-verdicts-2026-11-03.md`、`docs/verification/mistake-import-content-persistence-2026-11-04.md`、`docs/verification/document-consistency-2026-11-03.md`、`docs/verification/open-webui-tools-registration-2026-11-03.md`、`docs/verification/open-webui-browser-probe-2026-11-03.md`、`docs/verification/compose-isolation-2026-11-03-revision7.md` 和 `docs/verification/qa-matrix-2026-11-03.md`。

源码管理：已在确认项目根和父级没有仓库后建立 Git 基线，并发布至 https://github.com/zgybkjcn-a11y/dd-1.0-learning-system（公开，默认分支 `main`；旧 `master` 已删除）；初始交付提交 `ed67875d4eb189a226f30a38f71456be5b3233c7` 已包含在远端历史中。`.gitignore` 已通过 `git check-ignore` 验证数据、凭证与缓存排除。原有 `docker-compose.yml` 与 `batch_ingest.py` 留在本机并按精确路径忽略，不纳入公开版本；此前缺失的用户修改历史无法恢复。T01 已依据当前源码基线证据标为 `verified`，详见 `docs/verification/source-control-baseline-2026-11-03.md`。

当前未满足：在不升级生产的前提下，于隔离预发布 Open WebUI + Learning Service 中完成真实聊天模型 tool call 与浏览器最终可信 UI 回调、真实 OCR/模型提供商、整卷脱敏标注质量报告、外部数据库服务/对象存储/provider 网络故障演练和 T23 真实试用。T23 的试用准备见 `docs/verification/trial-readiness-2026-11-03.md`；未启动真实试用或创建虚构日志。预发布通过不等于正式切换，生产仍保持不变并需单独授权。

仓库 Goal 当前 blocked，API 最近为 null，尚不可 complete。确定性基础、P0、空标注规范和本轮 adapter/费用/会话/固定源码候选都有本地证据；正式网关与新镜像/运行配置、实际计费/故障/恢复仍需继续工程与目标环境联调。核心真实验收需隔离模型/provider 及明确调用许可、预算/外发范围、脱敏整卷/人工参考及真实可信 UI 入口；T23 另需参与者/监护人同意、启动与连续观察授权及 7–14 天真实时间。所有 T 状态保留，不创建或 complete Goal，不执行生产切换、付费调用或真实资料外发。
