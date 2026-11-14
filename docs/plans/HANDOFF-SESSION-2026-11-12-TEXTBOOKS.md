# 家庭学习：全学科补题、挑战题与教材阅读交接

2026-11-13接续入口已汇总到[教材补齐、题库质量与主站优化交接](HANDOFF-SESSION-2026-11-13-MAIN-SITE.md)，包含20册/1145题现状、20项明确缺口、主站优化建议与新命令。请按新交接第7节继续；以下保留各批次历史，本页旧命令不作为最新执行顺序。

2026-11-12最新：按用户“将缺少的教材补齐”已上线新增7册原页阅读，当前二年级6册、七年级14册，共20册/152目录范围；新增二下数学、道法及七下英语、道法、历史、地理、生物。831个新增PDF原页全部渲染通过；66项教材/接口发布检查、99项片段兼容检查（模块有重叠）、390/1280两视口2项浏览器通过。50张表3383条既有行逐行哈希相同，1145题（418/727）和schema14保持；原13份PDF哈希相同。新7册仅原页阅读，无正式配题、无关键词索引，未用未审核OCR。线上覆盖仍subject-v5，本地math-v15/subject-v16及三道数学候选未发布。Compose learning_data/deployments/family-textbook-completion-20261112/compose.json；API/worker/gateway镜像sha256:6014a23756647d72fea8afaa074fc05b4fab7cff6e804d570bc34cc23e21c6f6。C01四容器保持停止，无模型/OCR/embedding调用、不提交推送，真实手机验收继续暂缓。验收 docs/verification/TEXTBOOK-COMPLETION-2026-11-12.md。教材补齐请求已完成；题库质量接续仍为第5节已审明的上册20项缺口本地候选，再下册；新7册不得冒称题库或知识点覆盖完整。

以下为本次补齐前的历史记录；旧13册/98范围以及旧当前发布身份按当时口径保留，以本文顶部和current-manifest.json为准。

2026-11-12续批最新状态：数学清单math-v15，全学科本地候选subject-v16；当前审阅包为`learning_data/verification/upper-subject-review-20261112/review-v17/`，详见[上册语文英语与科目缺口复核](../verification/UPPER-SUBJECT-KNOWLEDGE-REVIEW-2026-11-12.md)。正式题ID快照仍为二年级418、七年级727，线上仍是subject-v5、1145题/schema14。此前数学六章与二上两个活动范围、七上语文和英语已完成本轮映射审阅；数学review-v15保留生成时的math-v15/subject-v14，科目review-v16保留subject-v15。本批继续逐项审阅道法、七上史地生剩余27项要求范围的131道正式题，修订16条映射（5条辅助升直接、4条新增直接、7条新增辅助），7项要求首次获得直接题型证据。subject-v16汇总为112 configured、288 partial、258 gap，308项human、350项bounded属性不变；同核心动作不拆题型族，configured数量未增加。目标范围仍有5项无映射、15项只有辅助题，全部已审并记录缺口原因，见review-v17的`candidate-review-decisions.json`。本地三道数学纠错候选仍未导入；章节题源1074道，正式题量不变。六模块定向回归83 passed，1145道正式题内容逐项相同。未导入、迁移、部署、重启服务/C01或调用模型/OCR/embedding，使用数据未动；真实手机验收继续暂缓，不提交或推送。下一步先为这20项明确缺口准备本地候选并复核，再按原顺序处理下册，不重复审同章候选。

本交接后文中更早写成math-v8/subject-v7及其他历史口径的续批摘要按其记录时点保留，不代表当前候选状态。

以下后续正文保留subject-v4/v5等批次的交接历史；当前本地候选以本文顶部和第5.1节为准，当前部署仍以发布清单为准。

最新续批（2026-11-12）：按第5节继续完成语文/英语缺口批次，新增14题覆盖二上语文、七上语文、七上英语的13个教材范围，全学科映射升级subject-v5。正式1145题（二年级418、七年级727）、1071道章节题、schema14；覆盖编辑状态为93 configured、294 partial、271 gap，人工要求308、bounded要求350。数学v6统计口径未变；这些状态不代表课标完整率或学生掌握率。部署、测试、备份和行保全见[题库质量验收](../verification/KNOWLEDGE-QUALITY-2026-11-12.md)及[本批验收](../verification/SUBJECT-GAPS-2026-11-12.md)。当前部署以[current-manifest.json](../releases/current-manifest.json)为准。下一步继续审数学单一解题动作，再史地生、道德与法治及下册；真人签署、课标交叉核对、真实难度校准仍待完成。真实手机验收继续暂缓，C01四容器保持停止；不提交或推送。

