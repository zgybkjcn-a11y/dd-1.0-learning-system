# 智能学习系统文档入口

2026-11-08：A09 [静态交付准备验收](verification/A09-static-samples-2026-11-08.md)通过30项定向检查及隔离nginx候选4/回退3路由；[交付与设备检查表](open-webui-reuse/static-samples-delivery.md)已就绪。工程ready，发布与真实设备/家长验收pending，总状态open。下一项 **B01：七上第二章覆盖表**；下方为历史记录。

A08已完成[既有Tool升级与回退本地验收](verification/A08-tool-lifecycle-2026-11-07.md)，54项及固定WebUI原生验证通过；[维护操作单](open-webui-reuse/tool-upgrade-rollback.md)。正式Tool未升级，下一项 **A09：三个静态样本交付与设备体验**。下方A07及此前记录保留历史。

A07 已完成[五片段本地接入](verification/A07-runtime-passages-2026-11-07.md)，Tool 候选 **1.2.0**，服务能力默认关闭，未提交/部署；[运行契约](open-webui-reuse/textbook-passages-runtime.md)已补配置、引用和回退。下一项 **A08：既有 Tool 升级与回退机制**。下段各轮结果保留历史日期语境。

2026-11-07 当前交付事实统一见[当前状态与兼容清单](releases/current-state.md)及[机器清单](releases/current-manifest.json)。A01 现状核对与 A03 可移植测试基础已完成，A02 已形成[两组交付单](releases/A02-candidate-delivery-2026-11-07.md)并通过[本地验收](verification/A02-candidate-delivery-2026-11-07.md)，状态为“已整理，待提交”；A04 [故障分类与恢复](open-webui-reuse/study-error-recovery.md)也已完成，[552 项单元/契约与原生六方法验证](verification/A04-study-errors-2026-11-07.md)通过，未提交/部署。A06 [冻结评测与基线](verification/A06-retrieval-evaluation-2026-11-07.md)已完成：73 项合成测试通过，新试点召回 2/20、无依据拒绝 2/10，质量未达标。A05 [有界检索与不足判定](verification/A05-chapter-retrieval-2026-11-07.md)现已完成，补充集召回 20/20、拒绝 10/10、泄漏 0/10；241 项单元/契约、4 项浏览器及原生六方法通过。Tool 本地候选 1.1.2，未提交/部署。A05 当时下一项 **A07：接入 5 个有效片段**。[A01 验证](verification/A01-current-state-2026-11-07.md)记录运行快照，[A03 验证](verification/A03-portable-tests-2026-11-07.md)记录干净环境 503 + 12 项通过；测试操作见[测试说明](TESTING.md)。远端 CI、发布和真实体验状态分别保留。

下一阶段执行入口：[实施方案](plans/DD-1.0-NEXT-IMPLEMENTATION-2026-11-07.md)、[工作计划](plans/DD-1.0-WORK-PLAN-2026-11-07.md)、[25 项任务台账](plans/dd-next-work-tracker.json)、[续接指令](plans/RESUME-NEXT-WORK.txt)。[项目评审](PROJECT-REVIEW-2026-11-07.md)保留编制依据。下方 11-04/11-05 状态均为历史，不据此重复绑定、安装或回退部署。

## 11-04 / 11-05 历史交付记录

2026-11-05 当前优先级：**两人数学测试版已部署**，一个现有家长账号切换七年级/二年级档案，14 道起步题、练习判分/恢复和手动错题本。用户已明确授权本家庭版生产上线；真实模型/OCR、学生资料外发和 Goal 写入仍禁止。设备证书导入和真实家长首次绑定待用户操作。复杂监控/完整恢复/商业化功能暂缓，不作为此次上线前置。下文旧批次的“未部署/禁止生产/下一步监控恢复”保留历史，仅在与本范围不冲突时适用。 入口/首次使用/验证及运维见[家庭测试版交接](goal/HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)。

最新本地工程：[W07–W10运行/恢复说明](open-webui-reuse/06-RUNTIME-RECOVERY-2026-11-04.md)、[新隔离镜像/HTTP/TLS/恢复报告](verification/reuse-runtime-recovery-2026-11-04.md)、[续跑交接](goal/HANDOFF-SESSION-2026-11-04-W07-W10.md)。正式门槛与任务状态保留。

最新W04/W05/W06本地工程：schema11/66/24、Tools1.1.0；工作台/共享Tools/人工审核冻结与合成验证已补，T/QA/真实门槛保留。见[第二批交接](goal/HANDOFF-SESSION-2026-11-04-W04-W06.md)。

更新日期：2026-11-04。项目：独立智能学习服务，复用本机已部署 Open WebUI。

## 从这里开始

先读[当前交付清单](releases/current-state.md)，再按[台账](plans/dd-next-work-tracker.json)继续。当前主站为 `https://172.19.116.53/`；[复用部署文档入口](open-webui-reuse/README.md)保留原规划、开发文档和 14 工作包历史。旧 HTTP 地址和“HTTPS/登录桥接仍待实施”描述属于 11-04 起点。

