# 会话交接：教材补齐、题库质量与主站优化

整理时间：2026-11-13（Asia/Shanghai）。项目：`/home/deniskorfei/projects/open-webui`。

本文件汇总本会话及连续“继续”批次的可核验成果，替代旧交接中的过期“当前/下一步”。本次整理只读核对运行状态与公开静态资源，新增交接和入口文档；没有修改运行功能、导入题库、迁移、部署或重启服务。主站优化是建议，尚未实施。

## 1. 新会话先看这几条

- **教材原页已补齐**：按学校已确认开设学科，二年级语文、数学、道德与法治上下册共6册；七年级语文、数学、英语、道德与法治、历史、地理、生物上下册共14册。合计 **20册、152个目录范围**。二年级暂未开英语，不算缺册；物理、化学按后续开课年级安排。
- **教材齐全不等于题库齐全**。最新7册仅原页阅读，无正式配题、无关键词索引，也未建立完整知识点清单。原13册已有题与一轮题型升级，但整章知识点穷尽、教师审核和真实难度校准仍未完成。
- 正式题库 **1145题：二年级418、七年级727**，其中章节题1071，另有原60应用题及14起步题；schema14。线上全学科覆盖仍是 **subject-v5**。
- 本地最新候选是 **math-v15 / subject-v16**，审阅包 **review-v17**；三道数学纠错候选未安装。不要将本地映射、1074道本地章节题源或候选审阅页当成线上题库。
- 默认下一步：按第7节，为已经审明的 **20项上册缺口**编制本地候选并复核，再处理下册及新增7册。已审过的同章题不要重新当作“未审候选”循环检查。
- 主站已有学科伴学、课本聊天入口、资料联动、知识路线、分步课堂与复习打印样本。第6节建议围绕实际缺口扩展，不重做已有功能。

## 2. 约束与事实来源

1. 保留全部既有改动和使用数据，**不提交、不推送**，不执行`git reset/clean`或用旧工作区覆盖现有文件。
2. **不启动、重启或调用C01**，不删除STOP、不重置预算；模型窗口已关闭。四个隔离容器保持exited。
3. **真实手机验收继续暂缓**，只有用户明确恢复后才安排；390px模拟验收不能替代真机结果。
4. 不自动调用外部模型、OCR或embedding，不传出学生资料，不发送外部通知。本交接不要求新部署或重启。
5. 本次写文档前有223个变更路径：41个已跟踪改动、182个未跟踪。此为整理前快照，新增文档后数量会变化；它不是待清理列表。
6. 运行身份以[发布清单](../releases/current-manifest.json)的`latest_deployment`及对应证据为准，不能用Git HEAD、旧台账、旧段落中的“当前”代表线上。

本轮只读证据：[read-only-state.json](../../learning_data/verification/session-handoff-20261113/read-only-state.json)，时间2026-11-13 10:51（+08:00）。核对5个生产服务running，API/WebUI healthy，其余3个无healthcheck；4个C01容器exited。停止容器残留的历史unhealthy字段不表示正在运行，也不需要启动修复。

同轮匿名GET验证主站`loader.js`、`custom.css`、`dd-family-bridge.js`及Mermaid资源均HTTP200、no-store、哈希匹配已发布记录；前三份也与当前工作区对应源码逐字节一致。**没有读取生产学生记录**：题量、schema和数据库保全数字沿用11月12日已验证发布证据，不冒称本次重查数据库或新跑工程验收。

## 3. 本会话任务及完成位置