最新续批（2026-11-12）：第5节数学质量主线已执行两批。当前subject-v4新增10题覆盖5项bounded缺口，正式1131题/schema14；全部部署、测试、备份与行保全证据见[题库质量验收](../verification/KNOWLEDGE-QUALITY-2026-11-12.md)及RESUME-NEXT-WORK.txt顶部。下一步按原优先序审二上/七上语文和七上英语，再其他学科；数学单一解题动作继续审。当前部署以current-manifest.json为准。以下为此前交接历史。

整理时间：2026-11-12，Asia/Shanghai。工作目录 `/home/deniskorfei/projects/open-webui`。用户本轮要求总结、写交接并提供新会话命令；本轮只做只读核对与交接整理，没有继续补题、修改运行功能、重新部署或调用外部模型。

## 1. 新会话先知道的结论

- 用户主线是**所有已接入教材分批补题并升级质量**：先二年级、七年级数学，再当前在学上册（含语文、英语等），再其余空白。此前“继续”授权沿此主线执行，不必再次询问覆盖哪部分。
- 已上线13册、7学科、98个章节/活动/附录目录范围的起步题与后续题型升级，正式共 **1121题**（二年级410、七年级711）。有题、题型升级已完成一轮；**整章知识点穷尽、教师复核、真实难度校准未完成**。
- 四档难度已上线：简单、正常、困难、挑战。最新98道挑战题每目录范围一道，支持多选、排序、数值、单选、限定短答组合。
- 最新用户的教材界面要求已完成并上线：三角与标题首行对齐；图片上层左右悬浮上一页/下一页；放大窗口也可悬浮翻页且保留缩放；跨章连续阅读；目录跟随实际页码高亮、内部滚动，桌面目录随阅读区停留。
- 当前没有未完成的已提出阅读器修复。下一步建议回到**知识点和题目质量缺口**，不要再从“首次批量补空白”重做。
- 真实家庭手机验收按用户指令暂缓；C01模型验收已结束，4个隔离容器保持停止。不自动恢复模型、不扩展到OCR或学生资料外发。

本交接优先于旧交接中“下一步Bxx”“尚未部署”“恢复模型”等历史描述。当前发布身份以 [current-manifest.json](../releases/current-manifest.json) 的 `latest_deployment`、本交接及最新证据为准，不用Git HEAD代表线上版本。

## 2. 本会话任务与完成位置

| 用户任务 | 已做工作 | 当前状态 / 证据 |
| --- | --- | --- |
| 所有教材分批补空白 | 首批新增414章节题，覆盖13册98目录范围，按数学→当前上册其他科→其余顺序完成 | 已上线；[章节补题](../verification/CHAPTER-PRACTICE-2026-11-09.md) |
| 数学整章知识点与题目对应 | 二上新增88题、七上新增136题；建立知识点/能力要求/直接题/辅助题/缺口表 | 已上线草案；[二上](../verification/MATH-KNOWLEDGE-G2-2026-11-09.md)、[七上](../verification/MATH-KNOWLEDGE-G7-2026-11-09.md)；完整覆盖未完成 |
| 二上数学太简单、单一 | 新增48道提高题，21道带图，35道旧题重新分档；随后新增16道分步题、48作答项 | 已上线；[提高题](../verification/MATH-G2-CHALLENGE-2026-11-10.md)、[分步题](../verification/MATH-G2-MULTISTEP-2026-11-10.md) |
| 数学以外学科也升级 | 其余12册90范围新增180题、453作答项、11道图表题；78道旧非数学题校正展示难度，自动难度避开空档 | 已上线；[全学科题型扩充](../verification/OTHER-TEXTBOOKS-VARIETY-2026-11-10.md) |
| 按知识点补题、丰富短答 | 新增67题、187作答项，含84限定短答与25条常见错答反馈；扩展到276点、658要求 | 已上线草案；[知识点与短答](../verification/SUBJECT-KNOWLEDGE-2026-11-10.md) |
| 增加“挑战”档并丰富题型 | 新增98挑战题、261作答项；多选、卡片排序及组合题；schema14、structured-fields-v3 | 已上线；[挑战档验收](../verification/CHALLENGE-TIER-2026-11-11.md)、[使用说明](../open-webui-reuse/challenge-tier.md) |
| 三角与当前页标题不同行 | 标题改为inline并清除上下margin，保留原生summary折叠 | 已上线；[标题修正](../verification/READER-SUMMARY-2026-11-11.md) |
| 图片左右翻页、目录跟随 | 整册连续翻页/跳页；当前阅读页独立于练习范围；目录高亮/内部滚动、桌面sticky | 已上线；[导航验收](../verification/READER-NAVIGATION-2026-11-11.md) |
| 放大也能翻页，按钮须在图片上层 | 普通区和放大窗口改悬浮按钮；放大翻页保持窗口与缩放；失败原地重试；顶部普通翻页隐藏，搜索匹配切换保留 | **最新线上版本**；[悬浮翻页验收](../verification/READER-OVERLAY-2026-11-11.md) |
| 题源与完整覆盖方法 | 当前实际采用固定教材主题定位、本地自编题与公版短引；建立知识清单及题型映射，区分人工任务 | 已落入内容与覆盖机制；未购买或抓取新商业题库，未证明课程标准/教材知识穷尽 |

