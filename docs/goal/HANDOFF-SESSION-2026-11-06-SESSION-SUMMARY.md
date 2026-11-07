# DD-1.0 V1 家庭数学测试版：2026-11-06 会话交接

> **新会话先读 [2026-11-07 总交接](HANDOFF-SESSION-2026-11-07-SESSION-SUMMARY.md) 和 [继续指令](RESUME-SESSION-2026-11-07.txt)**：六方法原生 Tool 已注册，当前静态快照为 `chat-20261107`；二下数学 106 页离线 OCR 已完成但整页双重审核为 0。新增交互演示/知识图/PDF 仍是未实施建议。下文保留历史过程，不得用旧状态覆盖新部署。

> 2026-11-07 最新：主站原生聊天已注册私有六方法“课本伴学（只读）”，并新增聊天框旁教材检索、学科助手、分步讲解、检查思路、关联练习快捷提问。点“打开课本聊天”会在新标签页自动选中工具；原页引用可定位家庭阅读器。用户已明确授权此接入，正式 WebUI 仅新增目标 Tool/历史两行，未改其他数据或模型。当前静态快照 `main-study-20261106/assets/chat-20261107/`，Compose 不变，仅 nginx reload；未调用真实模型、未写 Goal。详见 [原生聊天接入验证](../verification/main-chat-study-2026-11-07.md)。

> 2026-11-07 最新：用户明确指定的 **cn-math-taxonomy + faststudy-knowledge** 已接入主站“学科伴学 → 知识路线与关联练习”：选概念、看先修/原页、按难度选已映射题、到家庭页显式开始，保留未完成题确认与档案隔离。仍是原74题（29道上游改编），精确映射20题/18概念，非全学科覆盖。静态快照更新为 `main-study-20261106/assets/knowledge-20261107/`；Compose 仍为 `compose-main-study-20261106.json`，仅 nginx reload，五容器未重启。详见 [两项目主站采用验证](../verification/main-study-knowledge-2026-11-07.md)。

> 2026-11-07 后续最新：主站学科伴学新增“开始分步课堂”“下载离线课堂”，深化 DeepTutor 编号参考/原页核对与 OpenMAIC 四步课堂/离线 HTML 设计采用。当前静态快照为 `main-study-20261106/assets/classroom-20261107/`，Compose 仍为 `compose-main-study-20261106.json`，只 nginx reload、五容器未重启。家庭资料互通保持；无真实模型/外部 OCR/正式 Tool 注册/Goal 写入。详见 [当前课堂验证](../verification/main-study-classroom-2026-11-07.md)。

> 2026-11-07 最新：学科伴学已打通家庭学习当前档案、课本/章节、理解工坊和原页；同浏览器家庭页选择可同步，主站可预览公开参考再填入聊天。Compose 仍为 `compose-main-study-20261106.json`，静态快照更新为 `main-study-20261106/assets/bridge-20261107/`，仅 nginx reload，五个容器未重启，服务镜像保持。初次需刷新主站和家庭页。未改正式 WebUI data/Tools、未调用模型、未写 Goal。详见 [互通验证](../verification/main-study-family-bridge-2026-11-07.md)。

> 最新主站入口更新：HTTPS 主站侧栏已上线“家庭学习”和“学科伴学”（DeepTutor 资料伴读 / OpenMAIC 分步学习设计参考，七学科、请求预览、填入聊天框、下载提纲）。当前 Compose 改为 `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`；仅 proxy 增加只读静态挂载并重建，家庭 API/worker/gateway 仍为 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`，其余容器 ID/启动时间保持。正式 WebUI data/Tools 未改，未调用模型。详见 [上线验证](../verification/main-study-sidebar-2026-11-06.md)。下文旧 Compose 状态为历史，勿覆盖。

> 本日后续最新：已上线“理解工坊”，当前 Compose 为 `learning_data/deployments/family-math-20261105/compose-study-workbench-20261106.json`，镜像 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`。家庭入口/绑定保持，保存输入刷新后可在课本操作区打开；二上第二单元仅乘法、第三单元起含除法，七上数轴/方程参考按章隔离，其余学科提供阅读问题串；可看原页和下载学习卡/关系图文本。原74题/两档案/一绑定/67次作答判分完整保留，provider0，正式WebUI及proxy未重启。服务端和Open WebUI Tools适配器1.2.0（15方法）已完成、原生加载器已验证；正式Tool注册仍未执行，用户“不读写正式WebUI data”的约束继续生效。SCENARIOS中的EduLab/DeepTutor/OpenMAIC仅借鉴设计，未整套安装或执行上游生成器。详见 [当前上线记录](../verification/study-workbench-2026-11-06.md) 与 [项目采用](../open-webui-reuse/scenarios-adoption.md)。下文四题Compose/53次作答为较早历史，勿覆盖新部署。二下OCR/教材审核限制不变；保留所有未提交改动，不写Goal API。