| 任务 | 已完成 | 当前边界 / 证据 |
| --- | --- | --- |
| 按旧交接第5节继续题库质量 | 新增10道数学缺口题、14道语文/英语缺口题并上线，正式题从1121增至1145 | [数学质量](../verification/KNOWLEDGE-QUALITY-2026-11-12.md)、[语文英语补题](../verification/SUBJECT-GAPS-2026-11-12.md) |
| 数学单一动作与映射复核 | 二上数学六单元及活动、七上数学六章逐题复核；区分计算、辨析、辅助与人工任务，形成math-v15 | [数学复核](../verification/MATH-SINGLE-ACTION-2026-11-12.md)；仅本地，三道纠错候选未安装 |
| 当前上册其他科目缺口复核 | 七上语文/英语及二上、七上道法、七上史地生续审；最后一批审核27项要求、131道不同正式题，修订16条映射，7项首次有直接证据 | [科目复核](../verification/UPPER-SUBJECT-KNOWLEDGE-REVIEW-2026-11-12.md)；subject-v16 / review-v17，仅本地 |
| 检查二年级、七年级是否缺册 | 核对学校开课范围、现行版本、官方目录及本地原件，明确缺少7本下册 | 已完成，未把二年级英语或高年级物理化学误算为缺册 |
| 将缺少教材补齐 | 新增二下数学/道法、七下英语/道法/历史/地理/生物，目录、原页、翻页、跳页和放大均可用 | **已上线20册/152范围**；[教材验收](../verification/TEXTBOOK-COMPLETION-2026-11-12.md) |
| 保留既有阅读器成果 | 标题三角对齐、图片上层悬浮翻页、放大翻页保持缩放、跨章阅读、目录跟随及桌面目录停留 | 已上线，无需重新实现；[悬浮翻页](../verification/READER-OVERLAY-2026-11-11.md) |
| 主站优化建议与会话交接 | 核对现有源码、发布证据与线上静态字节，列出建议、优先级、验收条件和接续命令 | 本文件第6—9节；本轮未实现新增功能 |

此前完成的414章题首批、数学深度题、分步作答、其他学科题型、限定短答及98道挑战题，已包含在当前1145题中，不能再叠加计数。四档难度为简单/正常/困难/挑战，答题项不额外计为题数，换数字或换故事不自动算新题型族。

### 3.1 最新教材补齐细节

| 新增教材ID | PDF总页数 | 书内可阅读页码 | PDF页码减书内页码 |
| --- | ---: | --- | ---: |
| `math-g2-lower` | 106 | 1–97 | 6 |
| `ethics-g2-lower` | 70 | 1–61 | 5 |
| `english-g7-lower` | 130 | 1–119 | 9 |
| `ethics-g7-lower` | 114 | 1–104 | 7 |
| `history-g7-lower` | 142 | 2–133 | 5 |
| `geography-g7-lower` | 126 | 1–118 | 5 |
| `biology-g7-lower` | 143 | 1–136 | 5 |

- 原件总831页均本地渲染成功。书内页码与PDF页序分别记录，历史不虚造编号第1页。逐页可渲染不等于全书教学内容审核。
- 来源、准确原件哈希、现行版本和目录核对见[来源清单](../../learning_data/textbooks/missing-lower-20261112/verified-source-manifest.json)及[运行目录](../../learning_service/data/textbook_lower_reading_v1.json)。二下数学复用此前核验PDF；二下道法来自国家智慧教育平台70张公开原页，本地合成无OCR文本层PDF；五本七下PDF采用与官方现行目录交叉核对的公开原件。未采纳旧版或错册，也不从下载站系列标签编造具体印次/ISBN。
- 新7册`search_available=False`、`collection=''`；UI禁用关键词查找，服务端同样回退原页浏览且不触发向量调用。原13册既有搜索能力保留，不意味着各册检索质量或OCR已全书审核。
- 66项教材/API/发布检查、99项兼容检查、390/1280两视口2项浏览器检查最终通过。前两组有重叠，不能相加冒称165个独立用例。首次浏览器脚本错误及后续修正记录保留。
- 发布前后50张表、3383条既有行哈希相同，1145题与schema14保持，原13份PDF哈希相同；三个家庭服务各90个运行文件哈希匹配。证据在`learning_data/verification/textbook-completion-20261112/`。

### 3.2 覆盖候选究竟做到哪里

| 对象 | 当前版本 / 位置 | 状态 |
| --- | --- | --- |
| 线上覆盖 | subject-v5；93 configured / 294 partial / 271 gap | 已部署；276点、658要求草案，308 human、350 bounded |
| 本地数学 | `learning_service/data/family_math_coverage_plan_v15.json` | 65 configured / 140 partial / 7 gap；数学专用口径，不能与全学科相加 |
| 本地全学科 | `learning_service/data/family_subject_coverage_plan_v16.json` | 112 configured / 288 partial / 258 gap；308 human、350 bounded不变，未发布 |
| 最新审阅包 | `learning_data/verification/upper-subject-review-20261112/review-v17/` | 正式题快照418/727；27项逐题决定在`candidate-review-decisions.json` |
| 数学旧审阅快照 | `learning_data/verification/math-single-action-20261112/review-v15/` | 保留生成时math-v15 / subject-v14，不代表当前subject-v16 |
| 未安装数学题 | `family_chapter_math_g7_action_candidates_v1.json`及`family_chapter_math_g7_chapter4_action_candidates_v1.json` | 共3道：减负数、负因子奇偶/零因子、减整式漏变号；不计正式覆盖 |

