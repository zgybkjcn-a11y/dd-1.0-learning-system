# DD-1.0 V1 交接：复用现有 WebUI 第一批本地工程

日期：2026-11-04（Asia/Shanghai）；目录 `/home/deniskorfei/projects/open-webui`，分支main。**第一批工程交接；最新续跑入口为[本会话完整总结](HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)**。承接[规划交接](HANDOFF-SESSION-2026-11-04-OPENWEBUI-REUSE.md)，不覆盖P0/provider历史。

## 用户输入与边界

用户“开始执行”授权本地工程，后续确认沿用当前IP。现有本机Docker Compose/内置账号入口 `http://172.19.116.53:53001/`；HTTPS开发目标 `https://172.19.116.53` 默认443、IP SAN证书及客户端信任。只读443无TCP监听不等于端口/防火墙/TLS通过；IP稳定性、证书/信任、旧HTTP策略和运维责任仍缺。

保留所有未提交改动，不reset/checkout/clean/提交/push；不读取/修改根docker-compose.yml、batch_ingest.py，不读正式WebUI data/环境秘密。不操作正式容器/网络/Tools/证书信任、不部署生产、不调用真实模型/OCR或外发真实学生资料；mock/外发关闭/零预算保持。默认单执行者，未启用子代理；不创建或complete Goal，API仍null，仓库blocked。

## 已做与验证

源码schema10、契约61paths/22schemas。W01输入部分固定，W02/W03本地实现及合成验证，W04前缀/版本基础部分实现，W05–W14仍planned。全部T/QA状态保留。

- 新 `login_gateway.py` / `gateway_http.py`：固定WebUI Cookie认证、一次性登录CSRF、60秒服务器声明、每次访问来源身份一致性、严格路径/最小转发、安全HTTP截止/上限。默认disabled、没有运行秘密或生产配置。
- migration010、`learner_context.py`、browser_auth/app/db：旧无来源会话撤销、绑定复核、账号共享选择/CAS、过期读写409、SQLite写事务内再次复核，切换消费挑战。
- `identity_admin.py` / `manage_learning_identities.py`：严格输入、只读plan、审阅hash、原子迁移/变更/审计、撤权/解绑/角色变化撤销。正式清单/库没有应用；课程初始化只建既有目标/模板，不建母题，不开放seed。
- `/learning`浏览器URL、登录链接、版本头和身份/版本缓存命名空间；恢复撤销会话/清空选择/消费挑战，provider暂停与unknown保留。
- 74聚焦通过；390/1280px Chromium合成网关/表单/前缀手动错题、微型PNG上传/页图、标签切换409/刷新与退出通过。303后的导航由探针显式模拟，不能写成正式TLS跳转/登录。旧101全量、前次102聚焦分开，不相加；四格式/P0未重跑。

证据：[工程报告](../verification/open-webui-reuse-engineering-2026-11-04.md)、[机器汇总](../verification/open-webui-reuse-engineering-2026-11-04.json)、[浏览器JSON](../verification/reuse-gateway-browser-2026-11-04.json)。实际配置/CLI见[操作说明](../open-webui-reuse/04-LOCAL-IMPLEMENTATION-2026-11-04.md)，状态见[机器计划](../open-webui-reuse/work-plan-2026-11-04.json)。

## 版本与候选

P0仍保留schema7快照，不修改或按新源码复验。旧候选 `learning_data/release-preparation/dd-v1-provider-auth-20261104` 仍schema9/29文件，原集合SHA `974dc7e5dbd3b5fbee77b5559754a8c4b44004f092d36cac96371d6cc36ee335`，归档SHA `b01a718aac46eacdebffcdb5729265a516d8e7e1f27aa99ae2cca563a3472230`；当前源码与旧包预期不同。新packager verify保留旧profile。

新候选目录 `learning_data/release-preparation/dd-v1-reuse-gateway-20261104`，schema10/35文件；精确hash见工程JSON。image_digest=null，未构建/签名/发布/部署。源码再变时在新目录封包，不覆盖任一旧包。原始Dockerfile无缓存构建与新目标配置/镜像仍待W07，不能借用P0镜像。

## 下一项可执行工作

1. 读取本交接、状态/台账/阻塞/决策、四份复用文档、工作计划与QA；核对Git/只读Goal和候选差异。当前无真实调用授权，不能启动P1/P3；保持真实门槛。
2. **继续W04/W05**：完成实际产品入口和代表上传/测验恢复，审计缓存/异步响应在身份及上下文变化时的清理。适配Tools读取GET learner-context、带context_version；模型不能选择/替换学习者。共享模式下旧Tools写操作现在会因缺版本拒绝，尚未接入正式WebUI，不能说两端已同步。
3. Tools每方法最小结果投影与固定HTTPS工作台入口，保留四种可信操作/原生事件、取消/120秒失败/修订/重放/跨学习者拒绝；不把原始资料或答案自动送入聊天模型。实际分享/模型绑定后续只在具体获准环境进行。
4. W06人工变式审核发布：provider草稿不是批准题库；实现受限reviewer/admin审核、当前fingerprint/范围/母题复核、冻结question version与幂等投放，不开放internal seed。
5. W07以后形成独立sidecar/HTTPS代理/秘密引用/网络重连候选，默认mock关闭外发；固定新镜像、真实组合/监控/完整恢复仍缺。W01证书/信任/IP稳定性/HTTP策略和正式身份输入缺失时可继续合成本地开发，不自签生产条件。
6. 三通道分别准备聊天/学习模型/OCR许可与预算；学习台账不覆盖WebUI聊天。真实资料/人工标注阈值、P2质量、生产维护与7–14天试用保留外部门槛；不缩减V1、T24–T26不启动。

必要验证只覆盖发生变化的实现；本轮已通过项不无变更重跑。后续更新实际证据/缺项和交接，全部旧包/用户未提交改动继续保留。

## 最终核对

13个变更模块/脚本编译、14份Markdown的86个本地链接（0缺失）、5份JSON及14工作包无环依赖、diff-check通过。任务一致性：26任务、267条evidence路径、26台账行、17 QA行、24 manifest引用，原发布授权边界完整。工程起点87个既有改动文件中，58个指纹保持、29个有意修改，0缺失/意外修改；新增文件另行保留，未覆盖旧包或旧P0。Goal API最后只读仍null，全部T/QA状态保留。
