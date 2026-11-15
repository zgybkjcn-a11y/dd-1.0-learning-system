# 2026-11-15 今日学习路径 · 本地实现与验收

按用户确认的范围实现"今日路径"：**只做家庭页、不显示今日完成计数、总建议 25 分钟**。本轮只改本地工作树：未提交、未推送、未部署、未访问生产数据库、未迁移、未注册任何候选批次、未调用外部模型/OCR/embedding，C01 未启动，真实手机验收继续暂缓。

范围定义见 [候选范围](../plans/STUDY-PATH-CANDIDATE-SCOPE-2026-11-15.md)，使用与边界见 [今日学习路径说明](../open-webui-reuse/study-path.md)。

## 改动文件

新增：

- `learning_service/study_path.py` — 只读合成；全部为 SELECT。
- `tests/test_study_path.py` — 9 项。
- `tests/test_study_path_browser.py` — 2 视口。
- `docs/open-webui-reuse/study-path.md`
- `docs/verification/STUDY-PATH-2026-11-15.md`（本文件）

修改：

- `learning_service/app.py` — 新增 `GET /api/v1/study-path`；家庭首页 `#studyPath` 卡片与脚本；练习/错题视图隐藏规则。
- `learning_service/study_ui.py` — 切换课本/章节/难度保存工作区后刷新路径卡，避免显示旧范围。
- `learning_service/study_deadline.py` — `is_study_path` 加入 `/api/v1/study-path`。
- `deploy/open-webui-reuse/readonly_study_tools.py` — 内嵌 `study_deadline.py` 同步（逐字一致检查）。
- `docs/contracts/openapi-v1.json` — 重新生成，路径 76 → 77，只新增 `/api/v1/study-path`。
- `scripts/upgrade_readonly_study_tool.py` — 重固定 `app.py`、`study_deadline.py`、OpenAPI 快照与候选源码哈希。
- `tests/fixtures/readonly_study_tool_121_native.json` — `source_sha256` 跟随候选源码更新。
- `docs/README.md`、`docs/plans/RESUME-NEXT-WORK.txt`、`docs/releases/current-state.md` — 入口与状态。

未改动：题库与清单、`BATCHES`、`learning_service/migrations/`、`deploy/open-webui-reuse/main-study/`、`learning_data/` 里的任何学习记录。

## 实施细化（相对范围草案）

1. **新增 `choose` 兜底步**：没有练习范围，或记录的范围已不在当前教材目录时，路径给"先选课本和章节"，不猜测范围。
2. **复习时长按张估算**：每张 4 分钟、上限 20 分钟（与既有 `max_items=8 / suggested_minutes=20` 预算一致），而不是固定 20 分钟。
3. **预算超出不隐藏**：超出 25 分钟的步骤进入 `next_time`，页面显示"其余下次再做"。
4. **确定性口径**：除 `as_of` 读取时间外，同一状态两次请求结果完全相同。

## 验收命令与结果

| 命令 | 结果 |
| --- | --- |
| `python -m pytest tests/test_study_path.py -q` | 9 passed |
| `python -m pytest tests/test_study_path_browser.py -m browser -q` | 2 passed（390 / 1280） |
| `python -m pytest tests/test_study_path.py tests/test_study_deadlines.py tests/test_runtime_passages.py tests/test_family_math.py tests/test_family_practice.py -q` | 91 passed |
| `python -m pytest tests/test_readonly_tool_upgrade.py -q` | 53 passed |
| `python -m pytest tests/test_study_errors.py tests/test_study_read_db.py tests/test_study_read_scheduling.py tests/test_study_cache.py tests/test_study_support.py tests/test_learning_service.py tests/test_open_webui_compat.py tests/test_reuse_tools.py tests/test_learning_tools.py tests/test_gateway_family_routes.py tests/test_main_study_bridge.py tests/test_main_study_host.py tests/test_main_study_tool_registration.py tests/test_readonly_study_tools.py tests/test_textbooks.py tests/test_practice_collection.py -q` | 315 passed |
| `python -m pytest tests/test_family_adventure_browser.py tests/test_family_practice_browser.py tests/test_study_workbench_browser.py tests/test_study_support_browser.py tests/test_study_path_browser.py -m browser -q` | 10 passed |

全部使用合成身份与临时数据库；`provider_calls=0`，无 OCR/embedding 调用。

## 逐条对应范围验收

1. **零写入**：`test_read_is_deterministic_and_writes_nothing` 对 50 张表逐表行哈希前后比对，`audit_events`/`learning_events`/`provider_calls` 无新增。
2. **续做优先**：`test_resume_then_review_then_practice_and_scope`；`test_resume_disappears_once_the_item_is_graded`。
3. **复习一致**：`test_review_step_matches_review_tasks_exactly` 比对同一查询的张数与最早到期时间。
4. **进阶一致**：`test_practice_reason_is_the_guidance_text_verbatim` 与 `practice.guidance([])` 逐字相等。
5. **阅读兜底**：`test_reading_step_when_the_scope_has_no_installed_questions`（二上第一单元，页码 1）。
6. **覆盖口径**：接口无 `mastery` 字段，`notice` 明示"不代表掌握程度"。
7. **认证**：`test_untrusted_caller_is_rejected` 返回 401 `UNTRUSTED_CONTEXT`；learner 上下文版本沿用现有 409 逻辑。
8. **布局**：浏览器用例断言 390 与 1280 无横向滚动、无页面错误。
9. **外部调用**：同 1，`provider_calls=0`。
10. **回归**：上表 315 与 10 项通过，含 OpenAPI 快照与工具升级生命周期。
11. **可复现**：`stable()` 去掉 `as_of` 后两次结果相等。

## 未做（按范围）

- 主站"知识路线"未改（P1 单列）。
- 未做掌握度、跨册自适应排序、周月计划、提醒推送、服务端阅读位置。
- 未做图形 + 数学视觉扩展。
- 未发布：镜像未重建，生产仍运行代码升级后的旧镜像。

## 下一步

1. 在本地家庭页实际走一遍四类步骤（续做、复习、练习、阅读），记录两视口截图与操作路径。
2. 决定是否随下一批服务代码一起发布；发布仍需单独授权，并沿用停写备份、隔离冒烟与回表比对流程。
3. 如决定发布，需重建 `dd-learning` 镜像并更新 `docs/releases/current-manifest.json` 的镜像与 compose 记录。
