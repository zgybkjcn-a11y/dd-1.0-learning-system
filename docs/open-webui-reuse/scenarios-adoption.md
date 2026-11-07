# SCENARIOS 教育场景在本机家庭版的采用

> 2026-11-07 恢复后续工作：等式性质演示、Mermaid 可视化路线、三页章节复习 PDF 已完成**本地候选与隔离验证，尚未上线**。桌面/手机完整流程 2 项通过；已有线上版本仍为 `chat-20261107`，未重注册 Tool 或修改 Compose。新实物、版本许可与继续入口见 [三个小样本验证](../verification/main-study-samples-2026-11-07.md)。

> 2026-11-07 最新：主站原生聊天已注册私有六方法“课本伴学（只读）”，并新增聊天框旁教材检索、学科助手、分步讲解、检查思路、关联练习快捷提问。点“打开课本聊天”会在新标签页自动选中工具；原页引用可定位家庭阅读器。用户已明确授权此接入，正式 WebUI 仅新增目标 Tool/历史两行，未改其他数据或模型。当前静态快照 `main-study-20261106/assets/chat-20261107/`，Compose 不变，仅 nginx reload；未调用真实模型、未写 Goal。详见 [原生聊天接入验证](../verification/main-chat-study-2026-11-07.md)。

> 2026-11-07 最新：用户明确指定的 **cn-math-taxonomy + faststudy-knowledge** 已接入主站“学科伴学 → 知识路线与关联练习”：选概念、看先修/原页、按难度选已映射题、到家庭页显式开始，保留未完成题确认与档案隔离。仍是原74题（29道上游改编），精确映射20题/18概念，非全学科覆盖。静态快照更新为 `main-study-20261106/assets/knowledge-20261107/`；Compose 仍为 `compose-main-study-20261106.json`，仅 nginx reload，五容器未重启。详见 [两项目主站采用验证](../verification/main-study-knowledge-2026-11-07.md)。

> 2026-11-07 后续深化已上线：主站参考 DeepTutor 增加编号参考卡/课堂出处核对，参考 OpenMAIC 增加四步课堂、局部数学演示和可断网操作的单文件 HTML 导出；沿用家庭资料，未安装上游引擎。静态版本为 `classroom-20261107`，Compose 不变。见 [课堂采用验证](../verification/main-study-classroom-2026-11-07.md)。

> 2026-11-07：主站学科伴学已复用家庭服务的当前档案、教材目录、理解工坊参考与原图；同浏览器书章同步，带入聊天的公开资料可预览。仍无真实模型调用或正式 Tool 注册。见 [互通验证](../verification/main-study-family-bridge-2026-11-07.md)。

> 后续主站接入：`https://172.19.116.53/` 左侧已增加“家庭学习”和“学科伴学”；主站面板参考 DeepTutor 的资料伴读、OpenMAIC 的分步学习设计，支持七学科请求预览、填入聊天框及下载提纲。没有安装上游引擎或注册正式 Tool。新的当前 Compose 为 `compose-main-study-20261106.json`，只更新代理静态入口，家庭服务镜像保持。见 [发布与验证](../verification/main-study-sidebar-2026-11-06.md)。

