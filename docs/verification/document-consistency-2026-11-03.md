# DD-1.0 文档与交付状态一致性核验

日期：2026-11-03（Asia/Shanghai）

本报告核验任务/QA追踪、引用路径和发布边界。它不替代真实 Open WebUI、真实 provider、人工质量评估或学习者验收。

## 可复现检查

在项目根目录运行：

```text
python3 scripts/verify_goal_consistency.py
tasks=26, evidence paths=120, backlog task rows=26, QA matrix rows=17, manifest path references=18, release authorization boundaries intact

pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py
13 passed

pytest -q tests/test_learning_service.py -k 'admin_export_is_local_audited_artifact_and_delete_cleans_files or export_write_failure_cleans_partial_artifact_and_is_retryable or delete_records_and_cleans_derived_learning_resources or delete_cleanup_failure_keeps_resource_private_and_records_error or direct_full_upload_analysis_review_chain or grade_worker_preserves_raw_answer_and_applies_schedule_once or cancelled_session_rejects_submission or hint_submission_does_not_count_as_independent'
8 passed, 55 deselected

pytest -q
76 passed in 14.12s

python3 -m compileall -q learning_service tests scripts
passed
```

一致性检查使用标准库校验 `TASKS.json` 中 T01–T26 与全部证据路径、backlog 任务行、QA01–QA17 矩阵行，以及发布 manifest 的目标 ID、当前状态、授权边界和路径引用。`automated_tests` 是测试结果描述，不是文件路径；其余 manifest 证据路径及组件源码/部署/依赖路径都逐项确认存在。路径校验拒绝绝对路径和逃逸项目根目录的引用。

本次续跑将五类候选判定报告补入 T10/T11 任务证据，并在 QA04/QA05 矩阵中建立引用；新增源码管理基线和 T01/T12/T16 证据后，任务证据总数为 120。Tools/WebUI 兼容回归 13 项通过；错题本导出/删除及测验原答/提示/取消聚焦回归 8 项通过。早期文档审计记录的 109 是旧快照，不再作为当前计数。

该段为本报告早期 active/76-pass 历史快照；当前 Goal 与 manifest 状态由下方续跑记录更新。正式切换、真实学生资料外发和付费 provider 调用均为 `not_authorized`，持续试用仍待真实条件。隔离 Open WebUI 注册、原生 loader 和受信浏览器只读探针已验证；模型发起的浏览器 tool call、最终可信 UI 回调和真实 provider 仍待验证。schema revision 为 6，OpenAPI 为 55 paths / 19 schemas。全量 `pytest -q` 本次重跑为 76 passed（14.12 秒）；本轮没有修改业务实现。

## 后续增量核验（2026-11-03）

异步原生 UI callback 等待上限及 fail-closed 回归新增后，以下结果取代上方报告生成时的历史快照：

```text
python3 scripts/verify_goal_consistency.py
tasks=26, evidence paths=128, backlog task rows=26, QA matrix rows=17, manifest path references=19, release authorization boundaries intact

pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py
14 passed

pytest -q
78 passed in 15.58s (64 learning service + 11 Tools adapter + 3 Open WebUI compatibility)

python3 -m compileall -q learning_service tests scripts
passed

git diff --check
passed
```

超时回归确认 `confirm_import` 和 `submit_answer` 在 callback 未返回时都不请求或提交 challenge，详见 `trusted-ui-timeout-2026-11-03.md`。一致性脚本校验所有 26 个任务证据路径、backlog/QA 行数、manifest 引用和发布授权边界。Goal 仍为 active；真实模型 tool call、最终浏览器回调、provider、人工标注和 T23 仍未验收。

## 导入工作台浏览器复验（2026-11-03）

