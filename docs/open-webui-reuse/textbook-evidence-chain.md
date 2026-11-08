# 教材证据链：借鉴 RAGFlow 的第一阶段

2026-11-07 A07 已把五片段接入[本地服务与Tool 1.2.0](../verification/A07-runtime-passages-2026-11-07.md)，默认关闭、未部署，契约见[运行说明](textbook-passages-runtime.md)。以下A05及原样本描述保留历史；教师/整页/判分权限仍全部为false。

2026-11-07 A05 最新本地候选 Tool **1.1.2** 的[覆盖不足契约](chapter-retrieval.md)与[验收](../verification/A05-chapter-retrieval-2026-11-07.md)已完成：旧向量路径统一 grounding=incomplete，不能把空候选写成确定无依据；有界五片段试点已达标但尚未接服务。下文 locations_only/no_evidence 表格保留 1.1.0 阶段的历史语境。

2026-11-07 A04 增量已形成 Tool **1.1.1** 本地候选，[错误分类/恢复](study-error-recovery.md)与[验证记录](../verification/A04-study-errors-2026-11-07.md)另记；下方 1.1.0 是本阶段页级证据契约的历史版本，尚未部署。

2026-11-07。本地候选，尚未部署；只读 Tool 源码候选版本为 **1.1.0**，线上仍为已注册的 **1.0.0**。本轮复用当前学习服务与六个方法，没有引入 RAGFlow 运行时或新增依赖。验证见 [记录](../verification/textbook-evidence-2026-11-07.md)。

同日后续：已完成独立的 [5 页限定片段离线小样本](../verification/textbook-passages-2026-11-07.md)，包含助手转写/数学复核、版本绑定、20 问与正文引用回链。它尚未接入上述 Tool，线上与 Tool 候选的页级能力边界保持如下记录。

学生应能从引用返回正确版本的教材原页，同时知道系统到底拿到了什么证据。当前已有教材页定位和局部数学讲解，尚无可供聊天直接引用的已核验原文片段库。因此先建立页级身份与证据类型，明确返回资料不足；不能把“检索命中”和“有引用卡”当成回答已获教材支持。

## 已实现的链路

```mermaid
flowchart LR
    A[当前档案与书章范围] --> B[既有固定教材集合检索]
    B --> C[过滤文件、版本和章内页码]
    C --> D[教材来源 ID 与页级证据 ID]
    D --> E[Tool JSON 与原生 citation]
    E --> F[带档案 revision 的原页链接]
    F --> G[校验 PDF 哈希后展示原页]
    H[哈希绑定的本地概念参考] --> I[独立的本地讲解证据 ID]
    I --> E
    I --> D
```

授权书册在查询前确定，检索只访问该册固定集合；章内页码过滤沿用当前返回后的检查。**本轮没有实现检索引擎侧的章节 metadata 前置过滤**，也没有改变召回、重排或阈值。空关键词浏览走本地目录，不调用 embedding；真实关键词检索仍沿用既有 WebUI 检索入口，本轮测试全部替换为合成响应。

### 页级证据 `dd-textbook-page-evidence-v1`

`learning_service/textbooks.py::page_evidence` 只从可信目录生成证据，向量元数据不能指定证据 ID、审核结论或链接。

| 字段 | 含义 |
| --- | --- |
| `source_ref` | 书册 ID、固定版本键、源 PDF SHA256 共同确定的教材来源身份，对应设计中的 sourceRef |
| `evidence_id` | 来源身份加物理 PDF 页码确定的页级身份，与检索顺序、重复分块、查询词无关 |
| `book_id / grade / subject / semester` | 书册、年级、学科、上下册 |
| `edition / edition_id / pdf_sha256` | 展示版别、索引版本键与目录绑定的源文件校验值 |
| `chapter_id / chapter_title` | 该页实际所属章节，整本书查询也保留实际章节 |
| `printed_page / pdf_page` | 书内页码与从 1 开始计数的物理 PDF 页码，不能混用 |
| `source_binding` | 固定为 `catalogue_sha256`；不是宣称本次检索已读取并校验原文件 |
| `kind / locator_precision` | 固定为 `page_location / page`；没有段落框或句子精确高亮 |
| `review_status / quote_status` | 固定为 `location_only / unavailable` |
| `supports_textbook_answer / eligible_as_grading_basis` | 均为 `false` |

