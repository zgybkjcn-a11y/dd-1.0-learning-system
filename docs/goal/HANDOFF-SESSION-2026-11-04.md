# DD-1.0 V1 会话交接（2026-11-04）

更新时间：2026-11-04（Asia/Tokyo）
项目：DD-1.0 学习服务；工作目录：`/home/deniskorfei/projects/open-webui`；分支：`main`。

## 交接结论

本会话完成错题录入扩展、腾讯云教育 OCR provider 接入、导入确认后的错题内容持久化修复和本地回归。当前全量测试为 **101 passed**。腾讯 OCR 的代码路径、TC3 签名和合成响应已由测试覆盖，但使用的是占位密钥和模拟 HTTP 响应；**没有真实腾讯 API 调用、没有真实试卷样本、没有真实 OCR 质量结论，也没有部署**。

Goal 的仓库任务状态仍是 `blocked`：T04、T05、T23 缺少外部前置条件。`docs/goal/STATUS.md` 记载 Goal 工具状态为 `paused`，但本会话调用 `get_goal` 得到 `goal: null`。新会话应重新核对 Goal 工具状态；不要仅凭仓库文字推断 Goal API 中仍有活动目标，也不要将 Goal 标为 complete。

此前用户提出目前没有试卷/作业样本时可否先部署、之后再修复。现有代码允许在隔离环境做技术联调，但生产部署、付费 OCR 和真实资料外发没有在本会话执行或获批。没有真实样本就不能验收识别质量；不得将合成回归写成真实质量通过。

## 本会话完成内容

1. 错题本支持手动录入、图片/PDF 待复核候选、DOCX/XLSX 整份文档文本候选。文档导入采用“先生成候选、用户整理并确认后才进入错题本”。Office 走本地 OOXML 文本提取，不处理 `.doc`/`.xls`、嵌入扫描图、复杂版面或公式语义。
2. 接入腾讯云教育 OCR `QuestionSplitOCR`：TC3-HMAC-SHA256、图片 Base64、`UseNewModel` 配置、题目拆分、坐标转区域，并将每题生成为单独的待复核候选。返回的图片/裁剪数据不会持久化；API 错误、超时和超大响应会安全降级。
3. 增加配置项：`TENCENT_OCR_SECRET_ID`、`TENCENT_OCR_SECRET_KEY`、`TENCENT_OCR_TIMEOUT_SECONDS`、`TENCENT_OCR_USE_NEW_MODEL`、`TENCENT_OCR_EXTERNAL_CALLS_ENABLED`。`.env.example` 中密钥是占位符；默认 provider 仍为 mock，外发开关为 `0`。不能只填密钥就认为 provider 已授权或可用。
4. 增加腾讯 OCR 合成边界测试；补齐 PNG、PDF、DOCX、XLSX 导入确认后错题本列表/详情回归，修复确认路径未写入 `mistake_entries.content_json` 的缺口，并修正 Goal/QA/发布 manifest 中的当前测试数量。**没有修改 T05 状态**，仍为 blocked。

主要代码和文档：

- 腾讯 OCR provider、签名和响应清理：[learning_service/providers.py](../../learning_service/providers.py)
- Provider 配置：[learning_service/config.py](../../learning_service/config.py)、[.env.example](../../.env.example)
- 文档与手动错题导入：[learning_service/app.py](../../learning_service/app.py)
- 腾讯 OCR 回归：[tests/test_tencent_ocr.py](../../tests/test_tencent_ocr.py)
- 错题导入范围：[PAPER_HOMEWORK_IMPORT_DESIGN.md](../PAPER_HOMEWORK_IMPORT_DESIGN.md)
- 当前任务台账：[TASKS.json](TASKS.json)、[STATUS.md](STATUS.md)、[BLOCKERS.md](BLOCKERS.md)

## 当前任务状态

状态来源为 `docs/goal/TASKS.json`，不要用历史计划表覆盖它。

| 状态 | 任务 | 进度说明 |
| --- | --- | --- |
| `verified` | T01、T02、T06、T07、T08、T11、T15、T17、T19 | 本地/隔离实现和对应确定性证据已具备；各项真实入口边界见任务台账。 |
| `implemented` | T03、T09、T10、T12、T13、T14、T16、T18、T20、T21、T22 | 本地代码已实现，但分别仍有真实模型/浏览器回调、样本质量、人工审核或外部服务故障演练门槛。 |
| `blocked` | T04、T05、T23 | 缺少脱敏整卷及人工参考判定、真实 provider 调用授权，或真实试用参与者/时长条件。 |
| `deferred` | T24、T25、T26 | V1 后续范围，除非用户明确扩大范围，否则不启动。 |

### 验证结果

```text
pytest -q
101 passed in 18.56s
```

测试分布：服务 76、Tools 11、Open WebUI 兼容 3、腾讯 OCR 边界 5、隔离 Compose preflight 6。另已通过：

```text
python3 -m compileall -q learning_service tests scripts
git diff --check
python3 scripts/verify_goal_consistency.py
tasks=26, evidence paths=144, backlog task rows=26, QA matrix rows=17, manifest path references=22, release authorization boundaries intact
```