configured仅表示达到“两种经核对的直接题型族”这一编辑目标，**不是课标完整率、正确率或学生掌握率**。原13册276点/658要求尚非穷尽课程，更不包含新增7册完整知识清单。口述、自由作文、真实听说、作图、测量、实验不能被选择题正确替代。

最后科目复核的定向回归为83 passed；题干、答案和解析等1145道正式题内容逐项相同。此为原批次结果，本次文档整理没有重跑这些测试。subject-v16 SHA256为`f3861070f1081833a47bf5a2cca5dedb714de44f0fc8878eea85ec2d9490189a`。

## 4. 当前运行身份与保全

| 项目 | 当前值 |
| --- | --- |
| 主站 / 家庭入口 | `https://172.19.116.53/` / `/learning/ui`；未认证303登录跳转正常 |
| 活动Compose | `learning_data/deployments/family-textbook-completion-20261112/compose.json` |
| API / worker / gateway镜像 | `sha256:6014a23756647d72fea8afaa074fc05b4fab7cff6e804d570bc34cc23e21c6f6` |
| 发布源码 | `learning_data/releases/textbook-completion-20261112-final/`；profile `reuse-runtime-textbook-completion-v12`，134文件 |
| 源码集合SHA256 | `4ebfaede6a2b5605f3f23c7fb2bc3d7784638b9b893227f1bfefa8ba0ac108e7` |
| 源码归档SHA256 | `fb59e665812f1bca8c4ef66201f15da9f6030878ffb3bc5b3f2036f3138ab7c4` |
| WebUI / Tool / schema | 0.12.5 / 1.2.1 / 14 |
| WebUI镜像 | `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd` |
| 主站静态 | `learning_data/deployments/family-b11-c01-20261109/assets`，9资源；本次教材发布未改静态 |
| 学习数据 | 卷`dd-family-math_data`，容器内`/var/lib/dd-learning/learning.db` |
| 教材原件 | 容器内`/opt/dd-textbooks`；Docker主机挂载来源`/home/deniskorfei/projects/open-webui/learning_data/deployments/family-subject-textbooks-20261106` |
| 最新发布前备份 | `learning_data/verification/textbook-completion-20261112/private/backup/`，同级保留备份收据/验证 |
| 上一个服务配置 | `learning_data/deployments/family-subject-gaps-20261112/compose.json` |
| 上一个API / worker镜像 | `sha256:34f037086c106495f0446e5153279fd1a3227c493bba1d64bdbd4c927850d05c` |
| 上一个gateway镜像 | `sha256:1aa1a09316e8d9d944a0b97ce3ed994668319c618f2d36c096d9ebacea641138` |

教材发布从已上线subject-v5源码封包出发，只叠加6个经核对的教材相关文件，见[source-diff.json](../../learning_data/verification/textbook-completion-20261112/source-diff.json)。**没有从整个脏工作区构建**，因此本地覆盖候选没有混入线上。

如未来需要回退，先保全新使用数据，沿兼容方案恢复上一服务镜像，保留当前数据卷及新增PDF。不得用旧备份覆盖新学习记录，不得重跑历史部署脚本或入口开放前专用回退脚本。主站/代理较早组件字段可能留有历史启动时间，本轮实际状态以只读快照为准。

Docker daemon主机与当前工作区主机不同；文件传递用既有`docker cp`/辅助流程，不假定本地bind可见。不打印完整Compose、容器环境、令牌或私有数据库/备份内容。

## 5. 尚未完成与继续暂缓

