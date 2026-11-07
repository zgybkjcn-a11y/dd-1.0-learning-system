# 家庭数学版：人教新版教材接入与 OCR 双重审核

> **最新状态见 [2026-11-07 总交接](HANDOFF-SESSION-2026-11-07-SESSION-SUMMARY.md)**：二下数学 106 页已完成本机离线 OCR，完整页双重审核仍为 0，尚未入库；二下语文已有原生 PDF 阅读参考。主站六方法 Tool 已注册并上线，当前 Compose 为 `compose-main-study-20261106.json`、静态快照为 `chat-20261107`。下文较早的“未下载/未 OCR/未注册”等表述保留为历史，质量约束继续有效。

> 2026-11-07 最新：主站原生聊天已注册私有六方法“课本伴学（只读）”，并新增聊天框旁教材检索、学科助手、分步讲解、检查思路、关联练习快捷提问。点“打开课本聊天”会在新标签页自动选中工具；原页引用可定位家庭阅读器。用户已明确授权此接入，正式 WebUI 仅新增目标 Tool/历史两行，未改其他数据或模型。当前静态快照 `main-study-20261106/assets/chat-20261107/`，Compose 不变，仅 nginx reload；未调用真实模型、未写 Goal。详见 [原生聊天接入验证](../verification/main-chat-study-2026-11-07.md)。

> 2026-11-07 最新：用户明确指定的 **cn-math-taxonomy + faststudy-knowledge** 已接入主站“学科伴学 → 知识路线与关联练习”：选概念、看先修/原页、按难度选已映射题、到家庭页显式开始，保留未完成题确认与档案隔离。仍是原74题（29道上游改编），精确映射20题/18概念，非全学科覆盖。静态快照更新为 `main-study-20261106/assets/knowledge-20261107/`；Compose 仍为 `compose-main-study-20261106.json`，仅 nginx reload，五容器未重启。详见 [两项目主站采用验证](../verification/main-study-knowledge-2026-11-07.md)。

> 2026-11-07 后续最新：主站学科伴学新增“开始分步课堂”“下载离线课堂”，深化 DeepTutor 编号参考/原页核对与 OpenMAIC 四步课堂/离线 HTML 设计采用。当前静态快照为 `main-study-20261106/assets/classroom-20261107/`，Compose 仍为 `compose-main-study-20261106.json`，只 nginx reload、五容器未重启。家庭资料互通保持；无真实模型/外部 OCR/正式 Tool 注册/Goal 写入。详见 [当前课堂验证](../verification/main-study-classroom-2026-11-07.md)。

> 2026-11-07 最新：学科伴学已打通家庭学习当前档案、课本/章节、理解工坊和原页；同浏览器家庭页选择可同步，主站可预览公开参考再填入聊天。Compose 仍为 `compose-main-study-20261106.json`，静态快照更新为 `main-study-20261106/assets/bridge-20261107/`，仅 nginx reload，五个容器未重启，服务镜像保持。初次需刷新主站和家庭页。未改正式 WebUI data/Tools、未调用模型、未写 Goal。详见 [互通验证](../verification/main-study-family-bridge-2026-11-07.md)。

> 最新主站入口更新：HTTPS 主站侧栏已上线“家庭学习”和“学科伴学”（DeepTutor 资料伴读 / OpenMAIC 分步学习设计参考，七学科、请求预览、填入聊天框、下载提纲）。当前 Compose 改为 `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`；仅 proxy 增加只读静态挂载并重建，家庭 API/worker/gateway 仍为 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`，其余容器 ID/启动时间保持。正式 WebUI data/Tools 未改，未调用模型。详见 [上线验证](../verification/main-study-sidebar-2026-11-06.md)。下文旧 Compose 状态为历史，勿覆盖。

2026-11-06 后续当前：已上线 [理解工坊](../verification/study-workbench-2026-11-06.md)，最新Compose `compose-study-workbench-20261106.json`，镜像 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`。教材/档案/可选章节联动阅读步骤、数学局部参考与演示、原页放大及学习卡下载；20道题/18概念的小样本映射不等于全书掌握或判分依据，其他学科只有阅读问题串。74题/两档案/一绑定/67次作答判分及13册PDF保留，provider0；未重绑、重建卷、触碰正式WebUI数据或重启WebUI/proxy。四题升档规则不变。正式Tools仅提供已验证适配器候选；未注册。下文旧Compose为历史，不要覆盖当前部署；二下未审核OCR仍不能用于出题/判分，不写Goal API。