1. [设计开发总文档 DD-1.0](DESIGN_DEVELOPMENT_SPEC.md)：目标与范围、需求编号、架构、界面、导入/复习流程、数据字典、API、Agent/媒体规范、部署与验收。
2. [开发任务与验收清单](IMPLEMENTATION_BACKLOG.md)：26 个工作包、依赖、阶段成果、验收场景、重新估算方法及完成定义。
3. 按负责模块阅读下面的专题文档；运行事实查看核验快照，不能把设计接口当作已上线能力。

可复用的 [Goal 模式开发提示词](GOAL_MODE_DEVELOPMENT_PROMPT.md) 仅保留历史启动契约；旧 `goal: null` / blocked 描述属于历史记录，不代表本批查询结果或下一阶段任务状态。当前继续禁止 Goal 写入；实际断点以[任务台账](plans/dd-next-work-tracker.json)及其验证证据为准，不按历史提示词自动创建目标。正式切换、真实模型/OCR与资料外发、持续试用仍按各自有效范围执行。

## 专题与历史依据

| 文档 | 定位 |
| --- | --- |
| [主规划 R2 + U1](LEARNING_SYSTEM_REVIEW_AND_PLAN_2026-11-02.md) | 本机核验与基础决策、确定性调度、完整范围增补 |
| [试卷/作业上传与错题导入](PAPER_HOMEWORK_IMPORT_DESIGN.md) | 多图/PDF、分题、批改/答案识别、复核和入库 |
| [模型、Agent 与多模态教学](MULTIMODAL_AGENT_LEARNING_DESIGN.md) | 诊断与编排、绘图、精确交互、视频/GIF 扩展 |
| [升级兼容与恢复](UPGRADE_COMPATIBILITY_AND_RECOVERY.md) | 与上游隔离、数据所有权、演练与回退 |
| [二次审查记录](SECOND_REVIEW_2026-11-02.md) | 历史问题与修订；不替代新需求或运行验收 |
| [脱敏运行快照](AUDIT_BASELINE_2026-11-02.json) | 2026-11-02 历史只读核验；本地库存、端口和镜像 digest 已省略 |

## 已有原型

[数轴交互 HTML](prototypes/signed_numbers.html) 可直接在浏览器打开；[使用与验证说明](prototypes/README.md) 记录功能及边界。

它展示“减去负数”的预测、提示、数轴移动、错误路径和变式练习。是离线教学示例，不连接账号/模型/学习数据库，不保存成绩，不具备试卷上传识别功能，未接入正式 Open WebUI。

## 11-04 原型交付状态（历史）

| 项目 | 状态 |
| --- | --- |
| 规划、专题设计、总开发规格、任务清单 | 已形成文档 |
| 数轴教学原型 | 已有离线示例及原型检查记录 |
| 学习服务、数据库迁移、整卷上传/候选判定、正式错题本 | 已实现；合成/隔离验证通过 |
| 可信输入、测验、Agent 编排、数轴模板与薄 Tools 适配器 | 已实现；真实 Open WebUI/提供商接入待验证 |
| 备份恢复、删除生命周期、Compose 隔离与升级兼容 | 已实现；旧 schema 恢复和故障注入已有回归证据 |
| 真实 OCR/模型质量、浏览器闭环、学科人工裁决与持续试用 | 外部条件阻塞；不得以模拟结果替代 |

原完整 V1 范围包含整卷上传和一个正式教学模板，后续设想包括更多模板、视频/GIF 与策略化自动入库。当前交付和下一阶段阻塞以[当前清单](releases/current-state.md)、[任务台账](plans/dd-next-work-tracker.json)及其验证引用为准；`docs/goal/` 保留历史。

文档检查已覆盖相对链接、代码围栏、JSON 示例、16 项需求、17 项验收编号、26 个任务的依赖引用与无环性，以及调度示例的日期计算。这仅是文档一致性检查，不表示应用、模型/OCR或真实 UI 已验收。

## 文档维护规则

- 总设计负责统一实现契约；专题保留细则，修改后同步相关依赖。
- `SECOND_REVIEW_2026-11-02.md` 与运行快照保留历史语境，不覆盖成新的上线报告。
- 新代码、迁移、API 与模板固定版本；实现阶段追加真实验收证据，区分模拟/真实调用与待验证项。
- 不在文档、源码或日志里写真实密钥、学生个人资料、完整私有卷面或管理员令牌。

复用当前IP的第一批工程： [实际实现/CLI](open-webui-reuse/04-LOCAL-IMPLEMENTATION-2026-11-04.md)、[工程证据](verification/open-webui-reuse-engineering-2026-11-04.md)、[最新交接](goal/HANDOFF-SESSION-2026-11-04-REUSE-ENGINEERING.md)。

DD-1.0新会话入口：[会话完整总结](goal/HANDOFF-SESSION-2026-11-04-SESSION-SUMMARY.md)与[可复制续跑指令](goal/RESUME-SESSION-2026-11-04.txt)。
