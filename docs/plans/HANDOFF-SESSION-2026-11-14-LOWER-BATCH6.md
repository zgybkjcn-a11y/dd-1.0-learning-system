# 会话续办：下册第六批候选（二下数学 activity1、七下英语 Unit 5—8 与 Reading Plus）

2026-11-14（第六批），`/home/deniskorfei/projects/open-webui`。本文件续接[下册第五批交接](HANDOFF-SESSION-2026-11-14-LOWER-BATCH5.md)。旧交接与发布清单完整保留。

## 本轮已完成

1. **本批 7 题、28 个作答项**，覆盖六个范围各一处有界要求（二下数学同一范围两条要求分列）：
   - 二下数学 `activity1` 钟面（p2、3）：12 大格、60 小格、1 时 20 分=80 分、时刻与经过时间。
   - 二下数学 `activity1` 时间记录（p5、7）：8:20—9:00、9:10—9:45、10:00—10:30 三段经过时间，并辨认哪一项是时长。
   - 七下英语 Unit 5（p33、37）：现在进行时的疑问、陈述与辨认。
   - 七下英语 Unit 6（p41、45）：一般现在时与现在进行时的天气语境对照。
   - 七下英语 Unit 7（p49、53）：一般过去时的不规则动词、did 问答与 be 过去式。
   - 七下英语 Unit 8（p57、61）：叙事时态与老鼠、狮子的因果。
   - 七下英语 Reading Plus（p65）：章鱼材料的 300 种、3 颗心脏、无骨头、断腕再生。
2. 七题全部为直接题型族，全部挂未观察的人工任务；新增 configured 为 0。
3. 审阅包 `learning_data/verification/lower-gap-candidates-batch6-20261114/review-v1/`；批次 `lower_gap_candidates_batch6` 未注册、未安装；subject-v23 提案只在审阅包中。
4. 定向检查 9 项通过；同批回归共 **144 项通过、0 失败 0 跳过**（428.40 秒），见 `test-results.json` 与 `regression.xml`。审阅页 1280×1000 / 390×900 布局检查无横向滚动、无越界（`review-layout.json`）。

详见[第六批复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH6-2026-11-14.md)。

## 本轮逐页核对结果

### 二下数学（无原生文字层，页面图像目视核对）

| 书内页 | 内容 |
| --- | --- |
| 2 | 钟面三根指针（时针、分针、秒针）；12 个大格；每个大格 5 个小格；钟面共 60 个小格；时针转 1 大格是 1 时 |
| 3 | 拨针演示 12:00→12:30→1:00；1 时=60 分；1 分=60 秒；时针转 1 圈 12 小时；30 分叫半小时 |
| 5 | 事情与需要时间（50 米跑 11 秒、一千米跑 3 分 50 秒、马拉松 3 小时）；作息表第一节课 8:20—9:00；1 分钟活动 |
| 7 | 时间记录与先后顺序、时间小书制作要求 |

### 七下英语（原生文字层）

| 书内页 | 内容 |
| --- | --- |
| 33 | Unit 5 目标：用现在进行时谈正在发生的事、打电话 |
| 37 | Grammar Focus 与 3a/3b：be+doing 的疑问、否定与陈述 |
| 41 | Unit 6 目标：天气类型、两种时态谈天气活动 |
| 45 | Grammar Focus 与 3a/3b：习惯性活动与此刻活动的时态对照 |
| 49 | Unit 7 目标：一般过去时、学校旅行、日记 |
| 53 | Grammar Focus 与 3a/3b：过去时间状语、did 问答 |
| 57 | Unit 8 目标：讲故事、一般过去时与一般现在时、编结尾 |
| 61 | Grammar Focus 与 3a/3b：叙事时态对照；老鼠与狮子情节 |
| 65 | Reading Plus：章鱼约 300 种、八条腕、无骨头、三颗心脏、变色、喷墨、断腕再生 |

## 当前边界

- 正式题数量仍沿用已验证发布证据：1145 题（二年级 418、七年级 727），章节题 1071；线上 schema14、subject-v5。未重新访问生产数据库。
- 本地章节题源仍 1074 题；本批另存 7 道下册候选，前五批 7＋9＋9＋9＋9 道保持原样，均未加入 `BATCHES`。
- 固定正式题ID套用本地 subject-v16 时为 112 configured / 288 partial / **265** gap（265 = 原 258 + 本批 7 条候选专属行）；假设本批 7 题存在时为 112 / 295 / 258。新增 configured 为 0。
- 二下教材无原生文字层，p2/3/5/7 由页面图像目视核对；七下英语使用原生文字选段，未使用 OCR。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准；拨钟、一分钟活动、时间小书、打电话、写日记、复述故事均归人工任务且未观察。
- 真实手机验收继续暂缓。

## 文件与验证入口

- 第六批编写：`scripts/build_lower_gap_candidates_batch6.py`（拒绝覆盖不同内容）；导出：`scripts/review_lower_gap_candidates_batch6.py --output <新目录>`。
- 页面图像：`learning_data/verification/lower-gap-candidates-batch6-20261114/page-images/`（二下 p2/3/5/7）。
- 定向检查：`tests/test_lower_gap_candidates_batch6.py`。
- 测试环境：`learning_data/verification/a03-portable-tests-20261107T091348Z/venv/bin/python`。
- 结果：`learning_data/verification/lower-gap-candidates-batch6-20261114/test-results.json`、`regression.xml`、`review-layout.json`。

## 下一批默认工作

1. 二下道法第 2、3、4 单元共 4 题。
2. 七下道法第 2、3、4 单元共 3 题。
3. 七下历史第 2、3 单元与第 4 单元 2 条共 4 题。
4. 每个范围仍先展开知识点再出候选；补第二个直接族必须产生不同且完整的有效动作。

## 保全与禁止事项

继续保留全部既有改动和使用数据；不导入生产、不迁移或部署、不提交推送、不启动/重启/调用C01、不调用外部模型/OCR/embedding，不恢复真实手机验收，不以真实档案制造测试记录。
