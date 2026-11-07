# DD-1.0 V1 交接

2026-11-05 当前优先级：**两人数学测试版已部署**，一个现有家长账号切换七年级/二年级档案，14 道起步题、练习判分/恢复和手动错题本。用户已明确授权本家庭版生产上线；真实模型/OCR、学生资料外发和 Goal 写入仍禁止。设备证书导入和真实家长首次绑定待用户操作。复杂监控/完整恢复/商业化功能暂缓，不作为此次上线前置。下文旧批次的“未部署/禁止生产/下一步监控恢复”保留历史，仅在与本范围不冲突时适用。 入口/首次使用/验证及运维见[家庭测试版交接](HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)。

2026-11-04 停机补充：隔离停止工具现核对容器归属/固定ID、60秒宽限与实际退出码，非零/OOM/残留进程不能记为成功；新隔离WebUI冷启动及合成认证后正常停止，9项聚焦通过。原两次137原因未充分定位，正式负载/故障门槛保留。详见[停机报告](../verification/reuse-graceful-shutdown-2026-11-04.md)。


2026-11-04 第三批W07–W10：schema11/66/24、Tools1.1.0；独立sidecar/代理/秘密文件、固定基础OCI与16个hash依赖的50文件新源码候选/本地无缓存镜像、聚合告警及新隔离学习数据恢复已推进。实际结果与边界以[本轮交接](HANDOFF-SESSION-2026-11-04-W07-W10.md)和[工程报告](../verification/reuse-runtime-recovery-2026-11-04.md)为准。正式TLS/身份、聊天计费/网络/运维与完整架构恢复、模型最终原生回调/人工质量/试用仍缺，T/QA/Goal状态保留。


2026-11-04 第二批W04/W05/W06：当前schema11/契约66/24、Tools1.1.0，工作台/共享Tools/人工审核冻结版本已有本地实现和合成证据；89项主聚焦与19项有重叠契约复核通过，390/1280px合成浏览器通过。正式TLS/账号/Tools分享模型/最终原生回调、真实母题/人工质量、独立运行配置/新镜像与W07以后组合仍缺，T/QA状态不提升。详见[第二批历史交接](HANDOFF-SESSION-2026-11-04-W04-W06.md)与[工程报告](../verification/reuse-workbench-tools-review-2026-11-04.md)。旧P0/四格式没有重跑，未部署/真实调用/外发/Goal变更。

最新会话总结：[任务、进度、缺项与下一步](HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)；新会话可复制[续跑指令](RESUME-SESSION-2026-11-04.txt)。本次总结只更新文档，原工程测试/候选/任务与Goal状态保留。

最新工程交接：[复用现有WebUI第一批本地工程](HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)。用户确认沿用IP，HTTPS目标443；W02/W03本地实现并有合成证据，W04基础部分实现，schema10/契约61/22，74聚焦与390/1280px合成浏览器通过。现有运行部署未变、正式认证/TLS/Tools/审核/配置/镜像与真实验收仍缺，T/QA/Goal保留。

此前[规划交接](HANDOFF-SESSION-2026-11-04-OPENWEBUI-REUSE.md)和[provider交接](HANDOFF-SESSION-2026-11-04-PROVIDERS.md)保留历史schema9/29文件包与102聚焦；101是此前全量，P0仍schema7。

> P0 阶段的历史入口为 [`HANDOFF-SESSION-2026-11-04-P0.md`](HANDOFF-SESSION-2026-11-04-P0.md)。新会话从顶部会话总结进入；旧续篇、原交接及以下运行入口保留历史证据。

P0 交接生成时的状态：仓库 Goal `blocked`，API 为 `goal: null`，不创建或标记 `complete`。P0 新隔离环境和空标注规范已完成；当时诊断/变式适配器及费用控制仍有本地工程缺项，后续实现见顶部新交接。真实接入/质量门槛保留；当前源码与旧 P0 运行快照的区别及续跑命令以新交接为准。

