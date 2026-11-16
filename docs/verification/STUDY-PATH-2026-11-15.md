# 2026-11-15 今日学习路径 · 本地实现、发布与验收

按用户确认的范围实现"今日路径"：**只做家庭页、不显示今日完成计数、总建议 25 分钟**。同日按用户授权发布到本机生产：停写备份、切换镜像、逐表比对通过。未迁移数据库、未注册候选批次、未调用外部模型/OCR/embedding，C01 未启动、未重启 proxy 与 open-webui，真实手机验收继续暂缓。

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

## 生产发布（2026-11-15 晚）

按用户授权把本批代码发布到本机生产。

| 项目 | 记录 |
| --- | --- |
| 镜像 | `dd-learning:study-path-20261115` = `sha256:933c8ceadddf…` |
| Compose | `learning_data/deployments/family-study-path-20261115/compose.json`（`30ea04b8…`），仅换 api/worker/gateway |
| 隔离冒烟 | 生产数据副本在 `127.0.0.1:31998` 启动：`/health` ok、schema14、1145 题、77 路径含新接口 |
| 停写与备份 | 三容器停止后备份到 `learning_data/verification/study-path-release-20261115/private/snapshot`，回执 passed，校验 schema14 / integrity ok / 外键 0 |
| 切换后验收 | `/health` 返回 `{"status": true}`，`/learning/ui` 303；api healthy，worker/gateway running；proxy 与 open-webui 未重启 |
| 数据保全 | live 库与备份逐表行哈希：50 表、0 不一致；1145 题、99 次作答、2 名学习者、schema14 不变 |
| 新接口 | 容器内 OpenAPI 77 路径且含 `/api/v1/study-path`；未认证请求返回 401 `UNTRUSTED_CONTEXT`（路由存在，非 404） |
| CI | run 43726542097（commit `1615efa`）单元 1173 通过、浏览器 53 通过 |
| 回退 | `family-code-upgrade-20261115/compose.json` + 旧镜像 `sha256:6f6ad8a1…`，保留数据卷 |

发布期间修过一次 CI 失败：C01 冻结场景固定了只读 Tool 源码哈希，本批同步 `study_deadline.py` 后失效；按约定把场景升到 `c01-synthetic-v2` 并记录原因，未改写场景与历史结论。

证据：`learning_data/verification/study-path-release-20261115/`（`pre-state.txt`、`backup-receipt.json`、`backup-verify.json`、`deployment.json`）。

## 发布后修正（2026-11-16）：放置查询改为每次请求只装载一次

本地全量回归唯一的失败是 `tests/test_chapter_practice_browser.py::test_chapter_batches_in_family_browser[1280]`：点击档案卡后 `#textbookSubject` 持续为空且禁用，30 秒超时。CI 同一用例两个视口都通过，属于本机时序下才越线的耗时问题，不是路由错误。

定位：`study_path._available()` 对每个已批准题版各调用一次 `practice_scope()`/`question()`，而 `chapter_practice.bank()` 是刻意不缓存的（每次都读盘并校验 sha256）。家庭库有 418 个已批准版本，等于一次请求把整套章节题库重复装载数百次。生产库副本上实测 `compose` 为 4.4–6.4 秒；`loadToday` 在等待期间保持 `gameLoadingChoices`，课本下拉框全程禁用，最终超过 Playwright 的 30 秒上限。

修正：

- `learning_service/textbooks.py`：新增 `practice_scopes()`，一次装载章节/核心/备用题库后批量给出放置；起始题规则提取为 `_starter_scope()`，`practice_scope()` 的语义与返回值不变。
- `learning_service/study_path.py`：`_available()` 改用 `practice_scopes()` 一次性解析。
- 实测（同一生产库副本）：冷启动 0.65 秒、热 0.01–0.06 秒；修复前 4.4–6.4 秒。
- 回归：`test_placements_load_the_chapter_bank_once`（一次请求内题库装载次数 ≤ 1）、`test_bulk_placements_match_the_single_lookup`（批量结果与逐个查询逐项相等）。
- 只读 Tool：Tool 源码未变，`CANDIDATE_SHA256` 与 C01 冻结场景不变；只重新固定 `BACKEND` 里的 `learning_service/textbooks.py`。

### 验证与生产发布（2026-11-16）

| 项目 | 结果 |
| --- | --- |
| 本地浏览器回归 | `test_chapter_batches_in_family_browser[1280]` 通过 11:06（修复前 4:19 失败、15:22 失败） |
| 本地单元/契约回归 | 23 个模块 427 项通过 |
| CI | run 43794230563（commit `0f28b95`）单元 1175 通过、浏览器 53 通过；同用例由 722 秒降到 373 秒 |
| 镜像 | `dd-learning:study-path-fix-20261116` = `sha256:539a0dc2e7b0…` |
| 隔离冒烟 | 生产数据副本在 `127.0.0.1:31998`：`/health` ok、schema14、1145 题、77 路径；接口冷 0.787 秒、热 0.013 秒 |
| 停写与备份 | 三容器停止后备份至 `learning_data/verification/study-path-fix-20261116/private/snapshot`，回执 passed，校验 schema14 / integrity ok / 外键 0 |
| Compose | `learning_data/deployments/family-study-path-fix-20261116/compose.json`（`21b350a2…`），仅换 api/worker/gateway |
| 切换后验收 | `/health` `{"status": true}`、`/learning/ui` 303、api healthy、worker/gateway running；proxy 与 open-webui 未重启 |
| 数据保全 | live 库与备份逐表行哈希：50 表、0 不一致；1145 题、99 次作答、2 名学习者、schema14 不变 |
| 新接口 | 容器内 OpenAPI 77 路径含 `/api/v1/study-path`；未认证请求 401 `UNTRUSTED_CONTEXT` |
| 回退 | `family-study-path-20261115/compose.json` + 旧镜像 `sha256:933c8ceadddf…`，保留数据卷 |

证据：`learning_data/verification/study-path-fix-20261116/`（`pre-state.txt`、`backup-receipt.json`、`backup-verify.json`、`deployment.json`）。

## 下一步

1. 在家庭成员档上实际走一遍四类步骤（续做、复习、练习、阅读），记录两视口截图与操作路径。
2. 观察一周：路径是否常被复习步占满 25 分钟、`next_time` 是否造成"练习总被推后"的错觉；如有，调整为按张数分配或分两次。
3. 教师签署与课标交叉审核仍未完成，本卡片不宣称掌握度。
