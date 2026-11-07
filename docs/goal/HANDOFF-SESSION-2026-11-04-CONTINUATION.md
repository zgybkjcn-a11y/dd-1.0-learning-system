# DD-1.0 V1 会话交接续篇（2026-11-04）

> 最新会话总交接为 [`HANDOFF-SESSION-2026-11-04-P0.md`](HANDOFF-SESSION-2026-11-04-P0.md)，包含后续 P0 执行和生产就绪代码缺项。以下保留历史记录；新会话从最新文件进入。

更新时间：2026-11-04（Asia/Tokyo）  
项目：DD-1.0 学习服务  
工作目录：`/home/deniskorfei/projects/open-webui`  
分支：`main`

## 当前结论

本会话承接 `HANDOFF-SESSION-2026-11-04.md`，没有重置或清理工作区。优先核实并复跑了错题导入确认闭环：PNG、PDF、DOCX、XLSX 均覆盖上传、分析、人工判定、可信确认、错题本列表/详情，并直接对账 `mistake_entries.content_json`、判定证据、来源和 active 复习卡。

确认路径的内容持久化缺口已经修复：新建错题条目时将题目内容、学生作答、判定、教师证据和知识目标写入 `mistake_entries.content_json`。四种格式的聚焦测试为 **4 passed**；最新全量测试为 **101 passed**。`compileall`、`git diff --check` 和 Goal 一致性检查均通过。验证报告为 `docs/verification/mistake-import-content-persistence-2026-11-04.md`。

这些是合成资料、本地 deterministic mock 和自动化回归证据，不是腾讯 OCR 真实调用、真实学生资料或识别质量验收。

## 任务进度

任务状态以 `docs/goal/TASKS.json` 为准：

- `verified`：T01、T02、T06、T07、T08、T11、T15、T17、T19。表示对应本地/隔离证据达到该任务当前定义的确定性门槛，不代表整个 V1 已验收。
- `implemented`，仍有验收门槛：T03、T09、T10、T12、T13、T14、T16、T18、T20、T21、T22。
- `blocked`：T04、T05、T23。
- `deferred`：T24、T25、T26；除非用户扩大范围，不启动。

本轮指定的导入确认持久化工作已完成：图片/PDF/DOCX/XLSX 的列表、详情、来源、人工 judgment 和复习卡均有本地回归；Office 文档仅覆盖 `.docx`/`.xlsx` 结构化文本候选，不承诺 `.doc`/`.xls`、嵌入扫描图、复杂排版或公式语义。

## 尚未完成

1. **真实 Open WebUI 聊天闭环（T03/T18/T20，关联 T16/T23）**：隔离 Open WebUI 0.12.5 的 Tool 注册、loader 和合成回调已有证据，但还没有配置可调用模型并实测模型发起的浏览器 tool call、可信 UI 最终确认/作答回调，以及取消、超时、刷新恢复和跨学习者拒绝。
2. **人工参考质量集（T04，关联 T09/T10/T12/T13/T14）**：缺少脱敏整卷/作业、逐题人工转写与边界、作答和参考判定、题型覆盖及审核人；因此无法报告真实识别/分题/判错质量、漏题率或人工诊断质量。
3. **真实 provider（T05，关联 T09/T13/T14/T21）**：没有授权的真实 OCR/模型调用配置、预算/费用上限、出网范围和运行时凭据。provider 代码及模拟响应回归不等于真实接入验收。
4. **外部故障矩阵（T21/T22）**：外部数据库服务、对象存储和 provider 网络故障/恢复尚未实测；静态 Compose preflight 和 SQLite 本机进程故障测试不覆盖这些系统。
5. **真实试用（T23）**：尚无参与者/监护人同意、试用启动授权、provider 预算、人工抽检和连续 7–14 天观察记录。不得创建虚构试用日志或用加速时间代替观察。
6. **正式切换**：生产部署、付费调用、真实学生资料外发和正式数据切换仍需各自明确授权；本会话没有执行这些动作。

详细的最小外部输入见 `docs/goal/BLOCKERS.md`；QA 状态及各项证据见 `docs/verification/qa-matrix-2026-11-03.md`。

## 下一步建议

新会话开始时先读取本续篇及 `HANDOFF-SESSION-2026-11-04.md`、`docs/goal/STATUS.md`、`TASKS.json`、`BLOCKERS.md`、`DECISIONS.md`、QA 矩阵，核对 `git status --short --branch` 和 Goal API；Goal API 最近返回 `goal: null`，仓库任务状态为 `blocked`，不要把二者混为一谈，也不要创建或完成 Goal。

本地可做的导入确认持久化项已经完成。之后按最早可取得条件的外部门槛推进：优先在 disposable/staging Open WebUI 中接入隔离模型，完成真实聊天 tool call 和最终可信回调；需要真实 OCR/质量验证时，先取得授权的预算、出网范围、脱敏资料和逐题人工参考判定。若这些条件尚不可用，继续独立的本地代码/文档工作，并精确记录缺少的输入；不要将 mock 或合成数据升级为真实验收结论。

## 工作区与安全约束

