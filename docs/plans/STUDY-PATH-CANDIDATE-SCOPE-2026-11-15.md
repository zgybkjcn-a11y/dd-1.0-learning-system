# 学习路径本地候选范围（2026-11-15）

> 状态更新（同日）：本范围已按用户确认实现为本地候选，验收见 [STUDY-PATH-2026-11-15](../verification/STUDY-PATH-2026-11-15.md)，使用说明见 [今日学习路径](../open-webui-reuse/study-path.md)。实现细化：新增 `choose` 兜底步；复习按每张 4 分钟、上限 20 分钟估算；超出 25 分钟的步骤进入 `next_time` 而不隐藏；确定性口径为"除 `as_of` 外一致"。仍未提交、未推送、未部署。

本文件是**候选范围草案**：只定义要做什么、边界和验收，不含业务代码、不改运行源码、不迁移、不部署、不提交推送。文中"现有"陈述来自只读源码核对，未读取生产学生记录，不构成新的发布记录。

## 一、为什么先做这个方向

三项现状核对结果：

1. **"下一步"的证据已经存在，但没有合成。** 到期复习卡（`app.py:4015`，上限 8 张、建议 20 分钟、间隔 [1,2,4,7,15,30] 见 `app.py:53`）、进度统计（`app.py:4024`）、未完成练习恢复（`app.py:4032`、`practice.py:128-150`）、自动进阶建议（`practice.py:361`，连续 4 道不同题独立答对才升档，`practice.py:22`）、编辑覆盖清单（`practice_coverage.py:3` 明确声明"never a learner mastery measurement"）。这些各自可用，没有一处回答"今天先做什么"。
2. **家庭首页只有一个动作按钮。** 主按钮是"开始今日挑战"（`app.py:1001`），到期复习块在 `todaySection` 底部（`app.py:1021`）。孩子要先复习还是先做题，只能自己猜。
3. **主站"知识路线"覆盖面太窄。** 精确映射只有 20 题 / 18 个概念，限二上第二/三/五单元与七上第二/五章（`deploy/open-webui-reuse/main-study/study.js:223`），不足以驱动跨册路径。

所以本方向不是"再做一套推荐算法"，而是把已有事实按固定顺序合成一张今天能照着做的卡片。

## 二、可复用的既有事实（全部只读，不新增数据）

| 事实 | 位置 | 路径中的用途 | 边界 |
| --- | --- | --- | --- |
| 到期复习卡与阶段 | `review_cards`、`review_objectives`；`app.py:4015-4021` | 复习步；数量与排序完全复用现有查询 | 练习作答不推进卡（`app.py:5339` 起的分支） |
| 复习间隔 | `INTERVALS = [1,2,4,7,15,30]`，`app.py:53` | 只读展示"第 N 阶段" | 不改调度器 |
| 自动进阶建议 | `learner_guidance`，`practice.py:361`；判定 `practice.py:315` | 练习步的目标档位与理由文案 | 4 道规则；不是掌握度 |
| 未完成练习 | `practice_workspaces.current_session_id`，`practice.py:128-150` | 续做步；含 revision 冲突 409 | 不代答、不自动跳题 |
| 本范围可用题目 | `/api/v1/question-choices`，`app.py:4381` | 判断本章是否有题，决定练习步或阅读步 | 覆盖为编辑口径 |
| 教材目录与页码 | `textbooks.catalogue` | 阅读步跳转原页 | 原页可读不授予 OCR/答案资格 |
| 进度计数 | `/api/v1/progress`，`app.py:4024` | 顶部已完成/独立作答数字 | 只显示计数，不算掌握 |

## 三、候选范围 A：今日路径（只读合成）

### 3.1 形态

- 一个只读接口 `GET /api/v1/study-path`（名称暂定），按当前档案合成最多 4 个步骤。
- 家庭首页 hero 下方新增一块卡片 `#studyPath`，每步一个入口，复用现有按钮行为（继续挑战、到期复习、打开教材）。
- 非家庭模式同一块以 `details` 折叠出现，不新增页面、不新增导航项。

### 3.2 步骤与固定排序

优先级固定，不做自适应模型：

1. **续做（resume）** — 存在 `presented`/`reserved` 且未判分的 item 时出现。
2. **复习（review）** — 到期卡 > 0 时出现；条数与排序沿用现有查询（relearning 优先，再按 due_at）。
3. **练习（practice）** — 当前范围有题；档位与理由直接取自 `learner_guidance`。
4. **阅读（reading）** — 仅当当前范围可用题为 0 时替代练习步出现，指向目录页与原页。

