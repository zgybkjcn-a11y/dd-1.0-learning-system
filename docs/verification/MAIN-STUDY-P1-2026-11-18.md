# 主站 P1：第四档难度与统一学习入口（2026-11-18）

## 范围

按交接 `docs/plans/HANDOFF-SESSION-2026-11-13-MAIN-SITE.md` 第 6 节 P1，先做两项已明确的能力一致性改动：

1. 主站“知识路线与关联练习”补齐第四档“挑战”，并按真实映射显示空态。
2. 主站学科伴学面板新增“今天从这里继续”，汇总当前档案、课本/章节、续做、到期复习、练习/阅读建议与错题入口。

第三项“教材能力状态”未在本次改动中实现；主站仍不会声称新 7 册有练习或完整知识映射。

## 实现

| 文件 | 改动 |
| --- | --- |
| `deploy/open-webui-reuse/main-study/study.js` | 难度标签与下拉增加 `challenge: '挑战'`；空态改为按当前范围真实返回的难度逐一说明，不再只说“暂无”；新增 `loadToday()`/`renderToday()`，读取只读 `/api/v1/study-path` 并生成带 `studyRevision` 的深链；档案变化时清空并提示；失败时可重试或打开家庭页 |
| `deploy/open-webui-reuse/main-study/study.css` | 统一入口卡片、深色模式与移动端触控尺寸 |
| `learning_service/login_gateway.py` | 网关允许 `GET /learning/api/v1/study-path`，并纳入学习超时/错误传播；此前家庭页自己的“今天从这里开始”经网关会得到 404 `ROUTE_REJECTED` |
| `scripts/upgrade_readonly_study_tool.py` | 重新固定 `login_gateway.py` 哈希 |

统一入口不读取令牌、作答、成绩或题库答案；只调用既有同源只读接口，并在请求后再次核对 `/auth/session` 的上下文版本。

## 真实映射核对

本地已审映射 `learning_service/data/family_concepts_v1.json` 仍为 20 道题、18 个概念，难度只有 `easy/normal/hard`，**没有** `challenge`。因此：

- 下拉框会显示“挑战”，选中后显示“这个知识点当前没有已核对的‘挑战’题；已核对映射只有简单、正常、困难”，且不生成任何练习链接；
- 路线状态同时显示“当前映射没有挑战档”；
- 不把其他难度题改标为挑战，也不临时编题。

新增 `tests/test_math_references.py::test_reviewed_mappings_have_no_fourth_tier_questions` 固定这一事实；若以后映射加入挑战题，该测试会提醒同步更新说明。

## 验证

| 项目 | 结果 |
| --- | --- |
| 主站浏览器（1280/390） | `tests/test_main_study_bridge.py` + `tests/test_main_study_host.py` 21 项通过（362.52 秒） |
| 第四档空态 | 选中“挑战”时显示真实空态，练习链接数为 0；选“正常”时同样显示真实缺失的难度 |
| 统一入口 | 显示当前档案与第二章节，含错题收藏入口；`study-path` 经网关返回 200 |
| 网关边界 | 新增 `GET study-path` 转发与 `POST/PUT` 拒绝测试；未认证为 401 |
| 全量非浏览器 | `python -m pytest tests -q -m "not browser and not local_materials"`：1258 通过，55 排除（browser/local_materials），515.82 秒（缓存修复后；修复前同集合 3721.47 秒） |
| 章节练习浏览器 | CI run 44248722760（commit `1ce7334`）浏览器 53 项通过（704.06 秒），含 `test_chapter_practice_browser.py`、`test_challenge_tier_browser.py` |
| CI | run 44248722760：单元/契约 1181 通过（55 排除，225.59 秒）、浏览器 53 通过，0 失败 |

## 生产发布（2026-11-18）

按用户随后授权，主站 P1 静态资源已发布到本机生产，仅重建 `learning-proxy`：

| 项目 | 结果 |
| --- | --- |
| 静态目录 | 新发布目录 `learning_data/deployments/family-main-study-p1-20261118/assets` 挂到 `/opt/dd-main-study`；旧目录保留 |
| 文件 | `study.js` `0955ec05…`→`9703f0f3…`；`study.css` `d276f5ce…`→`113fdfe4…`；`SOURCES.md` 补 P1 说明；`family-bridge.js`、`vendor/mermaid-11.12.1.min.js` 逐字节不变 |
| Compose | `learning_data/deployments/family-main-study-p1-20261118/compose.json`（`9b4ccea1…`），相对上一版仅改 proxy 的静态 bind source；nginx 配置未改（`47522e68…`） |
| 切换 | `docker compose … up -d learning-proxy`；api/worker/gateway、open-webui 与 C01 均未重启 |
| 匿名读取 | 四个静态路由 200、no-store、MIME 正确，哈希与发布目录逐字节一致；`node --check study.js` 通过 |
| 服务路由 | `/health` 200、`/learning/ui` 303、未认证 `question-choices` 401 |
| 部署后浏览器 | `scripts/probe_main_study.py`（`DD_MAIN_STUDY_DEPLOYED=1`，复用线上真实静态字节、API 全部合成拦截）1280/390 两视口通过，页面错误 0、模型调用 0 |
| 回退 | 用 `family-question-bank-cache-20261118/compose.json` 重建 `learning-proxy`，旧静态目录仍在 |

证据：`learning_data/verification/main-study-p1-20261118/`（`pre-state.txt`、`post-state.txt`、`deployment.json`、`deployed-probe/`）。

## 未做与边界

- P1 的两项能力已上线；浏览器探针未模拟家庭登录，挑战空态与统一入口的行为由同字节的合成浏览器用例（CI 浏览器 53 项）覆盖。
- “教材能力状态”未实现；不向不存在的索引发请求，也不展示虚假练习覆盖。
- 统一入口的顺序来自 `study-path` 的既有只读规则（续做 → 到期复习 → 练习/阅读 → 选范围），不代表掌握程度；未完成题切换仍由家庭页的确认流程处理。
- 未调用外部模型/OCR/embedding，未启动 C01，真实手机验收继续暂缓。