2026-11-06。用户指定 [SCENARIOS.md](https://github.com/dangjian/faststudy-knowledge/blob/main/docs/SCENARIOS.md)，继续采用“现有学习服务 → Open WebUI Tools”的接入方式。

参考文档固定为 `508748a2c8dddc1253100b2d10d91c9526903f67`，本地证据在 `learning_data/verification/scenarios-integration-20261106/`。对重点项目另行读取固定 commit 的 README 与真实 LICENSE，不把文档中的版本、星数或功能描述当成直接验收结果。

| 项目 | 本轮采用与实际状态 | 后续引入条件 |
| --- | --- | --- |
| [EduLab](https://github.com/wy51ai/edulab) | Apache-2.0，commit `805fdc5dd6bdf942290a7791924bf0ee08f26632`。借鉴独立交互 HTML、参数变化、图示与解释并排；本地已编写相同组的乘除演示和有理数数轴演示。未复制其代码、安装 skill 或执行其生成器。 | 原项目立体/解析几何多用向量、圆锥曲线，超出当前二/七年级范围；化学也不属于当前开课范围。选中适龄模板后再核对计算、依赖、许可证与离线运行。 |
| [Mermaid](https://github.com/mermaid-js/mermaid) / [Marp](https://github.com/marp-team/marp-cli) | 采用文本图与 Markdown 讲义格式，新增服务导出及下载样例。数学图区分目录、本地映射、先修参考；其他学科图只表示阅读步骤。未新增渲染器依赖。 | 若需要在工作台直接渲染或输出 PPTX/PDF，固定并核查渲染器版本后离线打包。SCENARIOS 标注两者 MIT；本轮未复制它们的代码。 |
| [DeepTutor](https://github.com/HKUDS/DeepTutor) | Apache-2.0，commit `60fb3bdfddb30b7740c7ce3bd9b28d908f2af6db`。README 实物支持知识库、PageIndex/图检索等来源引用；借鉴按资料范围回到出处的阅读方法。未部署第二套 RAG、导入它的教材或调用模型。 | 先用公开、已核对的小样本离线测检索和引用；具体引擎可能需要推理/embedding，不能凭开源许可认定无外部费用。当前已有教材检索，需先证明新增收益。 |
| [OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) | MIT，commit `5bd8cc840ee6397d063e1fe6aba974b9f0401593`。README 实物支持来源资料、知识库 `@`、PPTX/离线 HTML 课堂；借鉴分段课堂与可携带输出。未部署 PostgreSQL、课堂服务器或生成代理。 | 先给它本地核对的大纲/概念/出处，不能直接用主题自由生成正式课件或题目。安装及模型调用另按用户授权与适龄审核推进。 |

## 已写入候选的学科辅助

新增只读 `GET /api/v1/study-support` 与 Tool `get_study_support(subject="", book_id="", chapter_id="")`。与数学参考一样，从共享档案决定年级和可用课本，查询前后检查选择版本；模型不能传学习者。默认数学上册，章节可不选。

- 数学：已有 20 道题、18 个概念的参考映射、核对问题、局部原页位置；图和讲义同样不判分。
- 语文：整体理解 → 找原文依据 → 比较表达。
- 英语：理解交流情境 → 观察表达 → 尝试迁移并核对。
- 道法：辨认事实情境 → 说明规则/责任的理由 → 联系生活。
- 历史：时间与地点 → 背景/原因/过程/影响 → 比较证据。
- 地理：方向/图例/比例尺 → 条件与现象 → 同指标比较地区。
- 生物：观察结构 → 联系功能与条件 → 区分观察和推断。

以上非数学问题串由本项目编写，标为 `reading_scaffold_only`。没有套用 faststudy 的北师大版概念、没有从未审核 OCR 提取学科答案，也没有建立未经核对的跨学科依赖。二年级不提供学校尚未开设的英语；七年级不提供物理/化学。下册缺书时不会静默借用其他年级。

## 可体验的本地样例

`learning_data/verification/scenarios-integration-20261106/examples-v3/offline-study.html` 是最新自包含离线页面，覆盖当前 13 册、111 个整书/章节范围。它只含公共参考元数据和合成导出，不连接真实学习档案、不保存作答。可调每组数量/组数；二上第二单元仅乘法，第三单元起比较两种除法。七上有理数范围可改变起点/变化量，观察加减方向。第五章显示概念和等式性质参考卡，不混入数轴演示。早期v1/v2样例保留历史。

同目录 `exports/` 含各范围的 Markdown 学习卡和 Mermaid 图。页面可按当前范围下载这两类文本。它们是已经生成的输入样例；尚未通过 Marp/Slidev 渲染成 PPTX/PDF，也未部署 DeepTutor/OpenMAIC/EduLab。

## 接入边界

适配器 1.2.0 共 15 个公开方法，其中本轮新增 4 个只读方法。数学和学科辅助经学习服务返回明确的 `reference_only`、`teacher_reviewed=false`、`mastery_claim=null`，并在 Tools 端限制字段、列表与文本长度。学习记录、题库、评分和现有家长绑定保持原流程。

后续已把“理解工坊”直接接入现有家庭工作台，具备当前书/章联动、原页放大、演示和下载；工作台版本source profile为 `reuse-runtime-study-workbench-v1`，历史数学参考profile仍可验证。源码候选及原生加载器验证完成后，由管理员在正式 WebUI UI 导入适配器即可走原生Tools；用户仍要求不读取/修改正式 WebUI data，本轮没有借 API 或数据库写入正式 Tool 记录。未调用模型、付费/外部 OCR、外发学生资料或写入生产向量。工作台实际发布状态见 `docs/verification/study-workbench-2026-11-06.md`。