| 待办 | 当前状态 | 下一步边界 |
| --- | --- | --- |
| 上册20项明确缺口 | 同章已安装题审完，5项无映射、15项只有辅助 | 先编本地候选、逐题复核，不直接导入或部署 |
| 下册及新增7册知识点与题库 | 新7册无正式题/完整知识清单；原有下册也未穷尽覆盖 | 逐册核对现行教材，建立清单，再分批补题 |
| 课程标准交叉核对、教师签署、真实难度 | 均未完成；助手内容复算不等于真人教学签署 | 保留pending，不能自动代签或用编辑覆盖推算掌握率 |
| 人工任务闭环 | 已有操作任务单、课堂自查；尚无人工任务完成及复核的持久化记录 | 如开发，区分学生自述、家长确认、教师意见与自动判分 |
| B04二下数学OCR | 离线OCR已有；仅5页处理、4页助手双步骤通过，`B04-P013-D01`图形问题未解 | 原页阅读上线不等于全书OCR/教师审核通过；不自动启用外部OCR |
| B02真实学习观察 | 真实1/3/7天无提示观察未完成；12道备用候选未安装 | 不用合成记录代填，不为补数量导入备用题 |
| B07备份 | 同机完整备份/校验已有；独立故障域、责任人、实际RPO/RTO未落实 | 需单独实施和恢复核验，不能将同机证据当独立备份 |
| B08外部观察 | 外部端点、阈值、权限和值守责任待定 | 不自动发送通知或接入外部服务 |
| C01 | 技术/助手历史24/24及开发补充3/3通过；真人教学签署pending | 已结束并停止，不继续模型验收；模型别名非不可变版本、合成开发验收非真实学习效果证明 |
| 真实手机 | 用户明确暂缓；桌面7项与HP102w三页纸张打印已通过 | 不重复未变桌面/纸张验收，不催真机，不用模拟宽度代填 |
| 其他旧台账 | C02真实OCR、C03完整恢复/删除/记账、C05全栈与媒体再评估未自动启动 | 按各自真实缺口保留；旧C04“小单元扩展”不能覆盖后续全学科现状 |
| Git交付 | 大量既有改动及未跟踪文件，未整理提交/推送 | 按用户要求原样保留；不为交接清理或提交 |

## 6. 主站能优化什么、可增加哪些功能

### 6.1 已有能力，先复用

主站现有侧栏“家庭学习/学科伴学”和聊天框“课本聊天、查课本、分步讲解、检查思路、关联练习”；通过同源会话读取当前档案与教材/章节，支持跨标签书章同步。已有局部数学知识卡、先修关系、原页链接、关联题跳转、四步课堂、局部交互演示、离线HTML和七上数学第五章三页复习打印样本。它们不是完整逐科课程或全章知识图谱。

家庭页已经有今日挑战、到期复习、错题收藏、练习草稿/会话恢复和简单统计。主站若增加首页/家长视图，应整合这些数据和入口。当前书章选择只在同一浏览器本地隔离共享，阅读页主要在内存中；尚无统一服务端逐档案逐册阅读位置/书签。课堂自查勾选只存在当次课堂，不记录成绩。

身份变化清空旧参考、请求revision核验、丢弃迟到响应、断连提示和宿主草稿保护已存在。切换家庭档案不会自动切换原生历史聊天或草稿，界面已有提示及新课本聊天入口，不能描述成已实现聊天按孩子完全隔离。

### 6.2 建议优先级（均未实施）

| 优先级 | 建议 | 现有基础与具体增量 | 验收重点 |
| --- | --- | --- | --- |
| P1 | 主站与家庭页能力保持一致 | 主站关联练习`difficulties`及筛选目前仅easy/normal/hard，家庭已有challenge；补齐第四档及真实空态，核对知识映射/API是否实际返回挑战题 | 有题时正确显示“挑战”；无映射时如实空态，不能只加按钮冒称全部题可用 |
| P1 | 统一学习首页/继续入口 | 汇总当前档案、教材、未完成练习、到期复习、错题入口；复用家庭页现有能力，减少主站与家庭页反复查找 | 每个入口回到同一有效档案/书章；未完成题切换仍走确认；无数据有清楚下一步 |
| P1 | 教材能力状态清晰一致 | 家庭页已对新7册禁用查找；主站快捷操作应按目录元数据展示“原页可读/可检索/有练习/知识映射局部”等实际能力 | 新7册直接引导目录/跳页；不向不存在的索引发送请求；不显示虚假练习与完整覆盖 |
| P2 | 阅读位置、书签与跨设备继续 | 在现有翻页器和书章桥接上新增逐档案逐册的书内页码、书签、更新时间；先做好本设备，再设计服务端同步 | 刷新恢复到有效页；两档案不串；旧revision不能回写；教材换版时核对原件身份；跨设备需服务端记录 |
| P2 | 家长学习回顾与人工任务记录 | 整合实际练习、提示使用、错题/复习事实，补口述、画图、实测等任务提交与家长确认；可提供本地周回顾/打印 | 区分完成/自述/复核与自动判分；编辑覆盖率不能当孩子掌握率；反馈可更正并有来源时间 |
| P2 | 更明确的课本聊天范围 | 在已有新聊天入口和切档提醒上，提供当前档案/课本的明确上下文提示，探索用户主动选择的会话分组或绑定 | 原生草稿和历史保留；跨档案必须重新核对；先确认宿主兼容接口，不擅自改写历史聊天 |
| P3 | 新册可核验全文定位与更多课堂/复习材料 | 新7册先做本地文字质量/页码抽查及出处核验，再建立有界检索；复用现有课堂与导出机制扩展经审内容 | 原件与文字/页码绑定，证据可撤回；原页可读不授予OCR/答案资格；不自动调用外部模型或OCR |

