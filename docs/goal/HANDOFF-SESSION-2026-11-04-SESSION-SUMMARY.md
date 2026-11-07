# DD-1.0 V1 本会话总结与续跑交接

2026-11-05 当前优先级：**两人数学测试版已部署**，一个现有家长账号切换七年级/二年级档案，14 道起步题、练习判分/恢复和手动错题本。用户已明确授权本家庭版生产上线；真实模型/OCR、学生资料外发和 Goal 写入仍禁止。设备证书导入和真实家长首次绑定待用户操作。复杂监控/完整恢复/商业化功能暂缓，不作为此次上线前置。下文旧批次的“未部署/禁止生产/下一步监控恢复”保留历史，仅在与本范围不冲突时适用。 入口/首次使用/验证及运维见[家庭测试版交接](HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)。

日期：2026-11-04（Asia/Shanghai）。工作目录：`/home/deniskorfei/projects/open-webui`；分支：`main`。**首批工程会话总结；最新入口为[W07–W10交接](HANDOFF-SESSION-2026-11-04-W07-W10.md)**。本文件汇总任务、现状、缺项、下一步与新会话指令；[第一批工程交接](HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)、provider/P0旧交接保留原证据。

本次总结只读取仓库状态、台账、交接和证据并更新文档，没有再次跑pytest、浏览器、四格式或P0验证，没有修改业务代码、运行配置、候选包或部署。Goal API在本次总结起点返回`goal: null`，仓库Goal仍blocked。

## 1. 本会话在做哪些任务

主任务是继续DD-1.0 V1学习服务，复用已经部署的Open WebUI，先形成规划/技术开发文档/工作计划，再执行第一批本地工程。完整V1范围保留，W编号只是原T01–T26的实施子包，不创建新Goal或替代原任务。

| 任务 | 本会话做到哪里 | 主要产物/证据 |
| --- | --- | --- |
| 承接P0与已有学习服务 | 读取历史、状态与缺项，复用四格式/P0/provider已有证据 | [P0交接](HANDOFF-SESSION-2026-11-04-P0.md)、[provider交接](HANDOFF-SESSION-2026-11-04-PROVIDERS.md) |
| 复用现有WebUI方案 | 确定复用同一本机容器，学习API/worker/网关/数据独立；分开聊天、学习模型和OCR费用 | [规划方案](../open-webui-reuse/01-PLANNING-2026-11-04.md) |
| 技术设计与排期 | 形成登录桥接、路径、身份/上下文、Tools、审核发布、配置/恢复设计及14工作包 | [技术文档](../open-webui-reuse/02-TECHNICAL-DESIGN-2026-11-04.md)、[工作计划](../open-webui-reuse/03-WORK-PLAN-2026-11-04.md) |
| W01环境/TLS输入 | 用户确认沿用当前IP，固定HTTPS开发目标；443只读未见TCP监听 | [部署输入](../open-webui-reuse/deployment-inputs-2026-11-04.json) |
| W02内置登录网关 | 本地实现并用合成响应验证；默认关闭，未接正式账号/TLS | [login_gateway.py](../../learning_service/login_gateway.py)、[gateway_http.py](../../learning_service/gateway_http.py) |
| W03身份管理与上下文 | 来源会话/绑定复核、CLI、migration010、共享选择/CAS、事务内保护、撤权及恢复 | [实际实现/CLI说明](../open-webui-reuse/04-LOCAL-IMPLEMENTATION-2026-11-04.md) |
| W04工作台基础 | 添加`/learning`前缀、登录链接、版本头、缓存命名空间及旧标签页409/刷新 | [app.py](../../learning_service/app.py)、[合成浏览器记录](../verification/reuse-gateway-browser-2026-11-04.json) |
| 发布准备与验证 | 新35文件schema10源码包；旧schema9/29文件包兼容校验保留；未构建镜像 | [工程报告](../verification/open-webui-reuse-engineering-2026-11-04.md)、[机器记录](../verification/open-webui-reuse-engineering-2026-11-04.json) |
| 状态与续跑交接 | 更新任务证据/缺项、STATUS/BLOCKERS/DECISIONS/QA与交接，状态不提升 | [TASKS.json](TASKS.json)、[QA矩阵](../verification/qa-matrix-2026-11-03.md) |

已有provider基线包含诊断/变式OpenAI兼容HTTP adapter、用量/费用预留/限额/暂停/对账和浏览器会话。它们有本地实现，不再是只有占位工厂；真实端点/模型/价格/账单和调用验收仍缺。四格式错题持久化与P0此前已完成，不重新实现或无变更重跑。

## 2. 部署输入与当前版本