这些是本地确定性/合成数据证据，不覆盖腾讯云真实调用或真实试卷质量。

## 尚未完成和缺少的条件

- **T03/T16/T18/T20：真实 Open WebUI 链路。** 尚无隔离模型配置和最终可信 UI 回调的端到端验收。需在 disposable/staging 环境完成模型 tool call、原生输入/确认、成功/取消/超时/刷新恢复、跨学习者拒绝；生产 Open WebUI 和正式数据不参与。
- **T04：人工参考数据。** 没有脱敏多页试卷/作业样本、逐题人工转写/题目边界/作答/批改参考判定，也没有明确验收集和审核人。无此数据不能计算准确率、召回率或漏题率。
- **T05：真实 provider。** 已有腾讯 provider 实现，不等于真实集成已验收。缺少有效运行时密钥、明确调用预算/费用上限、外发授权、出网 endpoint 范围和真实受控调用许可。当前占位符与 `TENCENT_OCR_EXTERNAL_CALLS_ENABLED=0` 应继续保留，直到这些条件明确。
- **T09/T10/T12/T13/T14：真实质量和人工复核。** 缺少真实样本、人工题型覆盖、错题来源回查/再错/撤回演练、诊断抽检及变式审核题库。当前 OCR 结果始终是候选，不能自动确认入库。
- **导入确认后的错题内容持久化：已完成本地回归。** 四种文件格式均覆盖上传→分析→人工判定→可信确认→错题本列表/详情，直接对账 `mistake_entries.content_json`、人工 judgment 证据、来源判定和 active 复习卡；记录见 `docs/verification/mistake-import-content-persistence-2026-11-04.md`。该证据使用合成资料，不替代真实 OCR 或真实质量验收。
- **T21/T22：外部故障和预发布组合。** 尚未完成真实 Open WebUI 组合以及外部数据库、对象存储、provider 网络故障中断/恢复矩阵；生产切换也没有授权。
- **T23：真实试用。** 缺少参与者/监护人同意、数据保留删除规则、provider 预算、人工抽检、可信入口和连续 7–14 天观察。不得虚构日志或加速时间。

阻塞与最小外部输入详见 [BLOCKERS.md](BLOCKERS.md) 和 [trial-readiness-2026-11-03.md](../verification/trial-readiness-2026-11-03.md)。

## 下一步

1. 新会话先读本交接、`docs/GOAL_MODE_DEVELOPMENT_PROMPT.md`、`docs/goal/STATUS.md`、`TASKS.json`、`DECISIONS.md`、`BLOCKERS.md`、QA 矩阵及 `git status --short --branch`。核实 Goal 工具 API 状态与仓库记录差异。
2. 继续核对腾讯 OCR 从上传到 worker 到候选的集成边界；保持默认 mock 和外发关闭，不得通过测试代码替代真实质量验收。
3. 要实际调用腾讯 OCR 前，先明确授权、费用上限、脱敏/合成图片范围、出网策略和运行时密钥来源；在独立 staging 中以合成图片做一次受控冒烟，记录费用、耗时、RequestId 和错误降级。不要将真实学生资料发送给接口，除非另有明确授权。
4. 取得脱敏整卷和人工参考标注后，再做逐页/逐题对照报告；报告题目覆盖、漏题、文本错误、区域偏差、弃判、耗时和费用。质量指标只基于实际人工标注计算。
5. 在隔离 Open WebUI 中补真实模型 tool call 和最终可信回调；随后完成外部依赖故障演练。按证据逐项更新任务台账和 QA，不把 `implemented` 自动提升成 `verified`。
6. 生产部署、正式切换、付费 provider、真实学生资料外发和 T23 试用各自保留授权门槛。继续保护工作区现有改动，不重置/覆盖用户文件。

建议新会话续跑指令：

```text
继续 DD-1.0 V1 任务。先阅读 docs/goal/HANDOFF-SESSION-2026-11-04.md、docs/GOAL_MODE_DEVELOPMENT_PROMPT.md、docs/goal/STATUS.md、TASKS.json、BLOCKERS.md、DECISIONS.md 和 QA 矩阵，核对 Goal API 与 Git 工作区状态。当前腾讯教育 OCR 已完成代码接入和合成回归（全量 101 passed），导入确认后的四种文件格式错题内容持久化回归也已完成，但没有真实 API 调用、真实试卷样本或 OCR 质量验收；默认 mock、外发开关关闭。继续完成无需真实资料/付费调用的隔离准备与代码工作；条件具备后只在获批的独立 staging 做受控验证。不要部署到生产、不要发送真实学生资料、不要产生未授权费用，不要把 T04/T05/T23 标成完成或把 Goal 标为 complete。保留现有工作区改动。
```

新会话注意：旧交接 `HANDOFF-SESSION-2026-11-03.md` 是前一会话记录，当前入口改为本文件。工作树有多处既有未提交修改和未跟踪文件，不能 reset、清理或覆盖；此前一直要求不读取/修改根目录 `docker-compose.yml` 与 `batch_ingest.py`，除非用户后续明确改变此限制。
