# DD-1.0 阻塞与外部前置

更新时间：2026-11-03

| 阻塞 | 影响 | 已尝试 | 可继续工作 | 最小外部动作 |
| --- | --- | --- | --- | --- |
| 无授权真实 OCR/模型连接、额度和外发范围 | T05、真实整卷质量、T23 | 完成 provider 边界、确定性 worker 和待复核降级 | 权限、上传、调度、恢复、模拟测试 | 提供明确 provider、预算、脱敏样本和外发授权 |
| 无脱敏整卷标注集/人工参考判定 | T04、T09/T10、质量报告 | 保留原件页、失败页、候选/证据状态 | 数据模型和人工复核流程 | 提供可控测试资料与审核结论 |
| 真实模型发起的 Open WebUI 浏览器 tool call/最终可信 UI 回调未验收 | T03、T18、T20、T23 | 已在隔离 Open WebUI 0.12.5 注册 `dd_learning_v1`，通过原生 loader、Valves/UserValves、宿主身份和合成服务回调探针；异步 callback 超过声明的 120 秒上限会 fail closed，导入确认与答案提交均不请求/提交 challenge，见 `docs/verification/trusted-ui-timeout-2026-11-03.md`；trusted-header 浏览器首页与 Tools 页面读取成功，见 `docs/verification/open-webui-browser-probe-2026-11-03.md`；独立 `/ui` 测验和导入复核 Chromium 合成链路分别见 `docs/verification/browser-test-workbench-2026-11-03.md`、`docs/verification/import-browser-recheck-2026-11-03.md`；revision 7 Compose 干净启动、恢复、重启持久性和清理边界已验证 | 在隔离账号配置可调用模型/provider 后验证聊天 tool call、浏览器交互和 trusted UI 最终确认/提交回调 | 提供隔离模型/provider、真实回调入口和授权配置；不需重做已完成的 Tool 注册 |
| 未授权正式切换、真实资料外发、付费调用 | 上线和 T23 | 完成可审阅代码、配置与检查清单 | 所有本地开发与隔离验收 | 用户在最终证据审阅后单独授权 |
| T23 真实试用尚未获准启动 | T23 结论和 G4 | 已形成 `docs/verification/trial-readiness-2026-11-03.md`，包含启动签核、7–14 天观察字段和停止条件；未创建参与者记录或虚构日志 | 继续完善隔离代码、报告模板和恢复说明 | 明确参与者/监护人同意、脱敏样本、人工审核、真实 Tools/回调、provider 预算和连续观察授权 |

本轮已清除的本地可实施项：schema revision 6 升级与旧版恢复、变式字段和 stage 5 maintenance gate、provider 边界回归、provider 异常事务回滚、上传数据库提交失败清理、PDF 页渲染失败清理、导出原子替换失败清理、导出/删除 tombstone 生命周期及清理失败隔离、管理员聚合 metrics、过期 lease 重领、备份 manifest 漂移/校验和/非空目标拒绝及恢复完整性检查，以及 SQLite writer 进程 `SIGKILL` 后的 WAL 完整性和继续写入验证；证据见 `docs/verification/maintenance-gate-2026-11-03.md`、`docs/verification/database-process-recovery-2026-11-03.md`、`docs/verification/service-tests-2026-11-02.md` 和 `docs/verification/observability-recovery-2026-11-02.md`。外部数据库服务、对象存储和真实网络 provider 故障仍未在本地覆盖；上述外部阻塞仍未被本地 mock 或合成资料替代。

本轮新增清除的本地项：页面修订 CAS、复核申请生命周期；Tools 适配器可信上下文/结构化错误/资源路径编码/固定 challenge 分派回归；Agent 可信交互 UI-only handoff 回归；Open WebUI 源码加载、Valves 注入、保留签名过滤、宿主 user subject 和 UserValves 学习者上下文回归。证据见 `docs/verification/tools-agent-2026-11-03.md` 和 `docs/verification/open-webui-tools-compat-2026-11-03.md`。隔离 Open WebUI Tool 注册和原生 loader/合成服务回调已运行；真实浏览器组合与最终可信 UI 回调仍未验收，因此 T03/T20 仍有未完成验收。

本轮继续清除本地可实施项：批量确认现在要求当前 revision 的非空人工证据和一致 judgment，重复/非法候选与 challenge 后 judgment 变化均有回归；Agent 动作仅返回 UI-only handoff；薄 Tools 适配器通过原生 `input`/`confirmation` 回调收集用户响应，并只在用户接受后创建/消费 challenge。浏览器首页和 Tools 页面读取已由真实浏览器验证，但模型发起的 tool call 与最终浏览器回调仍未完成。

本轮工作树复验再次确认：独立 Compose project `dd-learning-livecheck-20261103b` 在生产模式下 `/health` 为 200（schema revision 6）、`POST /internal/bootstrap` 为 404、无受信上下文的业务请求为 401；结束后容器、卷和网络均已清理。该复验不改变真实 Open WebUI、真实 provider、人工标注和 T23 的外部阻塞。

本轮测验工作台浏览器复验新增一条可实施项：复核申请成功消息此前被随后触发的成绩读取覆盖，已调整 UI 更新顺序并由 Chromium 全流程确认。用户原有的未跟踪 `docker-compose.yml` 和 `batch_ingest.py` 未读取内容或纳入本轮改动。

本轮恢复证据已补齐：独立 Compose project `dd-learning-restore-check-20261103e` 以全新命名卷完成 API/worker 启动、生产边界探针、合成授权与附件备份恢复、API 重启后状态对账，并在结束时删除容器、卷和网络；详见 `docs/verification/compose-isolation-2026-11-03-revision7.md`。这只扩大 T22/QA15 的本地证据，不解除真实 Open WebUI、provider、人工标注或 T23 阻塞。

本轮又在不触碰现存隔离容器的临时 API/worker 环境中复验整卷导入工作台。两页候选、原页预览、人工判定/证据、可信确认与错题来源在浏览器和 SQLite 中对账一致；结果见 `docs/verification/import-browser-recheck-2026-11-03.md`。这是合成数据与 deterministic mock provider 证据，不改变 T03/T04/T05/T23 的真实外部阻塞。
