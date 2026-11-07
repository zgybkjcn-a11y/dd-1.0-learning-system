# DD-1.0 阻塞与外部前置

2026-11-05 当前优先级：**两人数学测试版已部署**，一个现有家长账号切换七年级/二年级档案，14 道起步题、练习判分/恢复和手动错题本。用户已明确授权本家庭版生产上线；真实模型/OCR、学生资料外发和 Goal 写入仍禁止。设备根证书已安装并通过系统 TLS 校验，真实家长首次绑定待用户操作。复杂监控/完整恢复/商业化功能暂缓，不作为此次上线前置。下文旧批次的“未部署/禁止生产/下一步监控恢复”保留历史，仅在与本范围不冲突时适用。入口/首次使用/验证及运维见[家庭测试版交接](HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)。

2026-11-05 W08/W09补充：周期监控/去重提醒/容量/备份回执与独立失联检查已本地实现，21项新增聚焦和新隔离验证通过。SQL只读，但SQLite辅助文件需数据卷写权限；初次只读挂载失败证据保留。完整恢复七组件与顺序已设计，正式来源/秘密/RPO/RTO未填、合成回执不算真实备份。详见[监控与恢复计划报告](../verification/reuse-monitoring-recovery-plan-2026-11-05.md)。T/QA/W/Goal状态及执行限制保持。

2026-11-04 故障补充：新隔离组合已验证网关/API/WebUI停机隔离、认证WSS下退出与同Cookie恢复、主动SIGKILL137及合成库完整性；nginx解析/连接超时改为3秒，修改后故障请求约3秒返回。10项新增编排防护通过，六个测试容器最终退出0、卷保留；正式门槛/原137根因/T/QA/Goal状态不变。详见[故障报告](../verification/reuse-fault-isolation-2026-11-04.md)。

2026-11-04 停机补充：隔离停止工具现核对容器归属/固定ID、60秒宽限与实际退出码，非零/OOM/残留进程不能记为成功；新隔离WebUI冷启动及合成认证后正常停止，9项聚焦通过。原两次137原因未充分定位，正式负载/故障门槛保留。详见[停机报告](../verification/reuse-graceful-shutdown-2026-11-04.md)。


2026-11-04 第三批W07–W10：schema11/66/24、Tools1.1.0；独立sidecar/代理/秘密文件、固定基础OCI与16个hash依赖的50文件新源码候选/本地无缓存镜像、聚合告警及新隔离学习数据恢复已推进。实际结果与边界以[本轮交接](HANDOFF-SESSION-2026-11-04-W07-W10.md)和[工程报告](../verification/reuse-runtime-recovery-2026-11-04.md)为准。正式TLS/身份、聊天计费/网络/运维与完整架构恢复、模型最终原生回调/人工质量/试用仍缺，T/QA/Goal状态保留。


2026-11-04 第二批W04/W05/W06：当前schema11/契约66/24、Tools1.1.0，工作台/共享Tools/人工审核冻结版本已有本地实现和合成证据；89项主聚焦与19项有重叠契约复核通过，390/1280px合成浏览器通过。正式TLS/账号/Tools分享模型/最终原生回调、真实母题/人工质量、独立运行配置/新镜像与W07以后组合仍缺，T/QA状态不提升。详见[第二批历史交接](HANDOFF-SESSION-2026-11-04-W04-W06.md)与[工程报告](../verification/reuse-workbench-tools-review-2026-11-04.md)。旧P0/四格式没有重跑，未部署/真实调用/外发/Goal变更。

更新时间：2026-11-04

部署方向已由用户确定：复用本机 `http://172.19.116.53:53001/` 的现有 Open WebUI（Docker Compose、内置账号）。只读实测容器/项目/服务为 open-webui、版本0.12.5；未读取根 Compose、正式数据库/密钥或模型配置。对应[规划与工作计划](../open-webui-reuse/README.md)及[新交接](HANDOFF-SESSION-2026-11-04-OPENWEBUI-REUSE.md)已形成，仅为规划。