新增章节题分批数量：414 + 88 + 136 + 48 + 16 + 180 + 67 + 98 = **1047**。加原60应用题和14起步题，共1121。**作答项不额外算题，改数/换故事不额外算题型。** 历史12道备用候选仍未安装。

## 3. 各科教材现在怎样

以下为章节题与原应用题，不含14起步题；全部已做题型升级，均有挑战题。

| 教材 | 题量 | 其中最新挑战题 |
| --- | ---: | ---: |
| 二年级数学上册 | 260 | 8 |
| 七年级数学上册 | 232 | 6 |
| 七年级数学下册 | 96 | 6 |
| 二年级语文上册 | 58 | 9 |
| 二年级语文下册 | 58 | 9 |
| 七年级语文上册 | 40 | 6 |
| 七年级语文下册 | 40 | 6 |
| 七年级英语上册 | 120 | 18 |
| 二年级道德与法治上册 | 26 | 4 |
| 七年级道德与法治上册 | 26 | 4 |
| 七年级历史上册 | 42 | 6 |
| 七年级地理上册 | 60 | 9 |
| 七年级生物上册 | 49 | 7 |

已接入列表没有二年级英语、二年级数学下册等，不要把离线OCR材料当成已接入的正式题库。目录/预览组件可能预留物理、化学标识，但本次正式教材与练习范围仍是以上7科13册。

题目内容、标准答案与解析审阅：

- [最新98题审阅页](../../learning_data/verification/challenge-tier-20261111/review/questions.html)。
- [67题短答与反馈审阅](../../learning_data/verification/subject-knowledge-20261110/review/questions.html)、[276点清单与人工任务](../../learning_data/verification/subject-knowledge-20261110/review/knowledge.html)。
- `learning_service/data/NOTICE.md`记录来源。页码是原创题对应的主题位置，不能写成“本题摘自教材第N页”。教师签署仍为false。

## 4. 还有哪些没做

### 4.1 主线未完成：覆盖质量

2026-11-12 09:07开始的只读核对历史口径：当时全学科清单276点、658项要求，按现有规则为 **84 configured、287 partial、287 gap**。configured只表示达到“两种已核对直接题型”的编辑目标，不是课程标准完整率、正确率或学生掌握率；当前本地subject-v16数字见第5.1节；math review-v15中的subject-v14是该数学快照生成时的历史口径。

其中233项明确标注需人工核对。旧二上/七上数学行没有统一填写`assessment_modes`，并不表示其中的口述、画图、实测要求可以自动评分。统计时必须继续分清直接、辅助、待映射、人工；不能用选择正确替代独立解释或实操。

早期subject-v2全学科清单口径下：

| 优先教材 | 配题目标达到 / 部分 / 无映射要求 | 说明 |
| --- | --- | --- |
| 二上数学 | 35 / 35 / 6 | 76项要求；本表是subject-v2口径，旧math-v6的35/33/8保留作历史，不能混算 |
| 七上数学 | 11 / 125 / 0 | 136项要求；没有无映射项仍可能只有辅助题或一种直接题型 |
| 二上语文 | 未显式标人工的20项：1 / 14 / 5 | 另22项明确人工 |
| 七上语文 | 未显式标人工的16项：3 / 9 / 4 | 另24项明确人工 |
| 七上英语 | 未显式标人工的35项：10 / 20 / 5 | 另39项明确人工 |

