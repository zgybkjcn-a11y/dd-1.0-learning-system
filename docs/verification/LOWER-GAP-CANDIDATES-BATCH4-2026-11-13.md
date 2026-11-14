# 下册第四批 · 二下数学连环画、七下英语 Unit 2、七下生物与七下地理 · 本地候选复核

2026-11-13（第四批）。按[下册第三批交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH3.md)的顺序，继续为二下数学“数学连环画”、七下英语 Unit 2、七下生物第二至五章及栽培项目、七下地理第八章与固碳项目各一处有界要求编制候选，共 **9 题、36 个作答项**，逐题复核完毕。前三批 25 题及其审阅包保持原样。

**尚未导入或部署**。批次 `lower_gap_candidates_batch4` 未加入运行时 `BATCHES`；正式题快照仍 1145 题（二年级 418、七年级 727），本地章节题源仍 1074 题；线上仍 subject-v5，本地仍 math-v15 / subject-v16。subject-v21 提案只存在于本批审阅包。

## 可审入口

- [逐题审阅页](../../learning_data/verification/lower-gap-candidates-batch4-20261113/review-v1/index.html)
- [候选数据](../../learning_service/data/family_chapter_lower_gap_candidates_batch4_v1.json)
- [逐项覆盖差异](../../learning_data/verification/lower-gap-candidates-batch4-20261113/review-v1/coverage-diff.json)
- [原页与来源边界](../../learning_data/verification/lower-gap-candidates-batch4-20261113/review-v1/source-evidence.json)
- [人工任务](../../learning_data/verification/lower-gap-candidates-batch4-20261113/review-v1/manual-tasks.json)
- [summary.json](../../learning_data/verification/lower-gap-candidates-batch4-20261113/review-v1/summary.json)
- [页面图像核对记录](../../learning_data/verification/lower-gap-candidates-batch4-20261113/page-images/)

## 逐题结论

“通过”指同一助手的内容复核加独立复算，不是独立教师审核、课标交叉审核或学生真实难度校准。

| point_id | 候选 | 书内依据页 | 复核结果 |
| --- | --- | --- | --- |
| `math-g2-lower:activity2:inventory-1` | 数学连环画中的数量与算式 | 83, 84 | 完整有界要求，一个直接族；故事—问题—算式—结果对应 |
| `english-g7-lower:2:inventory-1` | 规则与义务：can, must, have to | 9, 13 | 完整有界要求，一个直接族；must/mustn't/don't have to 与祈使句 |
| `biology-g7-lower:2:inventory-1` | 光合作用与呼吸作用 | 29, 31, 33, 38 | 完整有界要求，一个直接族；场所、原料、实质与实验结论 |
| `biology-g7-lower:activity1:inventory-1` | 栽培项目的变量与记录 | 51, 52 | 完整有界要求，一个直接族；单变量、记录指标、平均值、失败修订 |
| `biology-g7-lower:3:inventory-1` | 生殖系统与青春期的普遍规律 | 58, 60, 64 | 完整有界要求，一个直接族；器官功能、受精与胚胎场所、个体差异 |
| `biology-g7-lower:4:inventory-1` | 营养物质的作用与重复测量 | 70, 71, 74 | 完整有界要求，一个直接族；三类营养作用、缺铁表现、平均值 |
| `biology-g7-lower:5:inventory-1` | 呼吸系统的组成与通气 | 92, 93, 98 | 完整有界要求，一个直接族；组成、胸廓变化、气体成分与交换方向 |
| `geography-g7-lower:8:inventory-1` | 日本的位置、地形与火山地震 | 20, 21 | 完整有界要求，一个直接族；四大岛、板块、火山地震原因、地形 |
| `geography-g7-lower:activity2:inventory-1` | 雨林固碳项目：面积、碳储量与单位面积 | 107, 108 | 完整有界要求，一个直接族；两项合计、单位面积换算、指标比较 |

九题全部为直接族（family_count=1），**新增 configured 仍为 0**。九题全部挂未观察的人工任务。

