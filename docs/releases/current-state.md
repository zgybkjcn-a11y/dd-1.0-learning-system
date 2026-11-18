# DD-1.0 当前状态与交付清单

2026-11-18主站教材能力状态已上线：主站“家庭学习资料”下新增能力行，显示当前课本的原页可读、是否支持关键词检索、已安装练习数与局部知识映射题数；数值全部由服务端 `learning_service/textbook_capabilities.py` 从已安装题版与已审映射推导，前端只按字段拼句。`GET /api/v1/textbooks` 每册新增 `capabilities`，OpenAPI 路径仍 77、schema 44→45。发布按停写备份→切换→逐表比对执行：镜像 `dd-learning:main-study-capability-20261118-r2`（`sha256:a228872c…`），Compose `learning_data/deployments/family-main-study-capability-20261118/compose.json`（`1841629d…`），静态目录同名 `assets`（`study.js`→`ef7b357d…`、`study.css`→`4164d004…`）；50 张表与备份逐表行哈希完全一致，1226 题、99 次作答、28 条审计事件、schema14 不变。发布中修正一处不实文案：首个镜像对检索关闭的册误写“可检索”，运行约 3 分钟后停写重发 `-r2`，说明文字改为由事实组合并新增 4 项一致性测试。能力为整册口径，不细分到章，也不展示掌握度或覆盖率。全量非浏览器 1267 通过（566.96 秒）；CI run 44279792862（commit `14c2cac`）单元 1190、浏览器 53 通过；部署后 1280/390 探针通过（页面错误 0、模型调用 0）。回退用 `family-main-study-p1-20261118/compose.json` 与旧镜像 `de8a6472…`。验收见[主站教材能力状态](../verification/MAIN-STUDY-TEXTBOOK-CAPABILITY-2026-11-18.md)。

2026-11-18候选题库已进入正式题库并发布：按用户决定跳过教师签署，由助手对 81 道下册/上册缺口候选完成课标交叉核对（81 接受、0 拒绝、76 直接族/5 辅助族；依据本地 subject-v16/math-v15 与下册清单的要求表述，**不是国家课标原文比对**），9 批登记进 `chapter_practice.BATCHES` 后安装到本机生产。正式库由 1145 题增至 1226 题，`family-g2` 可选题由 418 增至 436；安装同时新增 44 个知识点与 44 个复核目标。首次镜像 `sha256:d6e9883f…` 发布后发现 25 个批次超出解析缓存，`study-path` 约 10 秒；同日以 `sha256:de8a6472…`（源码 `1ce7334`）重发，缓存上限 16→64，`study-path` 降到 0.09–0.12 秒、`question-choices` 热 0.12–0.14 秒。当前 Compose `learning_data/deployments/family-question-bank-cache-20261118/compose.json`；两次切换均先停写、备份并校验（schema14、integrity ok、外键0），第二次 50 张表与切换前备份逐行哈希完全一致，99 次作答、2 名学习者、schema14 不变；重复安装新增 0。切换后 `/health`、`/learning/ui` 正常，未认证 `study-path` 经网关为 401（转发生效，旧版本 404）。同一提交还包含新 7 册知识点清单（54 范围/68 点/58 有本地题/10 仅人工任务/53 节未展开）主站 P1（第四档难度与统一入口）同日另行授权发布：新静态目录 `family-main-study-p1-20261118/assets`，仅重建 learning-proxy，四个静态路由 200/no-store 且哈希与发布目录一致，1280/390 部署后探针通过；nginx 配置、api/worker/gateway 与 open-webui 未动。教师签署仍为 `false`，真实难度未校准，覆盖计划未升版，configured/partial/gap 不因安装变化。全量非浏览器 1258 通过（8分35秒；修复前 62分01秒）；CI run 44248722760（commit `1ce7334`）单元 1181、浏览器 53 通过。回退用 11-17 Compose 与旧镜像 `9962c9a7…`，保留数据卷。验收见[候选进入正式题库](../verification/QUESTION-BANK-PROMOTION-2026-11-18.md)、[课标交叉核对](../verification/CURRICULUM-CROSSCHECK-2026-11-18.md)、[新7册知识点清单](../verification/NEW-BOOKS-KNOWLEDGE-2026-11-18.md)、[主站P1](../verification/MAIN-STUDY-P1-2026-11-18.md)。

2026-11-17候选题端点题库单次装载已发布：`/api/v1/question-choices` 原先对每个候选题版逐个查元数据、放置与校验，难度指导按历史作答再查一次、两份覆盖报告又各自装载全套题库，而章节/备用题库刻意不缓存，家庭库单请求热态约5.2秒。改为每请求每套题库只装载一次并共享后，`family-g2`（418题）热0.138秒、首请求1.224秒；每请求 core/chapter/reserve 各装载1次。按用户授权发布到本机生产：镜像 `sha256:9962c9a7…`，Compose `learning_data/deployments/family-question-choices-bulk-20261117/compose.json`；停写后一致性备份与校验通过（schema14、integrity ok、外键0），切换后 `/health`、`/learning/ui` 正常，50张表逐行哈希与备份一致，1145题、99次作答、schema14不变；proxy 与 open-webui 未重启，C01 未启动。CI run 44100899667（commit `af359ae`）单元1177、浏览器53通过。回退用11-16 Compose与旧镜像 `539a0dc2…`。验收见[QUESTION-CHOICES-BULK-2026-11-17](../verification/QUESTION-CHOICES-BULK-2026-11-17.md)。

2026-11-15学习路径已发布：家庭页新增"今天从这里开始"只读卡片，把续做、到期复习、自动进阶建议与教材阅读兜底按固定顺序合成最多四步、总建议25分钟，超出预算的步骤进入下次；新增只读接口 `/api/v1/study-path` 与 `learning_service/study_path.py`，零写入、不建表、不调模型，不显示完成计数与掌握度。按用户授权发布到本机生产：镜像 `sha256:933c8ceadddf…`，Compose `learning_data/deployments/family-study-path-20261115/compose.json`；停写后一致性备份与校验通过（schema14、integrity ok、外键0），切换后 `/health`、`/learning/ui` 正常，50张表逐行哈希与备份一致，1145题、99次作答、schema14不变；proxy 与 open-webui 未重启。CI run 43726542097（commit `1615efa`）单元1173、浏览器53通过。回退用11-15代码升级Compose与旧镜像 `6f6ad8a1…`。验收见[STUDY-PATH-2026-11-15](../verification/STUDY-PATH-2026-11-15.md)。

