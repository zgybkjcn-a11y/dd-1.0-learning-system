# 课标交叉核对与候选进入正式题库（2026-11-18）

## 结论

按用户决定跳过教师签署，由助手对 81 道下册/上册缺口候选做课标交叉核对；81 道全部通过本地可核验的结构、范围、证据与映射检查，已登记进本地正式题库（`chapter_practice.BATCHES` 9 个批次），供后续生产安装。教师签署仍为 `false`，真实难度仍未校准。

## 核对对象

9 个候选批次，共 81 题（上册 20 + 下册 61）：

| 批次 | 题数 |
| --- | --- |
| `upper_gap_candidates` | 20 |
| `lower_gap_candidates` | 7 |
| `lower_gap_candidates_batch2` | 9 |
| `lower_gap_candidates_batch3` | 9 |
| `lower_gap_candidates_batch4` | 9 |
| `lower_gap_candidates_batch5` | 9 |
| `lower_gap_candidates_batch6` | 7 |
| `lower_gap_candidates_batch7` | 7 |
| `lower_gap_candidates_batch8` | 4 |

## 方法与逐项检查

脚本 `scripts/crosscheck_curriculum_candidates.py` 对每题执行：

- 题库身份：`chapter._parse()` 全量内容校验（ID 形式、年级/教材/章节范围、学科一致、来源为本地编写、教材 PDF sha256、答案自洽与判分复算、字段覆盖）。
- 范围与课标依据：`knowledge.point_id` 必须能在本地 `family_subject_coverage_plan_v16.json`、`family_math_coverage_plan_v15.json` 或 `docs/quality/lower-knowledge-inventory-2026-11-13.json` 中找到；要求文本必须存在；下册清单任务必须是 `check`。
- 映射角色：`direct`/`supporting` 只能取已定义值；人工要求不得声称为自动直接达标；每题必须有核心动作、映射理由与族。
- 题面结构：响应字段数与核心动作数一致；字段覆盖与 `review.field_coverage` 一致。
- 复核标记：`review.status` 为助手核对，`teacher_reviewed` 必须为 `false`。

下册第三批把 `math-g7-lower:7:perpendicular-{definition,unique,distance}` 三条 refine 行按页位对应到已审父项 `math-g7-lower:7:perpendicular`，未修改父项页位。

## 结果

| 项目 | 结果 |
| --- | --- |
| 候选 | 81 |
| 接受 | 81 |
| 拒绝 | 0 |
| 直接族 | 76 |
| 辅助族 | 5 |
| 带人工跟进 | 59 |
| 按年级 | 二年级 18 / 七年级 63 |
| 按学科 | 语文 0 / 数学 14 / 英语 11 / 道法 16 / 历史 11 / 地理 14 / 生物 15 |

每题的判定、要求来源、角色、父项（如有）与文件 sha256 见证据 `learning_data/verification/curriculum-crosscheck-20261118/crosscheck.json`。

## 登记与语义变化

- `learning_service/chapter_practice.py` 的 `BATCHES` 新增上述 9 个批次及 sha256；`chapter.bank()` 由 1074 题变为 1155 题，范围由 98 个变为 142 个。
- 候选数据文件的 `status` 改为 `assistant_crosschecked`，顶层与逐题 `curriculum_standard_crosscheck` 记为 `assistant_crosscheck_passed_2026-11-18_against_local_plan_or_inventory`，逐题 `review.deployment_status` 为 `registered_family_bank`。
- 覆盖计划仍为 subject-v16 / math-v15，尚未把这些题目写成计划映射；因此覆盖报告里的 configured/partial/gap **不会**因本次登记自动变化，需另做计划升版。
- 题目可从本地题库读取并安装。**2026-11-18 已按用户授权安装到本机生产**：9 批全部新增 81 题，正式库由 1145 题增至 1226 题（二年级可选题 418→436）；安装同时新增 44 个知识点与 44 个复核目标，审计事件 +9；停写备份、逐表比对与切换后冒烟见 `docs/verification/QUESTION-BANK-PROMOTION-2026-11-18.md`。
- 安装入口为 `scripts/install_registered_batches.py`（`--dry-run` 只校验题库），逐批调用 `chapter.install`，只新增缺失题版，不删除或覆盖旧题、题版和使用记录。

## 局限

- 国家课标文本不在本仓库；本次核对的对象是本地已审计划/清单中的要求表述与教材页位证据，**不是课标原文比对**，不能写成“课标已全部对齐”。
- 教师签署为 `false`；助手复算与结构核对不替代真人教学审核。
- 口述、作图、实测等人工任务仍未被观察；自动题只证明指定的判分部分。
- 真实难度未校准，题目只标作者设定难度。