2026-11-04 本轮 Goal API 返回 `goal: null`。此前两个隔离实例当前均已停止（退出码 `255`），网络仍为 internal；未重启实例、调用真实 API 或重跑四格式导入测试。当前运行条件与外部门槛复核见 [`external-gates-recheck-2026-11-04.md`](../verification/external-gates-recheck-2026-11-04.md)，历史运行证据不代表当前就绪。

运行：

```bash
python3 -m compileall -q learning_service tests
pytest -q tests/test_learning_service.py
LEARNING_DEV_MODE=1 LEARNING_ADMIN_SECRET=dev python3 -m learning_service.app
python3 -m learning_service.worker
docker compose -f docker-compose.learning.yml up --build
```

部署入口是 `Dockerfile.learning`、`.dockerignore` 与 `docker-compose.learning.yml`。服务数据只写 `LEARNING_DATA_DIR` / `LEARNING_DB_PATH` / `LEARNING_ATTACHMENT_DIR`；不要挂载现有 Open WebUI `data/`。
镜像默认数据路径已经设为 `/var/lib/dd-learning`，Compose 通过同名环境变量显式固定并使用 `dd_learning_data` 独立卷。

当前确定性回归最近一次为 101 passed（服务 76、Tools 11、Open WebUI 兼容 3、腾讯 OCR 边界 5、隔离 Compose preflight 6）；工具与 Open WebUI 兼容聚焦回归为 14 passed。四种文件格式的确认后错题本内容、判定证据、来源、复习卡及数据库 `content_json` 对账见 `docs/verification/mistake-import-content-persistence-2026-11-04.md`。异步可信 UI callback 超时不创建或提交 challenge 的证据见 `docs/verification/trusted-ui-timeout-2026-11-03.md`；独立测验工作台 Chromium 合成闭环见 `docs/verification/browser-test-workbench-2026-11-03.md`；本次整卷导入浏览器复验及数据库对账见 `docs/verification/import-browser-recheck-2026-11-03.md`。provider 外部调用期间第二连接写入、WAL 协商有界重试和双进程首次启动压力证据见 `docs/verification/migration-atomicity-2026-11-03.md` 与 `docs/verification/service-tests-2026-11-02.md`；SQLite writer 进程 `SIGKILL` 后的完整性与继续写入证据见 `docs/verification/database-process-recovery-2026-11-03.md`。

已验证：migration 006 的 Agent 预算时间字段、migration 007 的手动错题与 Office 文本字段、migration 005 的复核申请、两个学习者授权隔离、多页资产/可信挑战/幂等/worker 恢复、stage 5 maintenance gate、正式测验判分、Agent 与 Tools 权限边界、备份完整性及 revision 6/7 隔离 Compose；revision 7 还实际完成全新 project 的 API/worker 启动、生产边界、合成数据恢复和重启持久性。隔离 Open WebUI 0.12.5 已实际注册 dd_learning_v1；原生 get_tools loader 验证 11 个公开方法、实例 Valves、per-user UserValves、宿主 __user__ subject 和可信 UI 回调内 challenge 消费；trusted-header 浏览器已验证首页和 Tools 管理页可访问。证据见 `docs/verification/open-webui-tools-registration-2026-11-03.md`、`docs/verification/open-webui-browser-probe-2026-11-03.md`、`docs/verification/compose-isolation-2026-11-03-revision6.md` 和 `docs/verification/compose-isolation-2026-11-03-revision7.md`。

待补证据：真实 Open WebUI 浏览器组合与最终可信 UI 回调、真实 OCR/模型、整卷标注质量、外部数据库/对象存储/provider 网络故障演练、人工学科裁决和 T23 真实试用。T23 试用准备见 `docs/verification/trial-readiness-2026-11-03.md`；当前只有隔离注册和合成数据证据，未启动真实试用。

禁止把模拟 provider、合成资料、离线原型或 101 项确定性测试描述成正式上线、真实准确率或真实学习效果。正式切换、付费调用和真实资料外发保持单独授权门槛。