建议主站的第一小批选择 **P1能力一致性与学习入口整理**。先完成本地可评审改动和合成验收，再按当时授权决定发布；不要先上大而空的AI课程平台、多代理课堂、语音评分或未经验证的掌握度大屏。本次交接没有实施或发布上述建议。

主站源码入口：`deploy/open-webui-reuse/main-study/study.js`、`study.css`、`family-bridge.js`；家庭能力在`learning_service/app.py`、`study_ui.py`、`study_reference.py`。历史说明见[资料联动](../verification/main-study-family-bridge-2026-11-07.md)、[课堂](../verification/main-study-classroom-2026-11-07.md)、[知识路线](../verification/main-study-knowledge-2026-11-07.md)、[宿主兼容](../open-webui-reuse/host-compatibility.md)。旧样本报告中的“未发布”和schema13属于当时快照，后续B11于11月9日已发布9项静态资源；当前家庭schema14。

## 7. 默认下一步：先把20项缺口做成可审候选

### 7.1 不再重复寻找同章现成题

以`review-v17/candidate-review-decisions.json`为逐项事实来源，下列20项已审完所在范围的现成正式题。`no_mapping`为5项，`supporting_only`为15项，均缺少满足完整要求的直接题型证据：

| point_id | 待补要求 | 当前证据 |
| --- | --- | --- |
| `ethics-g2-upper:4:participate` | 提出了解祖国的具体学习活动 | supporting_only |
| `ethics-g7-upper:2:family` | 表达需要并理解其他成员处境 | no_mapping |
| `ethics-g7-upper:2:teacher` | 以具体事实沟通分歧 | supporting_only |
| `ethics-g7-upper:2:group` | 比较分工方案对个人和集体的影响 | supporting_only |
| `history-g7-upper:2:culture` | 区分文物年代类别和历史信息 | supporting_only |
| `history-g7-upper:3:unification` | 区别政治经济文化方面的措施 | supporting_only |
| `history-g7-upper:4:three` | 根据战争与建国时间区分事件 | supporting_only |
| `history-g7-upper:4:reform` | 依据措施分析交融影响 | supporting_only |
| `history-g7-upper:5:map` | 结合图例时间判断空间变化 | no_mapping |
| `geography-g7-upper:2:space` | 区分恒星行星卫星及所属关系 | no_mapping |
| `geography-g7-upper:3:selection` | 按用途比较比例尺和地图内容 | no_mapping |
| `geography-g7-upper:5:temperature` | 计算日较差年较差并辨半球季节 | supporting_only |
| `geography-g7-upper:5:rain` | 比较季节总量及其单位 | supporting_only |
| `geography-g7-upper:6:population` | 区分总量密度和自然增长 | supporting_only |
| `geography-g7-upper:6:culture` | 依据材料比较文化并尊重差异 | supporting_only |
| `biology-g7-upper:1:observation` | 控制变量设置对照并记录重复结果 | supporting_only |
| `biology-g7-upper:2:celllife` | 区分细胞膜细胞核和能量转换结构 | supporting_only |
| `biology-g7-upper:3:single` | 说明一个细胞完成多种生命活动 | no_mapping |
| `biology-g7-upper:6:fungi` | 以结构和营养方式与细菌比较 | supporting_only |
| `biology-g7-upper:6:food` | 区分发酵保存与灭菌的条件 | supporting_only |

### 7.2 执行与验收顺序

1. 先读当前发布清单与review-v17，核对题ID快照及math-v15/subject-v16。保留旧版本和三道数学候选，不导入生产，不切换真实档案制造测试记录。
2. 分学科编制本地候选，绑定现行教材的范围与原页依据。完整复合要求必须完整考查；只覆盖部分时继续标为辅助，不为增加configured把同一动作拆成多族。实际表达、观察或实验仍保留人工任务。
3. 每题交付题干、正确答案、解析、常见错误反馈、核心动作/题型族、难度依据和候选映射；逐题复算、核对多解与措辞、检查图表及来源许可。使用本地编写内容，不声称抄自教材题目。
4. 在临时合成库验证候选结构、判分边界和幂等性，生成独立新审阅包与覆盖前后差异；候选证据和正式安装证据分别展示。继续保留教师签署false、课标crosscheck pending和真实难度未校准。
5. 定向回归通过后，记录本批题量、缺口变化、局限及下一批；本阶段停留在本地可审候选，不自动导入、迁移或部署。若后续发布，按届时授权从已部署封包叠加经审增量，不打包整个工作区。
6. 再逐册处理下册。先建知识点/能力/人工任务清单，优先校内正在使用或即将使用的范围；新增7册尚无正式题，先有依据再补题。主站功能如另行启动，优先第6节P1小批。

