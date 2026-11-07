# DD-1.0 诊断/变式、费用、认证与发布准备本地证据

日期：2026-11-04（Asia/Shanghai）。**完成本地工程与聚焦验证；没有真实模型/OCR、真实学生资料、正式网关/TLS、原生最终回调或生产验收。** 最新交接见 [`HANDOFF-SESSION-2026-11-04-PROVIDERS.md`](../goal/HANDOFF-SESSION-2026-11-04-PROVIDERS.md)。机器记录见 [`provider-auth-release-local-2026-11-04.json`](provider-auth-release-local-2026-11-04.json)。

## 实现与边界

| 工作 | 当前实现 | 已验证范围 | 仍缺 |
| --- | --- | --- | --- |
| 诊断 adapter | OpenAI 兼容 JSON schema；当前错题/来源证据，逐字引用、课程知识点、澄清与迟到拒绝；服务端固定模型/提示词元数据 | 合成响应成功、引用/范围/额外 approval/截断/tool call/重复 JSON/超量拒绝、证据变更、第二连接写入、worker 结果复用 | 实际模型/端点协议与学科人工抽检；后续证据变更的人工失效复核 |
| 变式 adapter | 已审核母题/学习者/目标，已有数轴模板整数约束，程序重建题干与答案，job 草稿待审核 | 正常与错误答案/定义域/单位/母题/目标/布尔参数/approval 拒绝，跨学习者及撤销审核后的迟到拒绝 | 真实母题、人工变式质量、审核发布投放联调；未扩大学科范围 |
| 用量与费用 | migration 008 台账，逐请求金额预留、累计/UTC 日金额、日/分钟次数、并发、持久暂停、用量估算与管理员对账；腾讯同样受控 | 并发抢预算、重试逐次预留、timeout/响应中断/未知用量保留占用、超额暂停、货币改变拒绝、权限/对账幂等和冲突、合成调用不得对账为真实费用 | 真实报价/账单、真实网络故障、现场停止与跨账单时点恢复、生产容量/监控 |
| 浏览器认证 | migration 009，一次性短 JWT 网关声明绑定既有身份，Secure/HttpOnly 会话、CSRF/Origin、学习者服务器选择、撤销/退出 | 签名/issuer/audience/寿命/重放/账号角色伪造拒绝、权限即时变更、跨学习者拒绝、恢复撤销；Chromium 工作台合成链路 | 真实登录网关实现、TLS/入口/身份绑定管理及目标环境联调；未完成 Open WebUI 最终回调 |
| 发布准备 | 29 文件白名单，确定性源码归档、逐文件/集合/归档 SHA-256、全新目录保护、生产空模板 | 打包/校验、同源归档可复现、篡改与 symlink/越界/覆盖拒绝；真实工作树候选已生成 | 基础/应用镜像 digest、无缓存构建、新 schema 9 隔离组合、签名发布、实际生产配置及完整一致性恢复 |

代码/操作说明：[`PROVIDER_CONFIGURATION.md`](../PROVIDER_CONFIGURATION.md)、[`releases/README.md`](../releases/README.md)。诊断/变式不再只有 UnconfiguredProvider 占位；未配置的供应商 ID 仍安全降级。当前源码管理员 metrics 的 external_calls.tracked=true 表示实现了台账，并不表示发生过真实调用或取得账单。金额、token 和 invoice 的单测数值均为合成契约样例。

模型/腾讯所有调用保持默认关闭。新 HTTP transport 禁止重定向和环境代理，设响应读取截止时间和大小上限；真实 DNS/网络/端点行为尚未验证。恢复副本将旧会话撤销、provider 暂停，reserved 标为 unknown 且保留金额；运行中的预留不能直接对账释放。所有模型输出保持 needs_review/approval_required，不自动入库、批准或判分。

## 实际检查

```text
pytest -q tests/test_model_providers.py tests/test_browser_auth.py tests/test_learning_release.py tests/test_tencent_ocr.py
67 passed in 12.66s

pytest -q tests/test_learning_service.py -k 'migration or admin_metrics or provider or diagnosis_worker or variant_source or objective_scope or agent_actions_execute_scoped or restore or challenge_expiry_and_actor_binding or learning_draft or cancelled_job'
21 passed, 55 deselected in 4.68s

pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py
14 passed in 0.31s

python3 -m compileall -q learning_service tests scripts
passed
```

本轮最新聚焦共 **102 passed（67 + 21 + 14）**，不是全量 pytest。此前 **101 passed** 保留为旧全量基线。四格式上传确认持久化、P0 整套验证和未变更 Compose preflight 没有重跑。

Chromium 在 390px/1280px 完成服务器会话读取→授权学习者选择→CSRF 手动写入→读取错题本/到期复习→跨学习者 404→退出撤销。两种视口无页面错误、意外网页 origin 或横向溢出；独立数据库有 2 条合成错题、0 条 live provider 调用。**全部 URL 由本地 TestClient/ASGI 拦截，不是实际 HTTPS/登录网关联调，更不是 Open WebUI 模型 tool call 或原生最终回调。** 证据：[`browser-auth-local-2026-11-04.json`](browser-auth-local-2026-11-04.json)；可复现脚本 `scripts/probe_browser_sessions.py`。

首轮浏览器探针在保存后等待列表自动刷新而超时，现有界面需要点击“读取错题本”；仅修正探针操作后通过，未以此声称修复产品认证缺陷。新脚本拒绝覆盖已有报告。

当前源码 OpenAPI 与隔离临时库生成结果一致，**61 paths / 22 schemas，schema 9**。新库、001 旧库升级/恢复、迁移原子性与并发初始化由相关回归验证。旧 56/20、schema 7 是 P0/此前基线，不能写成新代码的运行时验收。

## 固定源码候选

本机忽略目录：`learning_data/release-preparation/dd-v1-provider-auth-20261104/`。包含 `source.tar.gz`、`manifest.json`，可在新目录重建，不依赖 P0 `/tmp` 凭据；没有密钥、数据库、学生附件或根目录禁读文件。

- 29 个源码/契约/模板/说明文件，含既有未提交改动。
- 源码集合 SHA-256：`974dc7e5dbd3b5fbee77b5559754a8c4b44004f092d36cac96371d6cc36ee335`。
- 归档 SHA-256：`b01a718aac46eacdebffcdb5729265a516d8e7e1f27aa99ae2cca563a3472230`。
- image_digest=null，状态 local_source_candidate_not_built_not_deployed；未构建、提交/push、签名、发布或部署。

## 运行状态与缺项

只检查 P0 指定容器元数据：三服务 running，API/WebUI healthy，internal=true、无宿主发布端口，私有配置仍存在且 0600。P0 保留原 schema 7/源码/契约快照，本轮没有更新它或重复运行 verify/tools；当前源码和 P0 的差异是预期的。不要把新源码与旧运行实例写成一致，不修改旧 manifest hash 绕过保护。

Goal API 起点为 null；仓库 blocked，26 个 T 状态全部保留，T04/T05/T23 blocked、T24–T26 deferred。真实模型/可信浏览器回调、资料/审核人/冻结阈值、真实 provider/预算与实际账单、正式网关/新镜像/运行配置、实际架构故障/备份/试用仍分别保留。没有创建或 complete Goal、启动试用、真实 API 或生产部署。最终文档一致性、指纹保留和 Goal 复核以机器记录/最新交接末尾为准。