2026-11-15生产升级：按用户授权把 `ea95d1b` 的服务代码部署到本机生产（api/worker/gateway 镜像 `sha256:6f6ad8a1…`，Compose `learning_data/deployments/family-code-upgrade-20261115/compose.json`）。切换前停写并完成一致性备份与校验（schema14、integrity ok、外键错误 0），切换后 `/health`、WebUI、proxy 正常，50 张表逐行哈希与备份完全一致；1145 题、99 次作答、schema14 不变。学科覆盖清单由 subject-v5 切到 v16、数学覆盖由 v13 切到 v15（行数仍 276/53），下册八批候选仍未注册未安装，未导入题目、未迁移数据库、未调用外部模型/OCR/embedding、C01 未启动。回退用 11-12 Compose 与旧镜像 `6014a237…`，保留当前数据卷。验收见[代码升级报告](../verification/CODE-UPGRADE-2026-11-15.md)。

2026-11-14会话总结（第五至八批）：下册本地候选第五至八批完成，共27题/108个作答项（全部直接族），连同前四批八批共61条候选行/244个作答项，覆盖清单58条可出候选的新初步要求（清单68条，另10条仅参照）。全部未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5、本地math-v15/subject-v16。最后一批定向8项通过、15模块回归160项通过（0失败0跳过，476.25秒），合成安装1145→1149、重复安装新增0、provider_calls为0。下册清单已无剩余可出候选，详见[HANDOFF-SESSION-2026-11-14-LOWER-BATCH5-8-SESSION-SUMMARY](../plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH5-8-SESSION-SUMMARY.md)。

2026-11-14第八批：下册第八批候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH8.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH8-2026-11-14.md)）。三个范围各一处有界要求（历史第四单元两条要求分列）：北宋建立与中央集权、明朝建立与强化皇权、史料出处与史事要素、节日延续与文明特征。共4题/16个作答项，全部直接族且全部挂人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。七下历史使用原生文字层，未使用OCR。定向8项通过；同批回归共160项通过、0失败0跳过（476.25秒），记录见`learning_data/verification/lower-gap-candidates-batch8-20261114/test-results.json`。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。

2026-11-14第七批：下册第七批候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH7.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH7-2026-11-14.md)）。六个范围各一处有界要求（二下道法第二单元两条要求分列）：大自然观察与爱护生命、水与纸的用途、行为与品质对应、个人与共同梦想；七下道法自尊与恰当目标、传统思想理念、权利界限与知识产权。共7题/28个作答项，全部直接族且全部挂人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。二下道法按页面图像目视核对（第24页为空白课题页，水的内容在p25/26），未使用OCR。定向8项通过；同批回归共152项通过、0失败0跳过（450.73秒），记录见`learning_data/verification/lower-gap-candidates-batch7-20261114/test-results.json`。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。

2026-11-14第六批：下册第六批候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH6.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH6-2026-11-14.md)）。六个范围各一处有界要求（二下数学两条要求分列）：钟面与时间单位、作息记录的经过时间；七下英语 Unit 5 现在进行时、Unit 6 天气与时态、Unit 7 一般过去时、Unit 8 叙事时态、Reading Plus 章鱼事实。共7题/28个作答项，全部直接族且全部挂人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。二下数学p2/3/5/7按页面图像目视核对，未使用OCR。定向9项通过；同批回归共144项通过、0失败0跳过（428.40秒），记录见`learning_data/verification/lower-gap-candidates-batch6-20261114/test-results.json`。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。

2026-11-14第五批：下册第五批候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-14-LOWER-BATCH5.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH5-2026-11-14.md)）。九个范围各一处有界要求：七下生物第四章血液、第五章排泄、人体结构模型项目；七下地理东南亚世界遗产项目、第九章西亚、第十章美国、第十一章极地；七下英语Unit 3、Unit 4。共9题/36个作答项，全部直接族且全部挂人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。地理四处图件以渲染原页目视核对，未使用OCR；遗产处数按教材“截至2021年第44届”口径引用。定向9项通过；同批回归共135项通过、0失败0跳过（369.59秒），记录见`learning_data/verification/lower-gap-candidates-batch5-20261114/test-results.json`。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。

2026-11-13第四批：下册第四批候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH4.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH4-2026-11-13.md)）。九个范围各一处有界要求：二下数学连环画；七下英语Unit 2；七下生物光合作用与呼吸作用、栽培项目、生殖与青春期、营养物质、呼吸系统；七下地理日本自然环境与p108雨林固碳项目。共9题/36个作答项，全部直接族且全部挂人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。固碳题使用原页108图1目视核对值（面积1600/900/460/4000万公顷、碳储量17.1/15.4/8.0/88.0亿吨），已注明出处与口径。定向10项通过；同批回归共126项通过、0失败0跳过（362.18秒），记录见`learning_data/verification/lower-gap-candidates-batch4-20261113/test-results.json`。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。

2026-11-13第三批：下册第三批候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH3.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH3-2026-11-13.md)）。七下数学按复核页把perpendicular拆为垂直定义（p4）、垂线基本事实（p5）、垂线段最短与点到直线的距离（p6）三项，旧行printed_page=3保留未改、仅以refine行补充；二下数学第2—5单元6题。共9题/36个作答项，全部直接族且全部挂人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。定向9项通过；同批回归共116项通过、0失败0跳过（314.27秒），记录见`learning_data/verification/lower-gap-candidates-batch3-20261113/test-results.json`。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。

2026-11-13夜间：下册第二批四个起始范围候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-BATCH2.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-BATCH2-2026-11-13.md)）。二下道法、七下道法、七下历史、七下地理起始单元共9题/36个作答项，全部直接族且全部挂人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。同时确认七下数学perpendicular旧定位错误（垂直定义p4、垂线段最短与距离p6）和七下地理p108图中数字乱码（已目视核对），两项均未据此出题。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。

2026-11-13傍晚：下册首批三个起始范围候选在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-13-LOWER-CANDIDATES.md)、[复核报告](../verification/LOWER-GAP-CANDIDATES-2026-11-13.md)）。二下数学第1单元、七下英语Unit 1、七下生物第三单元第一章各一处有界要求，共7题/28个作答项，6题直接族、1题仅辅助附人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。定向8项加同批回归共99项通过。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。运行身份以11-12发布记录为准。

2026-11-13下午：上册20项缺口候选与下册初步知识清单在本地完成（[续办交接](../plans/HANDOFF-SESSION-2026-11-13-QUESTION-QUALITY.md)、[上册复核](../verification/UPPER-GAP-CANDIDATES-2026-11-13.md)、[下册清单](../verification/LOWER-KNOWLEDGE-INVENTORY-2026-11-13.md)）。20题/73个作答项，16项一个直接题型族、4项仅辅助附人工任务，新增configured为0；候选未注册未安装，正式题仍1145题（418/727）、schema14、线上subject-v5，本地math-v15/subject-v16。下册建立10册75范围初步清单，下册新题0。本轮未访问生产数据库、未导入/迁移/部署、未提交推送、C01未启动、无外部模型/OCR/embedding，真实手机仍暂缓。运行身份与题量以下方11-12发布记录为准。