各册完整只读统计见 [read-only-state.json](../../learning_data/verification/session-handoff-20261112/read-only-state.json)。这些数字来自现有草案映射，不等同已穷尽教材；缺口应先审题/补映射，再确定确实需要的新题。

尚未完成：课程标准逐项交叉核对、教师内容签署、语言题多解边界终审、真实学生难度校准；自由作文、口述理由、真实听力/发音、自由作图、实际测量与实验的可靠评价。人工任务说明已显示，**尚无人工任务完成情况的持久化记录功能**。

### 4.2 独立待办与暂缓事项

- 真实家庭手机：`deferred_by_user`，390宽度Chromium只是模拟，不替代手机验收；不要反复催验。
- C01：历史24/24 + 补充3/3技术与助手评审通过；教师/家长真人教学签署pending。模型工作已结束、4容器exited，不能重置预算/删除STOP/自动续跑。
- B02真实1/3/7天无提示学习观察pending；12道备用候选未安装，不为了补数量直接导入。
- B04二下数学完整页：5页已处理，4页助手双步骤通过，1页图形待解`B04-P013-D01`；不等于教师审核或整册通过。
- B07独立故障域副本、保管责任、实际RPO/RTO未完成；本机私有备份不等于独立备份。
- B08外部观察端、阈值/权限/值守责任仍待落实；不发送外部通知。
- Git交付尚未整理提交/推送。开始交接时164个变更路径（37已跟踪改动、127未跟踪）；本次文档新增会改变数量。保留全部既有工作，禁止reset/clean覆盖。
- C02真实OCR、C03跨系统完整恢复、C05全栈/媒体再评估未自动启动。旧C04“小单元扩展”计划已被后续全学科补题主线推进，旧台账不是当前内容现状。

## 5. 下一步建议与执行顺序

### 5.1 2026-11-12续批状态

当前本地候选为math-v15/subject-v16，使用正式ID快照418/727生成review-v17。全学科112 configured、288 partial、258 gap；308 human、350 bounded。本批已审完道法、七上史地生此前13项无映射和14项仅辅助要求，同章正式题去重131道，16条映射修订、7项首次有直接题型证据。仍有5项无映射和15项仅辅助，缺口与逐题审阅记录见[科目复核](../verification/UPPER-SUBJECT-KNOWLEDGE-REVIEW-2026-11-12.md)。下一步为这20项完整要求准备本地候选，先核对题干、答案、解析与同题型去重，再按原优先序处理下册；不导入或部署。教师签署、课程标准交叉核对、真实学生难度校准和人工任务继续保留。以下数学段落是review-v15生成时的历史记录。

本轮按当前正式题ID快照逐项审阅七上数学第1至6章、二上数学第1至6章及两个活动范围。七上第2章涵盖有理数运算与进位制，第3章审阅代数式与规律，第4章审阅整式加减，第5章审阅一元一次方程，第6章审阅初步几何。该批材料在`learning_data/verification/math-single-action-20261112/review-v15/`；正式快照为二年级418题、七年级727题。当时数学清单为math-v15，全学科为subject-v14；该快照不代表当前subject-v16候选。

以下编号建议保留为早期subject-v5阶段的历史执行顺序；第2、3章已经按其方法审完，当前接续以本节上方和文档顶部为准。

两道已安装题此前被过度标为“辨析”：`5−(−3)=8`只检验计算，`(−1)×(−2)×(−3)=−6`只检验三个非零负因子的乘积。候选清单已将它们移到对应的计算要求，并保留为辨析的辅助题；另编两道本地候选纠错题，分别检查减去负数和负因子奇偶/零因子。两道新题不在正式题ID快照，当前覆盖统计不计入。

数学review-v15中的subject-v14历史汇总为112 configured、275 partial、271 gap；308项人工要求、350项bounded要求。数学专用清单math-v15为65 configured、140 partial、7 gap。此前交接写的107/281/270与review-v11逐项JSON汇总不符，正确历史汇总是107/280/271；本轮审阅已重新计算。七上第4章subject口径16项中6项configured、10项partial；第5章16项中3项configured、13项partial（9 bounded、7 human）；第6章32项中5项configured、27项partial（20 bounded、12 human）。第4章将只计算整式差的题从“检查减去整个式”的直接辨析降为辅助，并映射到整式加减应用；另编一道漏变常数项符号的本地候选题，正式统计仍不计。第5章独立建模和解释步骤仍为人工任务。第6章将只读角度或表示单条射线的题降为辅助，并补足平面/立体辨析的直接映射。二上数学六章和活动范围已审，跨清单角色比对后，五项有界识别题在math清单提升为直接；13道未测量/未比较两个人身体尺的题降为辅助。人工要求和学科要求仍按原状态统计。配题目标只表示编辑映射状态，不是课程标准完整率或学习掌握率。