| 项目 | 当前结论 |
| --- | --- |
| 用户现有入口 | `http://172.19.116.53:53001/`；本机Docker Compose、内置账号 |
| 新HTTPS目标 | **`https://172.19.116.53`，默认443，沿用当前IP**；证书需含该IP的SAN并被客户端信任 |
| 现有WebUI | 之前只读记录为0.12.5；容器/project/service为open-webui、网络open-webui_default；本次总结没有重新检查运行health |
| 现有部署改动 | 未修改容器、端口、网络、Tools、WebUI数据库或证书信任；未实施生产接入 |
| 当前源码 | 数据库migration revision10；OpenAPI61 paths、22 schemas |
| P0 | 保留schema7历史快照；当前源码与它预期不同，没有更新/复验 |
| 认证 | 网关/API有本地实现；实际WebUI账号/Cookie、TLS和真实登录仍未验收 |
| 默认外发 | OCR/诊断/变式均mock；OCR/学习模型外发关闭、学习预算0；不代表WebUI聊天费用已受控 |
| Git/Goal | main有大量未提交改动；全部保留；Goal API为null，仓库blocked |

`ss`未发现443 TCP监听只表示检查时无监听，不证明端口可绑定、防火墙放行、证书有效或客户端信任。正式安装issuer、绑定清单、操作人、学习库与旧HTTP53001策略尚未确定，部署输入中待确认项继续保留。

## 3. 各工作包目前到哪里

| 工作包 | 状态 | 仍需完成 |
| --- | --- | --- |
| W01 环境/TLS/身份协议 | 输入部分固定 | IP稳定性、IP SAN证书/客户端信任、443/防火墙、旧HTTP策略和运维责任 |
| W02 登录网关 | 本地实现/合成验证 | 实际账号/Cookie、目标TLS、独立网关/代理组合 |
| W03 初始化/绑定/来源/上下文 | 本地实现/合成验证 | 正式身份清单/操作人/学习库及目标组合；正式库没有初始化 |
| W04 工作台路径/产品入口 | 基础部分实现 | 完整产品入口、上传/测验恢复、身份切换时缓存和异步响应清理 |
| W05 Tools/学习教练 | planned | 共享上下文/版本适配、最小结果、固定工作台链接、分享/模型配置及真实回调 |
| W06 人工变式审核发布 | planned | reviewer/admin审核、指纹/范围/母题复核、冻结版本、幂等批准/拒绝与投放 |
| W07 独立配置/镜像 | planned，仅有源码封包准备 | sidecar/HTTPS代理/秘密引用/网络重连、固定基础/应用镜像与组合 |
| W08 预算/网络/监控 | planned，已有学习费用台账基线 | 聊天/学习/OCR分别控制，实际网络/费用/告警与容量 |
| W09 迁移/完整恢复 | planned，已有本地会话/上下文恢复基线 | 完整数据/附件/审核/费用对账、现场故障、维护窗口和RPO/RTO |
| W10 新隔离组合 | planned | 新项目/独立卷的实际认证、路由、业务、故障与恢复 |
| W11 P1/P3真实调用 | planned，条件不齐且当前限制禁止调用 | 模型/端点/费用/资料许可、实际tool call/最终可信回调、真实provider证据 |
| W12 P2/P4人工质量 | planned；P2仍为空模板 | 脱敏整卷、人工参考/母题、审核人、冻结阈值和质量报告 |
| W13 生产接入/维护切换 | planned，未授权/未执行 | 具体发布物审阅、生产输入与切换/停止/恢复记录 |
| W14 小范围试用 | planned，未启动 | 参与者/监护人同意、预算/范围/启动条件及7–14自然日真实观察 |

以[机器工作计划](../open-webui-reuse/work-plan-2026-11-04.json)为准。W02/W03“本地实现/合成验证”不等于这些工作包的真实环境验收完成。

T任务状态保持：

| 状态 | 任务 |
| --- | --- |
| verified | T01、T02、T06、T07、T08、T11、T15、T17、T19 |
| implemented | T03、T09、T10、T12、T13、T14、T16、T18、T20、T21、T22 |
| blocked | T04、T05、T23 |
| deferred | T24、T25、T26 |

verified是已有本地任务状态，不表示V1整体或生产验收通过；QA状态保留，不以合成证据解除真实门槛。

## 4. 实现细节与接续时容易漏掉的事项