2026-11-13上午已整理[最新会话交接：教材补齐、题库质量与主站优化](../plans/HANDOFF-SESSION-2026-11-13-MAIN-SITE.md)。本轮只读核对5个生产服务running、API/WebUI healthy、4个C01容器exited；4份公开静态资源哈希与发布记录一致。未重新查询学生数据库、未运行工程测试或部署，题量/教材与下方11月12日验收不变。默认下一步为新交接第7节的上册20项缺口本地候选；主站优化为待实施建议。证据`learning_data/verification/session-handoff-20261113/read-only-state.json`；真实手机继续暂缓，不提交推送。

2026-11-12最新：按用户“将缺少的教材补齐”已上线新增7册原页阅读，当前二年级6册、七年级14册，共20册/152目录范围；新增二下数学、道法及七下英语、道法、历史、地理、生物。831个新增PDF原页全部渲染通过；66项教材/接口发布检查、99项片段兼容检查（模块有重叠）、390/1280两视口2项浏览器通过。50张表3383条既有行逐行哈希相同，1145题（418/727）和schema14保持；原13份PDF哈希相同。新7册仅原页阅读，无正式配题、无关键词索引，未用未审核OCR。线上覆盖仍subject-v5，本地math-v15/subject-v16及三道数学候选未发布。Compose learning_data/deployments/family-textbook-completion-20261112/compose.json；API/worker/gateway镜像sha256:6014a23756647d72fea8afaa074fc05b4fab7cff6e804d570bc34cc23e21c6f6。C01四容器保持停止，无模型/OCR/embedding调用、不提交推送，真实手机验收继续暂缓。验收 docs/verification/TEXTBOOK-COMPLETION-2026-11-12.md。教材补齐请求已完成；题库质量接续仍为第5节已审明的上册20项缺口本地候选，再下册；新7册不得冒称题库或知识点覆盖完整。

以下为历史发布记录。

2026-11-12语文/英语知识点缺口续批已上线：新增14题，覆盖二上语文、七上语文和七上英语的13个教材范围，全学科映射升级subject-v5。正式1145题（二年级418、七年级727），1071道章节题/schema14；658项要求为93 configured、294 partial、271 gap，另明确308项人工要求。以上是编辑映射状态，不代表课标完整率或学生掌握率。首次导入新增14题，重复导入新增0；旧题、题版和使用数据保留。
当前Compose `learning_data/deployments/family-subject-gaps-20261112/compose.json`，API/worker `sha256:34f037086c106495f0446e5153279fd1a3227c493bba1d64bdbd4c927850d05c`；仅更新API/worker，89个运行文件/服务哈希匹配。API与WebUI healthy；其他服务未变。50项内容/集成与29项发布兼容测试通过；旧章节练习浏览器复跑在1280失败、390中断，结果见本批验收。4个C01容器exited，真实手机验收仍暂缓，不提交或推送。详见[题库质量验收](../verification/KNOWLEDGE-QUALITY-2026-11-12.md)。

以下保留历史记录。

2026-11-12数学知识点质量续批已上线：5项此前缺少直接考查的要求新增10题、38个答题项；保留subject-v3全部旧映射与人工任务，升级到subject-v4。正式1131题（二年级414、七年级717），schema14；112项不同内容/集成测试及390/1280两视口通过。
当前Compose `learning_data/deployments/family-math-gaps-20261112/compose.json`，API/worker `sha256:8c62fd6735fcc5eab2fc9c778186131dff3519e586b1ccf2298089f7c3e73a33`；仅更新API/worker。4个C01容器exited，真实手机验收仍暂缓，不提交或推送。详见[题库质量验收](../verification/KNOWLEDGE-QUALITY-2026-11-12.md)。

以下保留历史记录。

2026-11-12已整理[全学科题库与教材阅读完整交接](../plans/HANDOFF-SESSION-2026-11-12-TEXTBOOKS.md)：任务、进度、未完成项及新会话命令均已列明。当天只读核对5服务running、API/WebUI healthy，1121题/schema14，C01四容器停止；未重部署。当前源清单遗留schema13元数据已校正为14，最新发布与模型验收记录保留。下一批建议做已上线题库的知识点与质量缺口核对。

以下为运行发布历史，最新阅读器版本见紧接的11-11记录。

2026-11-11教材图片悬浮翻页已上线：普通显示区和放大窗口均在图片左右上层悬浮上一页/下一页，放大翻页保持窗口和缩放比例，同步目录，失败可原地重试。4项390/1280浏览器验证通过，1121题/schema14。[验收记录](../verification/READER-OVERLAY-2026-11-11.md)。
当前Compose `learning_data/deployments/family-reader-overlay-20261111/compose.json`，API/worker `sha256:e9b9237c22212f03f0eceaac97960f037b93cbd8c5bddbdbf8ce9b69e0b88bd9`。

以下保留历史记录。

2026-11-11教材左右翻页与目录跟随已上线：图片左右按钮、整册跨章阅读/跳页、当前章节高亮/内部滚动、桌面目录随阅读区停留。保留练习范围与会话，19项教材API及4项两视口浏览器验证通过，1121题/schema14。[验收记录](../verification/READER-NAVIGATION-2026-11-11.md)。
当前Compose `learning_data/deployments/family-reader-navigation-20261111/compose.json`，API/worker `sha256:8f59022e3ea8907a11f7a583269046c7812480b05ac811979818b510b58617f5`。

以下保留历史记录。

2026-11-11教材页标题对齐修正已上线：折叠三角与页标题从同一行开始，桌面／窄屏及点击／键盘折叠核验通过。题库1121、schema14保持。[验收记录](../verification/READER-SUMMARY-2026-11-11.md)。
当前Compose `learning_data/deployments/family-reader-summary-20261111/compose.json`，API/worker `sha256:5d06454f7f81be4e020b7796b56262371b92d89a5d4f27f43d59ecd81c1e8d1d`。

以下保留历史记录。

2026-11-11第四档挑战与题型升级已上线：新增98题，13册98范围各一道；正式共1121题（二年级410、七年级711）。多选、排序与数值／单选／短答组合，共261作答项，支持恢复与可读收藏。386项单元／集成及2项两视口浏览器检查通过，旧记录保留；schema14。教师复核、真实难度校准及整章穷尽仍待完成。

[验收报告](../verification/CHALLENGE-TIER-2026-11-11.md)。当前Compose `learning_data/deployments/family-challenge-tier-20261111/compose.json`；API/worker `sha256:50ee80009a7e008f672193f61f99fbe2ba32aad9951a0fb6c3f46db6487576d8`，128源码／84运行文件，schema14。