日期：2026-11-06（Asia/Shanghai）
工作目录：`/home/deniskorfei/projects/open-webui`
分支：`main`；HEAD：`0fa0271`（工作区有大量未提交改动，必须全部保留）

本会话目标是把此前家庭版需求、教材接入和题目体验继续整理成可续跑状态。当前家庭版已经有可用的两档案数学试用、最新教材阅读器和连续应用题；下一会话应先支持真实体验反馈，再按已记录的教材/OCR门槛补内容。不要把历史交接中较早的 Compose、题数或“尚未登录/尚未绑定”状态当成当前状态。

## 已完成并已上线

### 家庭版登录、档案和基础功能

- 家长真实账号登录及一次启用码绑定已完成，已有两个学习档案（二年级、七年级）；不要重复绑定或公开启用码。
- 家庭入口：`https://172.19.116.53/learning/auth/login`；原 Open WebUI `http://172.19.116.53:53001/` 保留。
- 设备根证书已安装并通过 Windows 默认 TLS 校验；家庭版独立 Compose、API/worker/gateway/proxy 均保持运行，原 WebUI 容器、数据库、模型和 Tools 未改。
- 真实历史数据保留：1 个绑定、2 个档案、53 次已判分作答（以最新四题部署核验为准）、74 道题、provider 调用 0。保存当前输入后刷新即可，无需重绑。
- 已实现档案切换、提交判分、刷新恢复、手动错题本、错题知识目标自动填充、活泼“数学探险队”界面和首页简化。

### 题目与挑战

- 最新部署是“三档生活应用题 + 连续出题 + 四题升档”：总题库 74 道（原 14 道起步题 + 新增 60 道应用题）。
- 新题覆盖：二年级上册第二/三/五单元，各 12 题；七年级上册第二/五章，各 12 题。每个已覆盖章节的简单/正常/困难各 4 题。
- 题目可手动选简单、正常、困难；默认从简单开始，并按独立作答情况自动推荐进阶。当前规则为同一档连续独立答对 **4 道不同题** 才尝试下一档；重复题不累计，错误或使用提示中断累计；手动选档仍可用。
- “继续出题”按当前学科/课本/可选章节/难度范围取本轮未做题，不跨章、不偷偷重复；用尽会明确提示，可切档、换章节或重新练习。题后有提示和可折叠解析。
- 60 道新应用题中 29 道改编自固定 commit 的 `xiaoyang111222/cn-math-taxonomy`（CC BY-NC 4.0，页面保留来源/许可），31 道为本地编写；全部做过独立语义检查和有理数复算，但不是教师签署，也不是全教材覆盖。没有开启点击实时大模型出题。

### 教材、章节和阅读器

- 已统一为“学科 → 课本 → 章节（可选）”。不选章节默认整本书；挑战、下一题、复习和阅读跟随同一范围，未配题范围只读教材并禁用挑战。
- 阅读器是左侧窄目录、右侧宽单页，支持目录点选、前后页、页码跳转、原图点击放大、缩放/适应宽度、Esc 关闭并保留位置；整体和逐页折叠、每页内容标题、页底收起均已上线。工具栏把当前范围/展开/收起放在翻页跳转行右侧并自适应换行。
- 已接入 13 册人教/统编新版教材，共约 1,948 个片段、98 个章节区间：二年级语文/数学/道法；七年级语文/数学/英语/道法/历史/地理/生物。二年级学校暂未开英语；物理、化学按八/九年级开设，未伪装为二/七年级课程。
- 七上数学第 115/144 页图片、公式和链接显示问题已修复：检索显示固定 PDF 原页图，放大链接打开同页；原提取文本只用于定位，不代表已审核答案。
- 所有年级固定使用人教社当前适用最新版；版本通过人教社、教育主管部门、国家智慧教育平台和目录等多信源核对。旧教材和旧向量保留归档并与当前库隔离。

### 题库/项目调研

