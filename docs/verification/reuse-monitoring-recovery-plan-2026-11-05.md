# W08 周期监控与 W09 完整恢复计划补充

2026-11-05（从11-04跨日继续）；[使用说明](../open-webui-reuse/07-MONITORING-RECOVERY-PLAN-2026-11-05.md)、[机器记录](reuse-monitoring-recovery-plan-2026-11-05.json)、[最新交接](../goal/HANDOFF-SESSION-2026-11-04-W07-W10.md)。本轮补齐本地周期采集、固定告警码去重/提醒/解除、独立失联判断、容量阈值与备份回执观测，并形成七类组件的完整恢复设计；未实施生产监控或完整恢复。

## 实现与实测

[采集器](../../scripts/collect_learning_monitor.py)按只读SQL读取schema11聚合，公开健康探测由独立进程限制DNS/HTTP耗时；`statvfs`只读容量，备份回执只接受有限字段。固定大小状态原子写入0700目录/0600文件，单实例锁防止重叠，告警与正文/身份/凭据分开。当前结果只保存本地文件和受限日志，没有发送消息。

21项新增[聚焦测试](../../tests/test_learning_monitor.py)通过，1.48秒；覆盖只读聚合与费用保留、实际WAL可见性、空/未来schema/异常控制数据、去重/提醒/解除、损坏状态/时钟倒退/失联、容量边界、备份回执、符号链接、原子写失败、健康目标拒绝/截止与实际loopback重定向拒绝。此前W04–W06、56项运行恢复、停机9项、故障10项、P0、四格式与浏览器验证均未重复执行。

新项目 `dd-learning-reuse-monitor-20261104` 仅启动新学习API与采集器，使用全新学习卷和internal网络、无宿主端口，mock/外发关闭/学习预算0；没有启动WebUI、worker或业务导入。学习镜像保持 `sha256:b67894e6bb8a7023d392a4dd4547e77b0c1d9b39912da3ddd1a50aefbd2b8cbb`，新采集脚本独立只读挂载，镜像不包含该脚本。

| 场景 | 实际观察 |
| --- | --- |
| 首次只读数据卷挂载 | `SQLITE_CANTOPEN` 导致 `METRICS_UNAVAILABLE`，没有误报正常；失败报告保留 |
| SQLite辅助文件权限调整 | 使用UID10001及可写学习卷，SQL仍为mode=ro/query_only；队列超时、暂停、unknown与缺备份回执均被检测 |
| 周期采样与去重 | 实测2秒采样后等待；取证时累计initial1、抑制重复事件22、提醒3；采样耗时使实际周期长于2秒 |
| 重复任务 | 第二个采集进程退出3并报告 `MONITOR_ALREADY_RUNNING` |
| 合成备份回执 | 缺失、failed、passed、stale与恢复到fresh按预期转移；这些是夹具，不是本轮实际备份完成证据 |
| API停止/恢复 | `API_UNAVAILABLE` 新增并解除；未知费用告警持续存在 |
| 容量边界 | 用高阈值触发 `STORAGE_BYTES_LOW` 与 `STORAGE_INODES_LOW`，没有填盘或写附件；不构成正式并发容量测试 |
| 业务保留 | 新库完整性ok；一条合成unknown调用仍保留17微金额，无模型/OCR请求、无自动对账/解暂停 |
| 监控进程停止 | 独立只读状态探针以1秒失联阈值检出 `MONITOR_STALE`，退出2符合attention语义 |
| 最终源码冒烟 | API保持停止，最新脚本正常输出API不可用/缺回执/unknown三项，退出2；未重新启动先前运行场景 |

数据卷文件系统写权限是SQLite辅助文件的实际需求，并未降级为 `immutable=1`。**这不是文件系统级只读监控**；正式采用前须审阅该权限，或实现专用最小监控接口。[可选模板](../../deploy/open-webui-reuse/compose.monitor.template.yml)已完成显式env渲染与资源/挂载检查，未安装或启用到正式服务。0.25 CPU/128 MiB/32 PID是本地配置，不是生产容量结论。

实测最终：API、两次采集器及状态卷初始化容器退出0；失联检查和最终冒烟两个一次性探针退出2（预期attention），全部无运行PID/OOM。新卷、初次失败、日志和阶段记录保留，位于 `learning_data/verification/reuse-monitor-20261104/`。原项目/P0/正式WebUI未操作。

## W09完整设计的边界

[机器计划](../open-webui-reuse/full-recovery-plan.template.json)覆盖学习数据、WebUI数据、运行配置/Tools/绑定、秘密证书、备份后删除记录、备份后费用和固定镜像依赖七类组件，并定义停写/核验/恢复顺序与停止条件。正式来源、责任人、维护窗口、加密位置/密钥保管、保留策略、RPO/RTO和完整演练证据均保持null；未读取正式WebUI数据或秘密。

现有学习恢复只能重放快照内的删除记录；跨备份时点的删除/费用增量日志还需工程化。当前监控仅观察调用方提供的学习备份回执，不能验证其真实性或整个架构已恢复。下一批可继续把实际备份/归档校验/恢复结果分开接入回执，再补增量日志，不能把本轮合成passed回执计入真实备份验收。

## 固定物与状态

本轮不改应用源码/原50文件候选，不重建应用镜像。五文件运维补充包为 `learning_data/operations-preparation/dd-v1-monitor-20261105`，格式 `dd-learning-operations-source-v1`；包括采集器、测试、Compose模板、完整恢复JSON和操作说明。源码集合SHA256 `ec2a525e50de947349e235a221acffb9bbe89e133ec21637ba51a7d16b69964b`，归档SHA256 `19ca3a8aee87c9ec1e5cc7c395a6c2b8c418cf8a855125647b6a2df94fbe445d`。它是独立补充包，不冒称已构建应用镜像或已部署服务；旧候选/镜像/tag未覆盖。

全部T/QA/W状态保持，Goal API只读null、仓库blocked。正式IP证书/账号、三通道费用/出网、独立值守/通知、并发容量、完整架构/秘密恢复、模型最终原生回调、人工质量及试用门槛保留。无生产变更、真实模型/OCR、真实学生资料外发、Git提交/push或Goal写入。

收尾核对：起点148个未提交文件中137个hash不变、11个文档有意更新，0缺失/意外修改；新增7文件保留。10份Markdown的124个本地链接、26任务/356证据引用/17QA与14工作包状态/无环、2个Python编译和diff-check通过。原50文件应用候选与当前源码一致，五文件运维补充包自校验通过；20份来源JSON与3份日志/探针hash核对通过。HEAD保持，Goal API只读null。
