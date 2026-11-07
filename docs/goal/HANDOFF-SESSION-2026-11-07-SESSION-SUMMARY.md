# DD-1.0 家庭学习与 Open WebUI 主站伴学：2026-11-07 会话交接

工作目录：`/home/deniskorfei/projects/open-webui`。分支 `main...origin/main`，HEAD `0fa0271`。整理前 `git status --short` 有 203 个条目（含未跟踪目录折叠），全部保留；本次整理没有提交、推送或修改应用代码。

本文件汇总本会话从家庭体验、开源项目采用到主站原生聊天接入的结果。**当前状态以本文件及所链接的最新验证为准**；2026-11-06 交接中较早的 Compose、题量、“OCR 未执行”“正式 Tool 未注册”等描述为历史，不得据此回退或重复安装。

## 1. 当前结论

- 家庭学习与主站学科伴学已打通；主站侧栏和原生聊天均有学习入口。
- 私有六方法 Tool **“课本伴学（只读）”已经注册并上线**，不是待安装候选。用户明确澄清“教材知识库检错”指教材检索，不是新增转写纠错功能。
- 已有教材检索与原页引用、学科快捷提问、分步课堂、离线 HTML、局部知识路线与关联练习。
- cn-math-taxonomy / faststudy-knowledge 已有实际有限采用；DeepTutor / OpenMAIC / EduLab 采用了设计思路，没有整套安装上游引擎。
- 最新提出的 **等式性质交互演示、可视化知识路线图、章节复习 PDF** 仅完成建议和可行性核查，尚未开发或部署。
- 二下数学 **106/106 页离线 OCR 已完成**；完整页双重审核通过数仍为 **0**，未导入检索/生产向量，不能用于出题或判分。
- 2026-11-07 11:40（Asia/Shanghai）只读核对：五容器运行，WebUI/API healthy，容器 ID/镜像/启动时间与最新聊天发布记录一致。只读 Goal API 返回 `goal: null`；未创建、更新或完成 Goal。

## 2. 都有哪些任务，做到哪里

| 任务 | 已完成 | 仍未完成或边界 |
| --- | --- | --- |
| 家庭数学体验 | 两档案、章节可选、教材检索/原页放大、连续出题、三档难度、四题升档、错题本、刷新恢复均已实现 | 家长完整体验清单尚未逐项确认；自动验证不能代替实际教学验收 |
| 登录异常 | 用户遇到 `LEARNING_IDENTITY_MISMATCH`，从原学习入口重新进入后明确反馈“已恢复，可以正常使用” | 未确定具体失效根因；不应据错误码直接断言账号错绑；无需重绑 |
| 本机离线 OCR | 二下数学 106 页、3,161 行识别完成，保留原图/框/置信度/来源哈希 | 623 行置信度低于 0.97；全部页仍待完整转写及内容复核，高置信度也不代表通过 |
| 两个指定开源项目 | 29 道既有改编题保留来源；完成 20 题—18 概念局部数学映射、先修参考、原页位置 | 没有全书、全学科图谱或题库，没有自动掌握度诊断 |
| SCENARIOS 设计采用 | 理解工坊、阅读问题串、局部数学演示、学习卡/Mermaid 文本导出 | 未部署 DeepTutor、OpenMAIC、EduLab 引擎或执行它们的生成代理 |
| 主站入口与资料互通 | 左侧“家庭学习”“学科伴学”；复用当前家庭档案/课本/可选章节/原页，同浏览器书章同步 | 换孩子应另开课本聊天；历史聊天不会随档案切换自动改写 |
| 分步课堂与离线输出 | 目标→观察理解→自己解释→回顾核对；编号参考卡；单文件离线 HTML | 非数学主要是阅读活动；未产出正式 PDF/PPTX/视频课堂 |
| 主站知识路线与关联练习 | 选概念、看先修/原页、筛难度；到家庭页显式开始关联题 | 当前不是完整可视化知识图；仅已有 20 题/18 概念精确映射 |
| 原生聊天 Tools | 六方法私有 Tool 已注册；原生 citation；检索、学科助手及快捷草稿按钮已上线 | 真实模型是否正确选工具及讲解效果未验收，代理验证期间模型调用为 0 |
| 后续项目筛选 | 重新读取 SCENARIOS，并核查 JSXGraph、Mermaid、Marp、Excalidraw、Manim README | 新候选尚未引入依赖、实现、测试或上线 |

