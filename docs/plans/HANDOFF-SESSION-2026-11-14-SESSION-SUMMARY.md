# 会话交接：下册本地候选四批（2026-11-13 → 2026-11-14）

本文件是一次**会话级总结**，不是新的发布记录。旧交接、发布清单与各批复核报告完整保留。新会话只需读本文件、`docs/releases/current-manifest.json` 和最近一批交接即可继续。

## 一、本会话完成了哪些任务

起点：项目在 2026-11-13 下午已完成上册 20 项缺口候选与下册 10 册 75 范围初步清单，尚未为下册出候选。本会话按用户指示连续完成四批**本地候选**（未注册、未安装、未部署）：

| 批次 | 时间 | 范围 | 题量/作答项 | 题型族 | 候选文件 sha256 | 定向检查 | 同批回归 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 第一批 | 11-13 傍晚 | 二下数学第1单元、七下英语 Unit 1、七下生物第三单元第一章 | 7 / 28 | 6 直接 + 1 辅助 | `5b2ec2c2…` | 8 项 | 99 项 |
| 第二批 | 11-13 夜间 | 二下道法第1单元、七下道法第1单元、七下历史第1单元、七下地理第七章 | 9 / 36 | 9 直接 | `f12a92c9…` | 8 项 | 107 项 |
| 第三批 | 11-13 深夜 | 七下数学 7.1.2 拆三项（p4/p5/p6）、二下数学第2—5单元 | 9 / 36 | 9 直接 | `588952de…` | 9 项 | 116 项 |
| 第四批 | 11-13 夜间 | 二下数学连环画、七下英语 Unit 2、七下生物第二至五章及栽培项目、七下地理第八章与 p108 固碳项目 | 9 / 36 | 9 直接 | `dbed31c7…` | 10 项 | 126 项 |

合计 **34 题 / 136 个作答项**，33 个直接族、1 个辅助族；34 条候选行全部只是本地候选。

各批证据包：

- `learning_data/verification/lower-gap-candidates-20261113/review-v1/`
- `learning_data/verification/lower-gap-candidates-batch2-20261113/review-v1/`
- `learning_data/verification/lower-gap-candidates-batch3-20261113/review-v1/`
- `learning_data/verification/lower-gap-candidates-batch4-20261113/review-v1/`

各批报告与交接：

- `docs/verification/LOWER-GAP-CANDIDATES-2026-11-13.md`
- `docs/verification/LOWER-GAP-CANDIDATES-BATCH2-2026-11-13.md`
- `docs/verification/LOWER-GAP-CANDIDATES-BATCH3-2026-11-13.md`
- `docs/verification/LOWER-GAP-CANDIDATES-BATCH4-2026-11-13.md`
- `docs/plans/HANDOFF-SESSION-2026-11-13-LOWER-CANDIDATES.md`
- `docs/plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH2.md`
- `docs/plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH3.md`
- `docs/plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH4.md`

本会话还同步更新了 `docs/README.md`、`docs/releases/current-state.md`、`docs/plans/RESUME-NEXT-WORK.txt` 的批次入口。

## 二、目前做到哪里

### 2.1 覆盖进度

下册初步清单共 **10 册 / 75 目录范围 / 68 条新初步要求**（`docs/quality/lower-knowledge-inventory-2026-11-13.json`，sha `de6cd6e5…`）：

- 已出候选：**31 条清单要求**（对应 34 条候选行，其中 3 条是七下数学 perpendicular 的 p4—p6 refine 行）。
- 尚可出候选：**27 条**（下表）。
- 仅作参照、不单独出题：**10 条**（英语附录 10—16 共 7 条，历史附录 1 条，地理附录 1 条，生物附录 1 条，`action` 为空）。

| 册 | 剩余可出候选 | 具体范围 |
| --- | ---: | --- |
| 七下英语 | 7 | Unit 3、4、5、6、7、8、Reading Plus |
| 七下生物 | 3 | 第四单元第六章（血液）、第七章（泌尿）、人体结构模型项目 |
| 七下地理 | 4 | 东南亚世界遗产跨学科项目、第九章西亚、第十章美国、第十一章极地 |
| 二下道法 | 4 | 第2单元 2 条、第3单元、第4单元 |
| 七下道法 | 3 | 第2、3、4单元 |
| 七下历史 | 4 | 第2、3单元、第4单元 2 条 |
| 二下数学 | 2 | activity1 的 2 条 |