排序键 `(priority, book_id, chapter_id)`，同输入必得同输出，可做快照断言。

### 3.3 返回结构草案

```json
{
  "learner_id": "…",
  "scope": {"book_id": "…", "chapter_id": "…", "subject": "…"},
  "steps": [
    {"kind": "review", "title": "到期复习", "count": 3, "minutes": 20,
     "reason": "…", "evidence": ["review_cards"], "enabled": true}
  ],
  "total_minutes": 25,
  "notice": "按已有记录给出建议顺序，不代表掌握度。",
  "as_of": "…"
}
```

### 3.4 文案规则

- `guidance` 的 reason 原样透出，不自造新理由。
- 覆盖信息一律标注"编辑覆盖"；接口与 UI 均无 `mastery` 字段。
- 时间只给建议值，超过 25 分钟时只显示前 3 步。

## 四、明确不做

- 不做掌握度 / 能力模型、不做掌握率大屏。
- 不做跨册自适应排序、不做周计划 / 月计划。
- 不做提醒、推送、通知。
- 不做服务端阅读位置（P2 单列）。
- 不改主站"知识路线"与挑战档展示（11-13 交接 P1 单列）。
- 不做图形 + 数学的视觉扩展（另一方向，单列）。
- 不加表、不加迁移、不改 `BATCHES`、不注册任何候选批次。
- 不调用模型 / OCR / embedding。

## 五、预计改动文件（实施时）

新增：

- `learning_service/study_path.py`（纯函数合成，约 180—220 行）
- `tests/test_study_path.py`
- `tests/test_study_path_browser.py`
- `docs/open-webui-reuse/study-path.md`
- `docs/verification/STUDY-PATH-<实施日>.md`

修改：

- `learning_service/app.py`（1 个路由 + 首页卡片标记与脚本，约 +80 行）
- `tests/test_family_practice.py`（若与路径共用 guidance 常量，补契约断言）
- `docs/README.md`（入口）

不动：`learning_service/data/*`（题库与清单）、`learning_service/migrations/`、`deploy/open-webui-reuse/main-study/*`、`BATCHES`、`learning_data/` 档案。

## 六、验收条件（每条可执行）

1. **零写入**：同一 GET 前后 `learning.db` 50 张表逐表行哈希一致；`audit`、`learning_events` 无新增；不建新表。
2. **续做优先**：存在未判分 item 时第一步必为 `resume`；item 判分或取消后该步消失。
3. **复习一致**：路径中的到期卡集合与 `/api/v1/review-tasks` 完全一致（同一 SQL 条件）；0 张时该步隐藏且不显示 20 分钟。
4. **进阶一致**：练习步档位与 reason 与 `/api/v1/question-choices` 的 `practice_guidance` 逐字一致；4 道规则不变。
5. **阅读兜底**：仅当本章可用题为 0 时出现 `reading`；页码来自目录元数据；打开失败降级到目录。
6. **覆盖口径**：任何覆盖信息标注"编辑覆盖"，接口与 UI 均无掌握度字段。
7. **认证与并发**：learner context version 不符 → 409（沿用现有错误码）；deadline → 503；未登录沿用现有 303/401。
8. **布局**：1280×1000 与 390×900 无横向滚动；卡片可键盘操作；不新增必填步骤。
9. **外部调用**：`provider_calls = 0`；无 OCR / embedding 调用。
10. **回归**：章节练习、家庭练习、学习工作台、教材浏览器、到期复习相关模块全通过；既有 attempt / review 数据不变。
11. **可复现**：同一合成数据两次 GET 结果字节一致。

## 七、风险

- **口径漂移**：复习与进阶口径若变，路径随之变。因此只透传、不重写，并复用同一查询。
- **被误读为掌握度**：文案必须显式"建议"与"编辑覆盖"，不出现百分比。
- **家庭页认知负担**：最多 4 步，默认只展开第一步。
- **性能**：一次读多表；沿用 `share_study_reads` 与 deadline，记录 P95 供参考，暂不设为门槛。

## 八、需要你决定的三件事

1. **范围**：只做家庭页，还是同时改主站入口？（建议只做家庭页，主站 P1 单列）
2. **计数**：是否显示"今日完成 X/Y"？（建议不显示，容易变成打卡压力与伪掌握）
3. **预算**：总建议 25 分钟是否合适，还是提供 10 / 15 / 20 分钟档？

## 九、批准后的实施顺序

1. 合成数据测试先行（排序、零写入、边界）。
2. 模块 + 路由，本地两视口检查。
3. 家庭首页卡片接入。
4. 全量回归，出验收报告与交接。
5. 发布另需授权，不随本范围自动部署。