第2章已将两道误标为辨析的已安装计算题降为辅助，并分别归入准确的计算动作；两道本地纠错候选不计为正式覆盖。第3章未发现可安全追加的现成直接映射；整体代入的数值替换属于同一题型族，反例辨析按单一核心动作统计，图形/表格推导题继续作为辅助，人工表达任务不由自动题替代。第4章对已安装题作了两处精确映射修订，并新增一道本地纠错候选。第5章逐题核验后未改映射；独立列方程、解释推理步骤等要求仍为人工核验。第6章校正自动题角色，并补足平面/立体辨析的现成直接映射。二上数学六章和活动范围逐题复核，没有新增题；跨清单角色差异已按题目动作修正，身体尺测量仍须人工观察。七上数学和二上数学审阅沿用正式快照418/727道题。该数学批之后已复核七上语文、英语及道法、史地生；当前接续工作见本节首段。候选题继续保留教师签署、课程标准交叉核对和真实学生难度校准状态，不导入或部署。

## 6. 当前运行与回退身份

以下2026-11-12快照是subject-v4数学部署后的状态；最新subject-v5语文/英语续批已更新API和worker。当前compose、镜像、题量与健康状态以本节续批更新和[current-manifest.json](../releases/current-manifest.json)顶部为准，表格中的math-v4发布身份保留为上一个已部署版本记录。

2026-11-12只读核对5服务均running，API与WebUI有healthcheck且healthy，其余3服务无healthcheck；1121题、1047章节题、schema14；4个C01隔离容器均exited。没有切换真实学习者或制造生产作答。

| 对象 | 当前值 |
| --- | --- |
| 入口 | `https://172.19.116.53/`，由主站进入家庭学习 |
| 家庭Compose | `learning_data/deployments/family-reader-overlay-20261111/compose.json` |
| API / worker镜像 | `sha256:e9b9237c22212f03f0eceaac97960f037b93cbd8c5bddbdbf8ce9b69e0b88bd9` |
| gateway镜像 | `sha256:1aa1a09316e8d9d944a0b97ce3ed994668319c618f2d36c096d9ebacea641138`，继续B11版 |
| WebUI | 0.12.5，镜像`sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd` |
| Tool | 历史最近已部署1.2.1，本轮未重新读正式Tool源码；阅读器升级未改Tool |
| 源码封包 | `learning_data/releases/reader-overlay-20261111-final/` |
| profile / 文件数 | `reuse-runtime-challenge-tier-v8`；128源码文件、API/worker各84运行文件匹配 |
| source set | `b8647a939ba9e723c78704c41aff50ecac1cbdfc6ca0d9d47e2ceab0282798d4` |
| archive SHA256 | `c5f8eb9426828d2c0a11964fca190879011d59e290713999753a041d47ed4feb` |
| 数据 | Docker卷`dd-family-math_data`，容器内`/var/lib/dd-learning/learning.db` |
| 最近可相容UI回退镜像 | `sha256:8f59022e3ea8907a11f7a583269046c7812480b05ac811979818b510b58617f5`（同1121题/schema14，仅先前普通翻页UI） |

不要把旧B11/schema13或更早镜像直接指向当前schema14，不要用旧备份覆盖上线后的新记录。最近阅读器更新没有题库导入或迁移；内容变化需要重新处理schema/协议/题号兼容。

本次交接发现`components.family_service.source.schema_revision`沿袭历史13，而当前封包、最新部署、数据库均为14；已仅校正**当前清单元数据**为14，历史部署记录保留。这不是新迁移或新发布。

## 7. 代码与验证入口