## 固碳项目的数据来源

第 108 页图 1 的文字层数字为乱码，本批按原页目视核对后出题：森林面积（万公顷）寒带 1 600、温带 900、亚热带 460、热带 4 000；森林碳储量（亿吨）17.1、15.4、8.0、88.0。题干与表题均注明“教材第 108 页图 1”“原页目视核对”“不代表当前实时统计”，单位为万公顷与亿吨。合计与单位面积换算是本地独立复算：面积 6 960 万公顷、碳储量 128.5 亿吨、热带 220 吨/公顷。

## 内容复核中修正的问题

1. `biology-g7-lower:2:inventory-1` 第 4 项原设干扰项“植物会消耗氧气”本身在生理上成立，不能作为“从实验结果不能推出”的干扰项，改为“密闭玻璃罩里根本没有氧气”，并同步改写错因反馈。

答案不得出现在题干或同题其他项题干中的断言，以及“干扰项必须确实错误”的逐项作答检查，均保留在 `tests/test_lower_gap_candidates_batch4.py`。

## 覆盖口径

| 证据口径 | configured | partial | gap |
| --- | ---: | ---: | ---: |
| 固定正式题ID + 本地subject-v16（含本批9条候选专属行） | 112 | 288 | 267 |
| 假设本批9题存在时的候选预览 | 112 | 297 | 258 |

- gap 从 258 增至 267 是本批把 9 条要求作为候选专属行加入对照表所致，不是原有条目退化。
- 9 项全部 gap → partial（各得一个直接族）；新增 configured 为 0。
- 这些是本地审阅统计，不是线上 subject-v5 的新运行统计；本批 proposal 独立于前三批 proposal，不合并计数。

## 验证与保全

- `tests/test_lower_gap_candidates_batch4.py` 10 项通过（41.23 秒）：九项可复现且未注册、前三批保持独立、每题必带未观察的人工任务、数学与生物与地理数值独立复算、生殖题只用普遍规律且不索取个人数据、固碳表值与单位换算一致、答案不泄漏、逐项错误/缺失/多余字段边界、安装前后证据分离、合成库安装与作答。
- 同批回归 **126 项通过、0 失败 0 跳过**（362.18 秒），覆盖数学单一动作、章节练习、覆盖、学科知识、知识质量、挑战档、上册候选与下册第一至第四批。记录见 `learning_data/verification/lower-gap-candidates-batch4-20261113/regression.xml` 与 `test-results.json`。
- 审阅页在 1280×1000 与 390×900 两视口布局检查：无横向滚动，9 篇文章与 1 张表无越界（`review-layout.json`）。这是无头浏览器检查，**不是真实手机验收**。
- 合成安装以 1145 道旧题与全部原表行为基线，增量 9 题后重复安装新增 0；逐题作答正确、跨年级隔离与提交幂等通过，`provider_calls` 为 0。
- 前三批候选文件与审阅包在本轮逐字节未改。

## 边界

- 九题只覆盖九个范围各一处有界要求，不是这些单元或章节的知识点穷尽。
- 二下数学与七下生物只考数值、选择和文字结论；连环画创作、栽培记录、模型制作与实际实验仍归人工任务且未观察。
- 七下英语只考书面选择；设计规则标志、解释规则帮助了谁与真实交流仍归人工任务。
- 七下地理两题只考文字结论与表内计算；地图定位、制图与公开数据核查仍归人工任务。
- 七下生物生殖题只用教材普遍规律与虚构情境，不索取任何真实个人或家庭身体数据，也不替代正规健康教育。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准。
- 未导入、未迁移、未部署、未重启服务或 C01；无外部模型/OCR/embedding；真实手机验收继续暂缓；不提交推送。

## 后续

下一批按交接顺序：七下生物第四单元第六、七章与人体模型项目；七下地理跨学科东南亚项目、第九至十一章；七下英语 Unit 3—8 与阅读拓展；二下数学第 5 单元其余条目。每个范围仍先展开知识点再出候选。

会话入口：[第四批续办交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH4.md)。