- 已核查多个同类项目并记录在 `docs/verification/math-practice-project-research-2026-11-06.md`。当前路线是固定、可审核题库，不按点击调用模型实时生成。
- `dangjian/faststudy-knowledge` 已下载 README、代码树、固定 commit `508748a2c8dddc1253100b2d10d91c9526903f67`、`LICENSE`、`LICENSE-DATA`、`NOTICE`，证据在 `learning_data/verification/faststudy-research-20261106/`。
  - 代码许可 MIT；自编图谱/补充数据 CC BY-NC-SA 4.0；教材原文转写归出版社，仓库明确声明不含题库（刷题层已裁撤）。
  - 可借鉴内容：按教材→章节→概念→易错点/先修链的查询结构、页码来源、离线纯文本和审计字段；不能直接把其教材转写或概念数据并入当前生产索引，除非逐项核对版本、内容和许可/版权边界。
  - 该仓库教材示例以西安版本为主，未证明适配河南当前人教最新版；不能用其版本替代本项目的多源教材核验。

## 当前最新部署

以最新验证记录为准：

- Compose：`learning_data/deployments/family-math-20261105/compose-practice-four-20261106.json`
- 镜像：`sha256:d94346e8ec8fada893f288aac5fddd8f26a1b6078d4eb23b1af9bfd2cc64e6cc`
- 部署/验证：`learning_data/deployments/family-math-20261105/deployment-practice-four-20261106.json`、`docs/verification/practice-four-2026-11-06.md`
- 题目与连续练习证据：`docs/verification/adaptive-practice-2026-11-06.md`、`learning_data/verification/practice-four-20261106/`
- 教材统一范围证据：`docs/verification/unified-textbook-reader-2026-11-06.md`
- 最新目录/折叠布局证据：`docs/verification/textbook-subjects-folding-2026-11-06.md`、`docs/verification/reader-toolbar-layout-2026-11-06.md`
- 原页显示修复：`docs/verification/textbook-page-display-fix-2026-11-06.md`
- 教材总交接和持续约定：`docs/goal/HANDOFF-SESSION-2026-11-06-TEXTBOOKS.md`、`docs/goal/TEXTBOOK-POLICY.md`

查看服务：

```bash
cd /home/deniskorfei/projects/open-webui
docker compose --env-file /dev/null -p dd-family-math \
  -f learning_data/deployments/family-math-20261105/compose-practice-four-20261106.json ps
```

## 尚未完成 / 明确缺口

1. **真实家长体验反馈**：尚未在最新页面确认家长刷新后的教材检索、章节选择、连续出题、四题升档、错题本和两个档案切换是否符合预期。下一会话先做这个，不要重绑。
2. **题库覆盖**：目前只有二上第二/三/五单元和七上第二/五章配有 60 道新应用题；其余章节/学科只有教材阅读，不能宣称全教材可挑战。
3. **二年级下册数学**：新版完整 106 页 PDF 已从 GitHub 下载并核对，每页图像可解码；106 张原图位于 `learning_data/textbooks/github-verified-20261106/math-g2-lower-images/`。尚未完成 OCR、逐页双重审核或入库，`fully_verified_pages=0`。用户已授权仅对二年级下册公开教材本机离线 OCR；下一步可直接从这套完整图片开始 OCR 和逐页复核，不必再找来源。
4. **二年级下册语文**：已从 `hantang/yuwen` docs 分支取得可提取文字新版并导入 129 片段；但拼音字体提取异常，当前仅阅读参考，仍需对照原 PDF，不能直接作为答案依据。
5. **待补教材**：二下道法、七下英语/道法/历史/地理/生物仍待补；其他年级和物理/化学尚未接入。
6. **审核门槛**：OCR 必须同时通过“逐页转写准确”和“识别后内容/数学语义正确”两层独立核验；抽样或高置信度不能代替整书审核。未核验内容不得自动出题或判分。
7. **faststudy 复用评估**：还未把其图谱接入当前向量库，也未决定是否仅借鉴 schema。后续应先做一个只读、版本隔离的小样本映射，评估河南人教版二上/七上数学章节命中率，再决定是否采用；不要直接复制教材正文或题目。
8. **正式 V1**：真实模型/OCR外发、学生资料、provider 费用、完整恢复/RPO/RTO、复杂监控、商业化、人工教师审核及 7–14 天正式试用仍暂缓；不要将本家庭版上线等同完整 V1 完成。

## 下一会话操作顺序