身份算法使用 UTF-8 和完整 SHA256，字段间用换行分隔：

```text
source_ref  = "dd-textbook-" + SHA256(book_id + "\n" + edition_id + "\n" + pdf_sha256)
evidence_id = "dd-page-" + SHA256(source_ref + "\n" + decimal(pdf_page))
```

更换 PDF 会同时改变来源与页级身份。书内页码及章名属于目录定位信息，不参与页级内容身份；本轮沿用已核对的目录映射。服务端原页渲染时继续检查实际 PDF 字节哈希，拒绝变化文件和符号链接。

旧索引元数据没有 PDF 哈希时，仍可返回“目录绑定的原页位置”；若元数据显式提供 `pdf_sha256` 却与目录冲突，则丢弃。索引文字即使声称 `verified`、附有外部 URL，也不能升级为可引用原文。这里的哈希用于身份与一致性检查，不是内容正确性的证明。

### 本地讲解 `dd-local-explanation-evidence-v1`

现有数学概念解释继续来自哈希校验后的本地参考文件。Tool 为其生成单独的 `dd-explanation-…` ID，由 `reference_sha256` 和概念 ID 决定；`page_evidence_ids` 记录关联原页。数学学科助手与概念查询复用同一身份。

`kind=local_explanation`、`quote_status=not_a_textbook_quote`。这些内容可以作为明确标注的本地理解参考，但不是教材原句、教师签署或新增标准答案。原有题库审核资格不由这条证据链决定。

### Tool 和原生引用

六个公开方法及其参数保持原样。候选适配器校验服务端证据结构、重算身份、核对书章和两套页码；只投影允许字段。身份来自原生宿主，查询前后检查当前档案 revision。

- 页级证据同时出现在 Tool JSON、`citation.data.metadata[].evidence_id` 和 `citation.data.source.id` 中。
- 本地讲解引用使用自己的证据 ID，另带 `page_evidence_id`，避免把讲解误当教材原文。
- URL 由 Tool 根据固定工作区地址生成，携带实际书章、书内页码和当前 revision；不接受检索响应提供的 URL。ID 不包含账号、学习者或 revision，也不授予访问权限。
- 仍最多返回四页，保留原生引用展示；未添加自定义正文引用解析器。模型是否在正文正确引用、所写断言是否受证据支持，尚未通过真实模型验收。

检索的 `grounding` 明确区分：

| 状态 | Tool 的行为 |
| --- | --- |
| `locations_only` | 有范围内的候选原页，但没有已核验原文；`can_quote_textbook=false`、`can_answer_from_textbook=false` |
| `no_evidence` | 没有合格候选页，返回空页列表，不发 citation，并提示调整关键词或打开教材 |
| 错误/证据不一致/档案变化 | 返回不可用错误，不发 citation，不带旧参考 |

这些是工具返回的能力边界；本轮没有实现生成后逐句拦截器，因此不能保证聊天模型一定遵循提示。候选页也未经过本轮相关性评测，`locations_only` 不代表该页一定回答了问题。

## 已核验片段设计与离线进展

完整目标是 **回答中的断言 → 已核验片段 ID → sourceRef → 原文件与精确位置**。不得直接将当前 `page_location` 改成 `reviewed_passage`。

