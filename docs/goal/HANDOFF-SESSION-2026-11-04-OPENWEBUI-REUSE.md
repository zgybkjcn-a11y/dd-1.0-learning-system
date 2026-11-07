# DD-1.0 V1 交接：复用现有 Open WebUI 的规划与工作计划

日期：2026-11-04（Asia/Shanghai）；目录 `/home/deniskorfei/projects/open-webui`；分支 main。**规划阶段历史；最新续跑入口为[第一批工程交接](HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)。** 本轮用户要求生成规划方案、技术开发文档和工作计划，没有要求执行生产部署。

## 用户已确认的方向与只读事实

- 复用本机 Docker Compose、内置账号的 `http://172.19.116.53:53001/`，生产使用同一已有OpenWebUI；学习服务独立。
- 容器/Compose project/service 为 `open-webui`，running/healthy；版本接口返回0.12.5。宿主53001→容器8080，网络 `open-webui_default`，本项目 `data/` 绑定到 `/app/backend/data`。
- 只看指定容器元数据、镜像digest和公开版本接口，源码审阅了内置登录 `token` Cookie与 `GET /api/v1/auths/`；没有读取根Compose、环境/密钥、WebUI数据库、真实身份/Cookie、聊天模型配置或正式账号认证结果。

## 本轮产物

| 产物 | 用途 |
| --- | --- |
| [文档入口](../open-webui-reuse/README.md) | 三份主文档、部署输入与机器计划导航 |
| [规划方案](../open-webui-reuse/01-PLANNING-2026-11-04.md) | 现状、目标架构、用户流程、HTTPS迁移、发布/试用顺序 |
| [技术开发文档](../open-webui-reuse/02-TECHNICAL-DESIGN-2026-11-04.md) | 内置登录桥接、路径、来源身份/上下文、Tools、审核发布、配置/网络、费用和恢复 |
| [工作计划](../open-webui-reuse/03-WORK-PLAN-2026-11-04.md) | W01–W14依赖、负责人、产物、验收与阶段门；不新增/替代T任务 |
| [部署输入](../open-webui-reuse/deployment-inputs-2026-11-04.json) | 用户事实、只读元数据与待确认null参数；非可执行生产配置 |
| [机器工作计划](../open-webui-reuse/work-plan-2026-11-04.json) | 全部planned的14工作包、依赖、T/QA映射与工期口径 |

已更新文档入口、STATUS、TASKS evidence/notes/unmet、BLOCKERS、DECISIONS D26、旧计划第13节、通用/provider交接及QA规划说明。所有26项任务和QA状态保留；文档/元数据不作为代码完成或真实验收。

## 已有代码与新缺项

当前学习源码仍为schema9/契约61/22；102是此前聚焦，101是更早全量基线。旧P0仍schema7，不更新/复验它；29文件源码候选与原hash保持，不构建新镜像。

复用入口还需开发：受信HTTPS与旧HTTP处理、内置登录验证网关、会话来源身份/解绑后拒绝、正式初始化/绑定、两端统一学习者上下文、工作台 `/learning` 路径、Tools最小输出/固定入口、人工变式审核发布、新配置/镜像/网络重连及实际恢复。当前工作台根路径 `/api/v1/...` 不能直接通配代理；当前学习Cookie要求HTTPS默认443，不能在HTTP53001上降低要求冒充完成。

WebUI聊天模型计费/外发不受学习台账覆盖；聊天、学习模型、OCR分开落实许可、资料/费率/预算。现有WebUI模型配置没有读取，不能写成已有可用模型或无外发。真实P1/P3、资料/人工质量、生产切换、真实试用门槛继续保留；完整V1不缩减，T24–T26 deferred。

## 下一次从哪里继续

先读本文件、三份文档、STATUS/TASKS/BLOCKERS/DECISIONS和QA，再检查Git/Goal。默认单执行者，不启用子代理，不创建或complete Goal。

从W01确定实际HTTPS origin（内网域名或IP SAN证书/客户端信任）、443/IP稳定性、HTTP53001正式处理、原WebUI网络与绑定/运维责任。形成无秘密配置候选后开发W02/W03；未确定输入保留null。可先在本地合成环境开发网关、来源身份、上下文与路径，不读真实凭据或调用真实模型。

W01–W10估算12.5–21工程工作日，W11–W13另计3.5–8工作日和外部等待；W14观察7–14自然日另计。已有四格式/P0/未变更业务测试不无变更重跑；新代码只做必要的相关安全与组合验证。当前任务只是文档，尚未开始这些开发工作。

## 持续边界与收尾

保留全部未提交改动，不reset/checkout/清理/提交/push；不读取/修改根 `docker-compose.yml`、`batch_ingest.py`，不读取正式WebUI密钥库。保持OCR/学习模型mock、外发关闭，不调用真实模型/OCR API、发送真实学生资料或部署生产。用户确认复用和文档方向不代表上述限制已改变。

本轮未跑pytest、四格式、浏览器或P0套件，没有启动/停止/重建容器或变更Tools/网络。Goal API起点/收尾为null，仓库blocked；任务/QA状态不提升。最终文档、工作包依赖、源码候选与改动保留核对见[本轮机器记录](../verification/open-webui-reuse-planning-2026-11-04.json)。

## 本轮最终核对

收尾时间：2026-11-04 10:29:43 UTC（18:29:43 Asia/Shanghai）。三份主文档与入口/部署输入/机器工作计划已完成并验证，所有实施工作包仍planned；这是文档任务完成，V1及生产接入没有完成。

文档一致性与diff-check通过：`tasks=26, evidence paths=231, backlog task rows=26, QA matrix rows=17, manifest path references=24, release authorization boundaries intact`。13份相关Markdown的84个本地链接无缺失、5份JSON与1个JSON示例可解析；W01–W14依赖无环，Markdown/JSON的编号、T/QA映射、依赖和工期一致。

规划起点记录的78个既有改动文件中，仅8个进度/QA文档有意修改，其余70个指纹一致，0缺失/意外修改；源码、已有测试、配置与旧证据保留。另外更新文档总入口并新增本轮文档/交接/记录，未reset/checkout/清理/提交/push。

29文件候选与当前白名单源码及归档仍一致，原集合/归档SHA不变，image_digest=null；没有新镜像构建/发布或旧P0修改。现有WebUI的版本/元数据/安装源码只读检查不构成正式登录、tool call或生产功能验收。Goal API最终null，原26任务及QA状态保留，真实调用/资料/生产/试用授权边界完整。

## 后续执行入口

用户随后授权“开始执行”并确认沿用当前IP，第一批schema10网关/CLI/上下文本地工程与证据见[新交接](HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)。本文件schema9/全部planned/未执行和原包一致的描述是规划完成时历史，不能作为当前源码状态。原生产/真实调用/资料/试用边界保留。