以下保留历史记录。

2026-11-10 知识点与短答升级已上线：新增67题，正式共1023题（二年级380、七年级643）；13册276个知识点、658项要求草案，84个短答项、25条常见错答反馈。188项单元/集成及2项浏览器检查通过，旧记录保留。清单与课程标准、教师复核、真实难度仍待完成，人工能力不由自动答题计达标。

[验收报告](../verification/SUBJECT-KNOWLEDGE-2026-11-10.md)。当前Compose `learning_data/deployments/family-subject-knowledge-20261110/compose.json`；API/worker `sha256:1e9e793c797398dda28a0aa7867a7cce39162ab0d97baadcb32bdbbc665ae604`，125源码/81运行文件，schema13。

以下保留历史记录。

2026-11-10 全学科题型扩充已上线：新增180题，覆盖其余12册90范围；累计13册7学科均已做题型升级，正式共956题（二年级366、七年级590）。新增453个作答项、11道图表题，78道旧非数学题校正展示难度；自动进阶回避空档。164项单元/集成、2项两视口浏览器检查最终通过，旧记录完整保留。完整知识点、课程标准、听说写作实操与教师复核仍未完成。

报告：[全学科题型扩充](../verification/OTHER-TEXTBOOKS-VARIETY-2026-11-10.md)。当前Compose `learning_data/deployments/family-other-textbooks-variety-20261110/compose.json`；API/worker `sha256:034bb31b3a9c270b909b966dac8b8b108fb44289fc275997a6f3ec3cf6eaf181`，122源码/78运行文件，schema13。

以下保留历史记录。

2026-11-10 最新交付：[二上数学分步作答](../verification/MATH-G2-MULTISTEP-2026-11-10.md)已上线16题、48个作答项，其中8题带图表。每题逐格填数或逐项判断，全部正确才算答对，支持草稿恢复和可读的错题收藏。二上常规数学248题，正式全题库776题。151项单元/集成、8项浏览器检查最终通过，旧记录完整保留。[使用说明](../open-webui-reuse/math-g2-multistep.md)。

以下保留前批记录。

2026-11-10 最新交付：[二上数学题型与难度修正](../verification/MATH-G2-CHALLENGE-2026-11-10.md)已上线48道提高题，其中21道带图表；35道旧题重新分档，出题优先轮换不同题型。二上常规数学题232道，正式全题库760道。选择“正常/困难”可优先体验新题。[使用说明](../open-webui-reuse/math-g2-challenges.md)；141项单元/集成、10项浏览器检查通过，旧记录完整保留。整章完整覆盖与教师复核仍未完成。

以下保留前批记录。

最新状态（2026-11-09，七上知识点续批）：七上数学新增136题已上线，正式题库712题（二年级258、七年级454）。34个知识点均有对应或辅助练习；修正旧题证据分类与题型合并后，6/136项达到两种对应题型目标、52项仍没有直接考查题，不能称为完整覆盖。[验收记录](../verification/MATH-KNOWLEDGE-G7-2026-11-09.md)保存132项单元/集成、5项浏览器通过及旧行保全证据；[9项任务单](../open-webui-reuse/math-g7-practical-tasks.md)补充表达、建模与作图。当前Compose为family-math-knowledge-g7-20261109，仅API/worker升级。

以下保留前批记录。

最新状态（2026-11-09，二上知识点续批）：二上数学新增88题已上线，正式题库576题（二年级258、七年级318）。二上19个知识点都有映射练习，28/76项能力达到两种对应题型目标；39道辅助选择题单列，口述/实测仍有缺口。[上线验收](../verification/MATH-KNOWLEDGE-G2-2026-11-09.md)记录127项单元/集成及5项浏览器通过、旧记录保全和当前镜像。[7项操作任务单](../open-webui-reuse/math-g2-practical-tasks.md)可用于线下观察，完整知识覆盖仍未完成。

前批状态（2026-11-09）：家庭学习章节补题已部署。新增414道本地自编题，13本教材、98个目录范围均有起步题；API/worker使用章节补题镜像，网关仍为B11镜像，WebUI与代理保持不变，入口https://172.19.116.53。二上/七上数学新增53个知识点、212项能力的缺口表草案，尚未完成课程标准/教师复核，因此不表示整章知识覆盖完成。详见[章节补题上线验收](../verification/CHAPTER-PRACTICE-2026-11-09.md)及[当前题目与缺口审阅包](../../learning_data/verification/chapter-practice-20261109/final-review/preview.html)。

此前B11/C01部署和模型验收记录继续保留：[部署验收](../verification/DEPLOY-B11-C01-2026-11-09.md)通过；[C01最终报告](../verification/C01-real-model-2026-11-09.md)原24/24、开发补充3/3在同一v17冻结下技术通过，189/300请求、185次生成、固定订阅增量CNY0。追加窗口53.59/60分钟完成，模型已停止。[逐句教学评审](../verification/C01-teaching-review-2026-11-09.md)真人签署pending，手机暂缓。[最终交接](../plans/HANDOFF-SESSION-2026-11-09-DEPLOY-C01.md)保留为历史部署入口。

以下是保留的历史准备与阶段记录；其中旧“未运行/待授权/待修复/下一步”只描述当时状态，当前以以上最终记录为准。

最新接续（C01离线Tool夹具）：C01离线Tool协议夹具完成：合成PDF/PNG、书章符号绑定及完整回包已固定，六个只读方法的22个预设Tool步骤通过，10项定向检查通过。24个模型情景仍全部not_run；本批没有运行真实网关/服务/模型，不是选工具或教学质量验收。B11手机继续按用户指令暂缓，桌面与打印结果保持；运行候选、原性能基线和12秒预算不变。 [独立记录](../verification/C01-tool-fixtures-2026-11-08.md)。

C01离线用例及Tool协议夹具已准备；真实执行仍等待明确改变调用限制、提供方/模型版本、公开或合成材料范围、预算与实际复核者/教学阈值。届时先另建隔离服务/网关环境并冻结材料与提示，再执行；本批不能代替端到端环境或真实模型验收。手机暂缓，不重跑未变检查。 线上观察时间和现有候选包均未刷新。

以下保留历史记录。

最新接续（手机暂缓 / C01离线准备）：用户已明确暂缓B11真实家庭手机验收，记录为deferred_by_user，设备及结果仍为空；桌面浏览器7项与HP 102w/Chrome三页纸张通过保持，B11仍ready/candidate_only/pending/open。继续完成C01获准的离线准备：24个合成情景、六方法契约、人工评分规则与空白执行记录已冻结。真实模型执行仍deferred/gated，未调用、未评分、未部署。 [独立记录](../verification/C01-offline-preparation-2026-11-08.md)。

