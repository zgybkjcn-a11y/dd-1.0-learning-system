# DD-1.0 V1 会话交接文档

更新时间：2026-11-04（Asia/Shanghai）；仓库分支：`main`；公开远端：`https://github.com/zgybkjcn-a11y/dd-1.0-learning-system`；撰写交接前最新已推送提交：`2c755ff`（隔离预发布验收边界）。

## 交接结论

生产环境**没有升级、没有切换、没有写入生产数据**。当前完成的是独立 Learning Service、隔离 Compose、合成资料和确定性回归；真实验收必须在与生产隔离的 disposable/staging Open WebUI + Learning Service 中完成。预发布通过后仍要单独审阅迁移、备份、回滚和切换清单，并取得明确授权，才能讨论生产升级。

仓库持久化状态是 `Goal blocked`，因为真实 provider、人工标注和真实试用条件尚未具备。当前 Goal 工具记录为 `paused`；新会话应先读取 Goal 状态并按客户端契约恢复，不要把 `paused` 或仓库里的 `blocked` 改写成 `complete`。`implemented` 也不等于 `verified`。

## 本会话处理的任务

1. 完整读取并遵循 `docs/GOAL_MODE_DEVELOPMENT_PROMPT.md`，按主提示词核对现有代码、设计、任务台账、阻塞和验收证据。
2. 保留已有实现和用户改动，确认独立学习服务、迁移、权限、上传/复核、错题本、诊断、变式、调度、正式测验、数轴、Agent、Tools、备份/恢复和隔离部署证据。
3. 确认本地确定性测试、Chromium 合成工作台、隔离 Compose 恢复和 Open WebUI 0.12.5 Tool 注册证据的边界。
4. 确认真实模型 tool call、最终可信浏览器回调、真实 OCR/模型、整卷人工质量和 T23 真实试用仍未验收。
5. 维护公开 GitHub 仓库的 `main` 分支；生产环境未被触碰。未跟踪的本地 `docker-compose.yml` 和 `batch_ingest.py` 按精确路径忽略，未读取内容、未提交，也不得在后续日志中复述其中凭证。

## 任务台账当前状态

来源：`docs/goal/TASKS.json`、`docs/goal/STATUS.md`、`docs/verification/qa-matrix-2026-11-03.md`。

| 状态 | 任务 | 当前含义 |
| --- | --- | --- |
| `verified` | T01、T02、T06、T07、T08、T11、T15、T17、T19 | 已有本地实现和对应确定性/隔离证据；仍需遵守各任务的真实入口边界 |
| `implemented` | T03、T09、T10、T12、T13、T14、T16、T18、T20、T21、T22 | 代码和本地证据已存在，但仍有真实 provider、浏览器组合、人工质量或外部故障项未完成 |
| `blocked` | T04、T05、T23 | 缺少脱敏整卷人工参考判定、授权的真实 OCR/模型，或真实参与者/观察条件 |
| `deferred` | T24、T25、T26 | V1 之外的后续范围，用户未扩大范围前不启动 |

### 已完成的核心交付

- 独立 FastAPI Learning Service；SQLite/WAL、迁移至 schema revision 7、身份/学习者授权、附件与页级资产、worker/lease、幂等和 revision 约束。
- 整卷照片/PDF 导入、原件保留、逐页资产、失败页、候选判定、人工证据/批量确认、错题来源和删除 tombstone 生命周期。
- 错题本支持手动录入、图片/PDF 待复核候选和 DOCX/XLSX 整份结构化文本候选；文档候选默认先人工整理、确认后入错题本，`.doc`/`.xls`、嵌入扫描图和复杂版面暂不承诺。
- 当前 OpenAPI 为 56 paths / 20 schemas；真实 OCR/provider、标注样本和质量结论仍未具备，不能把 Office 文本提取写成真实 OCR 验收。
- 诊断待复核、学习草稿确认、interval-v1 调度、正式题面、原始作答保真、服务端判分、提示后不具备独立资格、stage 5 maintenance gate。
- 正式数轴模板 `signed_number_subtraction`、程序计算数学参数、静态回退、受控 Agent 动作和薄 `dd_learning_v1` Tools 适配器。
- Open WebUI 0.12.5 隔离实例已完成 Tool 注册、原生 loader、实例 Valves、per-user UserValves、宿主 `__user__` 身份和合成可信回调探针；这不等于真实模型发起的聊天 tool call。
- Docker/Compose 独立部署、生产边界（无宿主业务端口、生产模式 bootstrap 关闭、内部网络）、备份/恢复、迁移失败回滚、WAL/SQLite writer 进程恢复和聚合 metrics。

### 已执行且可复核的证据

- `pytest -q`：最近一次 97 passed（服务 72、Tools 11、Open WebUI 兼容 3、腾讯 OCR 边界 5、隔离 Compose preflight 6）；聚焦 Tools/Open WebUI 回归 14 passed。
- `python3 -m compileall -q learning_service tests scripts`、`python3 scripts/verify_goal_consistency.py`、`git diff --check` 通过。
- Chromium 合成整卷链路：上传两份资料 → 分析 → 原页预览 → 人工判定/证据 → 可信确认 → 错题本；另有测验启动、刷新恢复、提示、challenge/作答、服务端判分、复核申请和取消。
- 独立 Compose revision 7：全新项目启动、生产边界探针、合成账号/附件备份恢复、API 重启持久性对账和临时资源清理。
- 关键报告：`docs/verification/import-browser-recheck-2026-11-03.md`、`browser-test-workbench-2026-11-03.md`、`compose-isolation-2026-11-03-revision7.md`、`migration-atomicity-2026-11-03.md`、`database-process-recovery-2026-11-03.md`、`open-webui-tools-registration-2026-11-03.md`、`open-webui-browser-probe-2026-11-03.md`、`trusted-ui-timeout-2026-11-03.md`。

