# DD-1.0 V1 Goal 状态

更新时间：2026-11-03

Goal：`01a19afc-30a8-78f3-aa59-e73e24ea4e84`（blocked）

Goal 工具当前运行状态：`paused`。仓库的 `blocked` 表示真实验收前置条件缺失，不可标记 `complete`；两个状态分别记录，续跑前按客户端契约核对并恢复目标。

新会话交接：`docs/goal/HANDOFF-SESSION-2026-11-03.md`。Goal 工具状态与仓库验收状态分开记录；续跑前按当前客户端契约核对并恢复目标。

目标是独立学习服务的 V1 技术交付与隔离验收。正式上线、真实资料外发、付费调用和 T23 持续试用仍需各自授权与真实条件；T24–T26 deferred。

当前阶段：S1–S4 核心实现、隔离构建与自动化验收。

已完成并有本地证据：

- 独立 SQLite/WAL、迁移（含 001 旧库升级到 revision 6；新增复核申请表和 Agent 预算时间字段）、账号/身份/学习者授权、附件目录、原件页记录和失败页状态。
- 整卷导入批次、逐页候选、五类判定、revision、可信挑战、批量确认、幂等和错题来源。
- 诊断待复核、学习记录确认、interval-v1 复习卡、正式题面、原始作答、服务端判分和一次调度事件。
- 数轴正式入口（`signed_number_subtraction`）、静态回退、受控 Agent 动作和薄 Tools 适配器。
- 独立 Docker/Compose、worker、备份/恢复工具和最近 78 项确定性服务/Tools/兼容测试（服务 64、Tools 11、Open WebUI 兼容 3）；schema migration revision 已推进到 6。全新 Compose project 的干净启动、生产边界、合成账号/附件备份恢复和 API 重启持久性见 docs/verification/compose-isolation-2026-11-03-revision7.md；迁移失败回滚、修复后重试、WAL 协商重试和双进程并发初始化见 docs/verification/migration-atomicity-2026-11-03.md；SQLite writer 进程中断后的 WAL 完整性与继续写入见 docs/verification/database-process-recovery-2026-11-03.md。
- stage 5 维护准入已实现：独立正确自然日、审核变式、30 天暴露间隔、到期和 session mode 均由服务端证据判断；practice 作答不晋阶并返回明确的不准入证据。
- 管理员 metrics 只返回聚合队列、失败页、复核、生命周期和幂等计数；已验证不包含学习者标识、原图、原始答案或 provider payload。
- 已在真实隔离子进程中验证 provider 外部调用期间 `SIGKILL` 后没有页面/候选业务写入，过期 worker lease 可重领，attempts 正确递增且候选/来源区域不重复；另以第二 SQLite 连接写入回归确认 provider 等待不持有 writer lock；备份恢复拒绝 manifest 漂移、校验和篡改和非空目标，并在恢复后执行 SQLite integrity_check。
- `/ui` 已接通完整本地受信工作台：账号/学习者上下文、上传、整卷批次、分析/取消、候选读取、候选判定/目标/证据复核和可信批量确认入口；本轮 Chromium 重新跑通上传两份合成资料→整卷分析→两页来源预览→人工判定/证据保存→可信确认→错题本，390px/1280px 均无页面横向溢出，数据库对账为 2 个候选、1 条 judgment、1 条错题来源和 1 条 active 错题，详见 `docs/verification/import-browser-recheck-2026-11-03.md`。独立测验工作台还完成启动、刷新恢复、提示、POST challenge/作答、最终服务端判分、复核申请和取消，提示暴露后资格保持 false，见 `docs/verification/browser-test-workbench-2026-11-03.md`。revision 6 独立 Compose 中的生产边界探针已完成。隔离 Open WebUI 0.12.5 已实际注册 `dd_learning_v1`，并用原生 loader、实例 Valves、per-user UserValves、宿主 `__user__` 和合成回调探针完成验证；trusted-header 登录与 Tools 页面读取也已完成。证据见 `docs/verification/compose-isolation-2026-11-03-revision6.md`、`docs/verification/open-webui-tools-registration-2026-11-03.md` 和 `docs/verification/open-webui-browser-probe-2026-11-03.md`。真实模型发起的浏览器 tool call、最终可信 UI 回调仍待验证。
- 多页 PDF 保留原 PDF，并为每页生成独立私有 PNG 资产、尺寸和页内容回查入口；页级资产已覆盖备份恢复和管理员删除后的不可回查生命周期；整卷批次持久化已校验的参考答案文档关联。
- 学习草稿确认幂等键强制、同键异载荷冲突保护，确认只接受服务端草稿原文（可选回显不一致会拒绝且不消费挑战）；整卷批次取消后迟到 worker 不得写成成功。

