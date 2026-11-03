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

发布 manifest 仍为 `goal_active_not_complete`；正式切换、真实学生资料外发和付费 provider 调用均为 `not_authorized`，持续试用仍待真实条件。隔离 Open WebUI 注册、原生 loader 和受信浏览器只读探针已验证；模型发起的浏览器 tool call、最终可信 UI 回调和真实 provider 仍待验证。schema revision 为 6，OpenAPI 为 55 paths / 19 schemas。全量 `pytest -q` 本次重跑为 76 passed（14.12 秒）；本轮没有修改业务实现。

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

本报告更新后的 `python3 scripts/verify_goal_consistency.py` 结果为 `tasks=26, evidence paths=132, backlog task rows=26, QA matrix rows=17, manifest path references=20, release authorization boundaries intact`。最近一次全量自动化为 `pytest -q` 的 78 passed，`compileall` 与 `git diff --check` 通过。Goal 现为 blocked、尚不可 complete；真实 provider、整卷人工标注、模型发起的 Open WebUI 浏览器 tool call/最终可信回调、剩余外部服务故障注入及 T23 仍未满足原完成标准。阻塞恢复条件见 `docs/goal/BLOCKERS.md`。
