# 下册第六批 · 二下数学 activity1、七下英语 Unit 5—8 与 Reading Plus · 本地候选复核

2026-11-14（第六批）。按[下册第五批交接](../plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH5.md)的顺序，继续为二下数学 `activity1`“时间在哪里”的两条初步要求，以及七下英语 Unit 5—8 与 Reading Plus 各一处有界要求编制候选，共 **7 题、28 个作答项**，逐题复核完毕。前五批 43 题及其审阅包保持原样。

**尚未导入或部署**。批次 `lower_gap_candidates_batch6` 未加入运行时 `BATCHES`；正式题快照仍 1145 题（二年级 418、七年级 727），本地章节题源仍 1074 题；线上仍 subject-v5，本地仍 math-v15 / subject-v16。subject-v23 提案只存在于本批审阅包。

## 可审入口

- [逐题审阅页](../../learning_data/verification/lower-gap-candidates-batch6-20261114/review-v1/index.html)
- [候选数据](../../learning_service/data/family_chapter_lower_gap_candidates_batch6_v1.json)
- [逐项覆盖差异](../../learning_data/verification/lower-gap-candidates-batch6-20261114/review-v1/coverage-diff.json)
- [原页与来源边界](../../learning_data/verification/lower-gap-candidates-batch6-20261114/review-v1/source-evidence.json)
- [人工任务](../../learning_data/verification/lower-gap-candidates-batch6-20261114/review-v1/manual-tasks.json)
- [summary.json](../../learning_data/verification/lower-gap-candidates-batch6-20261114/review-v1/summary.json)
- [页面图像核对记录](../../learning_data/verification/lower-gap-candidates-batch6-20261114/page-images/)

## 逐题结论

“通过”指同一助手的内容复核加独立复算与字段约束检查，不是独立教师审核、课标交叉审核或学生真实难度校准。

| point_id | 候选 | 书内依据页 | 复核结果 |
| --- | --- | --- | --- |
| `math-g2-lower:activity1:inventory-1` | 钟面上的大格、小格与时间单位 | 2, 3 | 完整有界要求，一个直接族；12 大格／60 小格、1 时=60 分换算、时刻与经过时间 |
| `math-g2-lower:activity1:inventory-2` | 作息记录中的起止时刻与经过时间 | 5, 7 | 完整有界要求，一个直接族；三段不跨日经过时间与“哪一项是时长” |
| `english-g7-lower:5:inventory-1` | Present continuous: now and at the moment | 33, 37 | 完整有界要求，一个直接族；be+doing 的疑问、陈述与辨认 |
| `english-g7-lower:6:inventory-1` | Weather: simple present or present continuous | 41, 45 | 完整有界要求，一个直接族；习惯与此刻的时态对照 |
| `english-g7-lower:7:inventory-1` | Simple past: school trips and diaries | 49, 53 | 完整有界要求，一个直接族；不规则动词、did 问答、be 过去式 |
| `english-g7-lower:8:inventory-1` | Story tenses and event order | 57, 61 | 完整有界要求，一个直接族；叙事时态与故事因果 |
| `english-g7-lower:9:inventory-1` | Reading Plus: the amazing octopus | 65 | 完整有界要求，一个直接族；300 种、3 颗心脏、无骨头、断腕再生 |

七题全部为直接族（family_count=1），**新增 configured 仍为 0**。七题全部挂未观察的人工任务。

## 原页核对

| 册 | 核对方式 | 结果 |
| --- | --- | --- |
| 二下数学 | 页面图像目视核对（无原生文字层） | p2：钟面 3 根指针、12 大格、每大格 5 小格、时针转 1 大格是 1 时；p3：1 时=60 分、1 分=60 秒、时针转 1 圈 12 小时；p5：事情与需要时间、作息表 8:20—9:00；p7：时间记录与先后顺序 |
| 七下英语 | 原生文字层选段 | p33/37：现在进行时陈述、疑问、否定；p41/45：天气词汇与两种时态对照；p49/53：一般过去时与过去时间状语、did 问答；p57/61：叙事时态与老鼠、狮子情节；p65：章鱼拓展阅读的事实 |

页面图像保存在 `learning_data/verification/lower-gap-candidates-batch6-20261114/page-images/`，仅作目视核对，未使用 OCR。

## 内容复核中修正的问题

1. 英语 Unit 5—8 在编写时逐句与教材 3a、3b 比对，避开直接抄录：Unit 5 用 at the moment、Tom 在房间读书、使用电脑写信；Unit 7 用上月的科技馆、上周的航天馆；Unit 8 用七岁时的狐狸故事、昨晚写诗、从前捕到金鱼。教材原句没有进入候选。
2. 狮子和老鼠的因果题保留教材情节，但题干与四个选项均为自编，已在来源边界注明。
3. 二下数学的作息记录与钟面数值为本地自编，未使用书中学生的真实作息记录。

答案不得出现在题干或同题其他项题干中的断言，以及“干扰项必须确实错误”的逐项作答检查，均保留在 `tests/test_lower_gap_candidates_batch6.py`。

## 覆盖口径

| 证据口径 | configured | partial | gap |
| --- | ---: | ---: | ---: |
| 固定正式题ID + 本地subject-v16（含本批7条候选专属行） | 112 | 288 | 265 |
| 假设本批7题存在时的候选预览 | 112 | 295 | 258 |

- 与本批独立的 proposal 只加入本批 7 行（其中二下数学同一范围两条要求各一行），前五批的行不并入。
- 7 项全部 gap → partial（各得一个直接族）；新增 configured 为 0。
- 这些是本地审阅统计，不是线上 subject-v5 的新运行统计。

## 验证与保全

- `tests/test_lower_gap_candidates_batch6.py` 9 项通过（32.12 秒）：七项可复现且未注册、前五批保持独立、每题必带未观察的人工任务、数学与英语答案逐项核对、答案不泄漏、逐项错误/缺失/多余字段边界、安装前后证据分离与图像核对记录、合成库安装与作答。
- 同批回归 **144 项通过、0 失败 0 跳过**（428.40 秒），覆盖数学单一动作、章节练习、覆盖、学科知识、知识质量、挑战档、上册候选与下册第一至第六批。记录见 `regression.xml` 与 `test-results.json`。
- 审阅页在 1280×1000 与 390×900 两视口布局检查：无横向滚动，7 篇文章无越界（`review-layout.json`）。这是无头浏览器检查，**不是真实手机验收**。
- 合成安装以 1145 道旧题与全部原表行为基线，增量 7 题后重复安装新增 0；逐题作答正确、跨年级隔离与提交幂等通过，`provider_calls` 为 0。
- 前五批候选文件与审阅包在本轮逐字节未改。

## 边界

- 七题只覆盖六个范围各一处有界要求，不是这些单元或章节的知识点穷尽。
- 二下数学两题只考钟面结构与时刻／经过时间；实际拨钟、测量 1 分钟活动与时间小书仍归人工任务且未观察。
- 七下英语五题只考书面选择；打电话、介绍天气安排、写日记与复述故事仍归人工任务。
- Reading Plus 只取第 65 页可核对事实，不代表整册拓展阅读已逐篇复核。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准。
- 未导入、未迁移、未部署、未重启服务或 C01；无外部模型/OCR/embedding；真实手机验收继续暂缓；不提交推送。

## 后续

下一批：二下道法第 2—4 单元 4 题、七下道法第 2—4 单元 3 题（共 7 题）；最后七下历史第 2—4 单元 4 题。每个范围仍先展开知识点再出候选。

会话入口：[第六批续办交接](../plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH6.md)。