批量确认要求人工 judgment/证据，并覆盖 challenge 不消费回归。`start_trusted_interaction` 通过原生 `input`/`confirmation` 可信回调收集答案或确认；回调接受前不创建 challenge，接受后才由适配器提交一次性 challenge，返回结果不包含 nonce、challenge ID 或原始答案。`docs/OPEN_WEBUI_TOOLS_INTEGRATION.md`、`tests/open_webui_harness.py`、`tests/test_open_webui_compat.py` 和 `docs/verification/open-webui-tools-compat-2026-11-03.md` 仍覆盖当前 Open WebUI 0.12.5 的源码加载、实例级 Pydantic Valves、UserValves 学习者上下文和 `__user__` 保留签名过滤。兼容 harness 使用假的 HTTP 入口；隔离实例实际注册与原生合成回调另有证据，真实模型发起的浏览器 tool call 与最终浏览器回调仍待验收。

错题本录入现支持手动录入、图片/PDF 上传候选和 DOCX/XLSX 整份文本候选；文档导入默认生成待复核候选，用户整理确认后才进入错题本。它不提供 Office 扫描图片 OCR、复杂版面或公式语义识别。

本次续跑新增整卷导入 Chromium 复验：上传两份合成页、分析、来源预览、保存人工判定/证据、POST 获取确认 challenge、POST 确认、错题本读取；数据库中 2 个候选（1 个 confirmed/incorrect、1 个 needs_review/undetermined）对应 1 条人工 judgment、1 条错题来源和 1 条 active 错题，批次因仍有待复核候选而保持 `awaiting_review`，390px/1280px 无横向溢出。证据及边界见 `docs/verification/import-browser-recheck-2026-11-03.md`。测验工作台挑战/答案提交也均使用 POST，提示后不获得独立资格，复核成功提示保持可见。最近全量回归为 97 passed，工具与 Open WebUI 兼容聚焦为 14 passed；`compileall`、`scripts/verify_goal_consistency.py` 和 `git diff --check` 通过。一致性统计以本轮续跑复验结果为准；可复现的一致性校验位于 `scripts/verify_goal_consistency.py`，报告见 `docs/verification/document-consistency-2026-11-03.md`。

2026-11-04 续跑补齐 PNG、PDF、DOCX、XLSX 上传→分析→人工判定→可信确认→错题本列表/详情回归，并修复确认路径未将错题内容写入 `mistake_entries.content_json` 的缺口；全量 `pytest -q` 为 101 passed（服务 76、Tools 11、Open WebUI 兼容 3、腾讯 OCR 边界 5、隔离 Compose preflight 6）。合成资料本地证据和边界见 `docs/verification/mistake-import-content-persistence-2026-11-04.md`；该变化不代表真实 OCR 或真实资料验收。Goal API 本轮 `get_goal` 返回 `goal: null`，仓库任务状态仍为 blocked，未创建 Goal 或标记完成。

已在项目根建立本地源码仓库并提交 DD-1.0 基线；运行数据和凭证经 `.gitignore` 规则验证为忽略状态，没有远端或全局身份变更。顶层原有 `docker-compose.yml` 与 `batch_ingest.py` 未纳入基线，保持未跟踪；因初始化前无 Git 历史，无法恢复此前用户改动归属。T01 已 verified；T12/T16 的真实资料和可信工作台验收边界仍保留在任务记录中。

前次文档审计将 `docs/IMPLEMENTATION_BACKLOG.md` 顶部的 37 项/revision 3 数字标记为 2026-11-02 历史快照，当时确定性回归为 97 passed、schema revision 7，OpenAPI 核验为 56 paths / 20 schemas；本轮全量回归已增至 101 passed，任务证据、QA01–QA17 引用和发布 manifest 授权边界已复核。

Goal 已记录为 `blocked`：真实 provider/OCR、整卷人工标注、模型发起的 Open WebUI 浏览器 tool call/最终可信 UI 回调及 T23 真实条件未满足。当前不符合 V1 完成标准；收到 `docs/goal/BLOCKERS.md` 所列外部输入后从对应任务续验。
