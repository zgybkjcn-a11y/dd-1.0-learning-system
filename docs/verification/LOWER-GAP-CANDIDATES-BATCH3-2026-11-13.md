# 下册第三批 · 七下数学 7.1.2 与二下数学第 2—5 单元 · 本地候选复核

2026-11-13（第三批）。按[下册第二批交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH2.md)的顺序，先把七下数学第七章 p4—p6 的垂直内容拆成三项，再为二下数学第 2—5 单元各有界要求编制候选，共 **9 题、36 个作答项**，逐题复核完毕。第一批 7 题、第二批 9 题及其审阅包保持原样。

**尚未导入或部署**。批次 `lower_gap_candidates_batch3` 未加入运行时 `BATCHES`；正式题快照仍 1145 题（二年级 418、七年级 727），本地章节题源仍 1074 题；线上仍 subject-v5，本地仍 math-v15 / subject-v16。subject-v20 提案只存在于本批审阅包。

## 可审入口

- [逐题审阅页](../../learning_data/verification/lower-gap-candidates-batch3-20261113/review-v1/index.html)
- [候选数据](../../learning_service/data/family_chapter_lower_gap_candidates_batch3_v1.json)
- [逐项覆盖差异](../../learning_data/verification/lower-gap-candidates-batch3-20261113/review-v1/coverage-diff.json)
- [原页与来源边界](../../learning_data/verification/lower-gap-candidates-batch3-20261113/review-v1/source-evidence.json)
- [人工任务](../../learning_data/verification/lower-gap-candidates-batch3-20261113/review-v1/manual-tasks.json)
- [summary.json](../../learning_data/verification/lower-gap-candidates-batch3-20261113/review-v1/summary.json)
- [页面图像核对记录](../../learning_data/verification/lower-gap-candidates-batch3-20261113/page-images/)

## 逐题结论

“通过”指同一助手的内容复核加独立复算，不是独立教师审核、课标交叉审核或学生真实难度校准。

| point_id | 候选 | 书内依据页 | 复核结果 |
| --- | --- | --- | --- |
| `math-g7-lower:7:perpendicular-definition` | 垂直的定义与垂足 | 4 | 完整有界要求，一个直接族；由直角判垂直、邻角与垂足辨析 |
| `math-g7-lower:7:perpendicular-unique` | 垂线的基本事实 | 5 | 完整有界要求，一个直接族；两种位置的条数、射线线段所在直线、作图步骤 |
| `math-g7-lower:7:perpendicular-distance` | 垂线段最短与点到直线的距离 | 6 | 完整有界要求，一个直接族；长短比较、距离定义、直角三角形读距离与最长边 |
| `math-g2-lower:2:inventory-1` | 倍的认识与三类倍数问题 | 25, 27, 31 | 完整有界要求，一个直接族；求几倍、求几倍量、求一份量、区分“多几” |
| `math-g2-lower:3:inventory-1` | 数位、十进制与含零的数 | 41, 44, 50 | 完整有界要求，一个直接族；十进制换算、含零读写、数位组成、几个百 |
| `math-g2-lower:3:inventory-2` | 整十、整百、整千数的加减 | 57 | 完整有界要求，一个直接族；三道计算加计数单位说明 |
| `math-g2-lower:4:inventory-1` | 万以内加减的笔算与进退位 | 64, 65, 69 | 完整有界要求，一个直接族；一次进位、连续进位、连续退位、错因定位 |
| `math-g2-lower:4:inventory-2` | 加减各部分的关系 | 73 | 完整有界要求，一个直接族；由和求加数、逆运算关系式 |
| `math-g2-lower:5:inventory-1` | 数与运算的关联整理 | 87, 89, 92 | 完整有界要求，一个直接族；求倍数、求商、笔算共同规则、关系图归类 |

九题全部为直接族（family_count=1），**新增 configured 仍为 0**（编辑口径要求同一要求下两个不同直接族）。九题全部挂未观察的人工任务。

## 七下数学旧定位的处理

`math-g7-lower:7:perpendicular` 旧行仍保留 `printed_page=3`，**未删除、未改写**；本批以三条 `candidate_only` 的 refine 行分别定位 p4、p5、p6，并在行内写明“原行 printed_page=3 保留不改；本行按复核后的 p4—p6 拆分重新定位”。旧行原有映射与人工任务逐项不变。

