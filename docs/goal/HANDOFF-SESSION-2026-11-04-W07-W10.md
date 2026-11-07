# DD-1.0 W07–W10 本地运行与恢复交接

2026-11-05 当前优先级：**两人数学测试版已部署**，一个现有家长账号切换七年级/二年级档案，14 道起步题、练习判分/恢复和手动错题本。用户已明确授权本家庭版生产上线；真实模型/OCR、学生资料外发和 Goal 写入仍禁止。设备证书导入和真实家长首次绑定待用户操作。复杂监控/完整恢复/商业化功能暂缓，不作为此次上线前置。下文旧批次的“未部署/禁止生产/下一步监控恢复”保留历史，仅在与本范围不冲突时适用。 入口/首次使用/验证及运维见[家庭测试版交接](HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)。

2026-11-05 W08/W09补充：周期监控/去重提醒/容量/备份回执与独立失联检查已本地实现，21项新增聚焦和新隔离验证通过。SQL只读，但SQLite辅助文件需数据卷写权限；初次只读挂载失败证据保留。完整恢复七组件与顺序已设计，正式来源/秘密/RPO/RTO未填、合成回执不算真实备份。详见[监控与恢复计划报告](../verification/reuse-monitoring-recovery-plan-2026-11-05.md)。T/QA/W/Goal状态及执行限制保持。

2026-11-04 故障补充：新隔离组合已验证网关/API/WebUI停机隔离、认证WSS下退出与同Cookie恢复、主动SIGKILL137及合成库完整性；nginx解析/连接超时改为3秒，修改后故障请求约3秒返回。10项新增编排防护通过，六个测试容器最终退出0、卷保留；正式门槛/原137根因/T/QA/Goal状态不变。详见[故障报告](../verification/reuse-fault-isolation-2026-11-04.md)。

2026-11-04 停机补充：隔离停止工具现核对容器归属/固定ID、60秒宽限与实际退出码，非零/OOM/残留进程不能记为成功；新隔离WebUI冷启动及合成认证后正常停止，9项聚焦通过。原两次137原因未充分定位，正式负载/故障门槛保留。详见[停机报告](../verification/reuse-graceful-shutdown-2026-11-04.md)。


日期2026-11-04；工作目录`/home/deniskorfei/projects/open-webui`，main，HEAD `0fa02712ceda049b14d4b556faef3fdb2fa985ed`保持。本文件是最新续跑入口；[W04–W06](HANDOFF-SESSION-2026-11-04-W04-W06.md)与[原会话总结](HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)保留历史。

[操作说明](../open-webui-reuse/06-RUNTIME-RECOVERY-2026-11-04.md)、[工程报告](../verification/reuse-runtime-recovery-2026-11-04.md)、[机器记录](../verification/reuse-runtime-recovery-2026-11-04.json)。当前schema11/契约66/24/Tools1.1.0，T/QA状态全部保持；仓库blocked，只读Goal API null。

## 已完成的本地工程

- W07：独立sidecar/HTTPS代理、secret文件加载、API/worker完整配置一致、默认只读网络重连plan；新50文件`reuse-runtime-v1`候选和固定基础OCI/16个hash依赖的无缓存/无网络安装镜像。正式网络reconnect apply未执行。
- W08：默认mock/外发关闭/学习预算0、新隔离internal网络、固定聚合告警码和未知费用保留。原WebUI聊天费用/正式网络/告警调度/容量与实际三通道账单继续待验；OCR和学习仍共用学习全局预算。
- W09：新隔离API/worker停止并核验，原学习卷只读hash复制，在副本重放WAL、新卷恢复与业务/附件/费用对账；旧Cookie401、新登录/选择及冻结正确成绩回读通过。原WebUI/秘密/完整架构RPO/RTO未验收。
- W10：实际内部TLS/nginx/网关/API/新WebUI内置合成账号Cookie、代表上传、审核/判分/撤销和11方法原生loader/共享上下文最小投影通过。内部测试CA/HTTP客户端不替代正式IP证书、实际浏览器模型最终原生callback、正式Tools分享/人工质量。

56项相关聚焦通过；19/3是更早有重叠聚焦，不相加为全量。未重跑P0或四格式；原W04–W06合成浏览器和质量门槛保留。

## 固定物与运行状态

上一批已构建候选`learning_data/release-preparation/dd-v1-reuse-runtime-20261104-final`：源码集合`5e5dae5d58c0d04b8e7f91632e2eb6ececad7765163dd89df5aae6f404d8bd20`，归档`c0caf5fd20e1a92943b6ae3b51cf810c72a8d0fbc1ab11882580f5f49b40e7bd`。源码manifest仍image_digest=null；独立build.json记录本地镜像`sha256:b67894e6bb8a7023d392a4dd4547e77b0c1d9b39912da3ddd1a50aefbd2b8cbb`，未registry发布/签名/生产部署。