2026-11-06 当前最新：[自动升档改为四道不同题](../verification/practice-four-2026-11-06.md)。用户认为两道不足，采用3～5中的4道：同档连续独立答对4道不同题才尝试下一档，界面显示累计/剩余数；重复题不累加、错误/提示中断累计，主动重练可重新巩固。已上线Compose `compose-practice-four-20261106.json`，镜像 `sha256:d94346e8ec8fada893f288aac5fddd8f26a1b6078d4eb23b1af9bfd2cc64e6cc`，57文件/schema11。5项相关测试与线上核验通过，74题、原绑定/两档案/53次作答保持，WebUI/代理未重启，provider0。题库和原教材/OCR限制不变；保存当前输入后刷新。下文两题规则与旧Compose为历史，勿覆盖。保留所有未提交改动，不写Goal。

2026-11-06 当前最新：已上线[三档应用题与连续出题](../verification/adaptive-practice-2026-11-06.md)。新增60道生活应用题（二上第二/三/五单元36题，七上第二/五章24题），原14题保留，总74题。可选简单/正常/困难，默认根据独立答对与提示情况自动进阶；“继续出题”不重复本轮已做题，用尽明确提示；每题提示/答后折叠解析。29道来自固定commit开源题库改编、31道助手编写，逐题语义核查与独立复算，并非教师审核；其余章节学科仍未配题。当前Compose `compose-adaptive-practice-20261106.json`、镜像 `sha256:e40cec471ba75bd766d4cb0a9c5f3c9b94587f80238542f4a02c5b5615348e90`，57文件/schema11。40项相关测试及上线核查通过，原题/绑定/53次作答完整保留，13册PDF保持，原WebUI/代理未重启，provider0。家长保存输入后刷新即可，无需重绑。先读验证记录与[项目调研](../verification/math-practice-project-research-2026-11-06.md)，不要重新导入旧题库或用下文旧Compose覆盖。保留所有未提交改动、教材/OCR约定，不写Goal，不调用外部生成模型。

2026-11-06 最新布局调整：目录缩为136～168像素，右侧教材页加宽；“当前范围、展开/收起”并入翻页/跳转工具栏右侧，宽屏同排、窄屏自适应换行。五种视口和原页翻阅/放大检查通过，详见[布局验证](../verification/reader-toolbar-layout-2026-11-06.md)。当前Compose `compose-reader-toolbar-20261106.json`，镜像 `sha256:82a2388392bc6577a9775d1a6188a21b94924a7c3af87dbfbbf8082d0b3dc9b6`；数据保持，原WebUI/代理未重启。章节可选、统一范围和原图缩放功能保持；下文旧Compose为历史，勿覆盖。

最新状态（2026-11-06 统一学习范围与单页阅读）：用户明确要求章节非必选，已合并“学科→课本→章节（可选）”，默认整本书；挑战/下一题/复习/阅读跟随同一范围，支持本册章节卡片，未配题禁用挑战。教材改为左侧目录、右侧单页，支持目录定位、前后翻页、页码跳转；原图可点击放大、缩放/适应宽度、Esc关闭并保留阅读位置，手机目录可折叠。详见[最新验证记录](../verification/unified-textbook-reader-2026-11-06.md)。当前Compose `compose-unified-reader-20261106.json`，镜像 `sha256:417274d9a8da2af3d8982728d06488ded79443ad82e9130722b871c343aafb6e`，候选 `dd-v1-family-unified-reader-20261106-final`；54项相关测试及真实页/上线核验通过。13册/1,948片段及数据保持，未新增题目：二上数学4道乘法按第二/第五单元分为1/3题，七上第二章6题；原4道二年级加减题记录保留、不混入新版教材。其余范围暂未配题。旧四页纵向列表和分离的练习/教材选择已替换；勿用下文旧Compose覆盖。用户刷新后实际体验待反馈，原限制不变。