## 3. 当前部署，不能用旧 Compose 覆盖

| 项目 | 当前值 |
| --- | --- |
| 主站 | <https://172.19.116.53/> |
| 新开课本聊天 | <https://172.19.116.53/?tools=dd_family_study_readonly_v1> |
| 家庭登录 | <https://172.19.116.53/learning/auth/login> |
| 家庭工作台 | <https://172.19.116.53/learning/ui> |
| Compose | `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json` |
| 家庭 API/worker/gateway 镜像 | `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0` |
| Open WebUI | 0.12.5，`sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd` |
| 当前静态快照 | `learning_data/deployments/family-math-20261105/main-study-20261106/assets/chat-20261107/` |
| 当前代理配置 | `learning_data/deployments/family-math-20261105/main-study-20261106/nginx.conf` |

最近聊天发布只替换三条静态 alias 并 nginx 校验/reload，五容器未重建。交接整理时已复核三条 alias 指向 `chat-20261107`，三个源码文件哈希与发布记录一致。完整部署证据在 `learning_data/verification/main-chat-study-20261107/deployment/`。

已发布的静态哈希：

- `study.js`：`6e2325ad44c246351e00f4f8bc480dbcdcef4912f90085696793b208524db7e4`
- `study.css`：`b7ea956e897b0bf12a26f55e0213b794a924ff8c10e02647e83de8027514627a`
- `family-bridge.js`：`8bfe564373befe4d3bb64cfc4d91b67880545217f00d293da415938cce4f0347`

最新发布时 HTTPS 三个资源均为 200/no-store；本次交接整理只复核本地源码、配置和容器状态，没有重复执行已通过的浏览器或模型测试。

## 4. 主站聊天的实际行为

保存草稿后刷新主站与家庭页，在聊天框上方点“打开课本聊天”，新标签页会通过原生 `?tools=` 选中“课本伴学（只读）”。已有家长登录与绑定继续使用。

快捷按钮有“学科助手、查课本、分步讲解、检查思路、关联练习”。提问先填入草稿，用户补全 `____` 后自行发送；不覆盖已有草稿，不自动发送。工具使用当前家庭档案，快捷草稿明确携带所选书章；直接聊天未指定书章时先查目录，数学默认当前年级上册。

正式 Tool ID：`dd_family_study_readonly_v1`，版本 1.0.0。源码 `deploy/open-webui-reuse/readonly_study_tools.py`，SHA256 `733ad01dc38ed6b09fcae69047ff731e0eb83d59b0a2dd2432595a3508c6a650`。六方法：

- `get_study_catalogue`：当前档案可用课本/章节。
- `get_math_scope`：当前数学范围内的概念和关联题。
- `get_math_concept_reference`：概念、先修参考、原页。
- `get_math_question_reference`：已有题的知识点和练习入口。
- `get_study_support`：学科阅读问题串。
- `search_textbook`：最多四个相关页标题、页码和原页链接。

该 Tool 与旧 `learning_service/tools.py` 1.2.0 的十五方法适配器独立；旧完整业务适配器没有注册到正式聊天。新 Tool 无档案切换、写学习状态、出题、提交或判分方法。

身份来自宿主注入的 `__user__` / `__request__`，白名单 Cookie 仅发送固定本机服务 `open-webui:8080` / `learning-gateway:8000`；查询前后检查档案 revision。模型不能传 URL、凭据或学习者 ID。原页链接携带公开书章、页码及 revision，过期/越界会拒绝；切章仍保留未完成题确认。

检索只回显页位置，不把未核验提取正文作为教材原句。数学解释来自现有受限本地参考。真实用户发送聊天后是否调用工具，由现有模型能力决定；开发验证没有调用真实模型或 embedding。

正式注册依据用户“按建议执行”和“授权你开干接入”的明确授权，窄范围新增 **1 条 Tool + 1 条原生 tool_history**，仅属既有家庭绑定账号，**共享授权 0**。已保存 prepared/applied/verified 证据，禁止误判为“未注册”而重复导入。该例外不构成读取其他正式账号/聊天/工具或广泛修改数据库的授权。

## 5. 内容范围与开源采用

