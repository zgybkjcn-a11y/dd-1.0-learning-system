# DD-1.0 W04/W05/W06 本地续跑交接

日期：2026-11-04；工作目录`/home/deniskorfei/projects/open-webui`，分支main。承接[会话总结](HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)与[首批工程](HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)，本文件是当前工程入口。

当前schema11 /契约66 paths、24 schemas /Tools1.1.0。W04工作台与恢复/身份清理、W05共享Tools/最小投影与教练配置草稿、W06人工审核/冻结私有版本/幂等发布和撤销已本地实现、合成验证；W05正式分享/模型/最终原生回调，W06真实母题/人工质量仍缺。机器计划W04–W06为local_implemented_synthetic_verified，不等于真实工作包验收完成。全部T/QA状态保留，仓库blocked、只读Goal API null。

[实际操作说明](../open-webui-reuse/05-WORKBENCH-TOOLS-REVIEW-2026-11-04.md)、[工程报告](../verification/reuse-workbench-tools-review-2026-11-04.md)、[机器记录](../verification/reuse-workbench-tools-review-2026-11-04.json)、[浏览器记录](../verification/reuse-workbench-browser-2026-11-04.json)。89为本轮主聚焦、19为有重叠的契约/provider复核；390/1280px为全URL拦截/合成认证/ASGI，303后导航仍由探针模拟。没有全量、四格式或P0重跑。

## 接续时必须保留

- 沿用当前IP：现有`http://172.19.116.53:53001/`未改；HTTPS目标`https://172.19.116.53`默认443。IP SAN证书/客户端信任、稳定性/防火墙、旧HTTP策略、正式安装issuer/绑定清单/操作人/学习库仍缺。
- 适配器共享模式默认true，API通用默认false/复用网关要求true；工作台选择支持显式null并带CAS。UserValves只作一致性回显，模型不能选择学习者/版本。全部业务带版本，回调后用原版本，ABA切换不能恢复旧挑战。
- 工作台定位信息用标签内sessionStorage；原答、原件与表单不缓存。切换/409/401/注销取消请求、清空页面与旧元数据并撤销原页URL，迟到成功/失败不覆盖新上下文。
- 母题必须已有人工批准版本。mock/unconfigured草稿缺少合法数轴内容时只能拒绝，不能自动填母题/批准。新Idempotency-Key生成后续job，旧无键请求保留去重。审核仅受限reviewer/admin与受信浏览器；批准/reject/撤销都幂等，异载荷409。
- 冻结版本的内容、答案、scope和来源/审核不可改写。撤销使未提交项失效、新投放拒绝；pending按旧冻结答案判分，已有成绩/阶段不会隐式改写。真正质量纠错/重新评分仍须独立版本操作和人工证据。
- 普通job读取不返回变式答案草稿；审核详情只从受限工作台查看，Tools结果不能带原件/原答/答案键/个人资料/provider正文。
- 源码包schema9/29、schema10/35保持；新schema11/38候选在`learning_data/release-preparation/dd-v1-workbench-tools-review-20261104`，精确SHA见机器记录，image_digest仍null。源码再改在新目录prepare，不能覆盖旧包或借P0镜像验收新源码。

## 下一批

先核对STATUS/TASKS/BLOCKERS/DECISIONS、机器计划/QA/机器记录、Git与只读Goal；保留全部未提交改动。从W07独立sidecar/HTTPS代理/秘密引用/网络重连与固定构建候选推进，再W08三通道预算/网络/监控、W09完整备份恢复、W10全新隔离组合。不要读取根Compose或从根目录直接构建；实际镜像/组合没有验证，旧证据不能替代。

缺正式TLS/身份时继续可独立的本地配置准备，不自签真实门槛。W11真实模型/OCR/费用/资料许可，W12脱敏整卷/母题/人工审核/冻结质量阈值，W13具体发布/维护授权，W14参与者/监护人同意与7–14自然日真实观察仍分别保留，不缩减V1。

执行限制全部沿用：单执行者、不启用子代理；不reset/checkout/clean/提交/push；不读取/修改根docker-compose.yml、batch_ingest.py，不读取正式WebUI data/环境秘密；不操作正式容器/网络/Tools/证书信任、不生产部署、不真实模型/OCR/学生资料外发，保持mock/外发关闭/学习预算0；聊天费用不属于学习台账。不创建、更新或完成Goal，T24–T26不启动。

收尾核对：14个变更Python文件编译、18份Markdown的139个本地链接、6份JSON、14工作包无环、26任务/17QA/303条任务证据及diff-check通过。起点108个既有未提交文件中82个指纹不变、26个有意更新，0缺失/意外修改；另14项新文件或本轮新改动保留，Git HEAD不变。旧候选SHA保持，新候选源码匹配，Goal API只读仍null。