C01离线情景准备完成；真实执行等待限制变更、提供方/模型版本、公开或合成材料、调用预算、兼容隔离环境及实际复核者/教学阈值明确后另行冻结。B11手机按用户指令暂缓，不重复催验；其他外部验收继续独立保留。 本次只更新验收安排与离线设计，运行候选99文件、静态9资源、原性能证据和12秒预算保持；线上观察时间未刷新。

以下保留历史记录。

最新接续（实际纸张打印通过）：B11实际纸张打印已通过：用户反馈HP 102w、Chrome、3页正常；原文与此前提供的三页复习卡PDF哈希已独立保存。桌面浏览器7项通过和入口问题关闭保持，桌面与纸张范围现均通过。B11只剩真实家庭手机验收，仍为ready/candidate_only/pending/open；候选、原性能基线和12秒预算保持，未提交/推送/部署。 [纸张验收记录](../verification/B11-paper-print-2026-11-08.md)。

下一步：B11剩余真实家庭手机验收：记录设备/系统/浏览器及入口、触屏/双指缩放/软键盘、中文公式、切档隔离和断连恢复等实际反馈。桌面浏览器7项和HP 102w三页纸张打印已通过，不重复未变验收；手机未知项继续留空。

以下为历史记录。

最新接续（桌面入口已复验）：B11本机真实桌面浏览器7项已通过：user01已保存家庭学习入口复验通过且备注为空，和先前6项反馈合并计7项；原DNS问题按验收环境修复并经人工复验关闭，失败/诊断证据全保留。环境Ubuntu24.04.4/WSL2/WSLg＋Chrome146.0.7680.177，纸张打印未做、家庭手机待验。运行候选及B10原12/12门槛、12秒预算不变，B11总状态仍pending/open，未提交/推送/部署。 [真实桌面验收](../verification/B11-desktop-acceptance-2026-11-08.md)。

下一步：桌面浏览器7项已通过，无需重复未变检查。B11下一步收集真实家庭手机的系统/浏览器、触屏/双指缩放/软键盘及相关流程反馈；实际纸张打印与可读性另验。暂无手机或打印结果继续留空，不代签、不自动发布候选。

以下为历史记录。

最新接续（桌面反馈）：B11已收到本机真实桌面反馈：user01三次相同保存按一次处理，6项通过；家庭学习入口虽勾选通过，但备注与后续确认有DNS错误，单列待复验。小型探针复现验收拦截环境的303跳转漏接，修正本地会话的跳转/Cookie传递后，真实网关登录入口技术复查通过，新窗口只等待入口人工复验。纸张打印未做、家庭手机未验；运行候选、B10原12/12门槛和12秒预算保持，B11继续pending/open。 [独立反馈复核](../verification/B11-desktop-feedback-2026-11-08.md)。

下一步：在当前“B11 家庭学习入口回验”窗口中，从主站侧栏进入家庭学习并提交登录页，再保存唯一入口项；读取本批 recheck-session/human-feedback.jsonl 或用户明确反馈后再判定桌面入口通过。已有6项真实桌面通过保留，不整套重做。纸张打印和家庭手机继续独立待验，未发布/调用真实模型。

以下为历史记录。

最新接续（2026-11-08 B11）：B11本地工程验证完成：修复上游编辑器失效/异步替换时的填入保护、断网同档案草稿恢复、填入焦点及切档历史聊天提示，补齐缩放和触控尺寸。54项单元/契约、21项浏览器用例及固定WebUI0.12.5原生两视口通过；99文件源码候选、9资源静态候选/回退校验完成。B10后端及原性能12/12证据保持。用户确认暂无实际设备记录，B11为ready/candidate_only/pending/open，未提交/推送/部署。 [独立记录](../verification/B11-host-compatibility-2026-11-08.md)。


最新接续（2026-11-08 读取调度）：B10读取调度本地出口完成：先冻结线程诊断及两项隔离试验，采纳保持原检查体的进程内读取作用域串行调度；195个不同单元/契约用例通过，原900请求矩阵全部成功且输出一致，原P95门槛12/12通过。98文件schema13候选及旧97文件回退校验通过，UI/Tool未变证据按hash复用；未提交/推送/部署。B10为ready/candidate_only/passed/complete，B11尚未启动。 [独立记录](../verification/B10-thread-scheduling-2026-11-08.md)。

最新接续（2026-11-08 原页阶段）：B10原页逐请求阶段归因完成：3组450请求成功且输出与原基线一致、各组合成数据库前后不变。暖原页材料P50约11.92ms，服务函数体外约319.90ms；只读连接初始化变体和GET围栏透传变体的并发P95均未达预设采纳门槛，均只保留隔离证据。工作区运行代码及97文件候选不变；原验收10/12，B10仍in_progress/pending/open，B11未启动。 [独立记录](../verification/B10-page-stages-2026-11-08.md)。

最新接续（2026-11-08 portal归因）：B10 portal归因与隔离异步依赖试验完成：3组450请求全部成功、输出与原基线一致、各组合成数据库前后不变。复用portal使四并发暖原页P95由561.10降至352.25ms；两个内存依赖改async的隔离变体为580.47ms，未达预设采纳条件，未应用到工作区运行代码。原验收10/12，B10保持in_progress/pending/open，B11未启动。 [独立记录](../verification/B10-portal-attribution-2026-11-08.md)。

最新接续（2026-11-08 HTTP诊断）：B10本地HTTP对照诊断完成：旧95/新97文件候选×TestClient/隔离loopback，48配置、3600请求全部成功且输出与原基线一致。运行源码未变；HTTP与TestClient的传输/进程/portal拓扑不同，不将差值单独归因于网络或依赖函数。本批不实施缺乏单变量证据的运行优化；原性能验收仍10/12，B10保持in_progress/pending/open，B11未启动。 [独立记录](../verification/B10-http-diagnostic-2026-11-08.md)。

最新续批（B10尾延迟，2026-11-08）：同步只读操作内复用连接，原页每请求连接12→4、检索14→6、会话2→1，SELECT数量和身份/证据校验顺序保留。166项定向单元/契约与2项浏览器通过；900性能请求成功且输出一致，原门槛10/12通过，原页单请求冷缓存/四并发暖缓存仍未达。97文件schema13候选及旧95文件回退兼容已校验。本批未提交/部署，B10仍in_progress/pending/open，下一步先冻结loopback诊断；旧失败、此前11个本地提交和A09等独立验收保持。 [独立验收](../verification/B10-tail-latency-2026-11-08.md)。