初始规划缺项（本地实现已由顶部第三批证据更新，以下保留当时背景）：现有 HTTP 入口与当前学习 Secure Cookie/HTTPS默认443规则不兼容；需要受信 TLS 入口和内置登录桥接。工作台根路径 `/api/v1/...` 需要 `/learning/` 适配；正式绑定/来源会话/两端学习者上下文、变式审核发布、新配置/镜像、网络重连与恢复仍待开发。WebUI 聊天模型费用不在学习台账中，聊天/学习模型/OCR须分别管控；现有 WebUI 模型配置本轮未读取，未把它写成无外发或已有额度。W01–W14是现有任务的实施子包，不新增T或提升状态。

此前provider交接见 [`HANDOFF-SESSION-2026-11-04-PROVIDERS.md`](HANDOFF-SESSION-2026-11-04-PROVIDERS.md)。本轮补齐了结构化诊断/变式 adapter、用量/预留/限额/对账、服务端会话和固定源码候选的本地实现；实际模型/计费、网关实现/目标运行配置、新镜像、真实质量/回调仍未满足。P0 历史复核缺项不能继续误读为当前工厂仍只有 mock，也不能把本地实现写成真实验收。

前次外部条件只读复核：`get_goal` 仍为 `goal: null`，没有新增授权、模型连接或标注资料。此前 `dd-learning-isolated-api-20261103d` 与 `dd-openwebui-isolated-20261103d` 均为 `exited`（退出码 `255`）；隔离网络仍存在且 `internal=true`。当时停止原因和卷内状态未检查；未启动容器或重跑四格式导入持久化测试。历史事实见 [`external-gates-recheck-2026-11-04.md`](../verification/external-gates-recheck-2026-11-04.md)，后续进度如下。

此前按计划完成 P0 本地准备：旧实例/卷保留，SQLite 检查副本确认旧 schema 为 6、Tool 内容不同；另起 `dd-learning-p0-20261104` 新环境，P0 快照 schema 7、固定 Open WebUI 0.12.5、internal 网络/独立卷/无宿主端口、当时源码/完整契约、原生 loader 和合成身份通过，停止/恢复后复验通过。P0 检查时可用模型为 0，真实模型 tool call、浏览器最终回调仍未执行；P2 仅有空标注规范，没有真实资料或人工结论。停止原因仍未知；默认 mock、外发关闭与所有任务状态保持原样。报告见 [`p0-isolated-runtime-2026-11-04.md`](../verification/p0-isolated-runtime-2026-11-04.md)，模板见 [`docs/quality/README.md`](../quality/README.md)。下表的真实外部门槛继续保留。