- 最近全量验证：`pytest -q` 为 78 passed（服务 64、Tools 11、Open WebUI 兼容 3），无失败；`pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py` 为 14 passed；`python3 -m compileall -q learning_service tests scripts`、`python3 scripts/verify_goal_consistency.py` 与 `git diff --check` 通过。一致性统计为 26 个任务、132 条证据路径、26 个 backlog 行、17 个 QA 行、20 个 manifest 路径引用。OpenAPI runtime 与快照最近核验一致，为 55 paths、19 schemas。本轮新增异步原生 UI callback 120 秒等待上限，超时 fail closed；导入确认与答案提交的超时回归断言不会请求或提交 challenge，详见 `docs/verification/trusted-ui-timeout-2026-11-03.md`。两条 Chromium 合成工作台链路分别覆盖导入复核→错题本和测验恢复→提示→POST challenge/作答→服务端判分→复核/取消；页面无异常、请求失败和横向溢出，详细数据见对应报告。UI 更新顺序和 favicon 请求行为也在最新浏览器运行中复验。全量快照 77/76 和兼容聚焦 13 项均为历史结果；五类候选人工确认、错误来源、人工 judgment/证据边界、challenge 不消费和可信回调后才消费等回归继续通过。隔离 Compose revision 6 的 health 200、schema revision 6、POST bootstrap 404、无宿主端口和 internal 网络边界已验证。真实模型 tool call 与最终可信回调仍待 provider/授权。证据见 `docs/verification/trusted-ui-timeout-2026-11-03.md`、`docs/verification/browser-test-workbench-2026-11-03.md`、`docs/verification/import-browser-recheck-2026-11-03.md`、`docs/verification/import-confirmation-five-verdicts-2026-11-03.md`、`docs/verification/document-consistency-2026-11-03.md`、`docs/verification/open-webui-tools-registration-2026-11-03.md`、`docs/verification/open-webui-browser-probe-2026-11-03.md`、`docs/verification/compose-isolation-2026-11-03-revision7.md` 和 `docs/verification/qa-matrix-2026-11-03.md`。

源码管理：已在确认项目根和父级没有仓库后建立 Git 基线，并发布至 https://github.com/zgybkjcn-a11y/dd-1.0-learning-system（公开，默认分支 `main`；旧 `master` 已删除）；初始交付提交 `ed67875d4eb189a226f30a38f71456be5b3233c7` 已包含在远端历史中。`.gitignore` 已通过 `git check-ignore` 验证数据、凭证与缓存排除。原有 `docker-compose.yml` 与 `batch_ingest.py` 留在本机并按精确路径忽略，不纳入公开版本；此前缺失的用户修改历史无法恢复。T01 已依据当前源码基线证据标为 `verified`，详见 `docs/verification/source-control-baseline-2026-11-03.md`。

当前未满足：在不升级生产的前提下，于隔离预发布 Open WebUI + Learning Service 中完成真实聊天模型 tool call 与浏览器最终可信 UI 回调、真实 OCR/模型提供商、整卷脱敏标注质量报告、外部数据库服务/对象存储/provider 网络故障演练和 T23 真实试用。T23 的试用准备见 `docs/verification/trial-readiness-2026-11-03.md`；未启动真实试用或创建虚构日志。预发布通过不等于正式切换，生产仍保持不变并需单独授权。

Goal 当前为 blocked、尚不可 complete：本地可实施的源码、部署、恢复、确定性故障与合成浏览器工作已完成并留证；继续完成核心验收必须改变外部条件。恢复所需最小输入为隔离模型/provider 及明确调用预算和外发范围、脱敏整卷与人工参考判定、隔离 Open WebUI 模型/账号和真实可信 UI 回调入口；T23 另需参与者/监护人同意、连续观察授权与 7–14 天真实时间。正式切换、付费调用和真实资料外发仍分别按授权流程执行。收到相应条件后从 T03/T04/T05 和对应 QA 门槛续验，不把隔离注册、合成资料或 mock provider 标为真实通过。
