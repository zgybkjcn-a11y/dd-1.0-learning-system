# W04/W05/W06 本地实现与操作说明

日期：2026-11-04；目标仍为 `https://172.19.116.53/learning/ui`，默认443。新增工程只在源码、临时学习库和合成浏览器中验证，现有HTTP53001/WebUI部署没有改动。schema11 / OpenAPI66 paths、24 schemas；适配器版本1.1.0。

## W04 工作台

导航提供今日任务、上传、候选复核、错题详情、独立测验及受限变式审核。今日任务按到期卡片与 `GET /api/v1/question-choices` 的已批准版本生成按钮，版本列表不返回题面或答案键；正式题面在开始测验后读取。直接指定版本同样复核学习者课程与私有范围。

测验保留开始、原始作答、刷新恢复、提示、取消、pending轮询、最终判分与复核申请。上传/候选复核复用既有持久化实现，本轮仅用一份微型合成PNG检查新增入口和清理路径，没有重做四格式验证。

浏览器模式只把文档/测验定位元数据保存在当前标签的sessionStorage，命名空间含origin、前缀、账号、学习者、版本。原卷字节、候选原答、手动表单及未提交答案不写缓存；刷新恢复从授权API重读。同一标签切换、旧标签409、账号401与注销会中止未完成fetch，递增页面代次，清空表单/文件选择/候选/题面/输出，撤销原页blob URL并删除旧定位缓存。判分延迟轮询检查代次，来源读取也受同一取消保护。重新显示旧标签先核对会话；从浏览器返回缓存恢复的页面刷新后重读。

学习者选择支持显式 `learner_id:null` 清空共享选择，仍要求受信会话、CSRF与expected_revision。内部Tools不能执行选择。所有私有API响应为no-store；`__Host-`Cookie属性保持Secure、SameSite=Strict、Path=/、无Domain。

## W05 Tools与学习教练

[适配器说明](../OPEN_WEBUI_TOOLS_INTEGRATION.md)描述11个方法的最小投影。[配置草稿](learning-coach.template.json)保存固定工作台入口、系统提示、空账号范围与未指定模型；没有写入正式Tools、分享或模型配置。

`DD_SHARED_LEARNER_CONTEXT=true`默认开启适配器共享协议，API复用模式同时要求开启共享上下文。每次操作先读取服务器选择，固定宿主身份/学习者/版本；所有业务请求带版本，读取后再确认选择。UserValves为空跟随当前选择，有值且不一致明确拒绝；模型不能传学习者或版本。`false`只用于旧隔离协议的兼容回归。

四种固定可信操作继续通过原生input/confirmation收集用户响应。回调接受后用原版本申请/消费挑战，切换后不能换成新版本继续提交；取消、异常或120秒超时不提交。原始答案、nonce、挑战、原件、姓名邮箱、完整provider/错误正文不进入模型可见Tool结果。聊天模型/费用和资料范围仍需独立确定，学习预算0不代表聊天预算受控。

## W06 人工审核与冻结投放

| 方法/路径（内部API） | 行为 |
| --- | --- |
| GET `/api/v1/admin/variant-jobs` | 当前学习者的受限审核队列 |
| GET `/api/v1/admin/variant-jobs/{job_id}` | 候选、当前结果指纹、母题/范围校验、审核及撤销记录 |
| POST `/api/v1/admin/variant-jobs/{job_id}/review` | approve/reject、result_fingerprint、非空人工说明和Idempotency-Key |
| POST `/api/v1/admin/variant-reviews/{review_id}/revoke` | 非空撤销说明和Idempotency-Key，停止后续投放 |
| GET `/api/v1/question-choices` | 当前课程/学习者可用的已批准版本元数据 |

上述浏览器路径统一加`/learning`；网关只加入这五条明确路由，未开放internal或通配管理路径。审核仅限当前学习者的reviewer/admin，浏览器认证开启时必须经受信会话/CSRF；adapter通道不能审核。取得SQLite写锁后再次核对角色/授权，不能凭过期ctx角色发布。

批准只接受成功job的当前指纹，重读已批准母题及其完整来源快照，复核目标/课程/私有范围、数轴整数域[-100,100]、单位、非同题参数与程序题干/答案。不能把provider返回的approval当人工批准。合法候选在同一事务生成私有question与version1、冻结草稿/母题/job/审核人证据、审计及幂等结果；其中一步失败全部回滚。相同键/载荷返回相同版本，异载荷或另一审核决定409。

拒绝生成不可改写的审核记录，题库不增加。新幂等键的变式请求可生成新的job，供拒绝/撤销后的后续候选审核；同键重放复用job，同键异载荷409。没有键的旧请求保持原兼容去重协议。审核记录、已发布题干/答案/validator、所属学习者/目标和job结果受SQL冻结约束保护，修订通过新job产生新版本。

撤销追加记录并将题目/版本标为retracted，消费未提交题项的挑战并使其失效；新测验/列表不能投放撤销版本。已提交的pending作答继续按冻结答案完成判分，已有grade与attempt不被撤销操作改写；不会隐式重新评分或回滚既有阶段。撤销版本不能重新批准。普通job读取只返回变式审核要求，答案草稿只能从审核工作台读取。

授权导出包含审核/撤销/job及私有冻结版本；删除软撤回私有题目、取消未完成job并保留tombstone。恢复副本保留冻结证据，重放私有题目删除，撤销会话/选择与挑战并暂停provider。此处是新增结构的本地副本验证，完整现场恢复与维护窗口仍留W09。

## 证据和未满足项

[工程报告](../verification/reuse-workbench-tools-review-2026-11-04.md)、[合成浏览器记录](../verification/reuse-workbench-browser-2026-11-04.json)和[续跑交接](../goal/HANDOFF-SESSION-2026-11-04-W04-W06.md)记录结果。W04/W06 Chromium390/1280px通过；页面URL全部由探针拦截、WebUI认证合成、API/网关为进程内ASGI，303后导航仍由探针模拟。W05采用合成HTTP与loader harness，真实模型/最终原生回调未验收。

正式账号/绑定清单/安装issuer、IP SAN证书/客户端信任、IP稳定性/443防火墙/旧HTTP策略，真实母题/审核人/人工质量、实际模型/OCR/价格/账单和资料许可仍缺。W07独立运行配置/新镜像、W08三通道控制、W09完整恢复、W10新隔离组合继续planned；W11–W14保留真实条件，不启动T24–T26。T/QA状态、仓库blocked与只读Goal API null保留。