构建、运行、Tools、恢复和私有合成输入都在`learning_data/verification/w07-w10-20261104/`。旧29/35/38文件候选保持；新增a/b/c/d是中间尝试，保留原内容，不作为最终成功候选。新源码变化后在新目录封包，不覆盖现有目录/tag或hash。根目录不能用作Docker构建上下文。

本轮`dd-learning-reuse-20261104-b`和`dd-learning-reuse-20261104-final`均已停止，卷和镜像保留；原部署/P0没操作。新隔离WebUI经Compose stop退出137、OOMKilled=false，其优雅退出/停止宽限时间仍待本地确认；其他新服务退出0。不能直接再次运行完整probe：夹具要求空库且恢复目标拒绝覆盖；验证新变化应选新project/卷，或明确只读已有证据。

## 下一步

1. 核对STATUS/TASKS/BLOCKERS/DECISIONS、机器计划、QA、上述机器记录、Git及只读Goal；不要把planned历史段落当当前状态。
2. 停机工具和新隔离网关/API/WebUI故障、认证WSS、主动SIGKILL及恢复补充已完成，详见顶部故障报告。不要无变化重跑这些阶段或旧项目；原137原因、并发业务写入/实际负载和正式RPO/RTO仍未验收。本地周期监控/容量阈值与完整备份设计已由2026-11-05补充完成；下一批可衔接实际备份/归档校验/恢复结果的独立回执，再补跨备份时点删除/费用增量日志。正式条件分别满足后再实测。
3. W08正式聊天/学习/OCR费用和出网/监控输入、W09完整架构/秘密备份与RPO/RTO仍待；先形成可审阅具体配置，不能把学习局部恢复写成整个WebUI系统恢复。
4. W01正式IP证书/信任/443/旧HTTP策略与身份/操作人/学习库输入齐备后继续目标组合。W11真实调用明确授权、端点/模型/预算/资料范围；W12人工母题/参考/审核人/冻结阈值；W13具体发布/维护授权；W14参与者同意与7–14自然日实际观察分别满足。

执行限制持续：沿用当前IP，正式入口`http://172.19.116.53:53001/`保持，目标`https://172.19.116.53`默认443；单执行者，不启用子代理；保留所有未提交改动，不reset/checkout/clean/提交/push；禁读/改根docker-compose.yml、batch_ingest.py及正式WebUI data/环境秘密；不改正式容器/网络/Tools/证书信任、不生产部署、不真实模型/OCR/学生资料外发，保持mock/外发0/学习预算0；不创建/更新/完成Goal，不启动T24–T26。

最终核对：起点122个未提交文件中102个hash不变、20个有意修改，0缺失/意外修改，另18个新增/新改动文件保留，HEAD不变。14个Python文件编译、14份Markdown的159个本地链接、4份JSON、14工作包无环、26任务/17QA状态与335条任务证据引用、diff-check通过；最终50文件候选匹配当前源码，旧候选hash保持。Goal只读仍null。

停机补充收尾：新工具实测停止5.25秒、退出0，三次受控停止均只有SIGTERM/die0事件。新编排候选`learning_data/release-preparation/dd-v1-reuse-shutdown-20261104`仍50文件，只改变`probe_reuse_runtime.py`；未新构建镜像，应用镜像输入保持。当前新隔离WebUI已停止、卷保留。起点140个改动文件中129个hash不变、11个有意更新，另3个新文件，0缺失/意外修改；8份Markdown的81个链接、3份JSON、26任务/17QA状态与344条证据引用通过，HEAD不变、Goal只读null。

故障补充收尾：新候选`learning_data/release-preparation/dd-v1-reuse-faults-20261104`为50文件/schema11，只改nginx解析/连接超时；源码集合`6ff57b37a85a233682a8161d9f203d77b8b9b8f9841cf6152650a5c52fe899c7`，未新建应用镜像。新project `dd-learning-reuse-faults-20261104` 的五个服务及独立观察端均最终退出0，卷和主动SIGKILL137/首次超时失败证据保留。起点143文件中132不变、11有意修改、0缺失/意外修改，另5新增文件；87个链接、26任务/17QA/14工作包状态及350证据引用、编译/diff检查通过。最新实测与限制以故障报告为准，旧段落保留历史。

2026-11-05监控收尾：21项新增聚焦与新隔离周期/失联/容量/合成回执验证完成；脚本只读SQL，SQLite辅助文件需要卷写权限，原只读挂载失败留证。项目dd-learning-reuse-monitor-20261104所有容器停止；API/采集器/init退出0，失联和最终冒烟探针退出2为预期attention。五文件运维包`learning_data/operations-preparation/dd-v1-monitor-20261105`已封存，原50文件应用候选/镜像保持。148起点文件中137不变、11文档有意修改、0缺失/意外修改，另7新增；124链接/356证据引用/26T/17QA/14W状态与编译/diff核对通过，Goal只读null。下一步为实际备份/归档校验/恢复回执和跨快照删除/费用日志，正式完整恢复与所有原门槛保持。