| 阻塞 | 影响 | 已尝试 | 可继续工作 | 最小外部动作 |
| --- | --- | --- | --- | --- |
| 实际诊断/变式端点与质量未验收 | T05/T13/T14 | 已实现 OpenAI 兼容 JSON schema adapter、引用/范围/数学校验、迟到拒绝与合成回归；未知 provider ID 仍降级 | 准备目标协议兼容、母题参数/人工审核发布联调，不发真实请求 | 明确实际模型/端点、授权与资料范围、预算、审核母题与审核人 |
| 实际计费/账单及费用恢复未验收 | T05/T21/T23 | 源码 metrics tracked=true；逐次台账、金额/次数/并发限制、暂停、重试预留和管理员对账已实现；P0 旧指标未更新 | 完善实际架构停用/恢复和监控方案，保留失败/中断预留，不把合成数值当实际金额 | 提供真实费率/价格版本、预算、实际调用范围与账单参考；现场/跨账单恢复另需验证 |
| 正式认证/接入与发布仍未完成 | T03/T16/T20/T22 | schema11/66/24、50文件候选/固定本地镜像、sidecar/内部TLS与合成账号、11方法原生loader及学习新卷恢复通过 | 核对WebUI停止时限；准备正式监控/完整架构恢复与具体接入差异；保留mock/外发0 | 正式IP证书信任/443策略、账号issuer/绑定清单/操作人/学习库；正式切换另需授权 |
| 无授权真实 OCR/模型连接、额度和外发范围 | T05、真实整卷质量、T23 | 完成 provider 边界、确定性 worker 和待复核降级 | 权限、上传、调度、恢复、模拟测试 | 提供明确 provider、预算、脱敏样本和外发授权 |
| 无脱敏整卷标注集/人工参考判定 | T04、T09/T10、质量报告 | 保留原件页、失败页、候选/证据状态 | 数据模型和人工复核流程 | 提供可控测试资料与审核结论 |
| 真实模型发起的 Open WebUI 浏览器 tool call/最终可信 UI 回调未验收 | T03、T18、T20、T23 | 已在隔离 Open WebUI 0.12.5 注册 `dd_learning_v1`，通过原生 loader、Valves/UserValves、宿主身份和合成服务回调探针；异步 callback 超过声明的 120 秒上限会 fail closed，导入确认与答案提交均不请求/提交 challenge，见 `docs/verification/trusted-ui-timeout-2026-11-03.md`；trusted-header 浏览器首页与 Tools 页面读取成功，见 `docs/verification/open-webui-browser-probe-2026-11-03.md`；独立 `/ui` 测验和导入复核 Chromium 合成链路分别见 `docs/verification/browser-test-workbench-2026-11-03.md`、`docs/verification/import-browser-recheck-2026-11-03.md`；revision 7 Compose 干净启动、恢复、重启持久性和清理边界已验证 | 不需要升级生产：在与目标版本相同的 disposable/staging Open WebUI + 独立 Learning Service 中配置隔离模型，验证真实浏览器 tool call、可信 UI 最终确认/提交、取消/超时/恢复和跨学习者拒绝；生产数据、正式 `data/`、正式 API/通知均保持阻断 | 提供隔离模型/provider、真实回调入口和授权配置；不需重做已完成的 Tool 注册；预发布通过也不等于生产切换 |
| 未授权正式切换、真实资料外发、付费调用 | 上线和 T23 | 完成可审阅代码、配置与检查清单 | 所有本地开发与隔离验收 | 用户在最终证据审阅后单独授权 |
| T23 真实试用尚未获准启动 | T23 结论和 G4 | 已形成 `docs/verification/trial-readiness-2026-11-03.md`，包含启动签核、7–14 天观察字段和停止条件；未创建参与者记录或虚构日志 | 继续完善隔离代码、报告模板和恢复说明 | 明确参与者/监护人同意、脱敏样本、人工审核、真实 Tools/回调、provider 预算和连续观察授权 |

本轮已清除的本地可实施项：schema revision 7 升级与旧版恢复、变式字段和 stage 5 maintenance gate、provider 边界回归、provider 异常事务回滚、上传数据库提交失败清理、PDF 页渲染失败清理、导出原子替换失败清理、导出/删除 tombstone 生命周期及清理失败隔离、管理员聚合 metrics、过期 lease 重领、备份 manifest 漂移/校验和/非空目标拒绝及恢复完整性检查，以及 SQLite writer 进程 `SIGKILL` 后的 WAL 完整性和继续写入验证；证据见 `docs/verification/maintenance-gate-2026-11-03.md`、`docs/verification/database-process-recovery-2026-11-03.md`、`docs/verification/service-tests-2026-11-02.md` 和 `docs/verification/observability-recovery-2026-11-02.md`。外部数据库服务、对象存储和真实网络 provider 故障仍未在本地覆盖；上述外部阻塞仍未被本地 mock 或合成资料替代。

本轮新增清除的本地项：手动错题录入、DOCX/XLSX 整份结构化文本候选、损坏 Office 文件可见失败和 `.doc`/`.xls` 拒绝；页面修订 CAS、复核申请生命周期；Tools 适配器可信上下文/结构化错误/资源路径编码/固定 challenge 分派回归；Agent 可信交互 UI-only handoff 回归；Open WebUI 源码加载、Valves 注入、保留签名过滤、宿主 user subject 和 UserValves 学习者上下文回归。证据见 `docs/verification/tools-agent-2026-11-03.md` 和 `docs/verification/open-webui-tools-compat-2026-11-03.md`。隔离 Open WebUI Tool 注册和原生 loader/合成服务回调已运行；真实浏览器组合与最终可信 UI 回调仍未验收，因此 T03/T20 仍有未完成验收。