这些证据使用合成资料、模拟 provider 或独立服务；不能写成真实学科准确率、真实学习效果、正式上线或真实 provider 通过。

## 仍未完成的任务和验收门槛

1. **T03/T16/T18/T20：真实 Open WebUI 浏览器组合。** 在隔离 Open WebUI 中配置隔离模型，完成真实聊天模型 tool call → 原生 `input`/`confirmation` → 最终可信 UI 回调；至少覆盖成功、取消、超时、刷新恢复和跨学习者拒绝。记录模型/服务版本、请求事件 ID和脱敏截图/日志。
2. **T04/T09/T10/T12/T13/T14：真实整卷质量。** 提供脱敏多页样本和人工参考判定，运行真实 OCR/分题/诊断/变式路径，报告全量题、失败页、弃判、精确率、召回率、耗时和费用；没有标注集不得计算或承诺质量指标。
3. **T05：真实 provider。** 明确 provider、模型/OCR版本、预算、重试上限、超时、出网范围和授权；优先使用自托管模型降低付费风险。未授权时只能保留 mock 回归，不能宣称真实集成完成。
4. **T21/T22：外部故障演练。** 在隔离环境补做外部数据库服务、对象存储和 provider 网络中断/恢复；当前只覆盖 SQLite、worker、确定性 provider 和本地故障注入。
5. **T23：真实试用。** 需要参与者/监护人同意、删除与保留规则、人工抽检、真实 Tools/回调、provider 预算和连续 7–14 个自然日观察。当前没有参与者记录，也没有虚构日志。
6. **生产切换。** 不属于当前已完成事项；必须另行审阅具体镜像、配置、迁移、备份、回滚、停止和恢复方案，并取得明确授权。预发布证据不能替代生产批准。

## 新会话下一步

按以下顺序继续，避免重复已完成工作：

1. 先读取本文件以及 `docs/GOAL_MODE_DEVELOPMENT_PROMPT.md`、`docs/goal/STATUS.md`、`TASKS.json`、`DECISIONS.md`、`BLOCKERS.md` 和 QA 矩阵；核对 `git status --short --branch`，保留现有未跟踪忽略文件和用户改动。
2. 若用户尚未提供真实 provider/预算、脱敏标注集和隔离 Open WebUI 测试身份，继续完善隔离脚本、证据模板和外部故障演练，不进行生产变更、不发送真实资料、不产生付费调用。
3. 条件具备后，新建独立 Compose project、数据库、附件卷、网络和凭据；启动前确认没有挂载正式 `data/`、正式 API、正式存储或通知路由，出站仅到获准 endpoint。
4. 先用合成资料完成真实浏览器 tool call 和最终可信回调，再按授权范围运行脱敏样本；逐项补齐成功/取消/超时/跨学习者/刷新恢复证据。
5. 更新 `TASKS.json`、`STATUS.md`、`BLOCKERS.md`、QA 矩阵和 `docs/verification/`，只在真实证据成立后把相应任务从 `blocked`/`implemented` 推进；不把 mock、合成资料或隔离注册写成真实通过。
6. 外部条件全部满足并完成证据审阅后，才评估 Goal 是否达到完成标准；生产切换和 T23 仍分别走授权流程。

可直接作为新会话续跑指令：

```text
继续本项目 DD-1.0 V1 Goal。先读取 docs/goal/HANDOFF-SESSION-2026-11-03.md、docs/GOAL_MODE_DEVELOPMENT_PROMPT.md、docs/goal/STATUS.md、TASKS.json、DECISIONS.md、BLOCKERS.md 和相关验收证据，核对实际代码与 Git 状态。从最早可执行的未完成项继续：优先在独立预发布环境完成真实 Open WebUI 模型 tool call/可信回调、真实 provider/脱敏整卷质量和故障演练；没有明确授权、预算、样本或测试身份时继续做隔离准备，不改生产、不发送真实资料、不产生付费调用。保留已有实现和用户改动，持续测试修复，不能把 mock、合成资料或隔离注册标为真实通过，也不能把 Goal 标为 complete。
```

## 关键入口

- 主提示词：`docs/GOAL_MODE_DEVELOPMENT_PROMPT.md`
- 当前状态：`docs/goal/STATUS.md`
- 任务台账：`docs/goal/TASKS.json`
- 阻塞与最小外部动作：`docs/goal/BLOCKERS.md`
- 决策记录：`docs/goal/DECISIONS.md`
- 原交接与运行命令：`docs/goal/HANDOFF.md`
- 真实试用准备：`docs/verification/trial-readiness-2026-11-03.md`
- QA 矩阵：`docs/verification/qa-matrix-2026-11-03.md`