最新状态（2026-11-06 多学科与折叠，已上线）：以[多学科阅读验证与部署](../verification/textbook-subjects-folding-2026-11-06.md)为准。二年级提供语文、数学、道法，用户确认学校暂未开英语；七年级提供语数英、道法、历史、地理、生物，物理/化学按八/九年级开设。当前13册/1,948片段、98个章节区间，新增二上道法73片段并保留原25条文件记录。无关键词从章节开头顺序浏览，每组四页；关键词结果按书内页码升序。每页有内容标题，默认折叠，支持全部展开/收起、逐页折叠和页底收起，原图与放大链接保持准确。整体品牌为“学习探险队”。

当前Compose `learning_data/deployments/family-math-20261105/compose-subjects-folding-20261106.json`，固定镜像 `sha256:32808e7a852fbf23c0e4ef16893cd9d561083ed82f5465b2c823d4b85b1b9434`；最终候选 `dd-v1-family-subjects-folding-20261106-final`，source set `b7833f5993d83d411b64df246787e88be4c7ea1ce3967748cceda26bb6665fa4`。46项相关测试通过，真实PDF浏览器验证和上线核验通过；13册PDF只读挂载且哈希有效，真实50次作答/判分、两个档案、一个绑定及其他计数保持，原WebUI/代理未重启。保存输入后Ctrl+F5刷新即可，无需重绑。详情见[部署记录](../../learning_data/deployments/family-math-20261105/deployment-subjects-folding-20261106.json)。

当前范围仍是两个已有年级，其他学科仅教材阅读，数学练习仍原14道。二下数学待离线OCR及逐页双重审核；二下道法和七下英语/道法/历史/地理/生物待补齐。二下语文已用原生文字PDF作为阅读参考入库，无需继续OCR；图片可见与检索命中均不代表内容/答案通过审核。家长实际刷新后的使用反馈仍待确认。下文旧教材数量、旧Compose、下载阻塞及纯文本显示均为历史，不得用旧配置up覆盖；所有未提交改动与原有权限限制保持。

最新补充（2026-11-06 原页显示修复，已上线）：用户反馈七上第144/115页图片、公式及链接错误，现三册数学教材统一显示原PDF页面图像，点击“放大查看第N页原图”打开同一页；不再将失真的提取文字当正文展示。新增受既有登录/档案/上下文约束的原页接口，固定PDF只读挂载、哈希绑定索引版本。最新Compose为 `compose-textbook-pages-20261106.json`，镜像 `sha256:4c068b2200c36d087dd520682aa2121447b0eedaf40484e9f57c4ed037e2d464`。62项测试及两张实物页在手机/桌面的显示、放大验证通过；上线前后绑定1、档案2、作答/判分50、浏览器会话记录2一致，代理/WebUI容器未重启。用户保存输入后刷新再检索即可；无需重绑。详见[原页展示修复记录](../verification/textbook-page-display-fix-2026-11-06.md)。下文旧Compose/纯文本展示均为历史。当前参考库仍12册/1,875片段，原PDF提取文字尚未全文纠正，不用于出题/判分；OCR待办及其余限制保持。

同日最新补充（GitHub核查）：**此前两册完整来源阻塞已解除**，详见[GitHub实物核查](../verification/github-textbook-sources-2026-11-06.md)。`LYUGUISONG/Textbooks`提供数学106页、语文130页新版图片PDF，均已完整下载；`hantang/yuwen` docs分支另有130页新版语文可提取文字PDF，已优先导入129片段，当前12册/1,875片段。语文无需继续OCR，正文提取仍仅为阅读参考，拼音嵌入字体存在提取异常，不能当答案。数学106张完整图在 `learning_data/textbooks/github-verified-20261106/math-g2-lower-images/`，下一步从这里离线OCR并逐页双重核验；未入当前检索。旧图/旧OCR/旧文件保留。下文“二册下载受阻、11册”等为前一阶段历史，不再要求用户解决网站验证码或登录。当前家庭版镜像/Compose未变化，其他限制继续有效。