本轮继续清除本地可实施项：批量确认现在要求当前 revision 的非空人工证据和一致 judgment，重复/非法候选与 challenge 后 judgment 变化均有回归；Agent 动作仅返回 UI-only handoff；薄 Tools 适配器通过原生 `input`/`confirmation` 回调收集用户响应，并只在用户接受后创建/消费 challenge。浏览器首页和 Tools 页面读取已由真实浏览器验证，但模型发起的 tool call 与最终浏览器回调仍未完成。

历史工作树复验记录：独立 Compose project `dd-learning-livecheck-20261103b` 在生产模式下 `/health` 为 200（当时 schema revision 6）、`POST /internal/bootstrap` 为 404、无受信上下文的业务请求为 401；结束后容器、卷和网络均已清理。该复验不改变真实 Open WebUI、真实 provider、人工标注和 T23 的外部阻塞。

本轮测验工作台浏览器复验新增一条可实施项：复核申请成功消息此前被随后触发的成绩读取覆盖，已调整 UI 更新顺序并由 Chromium 全流程确认。用户原有的未跟踪 `docker-compose.yml` 和 `batch_ingest.py` 未读取内容或纳入本轮改动。

本轮恢复证据已补齐：独立 Compose project `dd-learning-restore-check-20261103e` 以全新命名卷完成 API/worker 启动、生产边界探针、合成授权与附件备份恢复、API 重启后状态对账，并在结束时删除容器、卷和网络；详见 `docs/verification/compose-isolation-2026-11-03-revision7.md`。这只扩大 T22/QA15 的本地证据，不解除真实 Open WebUI、provider、人工标注或 T23 阻塞。

本轮又在不触碰现存隔离容器的临时 API/worker 环境中复验整卷导入工作台。两页候选、原页预览、人工判定/证据、可信确认与错题来源在浏览器和 SQLite 中对账一致；结果见 `docs/verification/import-browser-recheck-2026-11-03.md`。这是合成数据与 deterministic mock provider 证据，不改变 T03/T04/T05/T23 的真实外部阻塞。

本轮新增 `scripts/check_isolated_compose.py` 与六项回归。检查器解析仓库 tracked Compose 并拒绝宿主端口、bind mount、非 internal 网络、外部卷、provider 替换、开发模式和提权旁路，实际静态检查通过且未启动容器；证据见 `docs/verification/compose-preflight-2026-11-03.md`。这补充 QA15 的静态环境前置检查，不覆盖主机防火墙、Open WebUI 持久化连接、外部数据库/对象存储/provider 故障，不改变 T21/T22 的未满足项或 Goal 的 blocked 状态。

## 2026-11-04 第一批复用工程更新

用户确认沿用IP，HTTPS目标为 `https://172.19.116.53`（443、IP SAN证书），宿主443未见TCP监听仅是只读输入。网关/身份CLI/来源绑定/共享上下文及前缀基础已有schema10本地实现，74聚焦与390/1280px合成浏览器通过；此前对应“仅规划/待开发”描述以[本轮工程证据](../verification/open-webui-reuse-engineering-2026-11-04.md)为准。浏览器303后续导航由探针模拟，实际TLS登录/回调未验收。

证书/客户端信任、IP稳定性、HTTP53001策略、正式绑定/操作人/学习库、完整入口/Tools上下文与最小投影、人工变式审核、独立sidecar/代理/新镜像、实际监控与完整恢复继续推进；真实模型/OCR/账单、脱敏整卷/人工参考和7–14天真实试用门槛保留。P0/schema7未改变或复验；P2仍空模板，101是此前全量、102是此前provider聚焦，74是本轮独立聚焦，不能相加称为全量。全部T/QA状态保留，Goal API为null；不生产部署、真实调用或外发资料。
