# 第四档挑战与题型升级验收

2026-11-11已上线98道原创挑战题，覆盖13册7学科的98个目录范围，每范围一道。正式题库共1121题：二年级410、七年级711；章节题1047、原应用题60、起步题14。历史12道备用候选未安装。

## 使用与题目

难度为简单、正常、困难、挑战；首页与答题页均可选择。自动进阶在同一档连续独立答对4道不同题后升档，困难可升挑战；错答或提示后降档，重复题不累计升级证据。挑战为试用分档，未完成真实学生校准。

本批261个作答项：多选97、排序32、数值63、单选39、限定短答30。真正的多选框与上移／下移卡片支持草稿刷新恢复、判分、提交后恢复及错题收藏。多选漏选或多选都需重看；排序必须完整且顺序正确，初始卡片不自动计已答。全项正确才记答对。答案、同义词及选择键在提交前保持私有。

数学覆盖分类讨论、最优方案、数量守恒、计费边界、参数消项和统计边界；语文覆盖双材料证据、错字修正、文言时序、论证及反例；英语覆盖信息更正、关系网络、词形、对话和日程；其余学科增加证据限制、指标比较、实验对照、分类检索及情境决策。没有把98个编辑标签当成98种独立交互类型。

[使用说明](../open-webui-reuse/challenge-tier.md) · [98题完整答案审阅页](../../learning_data/verification/challenge-tier-20261111/review/questions.html)。下表包含章节题与原应用题，不含14起步题。

| 教材 | 之前 | 新增挑战 | 当前 |
| --- | ---: | ---: | ---: |
| math-g2-upper | 252 | 8 | 260 |
| math-g7-upper | 226 | 6 | 232 |
| math-g7-lower | 90 | 6 | 96 |
| ethics-g2-upper | 22 | 4 | 26 |
| chinese-g2-upper | 49 | 9 | 58 |
| chinese-g2-lower | 49 | 9 | 58 |
| chinese-g7-upper | 34 | 6 | 40 |
| chinese-g7-lower | 34 | 6 | 40 |
| english-g7-upper | 102 | 18 | 120 |
| ethics-g7-upper | 22 | 4 | 26 |
| history-g7-upper | 36 | 6 | 42 |
| geography-g7-upper | 51 | 9 | 60 |
| biology-g7-upper | 42 | 7 | 49 |

## 内容与兼容

13份固定SHA256教材、98处主题位置经本地原生文本核对。题干、情境与资料为原创；文言短引标明公版篇名。页码表示主题位置，不表示教材原题转载。旧22个JSON文件逐字节不变，原276点658要求及已有映射逐项保留，仅增加98条辅助映射。对人工表达、真实听说、写作、画图和操作的缺口保持，不据每范围有题宣称整章穷尽。

新增structured-fields-v3支持多选集合及完整排序；旧v2、数值字段和单答协议继续可用。数据库014仅扩展两张练习表的难度约束；旧工作区、轮次ID及作答引用保持。常规启动和身份管理两个迁移入口均检查外键后提交，失败整体回滚。

## 验证与上线

386项单元／集成检查通过：新协议、内容和迁移31项，历史内容68项，服务、身份、恢复、备份、契约及封包兼容287项。98题全量开题、恢复、判分、重复提交、隐私和档案隔离检查通过；独立整数枚举、单位换算、方程代回验证数学约束。非法集合、重复或越界项、部分排序、篡改答案键和顺序差异都有负例。schema13的已填工作区、轮次和作答引用验证了并发迁移、幂等、失败回滚及两个入口。

Chromium145.0.7632.6在1280和390宽度各跑13册代表题，共2项检查通过：多选、卡片排序、未填项提示、错误判分、提示后刷新、提交后恢复、可读收藏及无横向溢出。真实家庭手机按既有约定暂缓。

最终封包learning_data/releases/challenge-tier-20261111-final，profile reuse-runtime-challenge-tier-v8；128源码／84运行文件每服务匹配。source set a38d6efece6ea7d0a16effdb9f7d4392460f4321385202ddfc9792a92a706a0a；archive 3dd8d6e2c85c8ed4a341cb7c4ac25e687c19628eccb725259b8d6f81f38e7658。镜像sha256:50ee80009a7e008f672193f61f99fbe2ba32aad9951a0fb6c3f46db6487576d8，固定基础镜像和16个已校验wheel，network=none、no-cache构建。

生产一致性副本先演练成功。上线时停止API和worker，完成整卷备份与校验，再迁移、导入及重复导入检查。逐表保全旧行；仅新增98个questions、98个question_versions、1条audit_events与1条schema_migrations，重复导入0新增。数据库完整性及外键检查通过，schema14。备份manifest SHA256 d99d299804b5792bcd2e00f0af7538de1f006d884ecc4b35d603c473bdc6a1f3；副本在本机私有目录，不代表独立故障域。

Compose learning_data/deployments/family-challenge-tier-20261111/compose.json，只更换API／worker镜像。5个服务运行，API healthy，网关／代理／WebUI镜像与启动时间保持。线上1047章节题版全部核验；已有选中档案只读列表HTTP200，711题（其中68挑战），9.225秒；内部UI200、未登录外部入口303。没有切换真实档案或制造真实作答；无外部模型、OCR或embedding调用，4个C01服务继续停止，既有模型验收记录保持。工作树无提交或推送。

回退必须处理schema14与新协议兼容，保全新使用记录，不能用旧备份覆盖当前数据库。证据见learning_data/verification/challenge-tier-20261111：tests-*.xml、source-check.json、inventory.json、rehearsal-result.jsonl、data-preservation.json、runtime-hashes.json、live-read.json及final-health.json。
