# 会话续办：下册首批候选与入口文档同步

2026-11-13（下午第二轮），`/home/deniskorfei/projects/open-webui`。本文件续接[上册候选交接](HANDOFF-SESSION-2026-11-13-QUESTION-QUALITY.md)，记录本轮两项工作：把上一批本地结果写进入口文档，然后按下册清单首批范围编制候选。旧交接与发布清单完整保留。

## 本轮已完成

1. **入口文档同步**：`docs/README.md`、`docs/releases/current-state.md`、`docs/plans/RESUME-NEXT-WORK.txt` 已写入 11-13 下午的上册20项候选与下册初步清单结果。此前三份文档仍停在当天上午的主站交接。
2. **下册首批候选**：为三个起始范围各一处有界要求编制原创候选，**7 题、28 个作答项**，逐题复核完成。
   - 二下数学第 1 单元（有余数的除法）：2 题，分别覆盖“余数的意义与约束”“余数在情境中的处理”，均为直接族。
   - 七下英语 Unit 1（Animal Friends）：3 题，覆盖动物信息与理由、名词复数与描述词、主旨与保护方法，均为直接族。
   - 七下生物第三单元第一章（被子植物的一生）：2 题；根尖与花为直接族，萌发条件与对照设计**只计辅助**并保留人工观察任务。
3. 审阅包 `learning_data/verification/lower-gap-candidates-20261113/review-v1/`；候选未注册、未安装；subject-v18 提案只在审阅包中，不改变本地 subject-v16 或线上 subject-v5。
4. 定向检查 8 项通过；与既有回归组同批共 99 项通过、0 失败 0 跳过，见 `learning_data/verification/lower-gap-candidates-20261113/test-results.json` 与 `regression.xml`。审阅页 1280×1000 / 390×900 布局检查无横向滚动、无越界（`review-layout.json`）。

详见[下册候选复核报告](../verification/LOWER-GAP-CANDIDATES-2026-11-13.md)。

## 当前边界

- 正式题数量仍沿用已验证发布证据：1145题（二年级418、七年级727），章节题1071；线上 schema14、subject-v5。未重新访问生产数据库，不能把本批证据说成生产重查。
- 本地章节题源仍 1074 题（含此前 3 道未安装数学纠错候选）；本批另存 7 道下册候选，未加入 `BATCHES`。
- 固定正式题ID套用本地 subject-v16 时为 112 configured / 288 partial / **265** gap（265 = 原258 + 本批新增的7条下册候选专属行）；假设本批7题存在时为 112 / 295 / 258。新增 configured 仍为 0。
- 二下教材无原生文字层，依据页由页面图像目视核对（第 11、12、15、19 页；PDF 17、18、21、25），未使用 OCR。七下英语与生物使用原生文字选段。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准；英语朗读/听力/自主表达与生物实验操作均未验收。
- 真实手机验收继续暂缓。

## 文件与验证入口

- 下册编写：`scripts/build_lower_gap_candidates.py`（拒绝覆盖不同内容）；导出：`scripts/review_lower_gap_candidates.py --output <新目录>`。现有 review-v1 不覆盖，后续修改须出新修订包。
- 定向检查：`tests/test_lower_gap_candidates.py`。
- 测试环境：`learning_data/verification/a03-portable-tests-20261107T091348Z/venv/bin/python`。
- 结果：`learning_data/verification/lower-gap-candidates-20261113/test-results.json`、`regression.xml`。

## 下一批默认工作

按实际学校进度优先；目前没有新的进度信息，暂按清单顺序：

1. 二下道法、七下道法、七下历史、七下地理的起始单元（各册首个 first_scope）。
2. 二下数学第 2–5 单元、七下英语 Unit 2、七下生物其余小节。
3. 七下数学第七章旧 `perpendicular` 定位错误（p3 实为对顶角例题，垂直定义在 p4、基本作图事实在 p5）与平移无直接映射项，需先复核再出候选。
4. 七下地理 p108 固碳图原生文字数字乱码，必须先目视核对完整图与单位才可出计算题；不得按文字层取数。

上册20项与下册首批7项均无需再次循环寻找已审同章题。如需为某个 partial 项补第二个直接族，必须产生不同且完整的有效动作，不能把同一动作拆族凑数。

## 保全与禁止事项

继续保留全部既有改动和使用数据；不导入生产、不迁移或部署、不提交推送、不启动/重启/调用C01、不调用外部模型/OCR/embedding，不恢复真实手机验收，不以真实档案制造测试记录。