当前仍为 74 道题：原 14 道 + 60 道应用题。新题仅覆盖二上第二/三/五单元及七上第二/五章；各范围简单/正常/困难各 4 题。同档连续独立答对 **4 道不同题** 才尝试升档；错答或提示中断累计，重复题不累计。不能将此规则称为已验证的掌握度评估。

已有教材阅读为 13 册、约 1,948 片段、98 章节区间，范围继承既有导入验证，本次没有重读正式数据库统计。二年级启用语文/数学/道法，学校暂未开英语；七年级启用语数英/道法/历史/地理/生物。全程遵循人教社当前适用新版与多源核验约定。其他学科主要提供阅读方法，不具有同等覆盖的已审核讲解、图谱或答案库。

| 项目 | 固定版本/许可 | 已实际采用 |
| --- | --- | --- |
| [cn-math-taxonomy](https://github.com/xiaoyang111222/cn-math-taxonomy) | `cf73951cf4b5d2bdbc8a75bb9cb9e961e55277ab`；数据 CC BY-NC 4.0 | 既有 29 道改编题保留署名/原始 ID/修改说明，部分题已接主站关联练习 |
| [faststudy-knowledge](https://github.com/dangjian/faststudy-knowledge) | `508748a2c8dddc1253100b2d10d91c9526903f67`；代码 MIT、图谱 CC BY-NC-SA 4.0、教材转写归出版社 | 书→章→概念→先修→出处结构；20 题/18 概念局部映射，本地人教版页码另核对；上游没有题库 |
| [DeepTutor](https://github.com/HKUDS/DeepTutor) | `60fb3bdfddb30b7740c7ce3bd9b28d908f2af6db`；Apache-2.0 | 资料伴读、编号参考、页级出处核对的设计 |
| [OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) | `5bd8cc840ee6397d063e1fe6aba974b9f0401593`；MIT | 四步课堂、分场景学习、单文件离线课堂的设计 |
| [EduLab](https://github.com/wy51ai/edulab) | `805fdc5dd6bdf942290a7791924bf0ee08f26632`；Apache-2.0 | 独立交互 HTML、参数图示与解释并排的设计；本地有同组乘除和数轴演示 |

不能把“参考设计、本地独立实现”说成“已经安装上游引擎”。没有整体复制教材转写、写生产向量或引入未经核验的跨学科依赖关系。完整采用说明见 [scenarios-adoption.md](../open-webui-reuse/scenarios-adoption.md) 和 [SOURCES.md](../../deploy/open-webui-reuse/main-study/SOURCES.md)。

## 6. 验证到哪里

最新详细报告：[main-chat-study-2026-11-07.md](../verification/main-chat-study-2026-11-07.md)。证据根目录 `learning_data/verification/main-chat-study-20261107/`。

| 验证 | 已有结果 |
| --- | --- |
| `tests/test_readonly_study_tools.py` + `tests/test_main_study_tool_registration.py` | 14 项通过，8.86 秒；身份/范围/引用/过滤/原子注册/幂等/拒绝覆盖 |
| `tests/test_main_study_bridge.py` | 桌面 1280、手机 390 两项完整流程通过，195.62 秒；原页第 30 页、过期/越界拒绝、草稿保留、档案隔离、原课堂与离线能力 |
| 实际 WebUI 0.12.5 原生 loader/get_tools | 六方法加载、宿主身份注入、保留参数隐藏、两条原生 citation 通过；临时断网容器、不挂正式 data |
| 发布后实际原生前端资源探针 | 桌面/手机通过；工具计数为 1、菜单显示正确名称、编辑器和侧栏正常；API 合成/拦截，页面错误 0、模型调用 0 |
| 本机网络与发布 | WebUI→固定网关可达，无 Cookie 返回 401；仅三条静态 alias 更新，五容器保持 |

这是接口、隔离和界面验证，**不等于真实模型调用质量、教学效果或全部家庭体验已经验收**。真实账号/模型反馈仍是待办。无新修改或失败时，不重复跑整套已通过测试。

## 7. 还没做，下一步按什么顺序

### A. 先跟进已有功能的实际体验

主站刷新→打开课本聊天→选择档案/课本/章节→试用快捷草稿→检查来源链接→跳家庭原页或显式开始关联题→换档案后另开聊天。已有验证可作为工程依据；家长反馈仍需区分“没有选中 Tool”“未登录家庭”“模型未调用”“没有映射”等原因。代理不自行发送真实模型请求。

若再报 `LEARNING_IDENTITY_MISMATCH`，先记录发生步骤，保存输入后由家长从原学习入口重新进入；不重绑、不读取凭据，不把本次恢复解释成已经查明根因。

### B. 最近一轮建议：三个小样本候选，尚未实施

用户问 SCENARIOS 还有什么可借鉴，本会话只读调研后提出以下顺序；最后一次用户指令是生成交接。**以下是待办建议，不是已完成成果，也不是新的整套安装/生产发布记录。** 新会话结合用户继续指令确定实施范围，在已有授权内先做可逆候选和隔离验证。

1. **等式性质交互演示**：借鉴 EduLab，评估 JSXGraph 或简单本地 SVG/Canvas。先从已有七上第五章参考做一例：两边同时加同一个数与仅一边改变的对比，学生先预测再操作解释。已有数轴/乘除演示保留。验证等式计算、适龄范围、手机操作、出处与档案隔离；无配套图示时不伪称覆盖该章全部概念。
2. **可视化知识路线图**：使用 Mermaid，将已有概念/先修列表变成可阅读图示并连接既有原页/关联题。先使用现有 18 概念中一个章节的小样本；区分先修与相关，缺边就保留空缺。当前已有 Mermaid 文本导出，但新可视化入口未实现。
3. **章节复习 PDF**：采用 Marp 或现有本地打印链，把已核对学习卡、例子、自检问题及出处组织成少量页面。先验证一章中文、公式、分页和来源链接，再接下载入口。Marp 支持 PDF/PPTX；默认 PPTX 多为渲染背景，不能承诺每个元素可编辑。

实现方式沿用“现有学习服务供资料→主站学科伴学展示→聊天入口链接”，初期不必增加模型调用或再建一套知识库。发布前完成候选与必要测试，并依据届时用户授权决定后续动作；既有六方法 Tool 无需重新注册。

### C. 后续研究备选

| 候选 | 学习用途 | 当前优先级 |
| --- | --- | --- |
| Excalidraw | 学生画数量关系、解题步骤、时间线、结构图 | 三项小样本之后；白板内容不自动视为审核答案 |
| Manim / manim-slides | 手工设计适龄短动画，逐步演示数学变化 | 有稳定讲解内容后，先离线渲染一个样例 |
| H5P / WhisperX | 视频暂停提问、概念对应时间点 | 有审核过的视频后再评估 |
| DeepTutor 的评测方法 | 用公开已核对的查书问题衡量命中章节、页码、出处 | 可先整理小样本标准集；运行不得绕过真实模型/embedding限制 |
| RAGFlow、Moodle / Open edX / Kolibri、Marimo / Quarto、Mol* | 检索引擎、课程平台、可执行笔记、分子可视化等 | 与当前家庭需求重叠或超出当前课程，暂缓整套引入 |

本次读取 [SCENARIOS 固定版本](https://github.com/dangjian/faststudy-knowledge/blob/508748a2c8dddc1253100b2d10d91c9526903f67/docs/SCENARIOS.md) 与 `main` 内容一致，SHA256 `ef1feea31ecbe13061b6e13bb71179b8322e5051dac6b6b5d336440fafb1cb97`。另读取 JSXGraph、Mermaid、Marp、Excalidraw、Manim 的公开 README 核查基本能力；尚未固定这些新增依赖版本、安装它们或完成依赖许可审查。引用具体代码/打包依赖前再按选定版本核查 LICENSE。

### D. 教材内容待办持续推进

二下数学源图位于 `learning_data/textbooks/github-verified-20261106/math-g2-lower-images/001.jpg` 至 `106.jpg`；来源 PDF 为 `learning_data/textbooks/github-candidates-20261106/lyu-math-g2-lower.pdf`。OCR 证据在 `learning_data/verification/math-g2-lower-offline-ocr-20261106/`，详见 [离线 OCR 报告](../verification/math-g2-lower-offline-ocr-2026-11-06.md)。

已查看书内 10/13/14 页部分片段，记录转写问题并独立复算 18 个商余数场景；不是整页通过，也不是教师签署。PDF 文件第 016/019/020 页分别对应书内 10/13/14 页，不能直接把文件序号当书内页码。下一步是按页建立完整转写审核与独立内容审核，不是重新 OCR 全书。原图、原 OCR、纠正、独立答案分开保存；图形、空格、单位、竖式、开放题都需核对。

`fully_verified_pages=0`、`question_or_answer_eligible_pages=0`。完整双重审核前不入检索/生产向量库，不用于出题判分；即使阅读索引通过，题目和答案还需单独审核。二下语文已经采用原生文字 PDF 作阅读参考，无需继续旧图片 OCR。二下道法及七下英语/道法/历史/地理/生物等缺册仍需按新版约定补齐；本会话没有完成这些缺口。

## 8. 持续约束与授权边界

- 保留所有未提交改动；不 reset/checkout/clean/commit/push，不覆盖其他会话工作。
- 不读取或修改根 `docker-compose.yml`、`batch_ingest.py`、环境秘密、无关聊天/账号/模型配置；日常只读核对也不要整库遍历或输出凭据。
- 正式 WebUI data 的例外仅为已经明确授权并完成的私有六方法 Tool 注册；不得把该例外扩展为一般数据库读写许可，不重复注册、不安装旧十五方法适配器。
- 不重绑、不重建卷、不用历史 Compose 覆盖当前部署；保持两个档案和已有学习记录。
- 不调用真实生成模型/embedding、付费/外部 OCR，不外发学生资料；仅按已有授权处理公开教材的本机离线 OCR。当前待办不包含生产向量写入。
- 不创建、更新、完成 Goal，也不因写入 `docs/goal/` 文档而调用 Goal 写 API；只读 `get_goal` 可用。本次为 null。
- 年级、学科、教材版本、可选章节及档案 revision 继续隔离；未映射、未审核的范围如实显示缺口。
- 不把助手核对称为教师签署，不把合成测试称为真实学生/真实模型教学验收。

## 9. 新会话先读哪些文件

优先读取本文件，再按任务阅读：

- [教材约定](TEXTBOOK-POLICY.md)。里面旧数量/旧 OCR 状态以本交接及最新报告为准，质量门槛继续有效。
- [主站原生聊天用法](../open-webui-reuse/main-chat-tools.md) 与 [最新验证](../verification/main-chat-study-2026-11-07.md)。
- [开源场景采用](../open-webui-reuse/scenarios-adoption.md)、[知识路线验证](../verification/main-study-knowledge-2026-11-07.md)、[课堂验证](../verification/main-study-classroom-2026-11-07.md)。
- [家庭体验与身份恢复](../verification/family-experience-followup-2026-11-06.md)、[四题升档](../verification/practice-four-2026-11-06.md)、[应用题](../verification/adaptive-practice-2026-11-06.md)。
- [二下数学 OCR](../verification/math-g2-lower-offline-ocr-2026-11-06.md)。

主要代码入口：`deploy/open-webui-reuse/main-study/{study.js,study.css,family-bridge.js}`、`deploy/open-webui-reuse/readonly_study_tools.py`、`learning_service/{study_support.py,math_references.py,study_ui.py,textbooks.py,practice.py}`。最近发布/注册脚本为 `scripts/prepare_main_chat_study.py`、`scripts/register_main_study_tools.py`；了解用途后按需使用，不在恢复会话时直接重跑。

## 10. 只读恢复核对与继续指令

```bash
cd /home/deniskorfei/projects/open-webui
git status --short --branch
docker compose --env-file /dev/null -p dd-family-math \
  -f learning_data/deployments/family-math-20261105/compose-main-study-20261106.json ps
docker inspect --format '{{.Name}} {{.Image}} {{.State.Status}} {{.State.StartedAt}}' open-webui
```

在支持的工具中只调用 `get_goal`，不创建 Goal。不要使用根 Compose，不输出完整 `docker inspect` 或 `compose config`，避免无关环境信息。若仅查 OCR 证据，可运行其 `verify-evidence.py`；它只能重验哈希和已记计算，不能自动批准页面。

完整新会话指令见 [RESUME-SESSION-2026-11-07.txt](RESUME-SESSION-2026-11-07.txt)。可在新会话直接粘贴该文件内容，或让新会话先读取它。此次交接只新增总结/继续指令及旧文档指向，不改变部署、题库、向量、绑定或 Goal。