本批完成的判断标准：20项逐一有“候选及复核结果”或明确的保留缺口原因；没有把人工要求或不完整复合能力自动判为达标；正式1145题与生产使用记录保持，C01未启动、无外部调用，无提交推送。

## 8. 工具入口与验证命令

覆盖生成/审阅入口：`scripts/build_subject_coverage_v16.py`、`scripts/review_knowledge_gaps.py`、`scripts/build_math_coverage_plan_v13.py`及后续版本引用；先读脚本参数与数据依赖，不直接重跑旧导入/部署脚本。发布准备为`scripts/prepare_learning_release.py`、`scripts/build_learning_candidate.py`。

只读起步（不会导入或部署）：

```bash
cd /home/deniskorfei/projects/open-webui
git status --short --branch
cat docs/plans/HANDOFF-SESSION-2026-11-13-MAIN-SITE.md
cat docs/releases/current-manifest.json
cat learning_data/verification/session-handoff-20261113/read-only-state.json
docker compose -p dd-family-math -f learning_data/deployments/family-textbook-completion-20261112/compose.json ps
```

有相关内容变更时，使用既有隔离测试环境做定向检查；本次文档整理不需要重跑：

```bash
learning_data/verification/a03-portable-tests-20261107T091348Z/venv/bin/python -m pytest -q tests/test_math_single_action_coverage.py tests/test_chapter_practice.py tests/test_practice_coverage.py tests/test_subject_knowledge.py tests/test_knowledge_quality.py tests/test_challenge_tier.py --tb=short
```

若修改主站，关注`tests/test_main_study_bridge.py`、`tests/test_main_study_host.py`以及实际宿主构建探针；修改教材则关注`tests/test_textbooks.py`、`tests/test_textbook_completion_browser.py`及旧片段兼容。浏览器使用合成身份/临时库；禁止把真实模型聊天或真实学生作答当自动化探针。

根`conftest.py`隔离环境、阻断外部网络并生成合成材料。已有测试环境Chromium145.0.7632.6；模块有变化才运行相关测试，不为文档整理重跑所有历史性能矩阵。

## 9. 新会话继续命令

默认继续原题库质量主线：

```bash
codex -C /home/deniskorfei/projects/open-webui '请完整阅读 docs/plans/HANDOFF-SESSION-2026-11-13-MAIN-SITE.md 和 docs/releases/current-manifest.json，按交接第7节继续题库质量与知识点缺口任务：先为review-v17已审明的上册20项缺口编制本地候选，逐题核对题干、答案、解析、完整要求和题型族，生成可审材料，再处理下册及新增7册知识清单。不要重复审已核对同章候选，不直接导入或部署。教材20册原页已补齐，线上1145题、subject-v5，本地math-v15/subject-v16未发布。保留全部既有改动和使用数据，不提交推送，不启动、重启或调用C01，不调用外部模型/OCR/embedding，真实手机验收继续暂缓。先核对现状，再推进可独立完成的工作。'
```

若明确改为先做主站优化，可使用这一条，范围限定为本地候选：

```bash
codex -C /home/deniskorfei/projects/open-webui '请完整阅读 docs/plans/HANDOFF-SESSION-2026-11-13-MAIN-SITE.md 和 docs/releases/current-manifest.json，按第6节先做主站P1能力一致性与学习入口优化的本地可审候选：核对并补齐挑战档展示/筛选，按真实教材元数据显示阅读、检索和练习能力，整合已有家庭学习继续入口。复用现有功能，保持档案revision核验、未完成练习确认与聊天草稿保护；使用合成身份和临时库验证，不自动部署，不混入本地覆盖候选。保留既有改动与使用数据，不提交推送，不启动或调用C01，不调用外部模型/OCR/embedding，真实手机验收继续暂缓。'
```

以上第二条是用户选择主站方向时可下达的新指令，不表示本次已经授权执行或完成这些建议。
