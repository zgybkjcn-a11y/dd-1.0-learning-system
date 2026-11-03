# DD-1.0 V1 交接

> 本会话的任务清单、当前状态、剩余门槛和续跑指令见 [`HANDOFF-SESSION-2026-11-03.md`](HANDOFF-SESSION-2026-11-03.md)。本文件保留完整运行入口与历史验收证据。

状态：Goal `blocked`，尚不可标记 `complete`。本地可实施项已完成；恢复需满足 `docs/goal/BLOCKERS.md` 所列真实外部条件。

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

当前聚焦确定性回归最近一次为 78 passed（服务 64、Tools 11、Open WebUI 兼容 3）；工具与 Open WebUI 兼容聚焦回归为 14 passed。异步可信 UI callback 超时不创建或提交 challenge 的证据见 `docs/verification/trusted-ui-timeout-2026-11-03.md`；独立测验工作台 Chromium 合成闭环见 `docs/verification/browser-test-workbench-2026-11-03.md`；本次整卷导入浏览器复验及数据库对账见 `docs/verification/import-browser-recheck-2026-11-03.md`。provider 外部调用期间第二连接写入、WAL 协商有界重试和双进程首次启动压力证据见 `docs/verification/migration-atomicity-2026-11-03.md` 与 `docs/verification/service-tests-2026-11-02.md`；SQLite writer 进程 `SIGKILL` 后的完整性与继续写入证据见 `docs/verification/database-process-recovery-2026-11-03.md`。

已验证：migration 006 的 Agent 预算时间字段、migration 005 的复核申请、两个学习者授权隔离、多页资产/可信挑战/幂等/worker 恢复、stage 5 maintenance gate、正式测验判分、Agent 与 Tools 权限边界、备份完整性及 revision 6/7 隔离 Compose；revision 7 还实际完成全新 project 的 API/worker 启动、生产边界、合成数据恢复和重启持久性。隔离 Open WebUI 0.12.5 已实际注册 dd_learning_v1；原生 get_tools loader 验证 11 个公开方法、实例 Valves、per-user UserValves、宿主 __user__ subject 和可信 UI 回调内 challenge 消费；trusted-header 浏览器已验证首页和 Tools 管理页可访问。证据见 `docs/verification/open-webui-tools-registration-2026-11-03.md`、`docs/verification/open-webui-browser-probe-2026-11-03.md`、`docs/verification/compose-isolation-2026-11-03-revision6.md` 和 `docs/verification/compose-isolation-2026-11-03-revision7.md`。

待补证据：真实 Open WebUI 浏览器组合与最终可信 UI 回调、真实 OCR/模型、整卷标注质量、外部数据库/对象存储/provider 网络故障演练、人工学科裁决和 T23 真实试用。T23 试用准备见 `docs/verification/trial-readiness-2026-11-03.md`；当前只有隔离注册和合成数据证据，未启动真实试用。

禁止把模拟 provider、合成资料、离线原型或 78 项确定性测试描述成正式上线、真实准确率或真实学习效果。正式切换、付费调用和真实资料外发保持单独授权门槛。

批量确认要求人工 judgment/证据，并覆盖 challenge 不消费回归。`start_trusted_interaction` 通过原生 `input`/`confirmation` 可信回调收集答案或确认；回调接受前不创建 challenge，接受后才由适配器提交一次性 challenge，返回结果不包含 nonce、challenge ID 或原始答案。`docs/OPEN_WEBUI_TOOLS_INTEGRATION.md`、`tests/open_webui_harness.py`、`tests/test_open_webui_compat.py` 和 `docs/verification/open-webui-tools-compat-2026-11-03.md` 仍覆盖当前 Open WebUI 0.12.5 的源码加载、实例级 Pydantic Valves、UserValves 学习者上下文和 `__user__` 保留签名过滤。兼容 harness 使用假的 HTTP 入口；隔离实例实际注册与原生合成回调另有证据，真实模型发起的浏览器 tool call 与最终浏览器回调仍待验收。

本次续跑新增整卷导入 Chromium 复验：上传两份合成页、分析、来源预览、保存人工判定/证据、POST 获取确认 challenge、POST 确认、错题本读取；数据库中 2 个候选（1 个 confirmed/incorrect、1 个 needs_review/undetermined）对应 1 条人工 judgment、1 条错题来源和 1 条 active 错题，批次因仍有待复核候选而保持 `awaiting_review`，390px/1280px 无横向溢出。证据及边界见 `docs/verification/import-browser-recheck-2026-11-03.md`。测验工作台挑战/答案提交也均使用 POST，提示后不获得独立资格，复核成功提示保持可见。最近全量回归为 78 passed，工具与 Open WebUI 兼容聚焦为 14 passed；`compileall`、`scripts/verify_goal_consistency.py` 和 `git diff --check` 通过。一致性统计为 26 个任务、132 条证据路径、26 个 backlog 行、17 个 QA 行和 20 个 manifest 路径引用。可复现的一致性校验位于 `scripts/verify_goal_consistency.py`；报告见 `docs/verification/document-consistency-2026-11-03.md`。

已在项目根建立本地源码仓库并提交 DD-1.0 基线；运行数据和凭证经 `.gitignore` 规则验证为忽略状态，没有远端或全局身份变更。顶层原有 `docker-compose.yml` 与 `batch_ingest.py` 未纳入基线，保持未跟踪；因初始化前无 Git 历史，无法恢复此前用户改动归属。T01 已 verified；T12/T16 的真实资料和可信工作台验收边界仍保留在任务记录中。

文档审计还将 `docs/IMPLEMENTATION_BACKLOG.md` 顶部的 37 项/revision 3 数字标记为 2026-11-02 历史快照，并明确当前确定性回归最近一次为 78 passed、schema revision 6，OpenAPI 最近核验为 55 paths / 19 schemas；任务证据、QA01–QA17 引用和发布 manifest 授权边界已复核。

Goal 已记录为 `blocked`：真实 provider/OCR、整卷人工标注、模型发起的 Open WebUI 浏览器 tool call/最终可信 UI 回调及 T23 真实条件未满足。当前不符合 V1 完成标准；收到 `docs/goal/BLOCKERS.md` 所列外部输入后从对应任务续验。
