# 下册首批三个起始范围 · 本地候选复核

2026-11-13。按[下册初步清单](LOWER-KNOWLEDGE-INVENTORY-2026-11-13.md)的首批范围，为三个起始范围各一处有界要求编制本地自编候选，共 7 题、28 个作答项，逐题复核完毕。

**尚未导入或部署**。候选批次 `lower_gap_candidates` 未加入运行时 `BATCHES`；正式题快照仍 1145 题（二年级 418、七年级 727），本地章节题源仍 1074 题；线上仍 subject-v5，本地仍 math-v15 / subject-v16。subject-v18 提案只存在于本批审阅包。

## 可审入口

- [逐题审阅页](../../learning_data/verification/lower-gap-candidates-20261113/review-v1/index.html)
- [候选数据](../../learning_service/data/family_chapter_lower_gap_candidates_v1.json)
- [逐项覆盖差异](../../learning_data/verification/lower-gap-candidates-20261113/review-v1/coverage-diff.json)
- [原页与来源边界](../../learning_data/verification/lower-gap-candidates-20261113/review-v1/source-evidence.json)
- [人工任务](../../learning_data/verification/lower-gap-candidates-20261113/review-v1/manual-tasks.json)
- [summary.json](../../learning_data/verification/lower-gap-candidates-20261113/review-v1/summary.json)

## 逐题结论

“通过”指同一助手的内容复核加独立算术约束检查，不是独立教师审核、课标交叉审核或学生真实难度校准。

| point_id | 候选 | 书内依据页 | 复核结果 |
| --- | --- | --- | --- |
| `math-g2-lower:1:inventory-1` | 摆小棒求商、余数与检验 | 11, 12, 15 | 完整有界要求，一个直接族；余数小于除数与关系式验算同题考查 |
| `math-g2-lower:1:inventory-2` | 余数要不要再多算一份 | 19 | 完整有界要求，一个直接族；组数、余数与“至少几个容器”分开判断 |
| `english-g7-lower:1:inventory-1` | Animal card: facts and the reason | 2, 4, 5 | 完整有界要求，一个直接族；卡片信息匹配加 why/because 短答 |
| `english-g7-lower:1:inventory-2` | Plurals and describing words | 3, 5 | 完整有界要求，一个直接族；规则/不规则复数与资料一致描述 |
| `english-g7-lower:1:inventory-3` | Main idea, reason and ways to help | 6, 7, 8 | 完整有界要求，一个直接族；主旨、原因、保护方法与细节区分 |
| `biology-g7-lower:1:inventory-1` | 萌发条件、自身条件与对照设计 | 2, 3, 4, 5 | **只计辅助**；读模拟记录不等于做过实验，保留人工观察任务 |
| `biology-g7-lower:1:inventory-2` | 根尖生长、传粉与受精 | 8, 9, 16, 17, 18 | 完整有界要求，一个直接族；按本册定义区分成对易混概念 |

关键复核点：

- 二下数学 23÷5=4…3、22÷5=4…2、40÷6=6…4（至少 7 盒）逐项复算；错误选项分别违反余数范围、把余数漏掉或多算一份。
- 二下教材无原生文字层，依据页由本地页面图像直接目视核对（第 11、12、15、19 页，PDF 17、18、21、25），未使用 OCR。
- 英语三题材料全部为自编短文与资料卡，未使用教材大象短文、对话或图片；`Because …` 短答只接受卡片给出的理由，接受大小写与有无句号，不接受其他理由。
- 生物萌发题数据明示“编题模拟记录，不是真实实验结果”；读表合计 27 粒只核对记录读取，实际观察另按人工任务。
- 生物根尖与花题按本册口径：分生区增加细胞数量、伸长区增大细胞体积、成熟区（根毛）吸收水和无机盐；传粉是花粉落到柱头上，受精是精子与卵细胞结合。

## 覆盖口径

| 证据口径 | configured | partial | gap |
| --- | ---: | ---: | ---: |
| 固定正式题ID + 本地subject-v16（新增7册无正式题） | 112 | 288 | 265 |
| 假设本批7题存在时的候选预览 | 112 | 295 | 258 |

- “安装前”的 gap 从 258 增至 265，是因为本批把 7 条下册初步要求作为候选专属行加入对照表，原本它们不在 subject-v16 中；这不是原有条目退化。
- 假想候选存在时，7 条全部从 gap 变为 partial：其中 6 项获得第一个**直接**题型族（family_count=1），1 项（萌发观察）只有辅助题（family_count=0）。
- 新增 configured 为 0：编辑口径要求同一要求下有两个不同直接题型族，本批每项只给了一个。
- 这些是本地审阅统计，不是线上 subject-v5 的新运行统计。

## 验证与保全

- `tests/test_lower_gap_candidates.py` 8 项通过（34.91 秒）：候选可复现且未注册、有界动作独立复算、文本答案只接受已记录变体、逐项错误/缺失/多余字段边界、人工与语言能力边界、安装前后证据分离、合成库安装与作答、练习册书目边界。
- 同批回归 99 项通过、0 失败 0 跳过（236.96 秒），覆盖数学单一动作、章节练习、覆盖、学科知识、知识质量、挑战档、上册候选与本批。记录见 `learning_data/verification/lower-gap-candidates-20261113/regression.xml` 与 `test-results.json`。
- 合成安装以 1145 道旧题与全部原表行为基线，增量 7 题后重复安装新增 0；逐题正确作答、跨年级隔离与提交幂等通过，`provider_calls` 为 0。没有访问生产数据库或制造真实学生记录。
- 审阅页在 1280×1000 与 390×900 两视口检查：页面无横向滚动，7 篇文章与 1 张模拟记录表均未越界（`review-layout.json`）。这是无头浏览器布局检查，**不是真实手机验收**。
- 过程中一次后台回归在候选文件被重新生成时运行，出现 `KeyError: 'challenge_id'` 的环境竞争失败；该次结果作废并保留记录，随后在文件稳定后重跑，以上数字取自重跑结果。

## 边界

- 7 题只覆盖三个起始范围各一处有界要求，**不是这三个单元的知识点穷尽**，也不覆盖其余 7 册下册内容。
- 新增7册此前没有正式题；本批只有本地预览，不能当作覆盖完成。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准；英语朗读/听力/自主表达与生物实验操作均未验收。
- 未导入、未迁移、未部署、未重启服务或 C01；无外部模型/OCR/embedding；真实手机验收继续暂缓；不提交推送。
- 教材统计值与图中数字保留原年份与原始状态；本批出题未采用任何未经目视核对的图中数据。

## 后续

下一批按剩余起始范围与真实校内进度推进：二下道法、七下道法、七下历史、七下地理起始单元；同时补二下数学第 2–5 单元、七下英语 Unit 2、七下生物其余小节。每个范围仍先展开知识点再出候选，不把“有一条记录”当成整章完整。

会话入口：[下册首批续办交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-CANDIDATES.md)。
