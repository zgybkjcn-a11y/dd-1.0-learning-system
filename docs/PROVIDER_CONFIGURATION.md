# 诊断、变式与外部用量配置

2026-11-04：新增的是可调用 HTTP 的适配器代码和本地合成响应回归，没有真实模型/OCR 请求或学科质量结论。默认仍为三个 mock provider，`TENCENT_OCR_EXTERNAL_CALLS_ENABLED=0`、`LEARNING_MODEL_EXTERNAL_CALLS_ENABLED=0`，预算为零；不改运行中的 P0 私有配置。

`openai-compatible-diagnosis-v1` / `openai-compatible-variant-v1` 使用 HTTPS `.../chat/completions`，非 streaming、`response_format=json_schema`、`max_tokens`，不提供 tools/function calls。端点必须完整匹配 `LEARNING_MODEL_ALLOWED_ENDPOINTS`，禁止 URL 凭据、query、fragment、重定向和环境代理。模型 ID、API key、完整 endpoint、范围和费率都尚未指定；实现选用协议不构成选定或授权一个真实供应商。兼容服务器若不支持该结构化输出协议，保留待复核失败，不回退为任意文本或另一供应商。

诊断从服务端当前错题/来源/已判作答取得最小证据，只发送 `knowledge_point_ids` 和 `evidence_fields`。允许字段是 question_text/student_answer/student_steps/correct_answer/teacher_feedback；不发账号、学习者、附件路径、图片、整个聊天记录或任意 provider payload。响应必须匹配 `DiagnosisOutput`，知识点在本题课程范围内，引用 ID 必须存在，引用的学生步骤必须是原始字段的逐字片段。没有 student_steps 时强制 needs_clarification。结果始终 needs_review；输入/来源改变时拒绝迟到结果，客户端 model_id/prompt_version 不改变实际模型或提示词版本。诊断 worker 在结果已落库而任务应答丢失后复用同一 job 的诊断，不重复调用或新增诊断。

变式只接受已审核且当前学习者可访问、目标一致的母题版本。当前代码范围为已有正式模板 `signed_number_subtraction`：整数参数 [-100,100]、整数域、无单位；母题需在 content 中提供 template_id/parameters，无法确认参数时不调用模型。响应必须保留母题/目标/模板/定义域/单位、使用不同参数，答案由程序重新计算。题干与 answer_key 从校验后的整数重建，不接收模型 HTML、代码、评分脚本或 approval。结果只保存 job 草稿，不写成 approved 题目或投入独立测验；人工审核/发布流程与真实题目质量仍需后续验证，未扩大学科范围。

所有真实 provider 工厂由 API/worker 注入同一 SQLite `UsageLedger`；腾讯 OCR 同样受控，无台账或预算时即使填入密钥并开启外发也拒绝调用。migration 008 保存逐次请求状态、provider/模型/安全 RequestId、响应用量、耗时、费率版本和费用预留，不保存学生标识、请求/响应正文或凭据。migration 009 是服务端浏览器会话；此前本地新库/升级为schema9；当前migration010升级至10，P0仍是schema7快照。

金额使用一个配置货币的整数百万分之一，1,000,000 micros = 1 个货币单位。模型按显式 input/output 每百万 token 费率，为最大 input/output token 预留最坏金额；请求 UTF-8 字节上限包含 system/schema，用作保守输入边界，不冒充目标供应商的 tokenizer。腾讯按每请求的显式金额预留。所有金额/日调用/分钟调用上限、费率引用必须填写，否则 fail closed；默认不编造价格或免费额度。费用日界为 UTC，与学习自然日/时区计算分开。

短写事务先检查暂停、货币一致、单次/累计/UTC 日金额、日次数、分钟次数和并发预留，再记录占用；HTTP 期间不持有 SQLite writer lock。每次 429/5xx 重试重新计数与预留，最多 2 次、默认 1 次，短退避 250ms；timeout/连接失败/无效 JSON 不自动重试。模型每次 timeout 上限 20 秒，OCR 上限 60 秒，响应读取有截止时间和字节上限。真实 DNS/网络故障和目标端点兼容仍未验收。

成功用量是响应申报的估算；在对账前预算占用保留完整预留，未知、失败、中断也不自动释放。申报用量/估算金额超过预留会持久暂停后续调用。管理员 metrics 返回聚合 tracked=true、live_http/synthetic_http 分类、状态、token、预留/估算/对账金额和拒绝原因；没有账单时 reconciled_cost_micros 为 null，synthetic_http 不可对账为真实费用。

`GET /api/v1/admin/provider-calls` 只给管理员读取最早 100 个记录，待对账记录优先，包含安全调用 ID/用量/状态且没有学生 payload，便于找回 worker 丢失的调用记录；对账后下一批待对账记录会排到前面。`POST /api/v1/admin/provider-control` 控制持久 paused；`POST /api/v1/admin/provider-calls/{call_id}/reconcile` 要求管理员、同货币、安全账单引用/RequestId、非运行中预留，同记录重试幂等、异载荷拒绝。对账记录明确是 operator_invoice_reference，服务不会自行核验供应商账单真实性。金额超过预留时暂停；恢复预算不会伪造已完成真实对账。当前尚需真实费率与账单、运行中预留中断后的现场停止/恢复程序和跨账单时点恢复对账，不能写成全部生产费用风险已验证。

备份恢复副本会撤销会话、暂停调用，把恢复出的 reserved 标为 unknown 并保留金额；管理员先完成运行/账单对账再决定恢复。实际生产一致性备份、外部故障/容量/告警及许可仍待完成。认证与固定候选的准备见 [`docs/releases/README.md`](releases/README.md)。
