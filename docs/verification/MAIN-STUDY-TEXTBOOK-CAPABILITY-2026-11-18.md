# 主站教材能力状态（2026-11-18）

## 结论

主站“家庭学习资料”区现在对**当前课本**显示服务端返回的真实能力：原页可读、是否支持关键词检索、已安装练习数、局部知识映射题数。数值全部由数据库与已审映射推导，不由前端推断；新 7 册显示“仅原页阅读”，不会借用相邻书册的练习或覆盖。

## 实现

| 文件 | 改动 |
| --- | --- |
| `learning_service/textbook_capabilities.py`（新增） | `book_capabilities(conn, curriculum)`：按已安装且已批准的题版统计每册题量，章节题按 `objective-family-chapter-<书>-<章>` 前缀归册，起步/备用题库按自身 `book_id` 归册；映射题数取自已审 `family_concepts_v1.json` 且必须是已安装题；`search_available=False` 的书给出“仅原页阅读”说明 |
| `learning_service/evidence_contracts.py` | 新增 `TextbookCapabilities` 契约，`TextbookBook.capabilities` 为可选字段 |
| `learning_service/study_routes.py` | `GET /api/v1/textbooks` 为每册附加 `capabilities` |
| `deploy/open-webui-reuse/main-study/study.js` | 新增 `#dd-study-book-capability`，`renderBookCapability()` 只按服务端字段拼句；档案/课本变化时随之更新 |
| `deploy/open-webui-reuse/main-study/study.css` | 能力行样式、深色模式与窄屏尺寸 |
| `docs/contracts/openapi-v1.json` | 重新生成：路径仍 77，schema 44→45，仅新增 `TextbookCapabilities` 与 `TextbookBook.capabilities` |
| `scripts/upgrade_readonly_study_tool.py` | 重钉 `study_routes.py`、`evidence_contracts.py`、`docs/contracts/openapi-v1.json` 三个哈希 |

设计约束：能力状态只读，不加载章节题库文件（避免为描述一本书而重新解析并校验全部批次）；映射参考被撤回时按“无映射”降级，不影响目录可用。

## 事实样例（本地已安装状态）

| 册 | 关键词检索 | 已安装练习 | 映射题 |
| --- | --- | --- | --- |
| 二上数学 | 支持 | 有 | 12 |
| 七上数学 | 支持 | 有 | 8 |
| 二下数学 / 二下道法 | 不支持 | 有（候选已安装） | 0 |
| 七下英语/道法/历史/地理/生物 | 不支持 | 有（候选已安装） | 0 |

新 7 册有练习但**没有**逐题知识映射，界面因此显示“有已安装练习，但没有已核对的逐题知识映射”，而不是“覆盖完整”。

## 隔离冒烟（生产数据副本）

首个候选镜像 `sha256:648914fd…`（后被 `-r2` 取代，原因见发布一节）在内部网络用生产数据库副本启动，未接触运行中服务：

| 册 | 关键词检索 | 已安装练习 | 映射题 |
| --- | --- | --- | --- |
| 二上数学 | 支持 | 264 | 12 |
| 二上道法 / 二上语文 / 二下语文 | 支持 | 27 / 62 / 58 | 0 |
| 二下数学 / 二下道法 | 不支持 | 11 / 6 | 0 |

七年级同理由服务端返回（七上数学 238 题、8 道映射；新下册五科检索关闭）。说明文字按事实组合：可检索且有映射、可检索无映射、检索关闭、无练习四种，互相不矛盾。

## 验证

| 项目 | 结果 |
| --- | --- |
| 新增定向 | `tests/test_textbook_capabilities.py` 9 项通过（只统计已安装、读本册不借邻册、检索开关与目录一致、映射数只算已安装题，另 4 项说明文字一致性） |
| 目录契约 | `tests/test_textbooks.py`、`tests/test_evidence_modules.py` 调整后 37 项通过 |
| 只读工具 | `tests/test_readonly_tool_upgrade.py` 53 项、`test_runtime_passages.py` + `test_c01_tool_fixtures.py` 62 项通过 |
| 主站浏览器 | `test_main_study_bridge.py` 1280/390 各 1 项通过；`test_main_study_host.py` 19 项通过 |
| 全量非浏览器 | `pytest tests -q -m "not browser and not local_materials"`：**1267 通过**、55 排除，566.96 秒（文案修复后；修复前同集合 1263 通过、573.78 秒） |
| CI | run 44279792862（commit `14c2cac`）：单元/契约 **1190 通过**（55 排除，179.85 秒）、浏览器 **53 通过**（651.66 秒），0 失败 |

## 生产发布（2026-11-18，用户授权）

按停写 → 备份校验 → 切换 → 逐表比对 → 冒烟的顺序发布：

| 项目 | 结果 |
| --- | --- |
| 旧版本 | 镜像 `sha256:de8a6472…`，Compose `family-main-study-p1-20261118/compose.json` |
| 当前版本 | 镜像 `dd-learning:main-study-capability-20261118-r2` = `sha256:a228872c…`；Compose `family-main-study-capability-20261118/compose.json`（`1841629d…`） |
| 静态 | `family-main-study-capability-20261118/assets`：`study.js` `9703f0f3…`→`ef7b357d…`、`study.css` `113fdfe4…`→`4164d004…`、`SOURCES.md` 补说明；bridge 与 Mermaid 逐字节不变 |
| 停写与备份 | 两次（首次切换、修正文案后重发）均先停 api/worker/gateway；最终备份 `private-r2/snapshot`，passed、校验 passed（`77496e2b…`），schema14 / integrity ok / 外键 0 |
| 数据保全 | 50 表与备份逐表行哈希完全一致（本批不写库）；1226 题、99 次作答、28 条审计事件、schema14 不变 |
| 路由 | `/health` 200、`/learning/ui` 303、`/learning/auth/login` 303、未认证 `question-choices` 与 `textbooks` 均 401 |
| 静态读取 | 四个路由 200、no-store、MIME 正确，哈希与发布目录一致 |
| 能力接口 | `family-g2` `textbooks` 200（0.073 秒）：二上数学 264 题/12 映射；二下数学 11 题且检索关闭、文案为“原页可读；本册暂不支持关键词检索…” |
| 其他接口 | `question-choices` 436 项、`study-path` 200（resume+practice，15 分钟）、OpenAPI 77 路径含 `TextbookCapabilities` |
| 部署后浏览器 | `scripts/probe_main_study.py`（`DD_MAIN_STUDY_DEPLOYED=1`）1280/390 通过，页面错误 0、模型调用 0 |


**发布中修正的一处不实文案**：首个镜像 `sha256:648914fd…` 对检索关闭的册写成“原文可读、可检索”。运行约 3 分钟后停写、重发 `-r2`，说明文字改为由事实组合，并新增 4 项文案一致性测试（读只读册时不得出现“可检索”）。两次回执与比对均在 `learning_data/verification/main-study-capability-20261118/`。

证据：`learning_data/verification/main-study-capability-20261118/`（`pre-state.txt`、`db-before.txt`、`post-state.json`、`merged-data.json`、`deployment.json`、`data-preservation.json`、备份回执与快照、`deployed-probe/`）。

## 未做与边界

- 只展示能力，不展示掌握度、完成率或覆盖率；没有新增题库、没有临时编题。
- 章节级能力未细分到“这一章有没有题”，仍是整册口径，避免把整册结论误读为逐章覆盖。
- “教材能力状态”之外的主站 P2/P3 建议（阅读位置与书签、家长回顾、新册全文检索）未实施。
- 未调用外部模型/OCR/embedding，C01 未启动，真实手机验收继续暂缓。