用户约定持续有效：[TEXTBOOK-POLICY.md](TEXTBOOK-POLICY.md)。所有年级采用人教社当前适用最新修订教材；语文/历史/道法为人教社统编新版。多个信源核实版次、课标与目录，不能把印次当新版。已授权更新教材相关 WebUI 数据、复用本地向量，以及仅对二年级数学/语文下册公开教材离线 OCR；其他限制不变，不需再次询问授权。

## 当前实际结果

原有13本文件均为旧版或提取失败资料。已新增11本新版到 Open WebUI，共1,746个向量片段：二年级数学/语文上册；七年级数学/语文上下册、英语/历史/地理/生物/道法上册。所有原文件记录、关联和向量保留；原两知识库仅重命名为归档，当前新版另建知识库。

| 年级 | 当前新版知识库 ID | 归档旧库 ID |
| --- | --- | --- |
| 二年级 | `44c8e0ce-74a8-553d-b7e8-d90941e9f62d` | `4934772d-5748-4101-a795-9c69af0459b3` |
| 七年级 | `37b98c69-0e63-5b58-b6c7-e16ee93d113e` | `9f90ce6b-01c4-48f0-bcca-4e29c47fe9ac` |

教材文件及逐页提取在 `learning_data/textbooks/pep-current-20261105/`。详细ID、来源、向量数见 [当前索引](../../learning_data/verification/family-textbooks-20261105/current-textbook-index.json)、[导入结果](../../learning_data/verification/family-textbooks-20261105/import-results.json)、[原13文件保留校验](../../learning_data/verification/family-textbooks-20261105/import-verified.json)。原教材快照是600权限的 `webui-textbook-backup.json`，仅教材相关行，不含无关聊天快照。