1. 片段单独保存 `text`、`text_sha256`、`source_ref`、两套页码、上下文范围；只有真实核对过位置时才提供框坐标。公式、单位、图表和题中错例须保留上下文。
2. 复核记录绑定源 PDF、片段文字及必要原图哈希，分别记录转写复核与独立内容复核、复核者类型和未解决问题。文本或来源改变即失效；助手核对不能冒称教师签署。
3. 可用状态必须由本地审核记录计算，不能由检索分数、模型自述或索引 metadata 提供。审核未过、被停用、过期或越界的片段不能成为回答依据。
4. 片段身份绑定来源、位置、文字哈希和审核版本；回答断言显式关联片段 ID。引用存在性、版本/范围一致性可以机械检查，“片段是否支持断言”需要另做内容核验。
5. 检索验证与回答依据验证分开记录：前者看命中页/片段，后者看引文准确、逐项支持和无证据时的行为。没有证据时不能用模型记忆补写成教材结论。

独立离线样本已选七上数学第二章 27、31、40、41、42 页的 5 个完整文字法则/定义，保留逐条助手转写核对、数学论证与精确有理数检查；配套 20 个直问、改写、越章和无依据问句。实现位于 `scripts/textbook_passage_sample.py`，限定原文、原图与复核记录保存在忽略目录。片段通过不代表整页通过；二下数学的整页双重审核通过数继续为 0。

离线样本采用 `assistant_reviewed_excerpt` 类型，支持如实标注的引文展示，仍令 `can_answer_from_textbook=false`。固定审核清单、源 PDF、原图、文字、上下文、复核记录、数学检查及其脚本均检查哈希；待复核、停用、过期、有未解决问题的片段不返回。正文只允许逐字引文及本次检索中的证据 ID，不生成自由回答。检索为显式词项匹配，20 问是开发样本，不是盲测准确率；不具备任意答案的语义支持判定。见 [完整验证与复跑方式](../verification/textbook-passages-2026-11-07.md)。

## RAGFlow 设计来源与许可

参考 `infiniflow/ragflow` **v1.0.0**（2026-11-06），固定 commit `db1cd5929a7885a3074547791f5ecc4d2f891739`，上游 [Apache-2.0 LICENSE](https://github.com/infiniflow/ragflow/blob/db1cd5929a7885a3074547791f5ecc4d2f891739/LICENSE)。本项目独立实现上述代码，没有复制或打包 RAGFlow 源码、文档正文或教材。

| 参考 | 本地采用或保留的设计 |
| --- | --- |
| [分块检查与启停](https://github.com/infiniflow/ragflow/blob/db1cd5929a7885a3074547791f5ecc4d2f891739/docs/guides/dataset/chunk_parsing_results_and_knowledge_fragment_management.md) | 对原文核对、区分可用性与检索命中；片段审核/启停仍待实现 |
| [Metadata 管理](https://github.com/infiniflow/ragflow/blob/db1cd5929a7885a3074547791f5ecc4d2f891739/docs/guides/dataset/metadata_management.md) | 保留教材、版本、页码；当前复用已有范围约束 |
| [检索测试](https://github.com/infiniflow/ragflow/blob/db1cd5929a7885a3074547791f5ecc4d2f891739/docs/guides/dataset/retrieval_testing.md) | 区分召回问题与回答问题，后续分开评测 |
| [引用解析](https://github.com/infiniflow/ragflow/blob/db1cd5929a7885a3074547791f5ecc4d2f891739/web/src/utils/citation-utils.ts) | 对不透明证据 ID 按身份解析；展示序号和检索顺序不充当证据身份 |
| [原文定位](https://github.com/infiniflow/ragflow/blob/db1cd5929a7885a3074547791f5ecc4d2f891739/web/src/utils/source-locate.ts) | 只承诺已有位置精度；本地当前精度为整页 |

上游软件许可不改变教材版权，也不替代本仓库的教材审核规则。

## 部署边界

新字段是现有服务响应的增量。旧 Tool 可以继续忽略它们；候选 Tool 1.1.0 需要本轮服务端证据字段，不应单独放到旧网关上。现有注册脚本的来源哈希和拒绝覆盖保护保留，禁止用它重新注册或覆盖已上线 Tool。

本轮只做本地候选、合成测试和断网原生加载验证，没有修改线上 Tool、绑定、Compose、数据卷、向量库或 Goal，没有调用真实生成/embedding 模型。