- 阅读器：[learning_service/app.py](../../learning_service/app.py)，CSS/HTML在`_UI_HTML`，JS重点`releaseTextbookPages`、`renderTextbookPage`、`openTextbookZoom`、`updateTextbookZoom`、`positionTextbookZoomButtons`、`syncReaderToc`、`syncReaderPageButtons`、`turnReaderPage`、`loadTextbookResults`。阅读页状态独立于`gameChapter`；切页不能自动调用`selectLearningScope`以免丢练习。
- 题库批次/哈希：[chapter_practice.py](../../learning_service/chapter_practice.py)；协议/判分`practice_response.py`；展示/题型`practice_design.py`；难度/轮次`practice.py`；持久化/草稿UI`study_ui.py`。
- 知识覆盖：本地`subject_coverage.py` + `data/family_subject_coverage_plan_v16.json`，线上仍subject-v5；本地数学`practice_coverage.py` + `data/family_math_coverage_plan_v15.json`，历史math-v6和subject-v2原样保留。数据文件有固定哈希，不能只改JSON而不更新依赖和相应验证。
- 内容生成：`scripts/build_chapter_practice_*.py`、`build_math_*.py`、`build_subject_knowledge_tasks.py`、`build_challenge_variety.py`等；这些生成脚本会改文件，不要为“查看现状”重跑。导入工具`import_chapter_practice.py`只在新批演练及保全后使用，已安装12批不重复补导。
- 最新阅读器4项浏览器场景通过，覆盖390/1280、悬浮命中位置、缩放保持、失败重试、加载中关闭不重开、跨章、搜索、片段撤回与换档。挑战批386单元/集成+2浏览器，上一导航批19教材API+4浏览器；这些是不同批证据，不机械相加冒称本次全量通过。
- 最新证据：`learning_data/verification/reader-overlay-20261111/`的`browser-accepted.log`、`validated-files.json`、`runtime-hashes.json`、`live-check.json`、`final-health.json`；原失败日志保留。现有取消练习断言已改等待取消后的首页状态，避免短暂提示被恢复状态覆盖。
- Python测试环境：`learning_data/verification/a03-portable-tests-20261107T091348Z/venv/bin/python`；Chromium145.0.7632.6。根`conftest.py`隔离环境、阻止外部网络并生成合成教材。只在有相关变化时运行测试。
- 构建封包：`scripts/prepare_learning_release.py`、`scripts/build_learning_candidate.py`；参考最新overlay批的`deploy.py`/`verify.py`流程，但**旧批脚本已用过，不能直接重跑部署或record**。新批新目录，不覆盖历史输出。
- Docker daemon主机与工作区主机不同，向辅助容器传工作区材料用`docker cp`/命名卷，不用主机bind假定文件可见；不输出完整Compose、容器环境或密钥。

## 8. 新会话直接使用

在终端开启新Codex会话：

```bash
codex -C /home/deniskorfei/projects/open-webui '请先完整阅读 docs/plans/HANDOFF-SESSION-2026-11-12-TEXTBOOKS.md、docs/plans/RESUME-NEXT-WORK.txt 和 docs/releases/current-manifest.json。继续家庭学习全学科题库质量主线：先按交接第5节生成当前正式题库的知识点缺口审阅，优先二上、七上数学，再当前上册语文、英语等，分批补题与完善映射。普通阅读和放大窗口悬浮翻页已经上线，不重做；保留所有既有改动和使用数据，不提交推送，不重启C01模型，不恢复暂缓的真实手机验收。先核对当前状态，再推进可独立完成的工作，不反复询问覆盖范围。'
```

若通过应用新建会话，工作目录选上面的项目路径，将引号中的整段提示直接粘贴即可。

新会话初始只读命令（不触发导入、部署或模型）：

```bash
cd /home/deniskorfei/projects/open-webui
git status --short --branch
cat docs/plans/HANDOFF-SESSION-2026-11-12-TEXTBOOKS.md
cat learning_data/verification/session-handoff-20261112/read-only-state.json
docker compose -p dd-family-math -f learning_data/deployments/family-reader-overlay-20261111/compose.json ps
docker inspect --format '{{.State.Status}} {{.State.Health.Status}}' open-webui
```

相关代码有变化时，阅读器定向验证命令：

```bash
learning_data/verification/a03-portable-tests-20261107T091348Z/venv/bin/python -m pytest -q tests/test_family_adventure_browser.py tests/test_runtime_passages_browser.py --fail-on-skip --tb=short
```

本次交接未重跑工程测试；仅只读核对运行、题库与覆盖统计并整理文档。未commit/push，未发外部消息，未启用新模型/OCR/embedding调用。