独立 `/ui` Chromium 重新跑通两份合成页面上传、整卷分析、两页来源预览、人工 `incorrect` 判定与证据保存、可信 challenge、批量确认及错题本读取。数据库对账为 2 个候选（1 个 confirmed/incorrect、1 个 needs_review/undetermined）、1 条人工 judgment、1 条错题来源和 1 条 active 错题；批次因仍有待复核候选而保持 `awaiting_review`。390px 和 1280px 视口无页面横向溢出，运行期间没有页面异常、控制台错误或失败请求。该合成闭环不代表真实 OCR/provider、真实资料质量、Open WebUI 模型发起的 tool call、最终可信 UI 回调或真实试用；完整记录见 `import-browser-recheck-2026-11-03.md`。

该阶段报告快照中的 `python3 scripts/verify_goal_consistency.py` 结果为 `tasks=26, evidence paths=132, backlog task rows=26, QA matrix rows=17, manifest path references=20, release authorization boundaries intact`；当时全量自动化为 `pytest -q` 的 78 passed，`compileall` 与 `git diff --check` 通过。当前结果见下方续跑增量。Goal 现为 blocked、尚不可 complete；真实 provider、整卷人工标注、模型发起的 Open WebUI 浏览器 tool call/最终可信回调、剩余外部服务故障注入及 T23 仍未满足原完成标准。阻塞恢复条件见 `docs/goal/BLOCKERS.md`。

## 本次续跑增量核验（2026-11-03）

本次修正 Tools 适配器异步 HTTP 请求的 executor 收尾后，重复 `asyncio.run()` 的 Tools/Open WebUI 聚焦回归与全量回归均可正常退出：

```text
pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py
14 passed

pytest -q
84 passed (64 learning service + 11 Tools adapter + 3 Open WebUI compatibility + 6 isolated Compose preflight)

python3 scripts/verify_goal_consistency.py
tasks=26, evidence paths=135, backlog task rows=26, QA matrix rows=17, manifest path references=20, release authorization boundaries intact

python3 -m compileall -q learning_service tests scripts
passed

git diff --check
passed
```

隔离 Compose preflight 的实际静态检查通过，未启动容器；6 项回归覆盖其拒绝规则。真实模型 tool call、最终可信 UI 回调、provider、人工标注、外部服务故障演练和 T23 仍未验收，Goal 保持 blocked。


## 后续续跑状态（2026-11-03）

错题本当前支持手动录入、图片/PDF 上传后生成待复核候选，以及 DOCX/XLSX 文本提取后整份生成候选；文档候选默认由用户整理并确认后才进入错题本。Office 提取只处理 OOXML 文本，不覆盖扫描图片 OCR、复杂版面和公式语义。该实现不提供真实 OCR 准确率证据；T04/T05、真实样本质量、Open WebUI 真实模型回调和 T23 仍按 `docs/goal/BLOCKERS.md` 阻塞。

本次续跑后当前状态：schema revision 7，OpenAPI runtime/快照均为 56 paths / 20 schemas；`pytest -q` 为 91 passed（服务 71、Tools 11、Open WebUI 兼容 3、隔离 Compose preflight 6），Tools/Open WebUI 聚焦回归为 14 passed。`compileall`、目标一致性脚本和 `git diff --check` 的结果以本报告最后更新记录为准。Goal 保持 blocked、尚不可 complete。


## 续跑复核（2026-11-04）

本次实现错题本手动录入和文档导入候选后，复核命令结果如下：

```text
pytest -q
91 passed in 16.51s

python3 -m compileall -q learning_service tests scripts
passed

python3 scripts/verify_goal_consistency.py
tasks=26, evidence paths=143, backlog task rows=26, QA matrix rows=17, manifest path references=21, release authorization boundaries intact

create_app().openapi() == docs/contracts/openapi-v1.json
56 paths, 20 schemas

git diff --check
passed
```

Goal 和 release manifest 均记录为 blocked/not complete；正式切换、真实学生资料外发和付费 provider 调用仍未获授权。错题录入实现的范围与限制见 `docs/PAPER_HOMEWORK_IMPORT_DESIGN.md`；没有真实试卷/作业样本和人工标注集，因此本轮只验证接口、结构化文档解析与人工确认流程，不形成 OCR 准确率或真实资料质量结论。
