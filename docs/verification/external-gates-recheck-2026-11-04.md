# DD-1.0 外部验收条件只读复核

日期：2026-11-04（Asia/Shanghai）。本轮承接 `docs/goal/HANDOFF-SESSION-2026-11-04-CONTINUATION.md`，仅核对状态并补充文档；没有重跑已完成的四格式导入持久化测试。

## 当前事实

- 已读取两份 2026-11-04 交接、STATUS、TASKS、BLOCKERS、DECISIONS 和 QA 矩阵。Git 为 `main...origin/main`，现有未提交修改和未跟踪文件保留。
- 本轮 `get_goal` 返回 `goal: null`。仓库验收状态仍为 `blocked`；没有创建或更新 Goal，TASKS 中各任务状态未改变。
- Docker 只读元数据表明此前隔离 Learning API 和 Open WebUI 均已停止。没有启动容器、读取数据库或凭据、发送模型请求或触发 UI 回调。

| 对象 | 本轮元数据 |
| --- | --- |
| `dd-learning-isolated-api-20261103d` | `status=exited`、`running=false`、`exit_code=255`、`oom_killed=false`；`finished_at=2026-11-03T05:35:01.381555123Z`；宿主端口绑定 `{}` |
| `dd-openwebui-isolated-20261103d` | `status=exited`、`running=false`、`exit_code=255`、`oom_killed=false`；`finished_at=2026-11-03T05:35:01.39693988Z`；宿主端口绑定 `{}` |
| 隔离网络 `dd-openwebui-isolated-20261103d` | 仍存在，`internal=true`、`driver=bridge` |
| Learning API 挂载 | 命名卷 `dd-learning-isolated-20261103d` → `/var/lib/dd-learning` |
| Open WebUI 挂载 | 命名卷 `dd-openwebui-data-isolated-20261103d` → `/app/backend/data` |

未检查停止原因、卷内数据、当前 schema、已安装 Tool 源码或模型连接；不能由退出码推断故障根因，也不能把历史 health/注册证据当作当前运行就绪。命名卷挂载和 internal 网络元数据不证明运行时防火墙、完整恢复或外部故障矩阵通过。

源码与示例默认值仍为 `LEARNING_DOCUMENT_PROVIDER=mock-document-v1`、`TENCENT_OCR_EXTERNAL_CALLS_ENABLED=0`，`Settings` 的对应默认值为 `mock-document-v1` / `False`。本轮未读取运行时密钥或 `.env`，未修改这些配置；这项检查只证明源码默认值，不能声称已经核验真实 provider 的运行时配置或授权。

## 下一项工作与缺少的输入

优先项仍是 T03/T18/T20（关联 T16/T23）的隔离 Open WebUI 真实模型 tool call 与最终浏览器可信回调。外部条件具备后先恢复并核对 disposable/staging 环境与当前源码兼容性，再从聊天入口验证成功、取消、超时、刷新恢复及跨学习者拒绝；已有 Tool 注册与四格式内容持久化证据保留，按相关变化决定必要复验。

本轮没有新增授权或外部资料，以下门槛仍未满足：

| 门槛 | 继续所需输入 |
| --- | --- |
| 隔离模型和可信 UI（T03/T16/T18/T20） | 仅供测试的模型连接、测试账号与学习者映射、可操作的浏览器原生 `input`/`confirmation` 回调入口；使用外部模型时另需明确调用范围、预算和出网许可 |
| 人工质量集（T04，关联 T09/T10/T12/T13/T14） | 获准使用的脱敏整卷/作业、逐题人工转写和边界、学生作答及参考判定、题型覆盖与审核人 |
| 真实 provider（T05） | 独立运行时凭据来源、明确 provider/endpoint、预算/费用上限、允许的测试资料和真实调用授权；本会话仍禁止真实 API 调用 |
| 外部故障矩阵（T21/T22） | 独立可恢复的数据库服务、对象存储和 provider 网络故障环境及受控演练范围；本轮元数据检查不计作故障演练 |
| 真实试用（T23） | 参与者/监护人同意、启动授权、数据保留删除规则、人工抽检、provider 预算及连续 7–14 天真实观察条件 |

在这些条件到位前保留当前阻塞状态。生产部署、真实资料外发与付费调用未执行；没有新增真实验收结论、质量指标、参与者记录或试用日志。

## 检查范围

运行条件复核仅执行 `git status`、Goal 读取、指定交接/状态文档读取、`docker ps -a --filter name=dd-`、两个指定隔离容器的 State/PortBindings/Mounts 元数据和指定隔离网络的 internal 属性读取，以及源码/示例默认值检索。没有读取或修改根目录 `docker-compose.yml`、`batch_ingest.py`。

文档补充后，`python3 scripts/verify_goal_consistency.py` 和排除上述两个根目录文件的 `git diff --check` 均通过。一致性统计仍为 `tasks=26, evidence paths=144, backlog task rows=26, QA matrix rows=17, manifest path references=22, release authorization boundaries intact`。本轮编辑的五份既有文档之外，37 个既有改动文件的 SHA-256 指纹与补充前一致；仅新增本报告，TASKS、源码、测试与配置内容均保持原样。

最近一次完整确定性回归仍以交接记录的 **101 passed** 为准；它是之前的合成资料与本地 mock 证据，本轮没有重跑或将其升级为真实验收。
