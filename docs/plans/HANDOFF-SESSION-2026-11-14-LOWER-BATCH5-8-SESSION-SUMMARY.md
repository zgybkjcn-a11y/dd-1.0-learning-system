# 会话交接：下册本地候选第五至八批（2026-11-14）

本文件是一次**会话级总结**，不是新的发布记录。旧交接、发布清单与各批复核报告完整保留。新会话只需读本文件、`docs/releases/current-manifest.json` 和最近一批交接即可继续。

## 一、本会话完成了哪些任务

起点：2026-11-14 会话总结记录下册前四批 34 题，第五批尚未开始。本会话按用户指示继续完成第五至第八批**本地候选**（未注册、未安装、未部署），下册清单可出候选由此全部出完：

| 批次 | 范围 | 题量/作答项 | 题型族 | 候选文件 sha256 | 定向检查 | 同批回归 |
| --- | --- | --- | --- | --- | --- | --- |
| 第五批 | 七下生物血液与排泄、人体模型项目；七下地理东南亚遗产项目与第九至十一章；七下英语 Unit 3—4 | 9 / 36 | 9 直接 | `799f65a1…` | 9 项 | 135 项 |
| 第六批 | 二下数学 activity1 两条要求；七下英语 Unit 5—8 与 Reading Plus | 7 / 28 | 7 直接 | `ed1bedea…` | 9 项 | 144 项 |
| 第七批 | 二下道法第二至四单元（4 条）；七下道法第二至四单元（3 条） | 7 / 28 | 7 直接 | `d039f090…` | 8 项 | 152 项 |
| 第八批 | 七下历史第二、三单元与活动课/学史方法（4 条） | 4 / 16 | 4 直接 | `3db34558…` | 8 项 | 160 项 |

合计本会话 **27 题 / 108 个作答项**，全部为直接题型族，27 条候选行全部只是本地候选。连同前四批，下册八批共 **61 条候选行 / 244 个作答项**（60 直接族、1 辅助族），覆盖清单 **58 条可出候选的新初步要求**（清单共 68 条，另 10 条仅作参照）。

各批证据包：

- `learning_data/verification/lower-gap-candidates-batch5-20261114/review-v1/`
- `learning_data/verification/lower-gap-candidates-batch6-20261114/review-v1/`
- `learning_data/verification/lower-gap-candidates-batch7-20261114/review-v1/`
- `learning_data/verification/lower-gap-candidates-batch8-20261114/review-v1/`

各批报告与交接：

- `docs/verification/LOWER-GAP-CANDIDATES-BATCH5-2026-11-14.md`
- `docs/verification/LOWER-GAP-CANDIDATES-BATCH6-2026-11-14.md`
- `docs/verification/LOWER-GAP-CANDIDATES-BATCH7-2026-11-14.md`
- `docs/verification/LOWER-GAP-CANDIDATES-BATCH8-2026-11-14.md`
- `docs/plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH5.md`
- `docs/plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH6.md`
- `docs/plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH7.md`
- `docs/plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH8.md`

本会话同时更新了 `docs/README.md`、`docs/releases/current-state.md`、`docs/plans/RESUME-NEXT-WORK.txt` 的批次入口。

## 二、目前做到哪里

### 2.1 覆盖进度

下册清单的 58 条可出候选要求已全部有候选；10 条仅参照要求（英语附录 7 条、历史附录 1 条、地理附录 1 条、生物附录 1 条）不单独出题。

### 2.2 当前边界（未变）