Git交付更新（2026-11-08）：B01–B10已按10个独立候选提交到本地main，覆盖93个不同公开文件，终点1021ff80268d；交付记录与台账另作文档提交。未推送/部署，既有源码及历史证据保留。B10的4/12性能配置仍未达标，下一项继续B10尾延迟；B07/B08外部条件、B05反馈、B04待解、B02真实观察和A09发布/家庭验收保持独立。[分批提交记录](B01-B10-git-delivery-2026-11-08.md)。


最新执行（B10，2026-11-08）：B10首批缓存与12秒总截止候选完成，248项不同单元/契约和2项浏览器通过；前后各900性能样本全部成功且输出一致，但冻结P95门槛仅8/12配置通过，4项未达。追加300样本诊断已定位到需继续细分的会话复核/服务调度链路；不降低身份/证据检查。95文件schema13源码候选及B09回退兼容已校验，Tool候选1.2.1；未提交/部署。B10工程in_progress、验收pending、总状态open，下一项继续B10尾延迟，不先记为完成。B07独立备份、B08外部观察端、B05家庭反馈、B04待解、B02真实观察与A09发布/家庭验收仍单列。[独立验收](../verification/B10-study-performance-2026-11-08.md)。


最新执行（B09，2026-11-08）：B09首批本地工程完成：拆出7个教材/伴学只读路由、读取校验与证据类型，收紧检索响应；补齐验证发现的B05/B06四个既有API网关转发方法/路径。286项不同单元/契约、2项浏览器通过，91文件schema13源码候选已校验，OpenAPI76路径/44模型。工程ready、本地验收passed、首批出口complete；未提交/部署，不代表全应用重构。下一项B10先冻结合成性能基准再测量。B07独立副本、B08外部监控未配置、B05家庭反馈、B04待解、B02真实观察与A09发布/家庭验收继续单列。[独立验收](../verification/B09-evidence-modules-2026-11-08.md)。


最新执行（B08，2026-11-08）：B08本地最小运行观察完成：采集器兼容schema11/12/13，补齐队列/租约及心跳异常检查；48项定向测试、10个CLI演练场景通过，7文件维护包已校验。B07的86文件运行包保持原哈希。工程ready、本地验证passed；正式监控/阈值、独立观察端及责任人未落实，验收pending、B08总状态open。下一项B09窄范围证据模块/响应类型拆分；B07独立副本、B05家庭反馈、B04待解、B02真实观察及A09发布/家庭验收继续单列。[独立验收](../verification/B08-minimal-monitor-2026-11-08.md)。


最新执行（B07，2026-11-08）：B07本地合成备份/校验/隔离恢复完成：51项定向测试通过，28组业务指纹一致、丢失0，恢复及对账0.374624秒；86文件schema13源码候选已校验。工程ready、本地验证passed；独立副本位置及保管人按用户答复仍为null，正式RPO/RTO未验收，验收pending、B07总状态open。下一项B08本地最小运行观察，先核对采集器schema11与当前schema13兼容；不启用生产监控或外部通知。B05家庭反馈、B04图形待解、B02真实观察及A09发布/家庭验收继续单列。[独立验收](../verification/B07-backup-recovery-2026-11-08.md)。


最新执行（2026-11-08）：B06本地工程完成：服务端轮次/范围/档位及当前会话恢复、同答幂等与异答冲突保留；92项不同单元/契约用例、8项浏览器通过，85文件schema13源码候选已校验。工程ready、本地验收passed、任务出口complete，未提交/部署；模拟设备不代替家庭验收。下一项B07先用合成数据演练一致性备份和隔离恢复，独立副本位置与保管责任待落实。B05家庭反馈、B04图形待解、B02真实观察及A09发布/家庭验收继续单列。[独立验收](../verification/B06-practice-recovery-2026-11-08.md)。

2026-11-08 B05最新本地候选：[显式错答收藏与到期复习](../verification/B05-practice-collection-2026-11-08.md)完成82单元/契约+6浏览器；schema12、`reuse-runtime-practice-collection-v1`、83文件源码包就绪。运行源码已相对B02变化，旧包继续作为历史证据，线上观察仍为A01；未提交/构建镜像/迁移正式库/部署。家庭反馈pending、B05总状态open，下一项 **B06**。

2026-11-08 B04最新本地记录：[二下首批完整页复核](../verification/B04-full-page-review-2026-11-08.md)完成连续5页处理，4页助手完整双步骤通过、1页图形待解，教师/题目/答案/判分资格均0。仅新增独立离线材料与公开汇总，运行源码和A01线上观察不变；未提交、入库或部署。下一项 **B05**；B04待解、B02真实观察与A09发布/家庭验收单列。

2026-11-08 B03：[独立片段复核工作台验证](../verification/B03-passage-review-2026-11-08.md)完成50单元/契约+2浏览器、实际1片段助手复核与16文件维护封包；本地出口complete。完整页审核仍0，未提交/部署，未改A07或B02运行包。下一项B04；B02真实观察与A09家庭验收待办，线上观察仍沿用A01。

2026-11-08 B02：[备用练习候选与验证](../verification/B02-reserve-practice-2026-11-08.md)完成12题/每档4题、题版冻结与未见选择，103单元/契约+4浏览器通过；81文件源码profile `reuse-runtime-practice-reserve-v1` 已校验，未构建/提交/部署。B02真实延迟观察pending、总状态open，继续B03；线上观察仍沿用A01，A09发布/家庭验收另列。

最新本地进度（2026-11-08）：**B01独立离线覆盖表完成，下一项B02**。[验收](../verification/B01-chapter-coverage-2026-11-08.md)记录19行、12道应用题（旧4+新助手候选8）、5有效片段及22+2定向检查；[使用说明](../open-webui-reuse/chapter-content-coverage.md)。本批未提交/部署，旧概念库、题库、服务与范围规则不变。A09发布/家庭设备及家长验收仍pending；线上观察时间仍为A01。

最新执行（2026-11-08）：A09 本地静态交付准备已完成，工程 ready，发布与家长设备验收 pending，总状态 open；下一项可继续 **B01**。[本地验收](../verification/A09-static-samples-2026-11-08.md)记录 30 项定向检查和隔离 nginx 候选 4 / 回退 3 条路由通过；[交付与设备检查表](../open-webui-reuse/static-samples-delivery.md)已就绪。九文件固定提交与旧样本一致，当前 A07 桥接未混入。以下各批次更新保留历史语境。

最新本地进度：**A08已完成，下一项A09**。[54项与原生迁移/六方法/历史/缓存验证](../verification/A08-tool-lifecycle-2026-11-07.md)通过，[升级回退操作单](../open-webui-reuse/tool-upgrade-rollback.md)与独立维护包就绪。正式Tool未读取或升级，A07服务/Tool1.2.0候选保持原样；下方各批次结果保留历史语境。

