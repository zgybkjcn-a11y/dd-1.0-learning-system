# A05 章内召回与证据不足判定验收

日期：2026-11-07（Asia/Shanghai）。本地五片段候选已达到冻结试点指标，旧整册检索路径明确标记覆盖不完整。**五片段尚未接入服务/Tool，整册真实向量召回仍未修复**；下一项为 A07。未提交、推送、部署、调用真实生成/embedding/OCR、写生产向量库或 Goal。

## 实现与接口证据

证据根目录：`learning_data/verification/a05-chapter-retrieval-20261107T131135Z/`。开始时保存 56 个已有未提交文件、Git HEAD/index 哈希及副本；HEAD 为 `deef3199f558ba72bbe3f2ff0c704586674a2232`。A06 全部材料、冻结题集与结果另作指纹记录并保留原样。

固定 WebUI 0.12.5 镜像的 `query/doc` 表单没有章节过滤字段。断网探针执行镜像内原表单和原查询函数，以合成向量库替代外部依赖：`where` / `metadata_filter` 被忽略，search 只收到 collection_name/vectors/limit；40 条章外结果挤掉第 41 条章内结果。证据为 `webui-query-source.json`、`webui-filter-probe.json`。没有访问真实查询端点或触发 embedding。完整能力表及字段定义见[检索设计](../open-webui-reuse/chapter-retrieval.md)。

本批改动：

- 新增离线 `textbook_passage_retrieval.py`：先授权并过滤书章，再按五类规则/定义意图及算式结构匹配；去重、评分、top4 和页码展示顺序分开；引用原片段全文，不计算或生成答案。
- 区分 no_evidence、low_relevance、insufficient_evidence；明确要求证明、图示、题目解答或其他不支持任务时不因词项命中而给引文。
- 旧 top40 路径增加 `retrieval.status=incomplete`、coverage_complete=false、排名记录和按页阅读恢复提示；有候选和空候选均不声称完整检索。
- 网关补充检索后的身份/档案/revision 校验，查询中切换档案或复核失败即丢弃旧结果；原 Tool 前后校验保留。
- Tool 本地候选 **1.1.2**、阅读页同步显示覆盖不足；旧服务缺少覆盖字段时也按未知/不完整处理。仍只返回原页位置，不转发未核验索引正文。

原样本检索脚本、原评分器、源 PDF、五片段正文、审核记录和词项均未修改。新逻辑不借用生产向量库，服务目前也没有导入这个离线脚本。A07 再抽取模块、接入路由和更新运行封包白名单。

## 评测冻结与结果

A06 40 问于本批明确转为改进回归集，其原 baseline/defects/exposure 文件保持历史原样，本批新增暴露及解决记录。开发 20 问、审计 4 问分别报告。补充 40 问在实现前于 **21:14:01 +08:00** 冻结，结构仍为 20 可回答 / 10 无依据 / 10 范围负例；与旧 64 问无规范化后完全重复的表达。首次补充评测前固定候选哈希，之后没有按补充题调参。

| 身份 | SHA256 |
| --- | --- |
| `a05-supplement-v1` | `ceddad4c8af01d6959923030acbc9b8b03aa9daa5ac88f6200723ee75539a368` |
| `candidate-freeze.json` | `3011a946eb85b4a49c62736b6cef2e6c196a44e64c336856d01cbb463e09dcd8` |
| 候选检索脚本 | `f0efc897e6dc8c4a2f293f0f3074c4556ad92b0bf7192a6ffeda08568b0f8cb2` |
| Tool 1.1.2 | `a158f47774062a454d6c12bb9944d1b480542ddafba384b71fd0103987afedd1` |
| 149 文件源码清单 | `2d5d228834888970f85734399eac15cefd25c0360bbc778af55ae8a0886d19f0` |

| 指标 | A06 原基线 | A05 对 A06 回归集 | A05 冻结补充集首次结果 |
| --- | --- | --- | --- |
| Recall@4 | 2/20 | **20/20** | **20/20** |
| 无依据拒绝 | 2/10 | **10/10** | **10/10** |
| 范围泄漏 / 成功处理 | 0/10 / 10/10 | **0/10 / 10/10** | **0/10 / 10/10** |
| 来源/版本/双页码准确 | 11/11 | **22/22** | **22/22** |
| 完整引文一致 / 完整交付 | 11/11 / 11/11 | **22/22 / 22/22** | **22/22 / 22/22** |
| 相关精确率 | 2/11 | **22/22** | **22/22** |
| 全部必需关联 | 2/22 | **22/22** | **22/22** |
| 多证据题 / 必需关联 | 0/2 / 0/4 | **2/2 / 4/4** | **2/2 / 4/4** |
| 精确符合预期 / 执行错误 | 14/40 / 0 | **40/40 / 0** | **40/40 / 0** |