版本依据包括人教[第十二套教材介绍](https://www.pep.com.cn/xw/zt/hd/12/)、[初中数学新版介绍](https://www.pep.com.cn/xw/zt/hd/12/xjcjs/cz/202408/t20240826_1994351.html)、[人教实际电子教材目录](https://jc.pep.com.cn/)、[河南2026秋目录通知](https://www.hnergc.cn/index.php?m=content&c=index&a=show&catid=14&id=867)、河南2026春教材目录PDF及国家智慧教育平台公开元数据。原始证据都在 `learning_data/verification/family-textbooks-20261105/`。七年级为2024启用新修订系列，二年级新版按年级逐步启用；不把下载站统一标2024当成每册版权年份。

## 已上线的学习工作区

首页“从课本找线索”可选数学上下册和真实教材章节，当前二年级上册8个单元/活动、七年级上下册各6章。复用原 WebUI 本地 embedding 和向量库，通过家长既有 Cookie 调用检索接口；先由学习服务验证档案、上下文和CSRF，再按文件、版本、页码过滤，最多4段。教材文本按纯文本渲染，显示书内页码和官方阅读链接。官方阅读器与下载PDF的前置页数可能不同，不声称链接会精确跳转原页。

这些是阅读参考，不是已审核题目或答案。现有练习仍是14道起步题、原有3个知识单元；**没有实现全教材每章都有题，没有从未核验OCR自动出题或判分**。二年级下册明确显示待核验。既有目录选择与档案切换保持。

入口仍为 <https://172.19.116.53/learning/auth/login>。保存当前输入后刷新可加载；保留现有登录绑定，无需重绑。当前 Compose：

```bash
docker compose --env-file /dev/null -p dd-family-math \
  -f learning_data/deployments/family-math-20261105/compose-textbooks-20261105.json ps
```

当前镜像：`sha256:1ff715a05f242b3b1eb492b36fb8f368906f1ad01702ff0bc034f3c0cd687a00`；schema11。仅更新家庭API/worker/gateway，proxy、TLS、网络、卷、原WebUI容器进程保持。新候选52文件：`learning_data/release-preparation/dd-v1-family-textbooks-20261105-final`，source set `5e8737cb58da28d84f2d365aed193d2bacac039f0d903171938d54c84b79a50e`。非final初次候选未构建，保留勿误用。

更新前在线备份 `learning_data/family-backups/family-textbooks-preupdate-20261105` 已验证SHA256及SQLite integrity。前后计数一致：家长1、档案2、绑定1、浏览器会话记录1、题目/版本14、学习会话51、作答/判分50、错题0、provider0。真实作答比旧交接43次增加；仍不能据聚合数据声称错题、刷新或新教材检索已由家长验收。

[部署记录](../../learning_data/deployments/family-math-20261105/deployment-textbooks-20261105.json)、[验证报告](../../learning_data/verification/family-textbooks-20261105/validation-report.json)：81项相关测试通过，含双重审核/导入门槛、年级/章节/旧版隔离、CSRF/过期上下文、上游异常/令牌隔离、移动与桌面浏览器、旧候选兼容。第一次浏览器启动在沙箱内卡住，停止本次测试进程后在沙箱外完成。一个旧测试跟随预期登录跳转导致404，改为验证303及登录目标后通过。20/20实际章节用本地缓存模型和已有向量只读查询有匹配结果；真实家长HTTP检索仍待实际点击验证，未读取真实Cookie。上线实际UI/源码hash、HTTPS health及数据计数均已核对。

## OCR：内容正确性与转写准确性分开

详见[真实片段核验报告](../verification/textbook-ocr-content-review-2026-11-06.md)。用户明确要求不仅对上原图，还要验证内容本身是否正确。当前实现：

- 完整纯算术等式用精确有理数独立验算；跨行/分隔数字不拼接；原文错等式即便忠实转写也不放行。
- 有余数除法同时核算重构等式和余数范围。文字题/单位/图形需完整上下文及独立推导依据。题干、图像或答案改变使旧审核失效。
- OCR导入须完整逐页转写与内容复核报告，并绑定PDF、逐页文本和报告校验值；“已审核”字符串或重复OCR不能放行。
- 三个真实数学片段有助手对图复核及独立计算，但并非人工签署或整页审核。原始OCR/图片不改；纠正和推导另存。题目审核模块不是对既有生产题库重新批量认证；本次新题发布0。

**二年级数学下册106页、语文下册130页仍未完整下载或入库。** 数学仅20张有效图，其余86张实为滑块HTML，已检测拒绝；语文目前3张有效图。两册 `fully_verified_pages=0`。官网人教阅读器遇人工滑块；国家平台完整PDF返回401、公开预览仅49页；独立阅读站下载超时。没有绕过访问控制，不能假称13册全部完成。

二年级官方阅读：[数学下册](https://book.pep.com.cn/1221001202251/)、[语文下册](https://book.pep.com.cn/1211001202251/)。国家平台数学 contentId `c1897b18-b302-4e8d-9fd4-40915c4b05c2`、语文 `0f93b83e-b3c2-4a5d-8acd-ea460ab962d4`，公开元数据保存在证据目录。后续须取得正常可访问的完整来源再继续，不猜受限下载地址、不自动解验证码。

脚本：`fetch_family_textbooks.py`（11本已完成，勿重下）、`fetch_pep_image_textbooks.py`（两册未完成）、`review_textbook_ocr.py`（仅离线识别与隔离）、`verify_textbook_samples.py`（3片段记录的计算及hash重验）、`import_family_textbooks.py`（增量入库及完整复核门槛）。OCR依赖仅在 `/tmp/dd-textbook-ocr-libs`。**容器 `/tmp/dd-import-family-textbooks.py` 是旧版，缺本次完整复核门槛；任何继续导入必须先复制项目最新脚本。**

## 后续与限制

下一步验证家长实际点击新教材检索；取得两本下册完整公开来源并逐页双重审核；再基于审核过的内容逐章补少量练习。不要用未审核摘录填补题量。保持全人教最新版约定。

保留全部未提交改动，不reset/checkout/clean/commit/push；不读改根 `docker-compose.yml`、`batch_ingest.py`、环境秘密及无关WebUI聊天/账号。不外发学生资料、不调用付费/外部生成模型/OCR，学习预算0。此次本地公开教材OCR授权不扩展到学生资料。不重绑、不重建卷，不写Goal、不提升完整V1 T/QA状态。旧Compose/镜像均保留，但不要用旧配置up覆盖新功能。