## 内容复核中修正的问题

1. `perpendicular-definition` 第 3 项原正确句“四个角都是直角”会泄露第 2 项答案（邻角 90°），改为垂足定义辨析。
2. `perpendicular-unique` 第 2 项原正确句同时给出直线上与直线外两种位置的条数，泄露第 1 项答案，改为“在同一平面内”这一条件的辨析。
3. `math-g2-lower:3:inventory-2` 第 3 项原用 1500−600，题干直接给出第 2 项答案 1500，改为 1700−900。
4. `math-g2-lower:4:inventory-2` 第 2 项原用 709 与 249，直接给出第 1 项答案 249，改为 836−478=358。
5. `math-g2-lower:5:inventory-1` 第 1 项原在题干写出 32÷8，与第 4 项归类判断重叠；第 1 项改为直接求倍数，第 4 项改为“和=加数+加数”所属分支。
6. 笔算题解析中“445+298”的十位进位说明改为逐位加进位，避免只核对结果的表述。
7. `math-g2-lower:4:inventory-1` 第 2 项的进位错因原把 733 归因于百位漏加，改为 633（十位、百位都漏加）与 733（十位漏加个位进位）两种不同错因。

以上修正保留在脚本与测试的断言中，`tests/test_lower_gap_candidates_batch3.py` 会检查正确选项文字不得出现在题干或同题其他项的题干里。

## 覆盖口径

| 证据口径 | configured | partial | gap |
| --- | ---: | ---: | ---: |
| 固定正式题ID + 本地subject-v16（含本批9条候选专属行） | 112 | 288 | 267 |
| 假设本批9题存在时的候选预览 | 112 | 297 | 258 |

- gap 从 258 增至 267 是本批把 9 条要求作为候选专属行加入对照表所致，不是原有条目退化。
- 9 项全部 gap → partial（各得一个直接族）；新增 configured 为 0。
- 这些是本地审阅统计，不是线上 subject-v5 的新运行统计；本批 proposal 独立于第二批 proposal，不把两批候选合并计数。

## 验证与保全

- `tests/test_lower_gap_candidates_batch3.py` 9 项通过（40.41 秒）：九项可复现且未注册、旧行逐项保留且仅以 refine 行补充、每题必带未观察的人工任务、七下垂直结论与二下全部数值独立复算、答案不泄漏、逐项错误/缺失/多余字段边界、安装前后证据分离、合成库安装与作答。
- 同批回归 **116 项通过、0 失败 0 跳过**（314.27 秒），覆盖数学单一动作、章节练习、覆盖、学科知识、知识质量、挑战档、上册候选、下册第一批、第二批与第三批。记录见 `learning_data/verification/lower-gap-candidates-batch3-20261113/regression.xml` 与 `test-results.json`。
- 审阅页在 1280×1000 与 390×900 两视口布局检查：无横向滚动，9 篇文章无越界（`review-layout.json`）。这是无头浏览器检查，**不是真实手机验收**。
- 合成安装以 1145 道旧题与全部原表行为基线，增量 9 题后重复安装新增 0；逐题作答正确、跨年级隔离与提交幂等通过，`provider_calls` 为 0。
- 第一批、第二批候选文件与审阅包在本轮逐字节未改。

## 边界

- 九题只覆盖七下数学 7.1.2 的三项与二下数学第 2—5 单元各一处有界要求，不是这些单元的知识点穷尽。
- 七下数学三项只考书面判断与计算；实际摆直角、三角尺作图与测量仍归人工任务且未观察。
- 二下数学六题只考数值与选择；摆一摆、画线段图、竖式过程与关系图仍归人工任务且未观察。
- 二下教材无原生文字层，依据页由页面图像目视核对，未使用 OCR；七下数学使用原生文字层。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准。
- 未导入、未迁移、未部署、未重启服务或 C01；无外部模型/OCR/embedding；真实手机验收继续暂缓；不提交推送。

## 后续

下一批按交接顺序：二下数学“数学连环画”与其余单元、七下英语 Unit 2、七下生物其余小节、七下地理其余章节与项目（含 p108 固碳图，须使用目视核对值并注明图 1、原页 108、万公顷与亿吨）。每个范围仍先展开知识点再出候选。

会话入口：[第三批续办交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH3.md)。