1. **网关默认关闭。** 固定内部WebUI认证`GET /api/v1/auths/`和token Cookie，不读WebUI密码/密钥库。WebUI admin/user仅准入，学习业务角色来自learner_access。服务器声明60秒、登录nonce120秒单进程有界一次性；JWT、Cookie、上游个人资料不进入浏览器/模型/失败日志。
2. **来源身份逐次验证。** 学习会话保存provider/issuer/subject，当前绑定必须仍指向原account；网关每次重新核验WebUI Cookie与来源身份。迁移撤销无来源的旧会话，解绑/撤权/角色变化撤销会话和选择、消费旧挑战，保留业务历史。
3. **共享模式要求上下文版本。** 浏览器不能用learner头覆盖服务器选择，CAS切换消费旧挑战；业务读写带版本，旧页409。SQLite写锁内再检查选择/版本/授权，防止授权后发生切换。默认兼容模式仍保留，复用网关强制共享模式。
4. **旧Tools尚未适配新模式。** 共享模式下写操作可能因缺`X-Learner-Context-Version`被拒绝；现有Tools未接入正式复用网关。W05必须读取GET learner-context并带版本、验证UserValves一致性，模型不能选择/替换学习者。不能把上下文API实现写成两端已同步。
5. **CLI不是WebUI数据库脚本。** validate不开库，plan使用只读快照、不创建目录/迁移；apply需显式目标Learning DB、操作人和审阅plan hash，迁移/变更/审计同事务。操作人字段是主机运维审计引用，执行权由主机权限控制；正式清单和库未应用。initialize_math只建既有目标/数轴模板，不创建/批准母题，bootstrap/questions seed保持关闭。
6. **变式目前仍是草稿。** provider结果不是人工批准，也不能自动入题库或投放；正式审核发布留W06。WebUI聊天、学习diagnosis/variant和OCR分开控制，学习费用台账不覆盖WebUI聊天。
7. **前缀与Cookie规则不能简化。** 浏览器用`/learning`，内部API/Tools不加前缀；Cookie保持Secure、SameSite=Strict、Path=/、无Domain，不能把`__Host-` Cookie改成Path=/learning或降低HTTPS要求。
8. **证据限制必须保留。** 浏览器探针拦截全部页面URL、合成WebUI认证、进程内ASGI；303和固定Location已验证，但之后由探针主动导航。真实TLS重定向/正式Cookie/真实模型最终原生回调均未验收。HTTP连接后总截止与慢速头有loopback证据，系统DNS阻塞上限和实际网络仍缺。

## 5. 已有验证与源码包

- 第一批工程最终 **74 passed in18.32s**，覆盖网关/身份/上下文/CLI/HTTP边界、会话及打包/迁移相关用例；不是全量。
- Chromium390px/1280px合成链路通过：表单交换、账号只读、明确选择、前缀手动错题/微型PNG上传/页图、旧标签页409、刷新同步、退出401/Cookie清理，无横向溢出/页面错误。live_provider_calls=0。
- 13个模块/脚本编译、14份Markdown的86个本地链接、5份JSON、14工作包无环、任务/QA/manifest引用与diff-check在工程收尾通过。
- 101是更早全量基线，102是此前provider聚焦，74是本轮工程聚焦；三者分开，不相加称为新全量。本次总结没有重跑这些验证。
- 工程起点87个既有改动文件，58个保持、29个有意修改、0缺失/意外修改；本次文档总结使用新的独立快照核对，保留旧审计。

| 候选 | 版本/文件数 | 源码集合SHA256 | 归档SHA256 |
| --- | --- | --- | --- |
| `learning_data/release-preparation/dd-v1-reuse-gateway-20261104` | schema10 /35文件 | `0a5352c5d9bfb22f39a2015c054442c930067ed2d5fcad9891b1316f4a598b85` | `2b6655c58d7a5af50e8b9712f7268baab50913fc91bf7c36298b0b0a5042a17c` |
| `learning_data/release-preparation/dd-v1-provider-auth-20261104` | schema9 /29文件 | `974dc7e5dbd3b5fbee77b5559754a8c4b44004f092d36cac96371d6cc36ee335` | `b01a718aac46eacdebffcdb5729265a516d8e7e1f27aa99ae2cca563a3472230` |

两个包均image_digest=null，未构建/签名/发布/部署；旧包未覆盖，新verify兼容旧profile。源码以后改变，在新目录prepare，不覆盖现存包或篡改hash。P0是schema7历史运行快照，不能对它执行当前源码一致性验证并把预期差异当故障，也不能借旧镜像验收新源码。

## 6. 下一步按什么顺序做