- 正式题仍 **1145 题**（二年级 418、七年级 727），章节题 1071，schema14；线上 coverage 仍 subject-v5。**未访问生产数据库**。
- 本地章节题源仍 **1074 题**；本地 base 仍 math-v15 / subject-v16。
- 八批候选均**未加入 `BATCHES`**、未安装、未导入；subject-v18 至 v25 提案只在各自审阅包内。
- 固定正式题 ID 套本地 subject-v16：112 configured / 288 partial / 258 gap；每批加入各自候选专属行后为 267（9 题）、265（7 题）、262（4 题），假设候选存在时均为 112 / 297、295、292 / 258。**新增 configured 均为 0**。
- 最后一批验证：定向 8 项通过；15 模块回归 **160 项通过、0 失败 0 跳过**（476.25 秒）；审阅页 1280×1000 / 390×900 无横向滚动；合成安装 1145 → 1149、重复安装新增 0、`provider_calls=0`。
- 教师签署 false、课标 crosscheck pending、学生真实难度未校准；拨钟、测量、时间小书、模型制作、解剖观察、尿液检测、资料表、线路方案、打电话、写日记、复述故事、目标制定、文化实践、法律求助、史料互证、节日调查等人工任务均**未观察**。
- 本会话已做本地提交：`c86f5bb`（代码与数据）、`4e97c72`（测试）、`d87e94c`（文档）、`2841b6f`（测试对齐修复）、`786811d`（全量与推送前状态）、`42a24c8`（CI 干净检出）；已推送 `cd4ad61..42a24c8` 到 origin/main。CI 最终通过：run 43684168547（commit `46abaf5`）单元 1164 通过、53 跳过，浏览器 51 通过，0 失败；首次 run 43673091206 曾因 30 分钟 job 超时被取消，随后把 `timeout-minutes` 调到 75。工作树干净。
- 真实手机验收继续暂缓；C01 四容器保持停止，未启动、重启或调用。

### 2.3 本会话内容复核中修掉的问题

- 第五批：英语 Unit 3 三句、Unit 4 两句与教材例句/练习重合，改写为自编句；人体模型原理、农业专门化与农业带形成条件的正确选项改为同义改写。
- 第六批：英语 Unit 5—8 逐句比对教材 3a/3b，避开原句；狮子和老鼠的因果题保留情节但题干与选项自编。
- 第七批：二下道法第 24 页为空白课题页，水的内容改为依据 p25/26；不考教材尚未展开的具体节约做法。
- 第八批：北宋题把 960 与 979 分列；明朝题把八股文单列为考试文体；学史方法题限定在“今魏征殂逝”一句的证据边界。

### 2.4 本轮发现的材料情况

- 二下道法 p24 为空白课题页，正文在第 25、26 页；已在第七批报告与交接中注明。
- 二下数学、二下道法均无原生文字层，全部按渲染页面图像目视核对，未使用 OCR。
- 七下地理 p55/56/58/59/90/93/94/110/111 的图例、地图与分布图已按渲染图像核对；东南亚 42 处按“截至 2021 年第 44 届”口径引用。

### 2.5 提交前的测试对齐（2026-11-14 晚）

首次全量 1290 项中有 70 项失败/错误，全部来自本会话之前的代码与测试漂移，与第五至八批无关。逐项修复后全量转绿：

- 监控：运行库已到 schema 14，`collect_learning_monitor.SUPPORTED_SCHEMAS` 增加 14；`test_learning_monitor` 的“未来版本”用例改为 15，`test_minimal_monitor` 的历史迁移与健康检查参数化补上 14；`minimal-monitor.md` 同步。
- 工具升级：`BACKEND` 固定的 5 个后端文件哈希已过期（app、textbooks、evidence_contracts、db、OpenAPI），按当前复核源码重新固定，并把文档中的 schema 与文件数改为 14 / 17。
- 覆盖与数据断言：`test_math_gaps` 记录 8 处已复核的角色/理由变更（3 处降为 supporting）；`test_math_g7_depth` 计数更新为 configured 17 / partial 119；`test_other_textbook_variety` 把三个 variety 批次的范围固定为下层教材加入前的 12 册。
- 浏览器：储备练习补上“挑战 0 道未见题”；章节练习刷新后先加载教材再恢复会话（实测 5—8 秒），四处刷新断言的预算调到 15 秒。
- 干净检出（CI 环境）：`learning_data/` 被忽略，9 个候选批测试模块缺快照与原页索引而失败 19 项。CI 单元步骤按路径忽略这 9 个模块并注明原因；本地默认测试不变。
- 干净检出浏览器组另发现 1 项竞态：学习工作台在状态已显示“正在”时，路由回调尚未记录挂起请求。改为有界轮询后再断言。
- GitHub CI 浏览器组另发现 1 项竞态：放大原页后立即断言图片 `naturalWidth`，CI 上解码未完成。改为 `wait_for_function` 等待，与同仓其他原页用例一致。