最新本地进度：**A07已完成，Tool候选1.2.0，下一项A08**。五片段已接入服务/网关/Tool及引用回链，默认关闭、未部署；688项单元/契约、6项浏览器、原生六方法/4引用通过。[A07验收](../verification/A07-runtime-passages-2026-11-07.md)与[运行契约](../open-webui-reuse/textbook-passages-runtime.md)。下方线上观察时间保持A01，不冒称刷新生产。

核对时间：2026-11-07 17:00:50–17:00:53（Asia/Shanghai）。任务：A01。机器可读事实见 [current-manifest.json](current-manifest.json)，本次核对方法和验收见 [A01 验证记录](../verification/A01-current-state-2026-11-07.md)。这是带时间的状态快照，不是新发布记录。

执行更新：A03 已完成[可移植测试基础](../TESTING.md)，干净环境 **503 项单元/契约 + 12 项浏览器通过，零失败、零跳过**，详见[A03 验证](../verification/A03-portable-tests-2026-11-07.md)。GitHub 自动检查为本地候选，远端未执行；实物教材组未运行。下方运行状态仍沿用 A01 的观察时间，A03 未再次查询运行组件或改变部署。A02 已完成[两组候选整理](A02-candidate-delivery-2026-11-07.md)，[本地验证](../verification/A02-candidate-delivery-2026-11-07.md)通过、待提交。A02 没有修改代码或重跑测试。A04 已完成[故障分类与恢复](../open-webui-reuse/study-error-recovery.md)，[552 项单元/契约及原生六方法验证](../verification/A04-study-errors-2026-11-07.md)通过，候选 Tool 1.1.1；本批未重跑浏览器。A06 已完成[冻结评测与基线](../verification/A06-retrieval-evaluation-2026-11-07.md)，73 项合成测试通过；新试点召回 2/20、无依据拒绝 2/10，质量未达标。A05 已完成[有界检索与不足判定](../verification/A05-chapter-retrieval-2026-11-07.md)，补充集召回 20/20、拒绝 10/10、泄漏 0/10，241 项单元/契约、4 项浏览器及原生六方法通过；A05当时Tool候选1.1.2、下一项A07；当前已由上方A07更新。

当前仓库为 `main`，HEAD `deef3199f558ba72bbe3f2ff0c704586674a2232`；本地 `origin/main` 指向同一提交，本次未访问远端。开始时有 19 个未提交/未跟踪文件，逐文件 SHA256 保存在清单的 `workspace.input_dirty_files`。这是本批开始前的指纹，不包含后来修改的 A01 文档，也不代表线上版本。原有业务候选保持原样。

## A01 组件状态（历史快照）

| 组件 | 当前状态 | 依据与验收范围 |
| --- | --- | --- |
| 家庭 API / worker / gateway | 已部署；三者同一镜像 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0` | 本次定向检查均 running，API healthy；另两者没有 Docker healthcheck，不能记为 healthy |
| 主站 Open WebUI | 已部署；镜像 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd` | 本次 running / healthy；0.12.5 版本号沿用固定镜像的[既有原生验证](../verification/main-chat-study-2026-11-07.md)，没有读取正式 data |
| nginx 代理 | 已部署；镜像 `sha256:1d13701a5f9f3fb01aaa88cef2344d65b6b5bf6b7d9fa4cf0dca557a8d7702ba` | 本次 running；主站实际 `set $webui http://open-webui:8080` 后 `proxy_pass $webui`，不能只搜索直接写出的 proxy_pass 判断目标 |
| 主站静态资源 | 在线 `chat-20261107` | 三条 alias 与匿名 HTTPS 文件哈希一致，均 200 / no-store；未发送登录或聊天请求 |
| 三个静态样本 | 样本源码已提交、A09准备脚本未提交；未上线 | 九文件来自固定 `deef3199`，与历史样本一致；新独立包与原资源回退已验证。工作树 A07 桥接另属片段候选。[A09验收](../verification/A09-static-samples-2026-11-08.md)记录30项及4+3路由通过；家长反馈 pending |
| 私有 Tool `dd_family_study_readonly_v1` | 历史发布记录为 1.0.0 | 仅沿用注册/验证记录，正式源码和分享范围本次未重读，当前值为 unknown；不得据此重跑注册或重绑 |
| 页级证据链 / Tool 1.2.0 | 未提交、未部署候选 | A07默认关闭片段接入；688项单元/契约、6项浏览器、原生六方法/4引用通过。A05的1.1.2结果保留历史；候选镜像尚无 |
| 七上第二章五片段 | 已接本地候选服务/Tool，默认关闭 | 书内 27/31/40/41/42 页，PDF 34/38/47/48/49 页；清单及源 PDF 哈希匹配；助手复核、非整页/教师审核、非判分依据 |
| 离线检索评测 | A06 本地交付完成、未提交 | 40 问冻结试点，召回 2/20、拒绝 2/10、泄漏 0/10、来源/引文 11/11；两次结果一致，质量改进待 A05 |
| 五片段检索改进 | A05算法原样抽取，A07已接本地服务 | A06 回归 40/40、补充集 40/40；召回 20/20、拒绝 10/10、范围泄漏 0/10、来源/引文 22/22。整册向量召回仍不完整 |
| 既有Tool维护候选 | A08本地通过、未正式应用 | 54项及固定WebUI原生schema/历史/缓存验证，操作单与独立维护包就绪 |
| 教材与题库 | 历史清单：13 册 / 98 目录区间 / 74 题 / 20 题映射 18 概念 | 沿用[项目评审](../PROJECT-REVIEW-2026-11-07.md)，本次不重计正式数据库；二下 OCR 106 页已完成，整页双重审核通过 0 页 |
| API 契约 | A07本地快照73 paths / 35 schemas | 临时服务OpenAPI与快照一致；不代表已上线 |
| 可移植测试基础 | A03 本地验收通过、未提交 | 27 个依赖及分发哈希锁定、合成 PDF、根测试隔离、可配置 Chromium 和 515 项必要检查；GitHub workflow 已编写、远端未运行 |

当前 Compose 固定为 `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`。主站入口 `https://172.19.116.53/`；活动代理配置为同目录的 `main-study-20261106/nginx.conf`。不用旧 P0 容器或旧 Compose 推断/替换这组部署。

## 源码、构建与内容身份

家庭服务对应的历史源码封包为 `learning_data/releases/dd-study-workbench-20261106-source-v2/`，profile `reuse-runtime-study-workbench-v1`，70 文件，声明 schema11。封包时 Git SHA 为 `0fa02712ceda049b14d4b556faef3fdb2fa985ed`，**当时工作树也有改动**，因此以源码集合哈希定位：

