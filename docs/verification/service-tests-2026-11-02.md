# 学习服务确定性测试

日期：2026-11-02（历史基线；当前增量复验见 `maintenance-gate-2026-11-03.md`）

命令：`pytest -q tests/test_learning_service.py`

历史基线结果：`37 passed`，无 warning。2026-11-03 中间快照为 62 passed（服务 53、Tools/Open WebUI 兼容 9）；之后全量回归曾为 76/77 passed；最新为 78 passed（服务 64、Tools 11、Open WebUI 兼容 3），当前 schema revision 6。维护准入和 practice 隔离见 `docs/verification/maintenance-gate-2026-11-03.md`，migration 原子性见 `docs/verification/migration-atomicity-2026-11-03.md`，SQLite 进程恢复见 `docs/verification/database-process-recovery-2026-11-03.md`，Tools/Agent 适配器见 `docs/verification/tools-agent-2026-11-03.md`，Agent 动作与诊断 worker 见 `docs/verification/agent-actions-2026-11-03.md`，可信 UI callback 超时回归见 `docs/verification/trusted-ui-timeout-2026-11-03.md`。

覆盖：

- 新库迁移、两个账号/学习者授权隔离和完整独立 `/ui` 工作台内容；
- 历史基线从仅有 migration 001 的旧库升级到 revision 3，并确认新增页资产/答案文档列及导出/删除生命周期列；之后 revision 5 的升级与变式字段、当前 revision 6 的迁移和恢复由 2026-11-03 增量报告复验；
- 有效图片、损坏图片和损坏 PDF 的失败状态；
- 多页 PDF 的逐页 PNG 派生资产、尺寸元数据、私有页内容回查和备份关联；
- 挑战生成、一次性消费、重放拒绝、过期/换人拒绝、批量确认、同键异载荷冲突和正式错题来源；
- 批次参考答案文档关联的学习者范围校验和持久化；
- 分析 worker 一次领取、租约、取消任务、迟到 worker 结果拒绝和来源幂等；
- 原始答案保真、提示/辅助不计独立掌握、服务端判分、interval-v1 首次调度只应用一次；
- 学习草稿确认只接受服务端原文，客户端替换回显会拒绝且不消费挑战，事件保存服务端内容；
- 学习草稿确认的强制幂等键、重试复用结果和原始内容保留；
- 整卷上传→分析→候选复核链、批次取消后保留原件且不再成功写入；
- 数轴 `start - subtrahend` 的精确结果、方向和参数边界；
- 学习者时区调度；
- 受控 Agent 白名单与步骤预算；
- SQLite 在线备份、附件复制和新目录恢复。
- provider 边界：文档、诊断、变式均保持 `needs_review`，确定性 mock 不进行外部调用；变式 worker 结果带有 `external_call=false` 证据。
- QA14 provider 故障注入：文档分析 provider 抛出异常时，事务回滚页状态、批次计数、候选和页区域写入；job 释放租约并记录 `WORKER_ERROR`，不会把页面标为已处理。
- QA14 导出存储故障注入：导出原子替换失败时，`export_jobs.status=failed`、错误可重试，最终文件和 `.tmp` 临时文件均清理；恢复写入后可生成新的 completed artifact。
- QA14 上传数据库故障注入：多页 PDF 已生成原件和页级派生资产后数据库提交失败时，事务回滚且所有附件文件清理，不留下孤儿资产。
- QA14 PDF 页写入故障注入：页级原子替换失败时，每页保持 `PDF_PAGE_RENDER_FAILED` 可见状态并清理 `.tmp`，原始 PDF 仍可回查。
- 学习者删除生命周期：原件、派生诊断/草稿/视觉素材、错题、复习卡、测验/作答和导出 artifact 均建立 tombstone 并清理；清理失败记录错误且学习者授权立即停用。
- 旧版恢复：只有 migration 001 的备份先迁移到当前 schema，再重放 asset tombstone；删除文件不会在恢复后重新公开。
- 管理员 metrics：按状态/类型、队列年龄、过期 lease、失败页、待复核、待删除和幂等记录聚合；测试确认 student 角色被拒绝，响应不含学习者标识或原始资料。
- worker 进程中断恢复：构造持久化的 expired `running` lease，重领后 `attempts` 从 1 增至 2，任务成功且候选/来源区域各只写一份。
- worker 真实子进程中断：子进程在 provider 外部调用期间被 `SIGKILL`，没有页面/候选业务写入；人工将已持久化 lease 置为 expired 后重领成功，`attempts` 从 1 增至 2，候选/来源区域各只写一份。另有第二 SQLite 连接写入回归，确认 provider 等待期间不持有 writer lock；SQLite writer 进程 `SIGKILL` 后未提交行回滚且恢复后可继续写入，详见 `docs/verification/database-process-recovery-2026-11-03.md`。
- 备份完整性：manifest 漂移、数据库校验和篡改和非空恢复目录均拒绝；恢复后执行 SQLite `PRAGMA integrity_check`。