1. **先接续W04/W05，而不是重做P0。** 读本交接、STATUS/TASKS/BLOCKERS/DECISIONS、复用技术/实际实现/工作计划、QA和工程JSON；检查Git/只读Goal，识别源码/候选版本。缺证书或正式身份输入时可继续本地合成开发。
2. **补W04完整工作台。** 代表上传/候选复核、今日任务/错题本、测验开始/作答/恢复/取消/复核；审计身份/学习者/版本变化时缓存、原件URL、异步响应及原始答案清理。只对新增或变化路径做必要测试，复用四格式持久化证据。
3. **补W05 Tools。** 读取共享上下文/版本，旧UserValves不一致明确拒绝；所有读取结果按最小字段投影，敏感原卷/原答从工作台读取；固定HTTPS链接。保留原生可信事件、四种固定交互、取消/120秒超时/修订/重放/跨学习者拒绝。只做合成验证，真实模型/最终原生回调门槛仍保留。
4. **做W06人工审核发布。** 受限reviewer/admin、approve/reject、当前指纹/人工说明/幂等键；重新验证母题批准、学习者/目标/整数域，事务冻结题目版本，仅批准版本可投放。拒绝/重放/冲突/撤销及已用成绩不能被改写需有测试。
5. **W07–W10工程准备。** 形成独立sidecar/代理/秘密引用/网络重连和可审阅配置，默认mock/外发关闭；固定新镜像，补费用/监控、完整恢复、新隔离组合。不要改根Compose或运行中的正式部署；原始Dockerfile无缓存构建仍未证明成功。
6. **外部条件到位后再推进W11–W14。** 真实模型/OCR/费用/资料许可和端点预算、脱敏整卷/人工参考/阈值、正式账号/TLS、参与者同意、具体发布审阅与维护窗口、试用启动授权分别满足。当前禁止真实调用/外发/生产，不因网络权限放宽自行启用；真实试用需7–14自然日，不能补写假日志。

## 7. 新会话继续任务的指令

可直接复制以下文本到新会话；同内容保存为[续跑指令文件](RESUME-SESSION-2026-11-04.txt)。若在终端切换项目，先运行`cd /home/deniskorfei/projects/open-webui`。

```text
继续DD-1.0 V1学习服务和复用现有Open WebUI任务。工作目录：/home/deniskorfei/projects/open-webui。

先读取docs/goal/HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md；再按其中清单读取STATUS.md、TASKS.json、BLOCKERS.md、DECISIONS.md、第一批工程交接、docs/open-webui-reuse中的技术/实际实现/工作计划与机器计划、QA矩阵和工程JSON。P0/provider旧交接仅作历史依据。检查git status --short --branch与只读Goal API。

已确认：复用本机Docker Compose/内置账号的http://172.19.116.53:53001/，沿用当前IP，HTTPS开发目标为https://172.19.116.53默认443。现有正式部署未改变；证书/客户端信任、IP稳定性、旧HTTP策略、正式绑定清单/操作人/学习库仍缺。

当前源码schema10、OpenAPI61paths/22schemas；W01部分输入固定，W02网关/W03身份CLI与共享上下文本地实现并有合成验证，W04仅前缀/版本基础，W05–W14仍planned。74是本轮聚焦，102是此前provider聚焦，101是更早全量；390/1280px为合成ASGI浏览器，303后续导航由探针模拟，不是正式登录/TLS/真实回调。P0/schema7、四格式持久化已完成；P2仍空模板。不要无变更重跑这些通过项。

从W04/W05接续：完善工作台产品入口/代表上传和测验恢复，处理身份/学习者变化后的缓存与异步响应；适配Tools读取服务端learner-context并携带context_version，模型不能选择/覆盖学习者，完成最小结果投影和固定HTTPS工作台链接。旧Tools尚未适配共享模式写入版本，不能宣称两端已同步。随后推进W06人工变式审核/冻结版本/幂等发布，W07以后独立配置/镜像/监控/完整恢复准备。已有诊断/变式/费用台账是本地实现，真实模型/价格/账单/网络/资料质量仍缺。

保留所有未提交改动，不reset、checkout、clean、提交或push；不读取/修改根docker-compose.yml、batch_ingest.py，不读取正式WebUI data/环境秘密。不操作正式容器/网络/Tools/证书信任，不部署生产；保持OCR/学习模型默认mock、外发关闭、预算0，不调用真实模型/OCR或外发真实学生资料。聊天费用不属于学习台账。不要把mock/合成/loader/ASGI写成真实验收，不创建/更新/complete Goal，T/QA状态按真实证据保留，T24–T26不启动。

默认单执行者，不启用子代理。旧schema9/29文件与schema10/35文件源码包保留，源码变化后只在新目录封包，image_digest仍null。只做变化相关的必要验证，更新任务证据/缺项/QA/交接；缺正式输入时继续可独立推进的本地工程，不自签真实门槛。
```

## 8. 总结阶段收尾

本次总结未修改源码、测试、运行配置或候选，未提升任务/QA、未变更Goal。文档链接/台账一致性、源码指纹与未提交改动保留核对将在[总结核对记录](../verification/session-summary-2026-11-04.json)记录；原工程报告保留74项测试的历史事实，不冒充本次重新验证。

总结收尾核对：5份入口/交接Markdown的57个本地链接无缺失；任务一致性与diff-check通过。本次起点105个既有改动文件中100个指纹不变、5个仅更新文档入口，0缺失/意外修改；35个封包源码文件和归档指纹保持。Goal API仍为null，T/QA不提升；新增总结/续跑指令/核对记录不覆盖原证据。