补充集逐概念：加法 5/5、减法 5/5、倒数 4/4、分配律 5/5、积的符号 3/3，共 22 个必需关联。旧开发集维持精确通过 20/20，其中可回答召回 15/15；审计回归从召回 0/4 改善为 4/4，来源与引文均 4/4。A06 的 30 项缺陷已在本地离线候选回归中解决，原缺陷不删除，解决记录在 `defect-resolution.json`。

补充集第二次使用相同代码和新输出目录复现，除执行时间外所有字段一致。r1 结果 SHA256 为 `978f536aec7d6ac4ad47240c68e434c2b0aad1453ed8c41706fd0ac081c78af4`；r2 为 `d3458aec2a162602ce0fc1a1f17e77c83b0549fc9124dc2e180132170ecc28e9`。材料均按执行当天验证，没有历史日期绕过。

真实题目、预期 ID、金标准全文和逐题输出只在忽略目录。两组评测共用五个片段/概念，补充题仍由同一助手编写、复核并实现，作者已知 A06 失败；**不能称独立人员、教师或外部盲测**。规则语法与任务排除仍可能误判未测试表达；小样本通过不能外推全书、教学效果或真实模型遵循能力。

## 合成、浏览器与兼容验证

复用 A03 锁定 Python 3.12.12 环境、Chromium 145.0.7632.6。相关检查合计 **241 项单元/契约 + 4 项浏览器通过**，零失败、错误、跳过；未重跑无关全套。`unit-r2.xml` 共 243 项，其中 241 项单元/契约及主站桥接桌面/手机 2 项；`browser-r1.xml` 另含家庭阅读桌面/手机 2 项，不重复计数。

```bash
python -m pytest -q tests/test_chapter_retrieval.py tests/test_textbooks.py \
  tests/test_readonly_study_tools.py tests/test_study_errors.py \
  tests/test_textbook_passage_sample.py tests/test_textbook_retrieval_evaluation.py \
  tests/test_login_gateway.py tests/test_main_study_bridge.py tests/test_learning_release.py
python -m pytest -q -m browser tests/test_family_adventure_browser.py
```

新增 38 项覆盖规则识别、无依据拒绝、前置范围过滤、top40 反例、排序/去重、缺少组合依据、网关查询后换档/身份冲突/服务失败、Tool 覆盖投影及旧服务退化；原页级与 A04 故障测试继续通过。十项 release 检查覆盖旧 profile；运行封包尚未增加离线检索脚本。

浏览器实际验证有结果/空结果的不足提示、清空关键词恢复按页阅读，以及已有主站桥接/切档保护。首次相关组 205 通过、4 失败，均为测试预期：两个旧 grounding 状态需适配新 incomplete 契约，两个新增断言需使用既有 401 身份冲突和 REFERENCE_INVALID 错误码；原失败记录保留。

固定镜像原生六方法加载与两条 citation **通过**，结果存于 `native-result.json`、`native-exit-r2.json`、`native-r2.log`。首次隔离探针在依赖导入阶段超过 90 秒，未进入断言；临时容器已停止，随后按既有离线原生流程重试成功。真实模型、生产挂载、正式 Tool 注册、远端 CI 和人工体验均未执行。

## 交付与接续

`source-manifest.json` / `clean-source/` 固定 149 文件；`test-summary.json` 分开记录单元、两组浏览器与原生证据。`increment-manifest.json`、`a05-increment.patch`、`increment-replay/` 只描述本批相对开始状态的增量；`delivery-validation.json` 核对哈希、原材料/旧证据保全、台账、链接和补丁回放。A02/A04/A06 审阅包保持原样，不能据其旧哈希提交当前工作树。

源码和报告为未提交候选；运行快照仍沿用 A01 的 17:00:50–17:00:53，本批没有刷新线上状态。片段继续是助手核对、非整页/教师审核、非判分依据。A05 仅完成本地有界试点与旧路径降级出口；A07 接入、A08 升级/回退、真实模型和实际体验分别验收。下一项 **A07：接入 5 个有效片段**，默认关闭新能力，固定服务器材料/哈希/当前时间并验证旧版本兼容。