- 当前分支为 `main`，工作区有大量既有未提交修改和未跟踪文件；新会话必须保留，不执行 reset、checkout、清理或覆盖。
- 不读取或修改仓库根目录 `docker-compose.yml`、`batch_ingest.py`。
- 腾讯 OCR provider 默认仍为 `mock-document-v1`，`TENCENT_OCR_EXTERNAL_CALLS_ENABLED=0`；不得调用真实 API、发送真实学生资料或部署生产，除非用户另行明确授权。
- 不把 mock、合成资料或本地测试标记为真实 OCR、真实模型、真实质量或正式验收通过；不得将 Goal 标记为 complete。

## 本会话复核结果

```text
pytest -q                                                                  101 passed
pytest -q tests/test_learning_service.py -k uploaded_mistake_confirmation_persists_content_judgment_source_and_review_card
                                                                           4 passed, 72 deselected
python3 -m compileall -q learning_service tests scripts                  passed
git diff --check                                                          passed
python3 scripts/verify_goal_consistency.py                                passed
```

最近一致性检查：`tasks=26, evidence paths=144, backlog task rows=26, QA matrix rows=17, manifest path references=22, release authorization boundaries intact`。Goal API：`goal: null`。仓库 Goal 状态仍为 blocked。

## 后续会话只读复核（2026-11-04，Asia/Shanghai）

本轮按上述入口读取交接与任务记录，并核对 `git status --short --branch` 和 Goal API：分支仍为 `main`，现有未提交改动保留，`get_goal` 仍返回 `goal: null`。没有创建或更新 Goal，TASKS/QA 状态未改变。

Docker 元数据复核发现 `dd-learning-isolated-api-20261103d` 与 `dd-openwebui-isolated-20261103d` 已停止（`running=false`、退出码 `255`），命名卷挂载和 `internal=true` 隔离网络仍有元数据记录。停止原因、卷内状态、当前 schema、Tool 源码和模型连接未检查；历史注册/health 证据不能当作当前运行就绪。未重启实例、触发模型请求或浏览器可信回调。

本轮只补充当前外部条件与交接入口，未重做四格式导入持久化、重跑全量测试或新增业务实现。源码/示例默认 mock 与外发关闭保持原样。详细事实与最小外部输入见 [`external-gates-recheck-2026-11-04.md`](../verification/external-gates-recheck-2026-11-04.md)。下一项仍是条件具备后恢复并核对隔离环境，从真实聊天 model tool call 和最终可信 UI 回调续验；脱敏标注集、provider 授权和真实试用条件继续按 BLOCKERS 等待，不能自签验收。

后续按用户要求形成详细任务计划 [`NEXT-TASK-PLAN-2026-11-04.md`](NEXT-TASK-PLAN-2026-11-04.md)，列出 P0–P7 的依赖、工作量、交付物和通过标准。该文件只用于排期；没有开始模型/provider 调用、真实资料使用或试用，当前任务状态与授权边界保持不变。

## 按计划执行 P0 与 P2 空规范（2026-11-04，Asia/Shanghai）

P0 本地技术准备已完成：旧实例仍停止、旧卷和 Tool 未修改；SQLite 检查副本确认旧 schema 为 6、Tool hash 与当前源码不同。日志不足确认退出原因，继续记为未知。使用独立 build context 和依赖版本匹配的缓存基底，另起 `dd-learning-p0-20261104`；没有读取禁读文件、下载依赖或拉取最新镜像。原始 Dockerfile 离线构建未成功，本次构建可复现范围依赖缓存基底，不声称无缓存构建通过。

新 Learning API/worker/Open WebUI 当前运行：schema 7、Open WebUI 0.12.5、内部 health 200、bootstrap 404、无受信上下文 401、跨学习者 404、源码指纹和完整 OpenAPI 一致；三个服务只使用新 project 的命名卷/internal 网络，无宿主端口。当前 Tool 已在新实例同步，原生 loader 11 方法、宿主身份与 UserValves 通过；新环境 stop/resume 后 API/完整契约、未重新注册的 Tool 读取复验通过。

运行目录 `/tmp/dd-p0-20261104/runtime/` 含 0600 的临时配置与凭据，不能打印、提交或当作长期备份。新实例可用模型为 0，未设置宿主浏览器入口、未执行真实模型 tool call 或浏览器最终可信回调。P2 只有 [`docs/quality/README.md`](../quality/README.md) 及零记录 CSV/空 JSON，阈值和审核人未填写；T04 仍缺真实标注资料。

完整执行记录、停止/恢复与续跑命令见 [`p0-isolated-runtime-2026-11-04.md`](../verification/p0-isolated-runtime-2026-11-04.md)。下一项从 P1 的测试模型/可信 UI 外部门槛继续，资料提供后推进 P2/P4；真实 provider 调用、生产部署、真实资料外发和试用仍未执行/获准。所有 T 任务状态保持原样，Goal 不创建或完成。101 passed 仍为此前基线，本轮未重跑四格式或全量 pytest。

本轮最终检查：三个新脚本编译、Compose 静态 preflight、模板零记录/未签核验证、文档一致性与 diff-check 通过；既有 project 的 start 覆盖请求被拒绝。最新一致性统计为 `tasks=26, evidence paths=149, backlog task rows=26, QA matrix rows=17, manifest path references=22, release authorization boundaries intact`。进度文档之外的 38 个既有改动文件指纹一致。Goal API 最后读取仍为 `goal: null`。
