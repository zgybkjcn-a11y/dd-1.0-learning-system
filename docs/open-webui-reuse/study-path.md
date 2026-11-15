# 今日学习路径（本地候选，未部署）

家庭页顶部的"今天从这里开始"卡片，把已经存在的学习事实按固定顺序合成最多四步。它**只读**、不写数据库、不建新表、不调用模型，也不代表掌握程度。

## 数据来源

| 步骤 | 来源 | 产出 |
| --- | --- | --- |
| 续做 `resume` | `practice_workspaces.current_session_id` + `test_items` 中 `reserved`/`presented` | 提示把上一道题做完 |
| 到期复习 `review` | 与 `/api/v1/review-tasks` 完全相同的查询 | 张数、最早到期时间；每张按 4 分钟估算，上限 20 分钟 |
| 练习 `practice` | `learner_guidance`（连续 4 道不同题独立答对才升档） | 档位与理由**逐字透传**，不重写 |
| 阅读 `reading` | 本章无已安装题目时 | 教材目录的起始页码 |
| 选择 `choose` | 没有练习范围，或记录的范围已不在当前教材目录中 | 引导回课本选择 |

排序固定为 `resume → review → practice|reading|choose`。总建议 25 分钟，超出预算的步骤进入 `next_time`，仍会显示但有"其余下次再做"提示。

## 接口

```http
GET /api/v1/study-path
```

```json
{
  "learner_id": "…",
  "scope": {"book_id": "…", "chapter_id": "", "subject": "math",
            "book_title": "…", "chapter_title": "整本书", "printed_page": 1},
  "steps": [
    {"kind": "resume", "title": "继续上次练习", "reason": "…", "minutes": 5,
     "enabled": true, "scope": {…}, "evidence": ["practice_workspaces", "test_items"]}
  ],
  "next_time": [{"kind": "practice", "title": "…", "reason": "…"}],
  "total_minutes": 25,
  "budget_minutes": 25,
  "notice": "按已有记录给出建议顺序，不代表掌握程度；数据来自本机学习记录。",
  "as_of": "2026-11-15T…Z"
}
```

`as_of` 是本次读取时间，其余部分对同一份数据是确定的：同一状态两次请求，`steps` 与 `next_time` 除读取时间外完全相同。

## 家庭页行为

- 只在家庭模式（`familyGameMode`）显示，位于冒险首页 hero 下方；进入"挑战答题"或"错题收藏"视图时隐藏。
- 每一步一个按钮：续做会重新读取工作区并进入答题；复习滚动到到期复习块；练习直接开始当前范围下一题；阅读展开教材阅读器并跳到本章起始页；选择滚动到课本选择区。
- 不显示"今日完成 X/Y"，避免把建议路径变成打卡压力。

## 边界

- 覆盖类信息只以"编辑覆盖"口径出现，接口与页面都没有 `mastery` 字段。
- 复习张数与理由来自现有接口，不新增规则；练习档位与理由来自 `learner_guidance`，不新增规则。
- 练习作答不推进复习卡（既有调度行为），路径也不改变这一点。
- 不写 `audit_events`、`learning_events`，不新增表，不改迁移。

## 维护提示

- 改复习口径时，同时改 `app.py` 的 `review_tasks` 与 `study_path._due_cards`，并保持测试 `test_review_step_matches_review_tasks_exactly` 通过。
- 改进阶规则时只需改 `practice.guidance`；路径会跟着变，不需要同步文案。
- 新增题目批次并安装后，`reading` 步会自动变成 `practice`，因为可用题计数来自 `question_versions` 与教材范围映射。

## 验证

- `tests/test_study_path.py`：排序、预算、复习一致、逐字透传、阅读兜底、选择兜底、确定性与零写入、判分后取消续做、未受信调用 401。
- `tests/test_study_path_browser.py`：390 与 1280 两视口，卡片顺序、复习与练习按钮、无横向滚动、无页面错误。
- 回归：`test_study_deadlines`、`test_family_math`、`test_family_practice`、`test_runtime_passages`（OpenAPI 快照）、`test_readonly_tool_upgrade` 等。

验收记录见 [STUDY-PATH-2026-11-15](../verification/STUDY-PATH-2026-11-15.md)。