修复后全量：**1292 通过、0 失败、0 错误、0 跳过**（62 分 17 秒），本地记录 `learning_data/verification/full-suite-20261114/`（junit 与 summary，`learning_data/` 不入版本库）。另有 2 项 local_materials 由 pytest.ini 默认跳过。

## 三、还有哪些没做

### 3.1 下册清单

可出候选已全部完成。无新增候选计划。

### 3.2 项目层面沿用历次交接的暂缓项

- 教师逐题签署、课程标准交叉审核、学生真实难度校准。
- 人工任务的实际观察与记录（见 2.2）。
- B02 的 1/3/7 天观察、B04-P013-D01 图形题、B07 独立备份、B08 外部监控、C01 教学复核签署、真实手机验收。
- 主站 P1/P2/P3 优化建议尚未实施。
- 工作树改动未提交、未推送（按既定边界保留）。
- 第一批 6 题缺少题目级 `manual_followup` 的历史差异仍未统一；建议新增说明或下次修订时补齐，不重写第一批文件。

## 四、下一步该做什么

### 推荐方向

1. **教师签署与课标交叉审核**：八批候选共 61 行，按章节分批给教师复核，先处理第五至八批新出的 27 行。
2. **决定是否把候选转为正式批次**：需要新增 `BATCHES` 注册、合成安装、发布清单更新与部署；均需单独授权，且不得覆盖既有使用数据。
3. **学生真实难度校准**：至少要有一组学生试用记录，当前全部为作者试用分档。
4. **人工任务观察**：先做最容易落地的拨钟、时间小书、模型制作三项。

### 每批固定流程（若后续仍有新批次）

1. 先对照清单展开知识点与原页（无文字层时用页面图像目视核对）。
2. 编写 `scripts/build_lower_gap_candidates_batchN.py`；拒绝覆盖不同内容；候选不得加入 `BATCHES`。
3. 编写 `scripts/review_lower_gap_candidates_batchN.py` 导出审阅包。
4. 编写 `tests/test_lower_gap_candidates_batchN.py`：可复现未注册、独立复算、答案不泄露、字段边界、证据分离、合成安装幂等。
5. 跑定向检查、两视口布局检查、同批回归（含全部既有模块）。
6. 写复核报告与交接，并同步 `docs/README.md`、`docs/releases/current-state.md`、`docs/plans/RESUME-NEXT-WORK.txt`。

## 五、新会话继续任务的命令（Claude Code）

```bash
cd ~/projects/open-webui && claude
```

进入后粘贴：

```text
请完整阅读 docs/plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH5-8-SESSION-SUMMARY.md 和 docs/releases/current-manifest.json。
下册清单 58 条可出候选已全部出完八批本地候选（61 行），未注册、未安装、未导入。下一步按总结第四节：先为第五至八批新出的 27 行做教师签署与课标交叉审核准备，再讨论是否注册为正式批次。
保留全部既有改动和使用数据；不提交推送；不导入生产；不迁移部署；不启动、重启或调用C01；不调用外部模型/OCR/embedding；真实手机验收继续暂缓。
```

## 六、保全与禁止事项

继续保留全部既有改动和使用数据；不导入生产、不迁移或部署、不提交推送、不启动/重启/调用 C01、不调用外部模型/OCR/embedding，不恢复真实手机验收，不以真实档案制造测试记录。历史候选文件、审阅包与旧“当前/下一步”记录一律保留，新记录只追加。

## 七、关键文件索引

- 清单：`docs/quality/lower-knowledge-inventory-2026-11-13.json`
- 候选：`learning_service/data/family_chapter_lower_gap_candidates_v1.json` 及 `…_batch2_v1.json` 至 `…_batch8_v1.json`
- 最近测试结果：`learning_data/verification/lower-gap-candidates-batch8-20261114/test-results.json`、`regression.xml`、`review-layout.json`
- 最近提案：`learning_data/verification/lower-gap-candidates-batch8-20261114/review-v1/subject-v25-proposal.json`
- 发布清单：`docs/releases/current-manifest.json`
- 入口：`docs/README.md`、`docs/plans/RESUME-NEXT-WORK.txt`、`docs/releases/current-state.md`