### 2.2 当前边界（未变）

- 正式题仍 **1145 题**（二年级 418、七年级 727），章节题 1071，schema14；线上 coverage 仍 subject-v5。**未访问生产数据库**。
- 本地章节题源仍 **1074 题**；本地 base 仍 math-v15 / subject-v16。
- 四批候选均**未加入 `BATCHES`**、未安装、未导入；subject-v18/v19/v20/v21 提案只在各自审阅包内。
- 固定正式题 ID 套本地 subject-v16：112 configured / 288 partial / 258 gap；每批加入 9 条候选专属行后为 267 gap，假设候选存在时为 112 / 297 / 258。**新增 configured 均为 0**。
- 最后一批验证：定向 10 项通过；11 模块回归 **126 项通过、0 失败 0 跳过**（362.18 秒）；审阅页 1280×1000 / 390×900 无横向滚动；合成安装 1145 → 1154、重复安装新增 0、`provider_calls=0`。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准；听写、朗读、作图、实验、模型制作、真实交流等人工任务均**未观察**。
- HEAD 仍 `60e8498a18926c9fcc7f5eda810c8606876be249`；工作树约 259 条改动；**未提交、未推送**。
- 真实手机验收继续暂缓；C01 四容器保持停止，未启动、重启或调用。

### 2.3 本会话内容复核中修掉的主要问题

- 第二批：题干泄露答案 3 处（“81°N”、与正确选项同名的“寻求帮助”、人数不符）。
- 第三批：题干泄露/重复 5 处；445+298 的 633/733 进位错因归属 1 处。
- 第四批：光合作用干扰项“植物会消耗氧气”本身生理成立，改为“密闭玻璃罩里根本没有氧气”。
- 第三批七下数学：旧 `perpendicular` 行 `printed_page=3` 保留未改，新增 p4/p5/p6 三条 refine 行；不重写历史记录。
- 第四批七下地理：p108 图 1 文字层数字乱码，按原页目视核对后出题，题内注明图 1、原页 108、万公顷/亿吨与“不代表当前实时统计”。

## 三、还有哪些没做

### 3.1 下册清单剩余

见 2.1 的 27 条可出候选 + 10 条仅参照。**第五批尚未开始**：本会话只抽取并阅读了相关原页文字，没有编写 `build_lower_gap_candidates_batch5.py`、没有生成候选文件、没有审阅包。

### 3.2 项目层面沿用历次交接的暂缓项

- 教师逐题签署、课程标准交叉审核、学生真实难度校准。
- 人工任务的实际观察与记录：栽培、模型制作、朗读/听辨、真实交流、地图绘制、实验操作等。
- B02 的 1/3/7 天观察、B04-P013-D01 图形题、B07 独立备份、B08 外部监控、C01 教学复核签署、真实手机验收。
- 主站 P1/P2/P3 优化建议尚未实施。
- 工作树改动未提交、未推送（按既定边界保留）。

## 四、下一步该做什么

### 推荐第五批（9 题，沿用同一流程）

1. 七下生物第四单元第六章：血液组成与红细胞运输氧（p103、104、106）。
2. 七下生物第四单元第七章：泌尿系统与尿的形成（p124、125、127）。
3. 七下生物人体结构模型项目：结构—功能—验证方法对应（p130、131）。
4. 七下地理东南亚世界遗产项目：分类表、图例与时间口径（p55、56）。
5. 七下地理第九章：西亚“三洲五海”、里海是湖泊、土耳其海峡与苏伊士运河（p58、59）。
6. 七下地理第十章：美国地形与农业地区专门化，不由单一条件推全部分布（p90、92、93、94）。
7. 七下地理第十一章：南北极海陆、气温降水、生物比较（p110、111、112）。
8. 七下英语 Unit 3：how often 与名词性物主代词（p17、21）。
9. 七下英语 Unit 4：可数与不可数名词、饮食偏好（p25、29）。

