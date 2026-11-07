# DD-1.0：复用已部署 Open WebUI 的实施文档

2026-11-05 当前优先级：**两人数学测试版已部署**，一个现有家长账号切换七年级/二年级档案，14 道起步题、练习判分/恢复和手动错题本。用户已明确授权本家庭版生产上线；真实模型/OCR、学生资料外发和 Goal 写入仍禁止。设备证书导入和真实家长首次绑定待用户操作。复杂监控/完整恢复/商业化功能暂缓，不作为此次上线前置。下文旧批次的“未部署/禁止生产/下一步监控恢复”保留历史，仅在与本范围不冲突时适用。 入口/首次使用/验证及运维见[家庭测试版交接](../goal/HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)。

最新进度（2026-11-05）：W07–W10已有固定镜像/内部TLS/故障恢复证据，本地周期监控与完整恢复设计已补充。参见[新操作说明](07-MONITORING-RECOVERY-PLAN-2026-11-05.md)、[报告](../verification/reuse-monitoring-recovery-plan-2026-11-05.md)与[当前交接](../goal/HANDOFF-SESSION-2026-11-04-W07-W10.md)。正式条件和T/QA/Goal保持；下文各批描述保留历史。

日期：2026-11-04（Asia/Shanghai）。状态：**W04/W05/W06本地开发及合成验证已执行，尚未实施生产接入**。用户选择复用本机 Docker Compose 中的 Open WebUI，访问地址为 `http://172.19.116.53:53001/`，登录方式为内置账号。用户确认沿用该IP，HTTPS目标为 `https://172.19.116.53`（443）；证书信任与正式HTTP策略尚待落实。

目标是在现有 Open WebUI 中提供学习入口和聊天 Tools，并在同一台主机上独立运行学习 API、worker、认证桥接网关与学习数据卷。用户继续使用现有账号；学习业务由独立服务负责。

## 三份主文档

| 文档 | 用途 |
| --- | --- |
| [规划方案](01-PLANNING-2026-11-04.md) | 目标、现状、架构、用户流程、实施顺序、发布和试用门槛 |
| [技术开发文档](02-TECHNICAL-DESIGN-2026-11-04.md) | 内置登录桥接、路径适配、身份和权限、Tools、部署、费用和恢复的开发契约 |
| [工作计划](03-WORK-PLAN-2026-11-04.md) | 14 个实施工作包、依赖、负责人、工作量、产物与验收条件 |

辅助文件：[部署输入与只读事实](deployment-inputs-2026-11-04.json)、[机器可读工作计划](work-plan-2026-11-04.json)。未确认参数为 `null`，这些文件不是可直接启动的生产配置。

## 最先解决的事项

1. 为现有容器确定受信 HTTPS 入口。当前学习浏览器会话要求 HTTPS，且只接受默认 443 或显式 443 的 origin；现有 HTTP 地址不能直接承载该会话。
2. 落实正式身份清单与目标登录组合；网关/绑定CLI/上下文有本地实现，Tools两端适配继续。
3. 完善已添加的 `/learning/` 路径、上下文版本与产品入口/恢复，避免请求进入WebUI根API。
4. 固定新学习服务镜像、独立部署配置，在新隔离组合中验证，再按工作计划进入真实链路、质量、生产切换和试用。

## 当前证据与范围

规划起点schema9、102项此前聚焦；当前源码schema10 / OpenAPI61 paths、22schemas，第一批74项聚焦通过，101为此前全量基线。P0 保持 schema 7 历史快照。现有 Open WebUI 的版本和 Docker 元数据已只读核对；内置登录验证协议只审阅了源码，没有登录正式账号、读取凭据、发起模型调用或完成实际认证桥接。

本次文档不缩减完整 V1 范围，T01–T26 和 QA 状态保留；T24–T26 deferred。保留全部未提交改动，不读取或修改根 `docker-compose.yml`、`batch_ingest.py`，不读取正式 WebUI 密钥库。OCR 和学习模型默认 mock、外发关闭；禁止真实模型/OCR API、真实学生资料外发与生产部署的限制仍有效。不创建或 complete Goal。

既有实现与证据见 [provider 交接](../goal/HANDOFF-SESSION-2026-11-04-PROVIDERS.md)、[Tools 说明](../OPEN_WEBUI_TOOLS_INTEGRATION.md)、[质量规范](../quality/README.md)、[试用准入](../verification/trial-readiness-2026-11-03.md)。下一次续跑从[会话总结](../goal/HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)进入，可复制[续跑指令](../goal/RESUME-SESSION-2026-11-04.txt)。

## 本地开发进度

见[第一批实现与操作说明](04-LOCAL-IMPLEMENTATION-2026-11-04.md)、[工程报告](../verification/open-webui-reuse-engineering-2026-11-04.md)和[最新交接](../goal/HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)。W01输入部分固定，W02/W03有本地合成证据，W04仅基础；W05以后保留待实施，T/QA不提升。

会话总交接：[任务/现状/缺项/下一步](../goal/HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)。

最新第二批：[工作台/Tools/人工审核操作说明](05-WORKBENCH-TOOLS-REVIEW-2026-11-04.md)、[工程报告](../verification/reuse-workbench-tools-review-2026-11-04.md)、[续跑交接](../goal/HANDOFF-SESSION-2026-11-04-W04-W06.md)。当前schema11/66/24；首批schema10/74是历史证据。W04/W05/W06本地实现并验证；W05正式分享/模型/原生回调、W06真实母题/人工质量、W07以后工程与真实门槛继续保留。

最新第三批：[运行与恢复说明](06-RUNTIME-RECOVERY-2026-11-04.md)、[工程报告](../verification/reuse-runtime-recovery-2026-11-04.md)、[W07–W10交接](../goal/HANDOFF-SESSION-2026-11-04-W07-W10.md)。固定50文件候选和本地镜像有独立证据；正式部署/真实模型/人工资料/试用仍未执行。