1. 读取本文件、`docs/goal/HANDOFF-SESSION-2026-11-06-TEXTBOOKS.md`、`docs/goal/TEXTBOOK-POLICY.md`，再检查 `git status --short --branch`、最新 Compose 状态和只读 Goal API。旧的 11 月 5 日续跑文件保留历史状态，以本交接的当前数据为准。
2. 打开家庭 HTTPS 入口，先验证已有家长会话是否仍有效；协助真实体验两个档案、章节不选/选章、教材检索、原页放大、继续出题、难度和四题升档。不要打印或重新使用启用码。
3. 只有发现直接影响使用的问题才做小修复；修改后运行对应最小测试，并在新的 `docs/verification/` 记录部署前后数据计数、镜像和测试结果。
4. 若继续教材工作，从已经下载的二下数学 106 张原图开始离线 OCR，逐页保留原图/OCR/置信度/复核记录；内容正确性要独立计算或推导，不能只对图。使用项目最新 `scripts/review_textbook_ocr.py`、`scripts/import_family_textbooks.py`；如需重新获取来源才用 `scripts/fetch_pep_image_textbooks.py`。不要使用容器中的旧 `/tmp/dd-import-family-textbooks.py`。
5. 若评估 faststudy，只读固定 commit，限于 schema/章节/概念映射和小样本，不写入生产向量库；保留 MIT、CC BY-NC-SA 及出版社版权说明。
6. 题库扩展优先固定参数模板和独立复算；每次补题后做章节/版本/范围隔离、难度、答案、单位、重复和显示回归。不要把未审核 OCR 或实时模型输出直接用于判分。

## 执行限制与保留事项

- 保留所有未提交改动；禁止 `reset`、`checkout`、`clean`、`commit`、`push`。
- 不读取或修改根 `docker-compose.yml`、`batch_ingest.py`、正式 WebUI data、环境秘密或无关聊天/账号数据。
- 不调用真实模型、付费/外部 OCR，不外发真实学生资料；家庭学习预算保持 0，provider 调用保持 0。用户已单独授权对二下公开教材使用本机离线 OCR，并要求内容正确性独立复核。
- 不重建数据卷、不重复绑定账号、不用历史 Compose 覆盖当前部署；不把旧教材或旧版向量静默补入当前库。
- 不创建、更新或完成 Goal；只读 Goal API 当前为 `goal: null`，仓库完整 V1 状态仍是历史 blocked。
- 不把“教材原图显示正确”“向量能检索到”或“助手独立复算”写成教师审核或全书质量保证。

## 新会话续跑命令

```text
继续 DD-1.0 V1 家庭数学测试版。工作目录：/home/deniskorfei/projects/open-webui。

先读取 docs/goal/HANDOFF-SESSION-2026-11-06-SESSION-SUMMARY.md、docs/goal/HANDOFF-SESSION-2026-11-06-TEXTBOOKS.md、docs/goal/TEXTBOOK-POLICY.md，以及 docs/verification/practice-four-2026-11-06.md、docs/verification/adaptive-practice-2026-11-06.md、docs/verification/math-practice-project-research-2026-11-06.md；检查 git status --short --branch、下面最新 Compose 状态和只读 Goal API。旧 11 月 5 日续跑文档中的账号/题目/下载状态为历史，以 11 月 6 日交接为准。

当前最新家庭部署使用 learning_data/deployments/family-math-20261105/compose-practice-four-20261106.json，镜像 sha256:d94346e8ec8fada893f288aac5fddd8f26a1b6078d4eb23b1af9bfd2cc64e6cc；入口 https://172.19.116.53/learning/auth/login。家长真实登录/启用码绑定已完成，两个档案和历史作答保留，无需重绑。先做真实体验：两个档案切换、学科/课本、章节可不选、教材目录/单页/放大、继续出题、简单/正常/困难、同档四道不同题升档、提示/错题本和刷新恢复。

题库当前 74 道：原14题 + 60道生活应用题。新题只覆盖二上第二/三/五单元、七上第二/五章，其余章节和学科仅阅读。不要把模型实时出题或未审核 OCR 用于判分。

faststudy-knowledge 已在 learning_data/verification/faststudy-research-20261106/ 核查至固定 commit 508748a2c8dddc1253100b2d10d91c9526903f67：代码 MIT，自编图谱 CC BY-NC-SA 4.0，教材转写归出版社，README 明确不含刷题题库。只可先做只读小样本章节/概念映射评估，不能直接复制其教材正文或宣称有可复用题库。

保留所有未提交改动；不要 reset/checkout/clean/commit/push；不要重建卷、重绑或用旧 Compose up；不要读取/修改根 docker-compose.yml、batch_ingest.py、正式 WebUI data/环境秘密；不要调用真实模型、付费/外部 OCR或外发学生资料。只可按已有授权对二下公开教材使用本机离线 OCR，并按“转写准确 + 内容正确”逐页双重审核后才入库。不要创建/更新/完成 Goal。按需要补最小修复和验证并记录。
```