上述页文本会话已抽取阅读，但**未落盘为证据**；新会话需重新按 `learning_scope` 映射提取，原生文字层书目走 `local_original_PDF_native_text_no_OCR`。

之后建议拆分：

- 第六批：七下英语 Unit 5—8 + Reading Plus（5 题）、二下数学 activity1（2 题）。
- 第七批：二下道法 4 题、七下道法 3 题。
- 第八批：七下历史 4 题，并补第一批缺少的题目级人工任务（见下）。

### 一个待处理的差异

批次 1 的 7 题中只有辅助题带 `manual_followup`，其余 6 题的人工任务记录在 coverage proposal 行内；批次 2—4 则每题都带。没有改写历史文件。若后续统一口径，建议**新增**说明或在下一次修订时补齐，不要重写第一批文件。

### 每批固定流程

1. 先对照清单展开知识点与原页（二下数学无文字层时用页面图像目视核对）。
2. 编写 `scripts/build_lower_gap_candidates_batchN.py`；拒绝覆盖不同内容；候选不得加入 `BATCHES`。
3. 编写 `scripts/review_lower_gap_candidates_batchN.py` 导出审阅包（index、coverage-diff、source-evidence、manual-tasks、summary、provenance、subject-vNN 提案）。
4. 编写 `tests/test_lower_gap_candidates_batchN.py`：可复现未注册、独立复算、答案不泄露、字段边界、证据分离、合成安装幂等。
5. 跑定向检查、两视口布局检查、同批回归（含全部既有模块）。
6. 写复核报告与交接，并同步 `docs/README.md`、`docs/releases/current-state.md`、`docs/plans/RESUME-NEXT-WORK.txt`。

## 五、新会话继续任务的命令（Claude Code）

```bash
cd ~/projects/open-webui && claude
```

进入后粘贴：

```text
请完整阅读 docs/plans/HANDOFF-SESSION-2026-11-14-SESSION-SUMMARY.md、docs/plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH4.md 和 docs/releases/current-manifest.json。
按总结第四节继续下册本地候选：先做第五批9题（七下生物第六章、第七章、人体结构模型项目；七下地理东南亚世界遗产项目、第九章西亚、第十章美国、第十一章极地；七下英语Unit 3、Unit 4），再做第六批及以后。
每批先展开知识点并按原页核对，再编写 build/review/test，候选不得加入BATCHES；跑定向测试、两视口布局检查和同批回归；写复核报告与交接并同步入口文档。
保留全部既有改动和使用数据；不提交推送；不导入生产；不迁移部署；不启动、重启或调用C01；不调用外部模型/OCR/embedding；真实手机验收继续暂缓。
```

若团队其他成员使用 Codex，可把同一段提示词改为：
`codex -C /home/deniskorfei/projects/open-webui '<上述提示词>'`。

## 六、保全与禁止事项

继续保留全部既有改动和使用数据；不导入生产、不迁移或部署、不提交推送、不启动/重启/调用 C01、不调用外部模型/OCR/embedding，不恢复真实手机验收，不以真实档案制造测试记录。历史候选文件、审阅包与旧“当前/下一步”记录一律保留，新记录只追加。

## 七、关键文件索引

- 清单：`docs/quality/lower-knowledge-inventory-2026-11-13.json`
- 候选：`learning_service/data/family_chapter_lower_gap_candidates_v1.json`、`…_batch2_v1.json`、`…_batch3_v1.json`、`…_batch4_v1.json`
- 最近测试结果：`learning_data/verification/lower-gap-candidates-batch4-20261113/test-results.json`、`regression.xml`、`review-layout.json`
- 最近提案：`learning_data/verification/lower-gap-candidates-batch4-20261113/review-v1/subject-v21-proposal.json`
- 发布清单：`docs/releases/current-manifest.json`
- 入口：`docs/README.md`、`docs/plans/RESUME-NEXT-WORK.txt`、`docs/releases/current-state.md`
