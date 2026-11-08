# A07 五片段服务与六方法 Tool 本地验收

2026-11-07（Asia/Shanghai）。五个有效片段已接入本地服务、网关、六方法 Tool 1.2.0 与阅读工作台；能力默认关闭，未部署。下一项 A08：既有 Tool 升级与回退机制。未提交、推送、调用真实生成/embedding/OCR、写生产向量库或 Goal。

## 实现与边界

证据目录：`learning_data/verification/a07-runtime-passages-20261107T135307Z/`。`workspace-before.json`、`files-before/`、`clean-inputs.json` 保存原有未提交文件和将修改的干净文件；HEAD 与 index 保持原样。A02/A04/A06/A05 历史包及五片段原材料保留。

运行模块为 `learning_service/passage_evidence.py`（源与审核绑定）、`passage_retrieval.py`（原 A05 有界检索）、`textbook_passages.py`（当前有效性和响应契约）。旧 scripts 入口兼容转发，运行模块不导入 scripts。A05 匹配算法 AST 完全一致，未按既有评测结果再调参。

服务器配置固定目录与清单 hash；启动校验、查询、详情与绑定原图均校验当前日期和材料，读取前后快照变化拒绝。北京时间截止日有效，次日零点失效；接口不接受历史日期、路径、身份或 pin。查询为 `mode=passages`，旧 items 保持页定位，新增 passage_result 返回完整引文、上下文、审核身份与覆盖状态。启用后坏材料停止检索，不回退未审核向量正文；空关键词原页阅读继续可用。

Tool 检查全文 hash、稳定证据 ID、双页码、审核日期与能力标记；逐项详情核验后重查整组结果，再核会话。完整 `answer.claims` 与原生 citation document 一致，原页链接带 studyEvidence 和 context revision。工作台在命中导航、图片加载后和重开链接时核验，失效清除旧引文。`teacher_reviewed=false`、`fully_reviewed_page=false`、`eligible_as_grading_basis=false`、`can_answer_from_textbook=false` 始终保留。

没有实时撤回推送；已持续显示的片段在下一次展示/导航/可见性变化时核验，到期计时清除。历史聊天文字无法追溯删除，重开引用必须重新授权。真实模型是否遵循引文约束、家长设备体验与教师审核仍未验收。部署配置、错误码和回退见[运行说明](../open-webui-reuse/textbook-passages-runtime.md)。

## 验证

**688项单元/契约（源码副本687项，另1项历史1.0.0兼容）+6项浏览器全部通过，零失败、错误、跳过。** 新Tool另外在A05原149文件服务/网关源码副本上通过原30项Tool集成检查；只替换Tool，不用新服务模拟旧服务。 最终计数与逐组证据见本目录 `test-summary.json`；JUnit 及失败排查日志完整保留。复用 A03 锁定 Python 3.12.12 / Chromium 145.0.7632.6，源码副本运行全部默认后端测试；浏览器为真实服务/网关搭配合成身份和合成 PDF，覆盖手机390与桌面1280。

新增检查覆盖：缺文件/坏 pin、改文字/上下文/源 PDF/图像/数学检查/审核 revision、撤回/禁用/待审/未解决问题、目录越界和祖先软链接、有效期起止和北京时间午夜、查询中跨日、服务/网关/Tool 请求中换档、旧缓存详情/图片失效、引文和 citation 绑定、默认关闭、禁止客户端材料/日期/身份参数、OpenAPI 快照一致和旧 release profile。

首轮既有相关127项与新增45项通过；补充档案复核后48项通过。浏览器初轮发现家庭工作台启动时计时变量尚未初始化，已移到首次清理前。随后测试夹具补家庭模式，并修正 Playwright 事件循环内调用 asyncio.run 的测试写法；原失败日志保留。实物回归初轮适配器遗漏 scope 字段，被原评分器正确拒绝；补传 Tool 已输出的 book_id/chapter_id 后通过，未改题集、算法或阈值。

固定 WebUI 0.12.5 镜像 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd` 在 network=none、只读根、临时 data 下原生加载六方法，4条 citation 通过，其中2条完整片段引文。`native-command.json`、`native-exit.json`、`native-result.json` 记录调用与退出；模型参数无身份/时间/路径，未挂正式 data。导入耗时约170秒，退出0，无重试。

| 兼容组合 | 本地结果 |
| --- | --- |
| 历史发布 Tool 1.0.0 + A07服务 | 页引用可用，不获得片段全文权限；源码从 HEAD 读取，hash匹配历史记录，未回读正式库 |
| A05 Tool 1.1.2 + A07服务 | 页定位 + incomplete，不引用片段全文 |
| Tool 1.2.0 + A05页级响应/关闭片段 | 保留页定位，can_quote_textbook=false |
| Tool 1.2.0 + A07服务 | 完整引文、证据、citation、原页回链通过 |
| 历史线上服务 + 新Tool | 不宣称兼容；历史服务缺页级 evidence，需配套升级服务/网关 |
| 新release profile与此前profile | 白名单/可重现封包/拒绝软链接/旧profile验证通过；无构建或部署 |

## 五片段实物回归

原清单 SHA256 `d1bf256db814afcf35ff22f28ad32fd4577b4608e12f9d069b7f72cfc8cacd63`，源 PDF SHA256 `d995a2072c2b00418eacf1fdfc7a00234953592f5fba61a4b227731c8a19fdd8`。按执行当天2026-11-07验证，五片段可用，原审核至2026-12-07。五张绑定原图和完整正文 hash 均一致，原21个包文件及PDF共22个文件未改。

| 题集（既有、已暴露回归） | 精确通过 | 可回答召回 | 无依据拒绝 | 范围泄漏 |
| --- | --- | --- | --- | --- |
| A06原40问 | 40/40 | 20/20 | 10/10 | 0/10 |
| A05补充40问 | 40/40 | 20/20 | 10/10 | 0/10 |
| 旧开发20问 | 20/20 | 15/15 | 独立记录 | 独立记录 |
| 旧审计4问 | 4/4 | 4/4 | 不适用 | 不适用 |

两组40问分别来源/全文22/22、多证据2/2；分母不混合。`material-summary.json` 为指标，`material-results.json` 为本地私有逐题输出，`run_material_regression.py` 为本次适配器。实物部分走服务纯业务和Tool投影，授权/并发另外由合成集验证；不是正式部署端到端或新盲测。题集、原审核、原评测输出未改，同一助手实现/核验，非教师/独立人员审核。

## 交付与续接

新 `reuse-runtime-textbook-passages-v1` 含三个运行模块、Tool和引用桥接；OpenAPI更新为73 paths / 35 schemas。`source-manifest.json` 固定166文件最终源码副本，`test-source-manifest.json`保留全后端测试时164文件输入（后续仅文档及额外历史Tool测试增加）；`release-candidate/` 为76文件确定性源码包，image_digest=null；`increment-manifest.json` / `a07-increment.patch` / `increment-replay/` 为本批增量；`delivery-validation.json` 核对保全、hash、隐私、链接、台账及回放。

只读材料部署说明见[运行契约](../open-webui-reuse/textbook-passages-runtime.md)，[当前清单](../releases/current-manifest.json)、[台账](../plans/dd-next-work-tracker.json)、[续接指令](../plans/RESUME-NEXT-WORK.txt)同步。线上观察仍为A01 **17:00:50–17:00:53 +08:00**；未刷新生产状态，正式Tool仅历史1.0.0证据。A02仍为已整理待提交、总状态open。本批为未提交本地候选，下一项A08在临时数据中验证既有ID升级与回退，不直接注册或重绑正式Tool。