其它本地证据：

- `python3 -m compileall -q learning_service tests` 通过；
- 使用临时 `LEARNING_ADMIN_SECRET` / `LEARNING_ADAPTER_SECRET` 执行 `docker compose -f docker-compose.learning.yml config --quiet` 通过；
- `docker build --file Dockerfile.learning --tag dd-learning:verification .` 通过。
- 使用镜像默认 `/var/lib/dd-learning` 路径导入应用并直接检查路由通过（52 条路由，`/ui` 为 `text/html` 且含整卷入口）；Compose 仍可覆盖同名数据环境变量。
- `.dockerignore` 已排除 `data/`、`learning_data/`、数据库、附件、Git 和测试/文档；重建日志显示构建上下文约 1.05 kB。
- 通过当前重建的独立 `docker run` 容器和 `docker exec` 完成真实容器内探针：`/health` 返回 200/schema revision 3，`/ui` 含整卷与候选复核控件，受信 `/internal/bootstrap` 使用合成账号成功；容器已停止且未挂载项目目录。
- 在同一独立容器内完成 HTTP 合成闭环：multipart PNG 上传、批次创建、分析排队、worker 领取并返回 `needs_review` 候选；容器停止后未保留运行实例。

所有样本均为合成数据；这些结果证明服务端确定性约束和隔离文件结构，不代表真实卷面 OCR、学科判定准确率、真实学习效果或 Open WebUI 浏览器闭环。

## QA14 故障注入增量

本轮在 `tests/test_learning_service.py` 增加并运行四项确定性故障注入：

- provider 异常覆盖 `run_worker_once` 的通用异常边界，确认 SQLite 写事务全部回滚，页面保持 `queued`、批次计数保持 0、没有 `import_items`/`source_regions`，job 为 `failed/WORKER_ERROR`。
- 导出临时文件已写入但 `Path.replace` 失败，确认最终 artifact 和 `.tmp` 均不存在，失败记录为可重试；解除注入后再次导出成功。
- 多页 PDF 已写入原件和页级派生资产后数据库提交失败，确认数据库事务回滚且原件、页级文件和 `.tmp` 均清理。
- 页级 PDF 原子替换失败，确认每页保持 `failed/PDF_PAGE_RENDER_FAILED` 可见状态，原始 PDF 仍可回查且没有 `.tmp` 残留。

本轮代码修复：导出失败处理现在同时清理临时路径和最终路径，上传失败处理同时清理原件和页级派生路径，页渲染失败处理清理页临时路径，避免原子替换或数据库提交失败留下不可见半成品。嵌入式 SQLite writer 进程中断已有独立回归；仍未覆盖真实对象存储、外部数据库服务和真实 provider 网络超时等故障。

## 独立 Compose 宿主 HTTP 与重启恢复

在生产模式 `LEARNING_DEV_MODE=0`、独立卷 `open-webui_dd_learning_data` 下，使用容器内一次性写入的纯合成身份绑定和学习者授权完成以下验证：

- `/health` 返回 HTTP 200，schema revision 3；`/ui` 返回 HTTP 200、12207 bytes，并含整卷上传和候选复核入口。
- 生产模式 `/internal/bootstrap` 返回 HTTP 404；受信身份头可列出合成学习者。
- 宿主 `curl` 完成 PNG 上传、整卷批次创建、分析排队、worker 处理和候选读取；随后以合成教师证据执行 revision 修订、一次性确认挑战和批量确认，最终批次为 `completed`，1 页 `processed`，错题本新增 1 个 `active` 条目。
- `docker compose down` 后不删卷 `up -d`，API/worker 健康恢复；确认前的检查点中身份、原件、批次和候选仍存在，批次仍为 `awaiting_review`，随后确认并再次恢复后的最终批次为 `completed`。

详细命令、请求头和结果见 `docs/verification/compose-isolation-2026-11-02.md`。该闭环使用合成 PNG，不能替代真实 Open WebUI 浏览器/Tools、真实 OCR/模型或学科人工验收。

## 本地 `/ui` Playwright 合成闭环

在独立 Compose project `dd-learning-browser-20261102`（端口 `32120`、独立卷、合成账号/学习者）中，Playwright 完成了账号/学习者上下文、PNG 上传、整卷批次创建、worker 分析、候选读取、候选 `incorrect` 复核保存、目标与证据填写、一次性可信确认和错题本读取。结果为 1 个 `active` 错题；390px 移动视口无横向溢出，上传与确认控件存在。

脱敏 JSON 和截图分别为 `docs/verification/browser-ui-2026-11-02.json`、`docs/verification/browser-ui-2026-11-02.png`。这证明当前独立服务 `/ui` 的浏览器可操作闭环，不等同于真实 Open WebUI 浏览器/Tools 注册和回调；合成 PNG 与 provider 也不代表真实 OCR、学科判定或学习效果。