- source set：`ad18b0aa5e0670e694939facb018ab5ca8380fa04849e1f71347f03e8bd9b727`。
- source archive：`baf54a0124c02bfe61047346cd9e4dc524a868cfa673c8d41270110276907b8e`，本次实际归档哈希匹配。
- 构建记录：`learning_data/verification/study-workbench-20261106/build/build.json`，源码集合/归档与封包对应，image ID 与当前三服务对应。

封包 manifest 自身的 `image_digest=null` / 未部署措辞保留封包时语境；运行结论来自独立[构建与发布记录](../verification/study-workbench-2026-11-06.md)和本次容器观察。当前运行数据库 schema 未读，镜像的 registry digest 未知，不以本机 image ID 冒称仓库发布 digest。

| 对象 | SHA256 | 本次核对方式 |
| --- | --- | --- |
| 线上 study.js | `6e2325ad44c246351e00f4f8bc480dbcdcef4912f90085696793b208524db7e4` | HTTPS 字节与 chat 快照一致 |
| 线上 study.css | `b7ea956e897b0bf12a26f55e0213b794a924ff8c10e02647e83de8027514627a` | HTTPS 字节与 chat 快照一致 |
| A01线上及当时样本 family-bridge.js | `8bfe564373befe4d3bb64cfc4d91b67880545217f00d293da415938cce4f0347` | HTTPS / 快照 / HEAD / 候选一致 |
| 样本 study.js | `fe26d4d4ae6834944fd093d9954808b118b7706daeb1aa42df459090cf75518d` | HEAD / 工作树 / 候选 / 原记录一致 |
| 样本 study.css | `952fddccb9e5366d350b0bd9bebf88fe76ebeea6861bed9b6d9fa7e697af292a` | HEAD / 工作树 / 候选 / 原记录一致 |
| Tool 1.0.0 | `733ad01dc38ed6b09fcae69047ff731e0eb83d59b0a2dd2432595a3508c6a650` | **历史注册证据，非本次正式库回读** |
| A05历史Tool 1.1.2 | `a158f47774062a454d6c12bb9944d1b480542ddafba384b71fd0103987afedd1` | A05 本地候选、149 文件副本及原生加载结果一致；旧 1.1.1 保存于 A04/A06 包 |
| A07当前Tool 1.2.0 | `23fc5c2558a0141750031acaee434f7b0abd81d884974e8d15ee781c1f2404d7` | 本地源码与原生六方法/4citation一致 |
| A07候选family-bridge.js | `876cb599ea7c1729bde5964138b4f22d5fdcd8ea6a580004c6b4807b4f3c7ab7` | 新增片段回链；历史静态样本快照不改，部署本桥接需配套A07服务 |
| 五片段 passages.json | `d1bf256db814afcf35ff22f28ad32fd4577b4608e12f9d069b7f72cfc8cacd63` | 本地忽略目录中的文件哈希 |

五片段复核记录均为 revision 1、2026-11-07 至 2026-12-07，enabled=true、未解决问题 0；本次日期处于该区间。A01只核对元数据与PDF哈希；A07已执行完整材料校验和既有题集回归，未重新学科复核或教师签署。使用时按服务器当前日期验证，到期停止并复核，不能用历史 `--as-of`；A07已冻结北京时间valid_until含当天、次日零点失效。保留 `teacher_reviewed=false`、`fully_reviewed_pages=0`、`eligible_as_grading_basis=false`、`can_answer_from_textbook=false`。教材正文和图片继续仅存本地忽略目录。

## 兼容组合与回退

| 组合 | 可据以开展的工作 | 尚未证明或禁止混用的部分 |
| --- | --- | --- |
| 当前家庭镜像 + WebUI 0.12.5 + chat 静态 + 历史 Tool 1.0.0 | 保留当前运行组合；容器/静态已复核 | 正式 Tool 本次未回读；真实聊天/设备反馈未新增 |
| 当前后端 + 三个静态样本 + 原 Tool | A09 可独立交付准备，已有隔离浏览器/nginx 证据 | 未上线；先满足 A03，不必等待片段服务或 Tool 升级 |
| 页级服务/覆盖不足候选 + Tool 1.1.2 | A05 241 项单元/契约、4 项浏览器与原生六方法支持本地接续 | 未封包为镜像、未部署；完整错误细分需相容网关/服务，不能单独把新 Tool 装到当前旧后端 |
| A07后端 + 历史Tool 1.0.0/1.1.2 | 使用hash一致的历史源码独立检查通过 | 只保留页定位，不获得片段正文权限；未回读正式Tool |
| 五片段 + A07服务/Tool1.2.0 | 本地接入与回链通过，默认关闭 | 未部署；真实模型/家长体验未验收，继续A08 |
| Tool1.2.0 + A05页级服务 | A05源码副本仅替换Tool，原30项集成检查通过 | 不等于缺少页级字段的历史线上服务兼容 |

静态样本回退基线是 `chat-20261107` 和 `learning_data/verification/main-study-samples-20261107/candidate/nginx.before.conf`；该文件哈希 `fcb3e8131090dbc5f89ad2b07186b0d17b897658a1c8cf9e18562bd3b7d0676a` 与本次活动配置一致。候选 `nginx.candidate.conf` 哈希 `e6c6b11d1696b79a766249c57baa6de237b4296f2dd0bec58c31d95678b19756`，仅作为后续 A09 的候选引用；正式应用/回退仍需检查当时配置和候选操作单，本次没有 reload。

家庭镜像保留上述当前 image ID/Compose 作为未来升级的输入；跨数据库/附件恢复仍待 B07。A08既有ID升级与哈希保护回退已在临时库通过，正式应用仍未执行，不能用注册脚本覆盖不同源码。片段尚无线上部署可回退。以上回退引用没有冒充本次已完成恢复演练。

## 接续

A01 验收“现状、身份、兼容、回退引用和入口一致”，A03 验收本地可移植测试与自动检查候选，其他任务的发布/实际体验状态分别保留。A02 本地交付整理已通过，46 个文件组成 U1/U2 两组，提交 SHA 均为 null，总状态保留 open。A04 本地故障分类与恢复验收通过，作为 A02 后的独立增量保存；A02 清单哈希只对应其固定审阅包。A06 本地评测交付已完成，基线检索质量未达标，独立增量与真实材料仍分开保存。A05 已完成本地有界试点与旧路径覆盖不足提示，质量结论仅限所测范围。A07已完成本地接入；A08已完成本地机制；下一项 **A09：三个静态样本交付与设备体验**；提交等待不阻塞本地工作。材料盘点不等于备份/恢复通过。进度以[25 项台账](../plans/dd-next-work-tracker.json)为准，继续指令见[续接文件](../plans/RESUME-NEXT-WORK.txt)。
