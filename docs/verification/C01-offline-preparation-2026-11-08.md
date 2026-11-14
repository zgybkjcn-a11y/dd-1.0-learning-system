# C01 离线准备与 B11 手机暂缓记录

用户已明确暂缓B11真实家庭手机验收，记录为deferred_by_user，设备及结果仍为空；桌面浏览器7项与HP 102w/Chrome三页纸张通过保持，B11仍ready/candidate_only/pending/open。继续完成C01获准的离线准备：24个合成情景、六方法契约、人工评分规则与空白执行记录已冻结。真实模型执行仍deferred/gated，未调用、未评分、未部署。

## 用户决定与状态

用户原文：“手机验收暂缓，记录下就行。继续下一步”。记录时间 `2026-11-08T15:34:06.770233+00:00`，精确发言时间未知。原文保存在 `learning_data/verification/c01-offline-preparation-20261108T152941Z/user-instruction.json`。手机仅安排状态为 `deferred_by_user`，验收仍 pending，设备、系统、浏览器、操作人、时间和结果仍 null；不把暂缓当免验或通过。已有桌面浏览器 7/7、入口问题人工复验关闭、HP 102w / Chrome / 3 页正常保持原证据。

C01 计划明确允许“此前可整理用例，不发送调用”。本批只完成该离线子范围，C01 四态仍 `deferred / not_applicable / gated / deferred`；B11 仍 `ready / candidate_only / pending / open`。其他 23 个任务对象、历史变更日志、A06 原失败基线与所有待外部条件项目保持。

## 离线产物

- [24 个冻结情景](../quality/c01-scenarios-v1.json)：六方法全部覆盖，含范围/证据/缺证据/注入/教学，逐项给出前提、用户轮次、所需调用与观察。
- [空白执行记录](../quality/c01-run-record.template.json)：24 项均 not_run，执行分母 0；提供方、模型版本、预算、复核者、教学阈值、输出和评分全部留空。
- [人工判定与执行规则](../open-webui-reuse/real-model-acceptance.md)：固定分母，零输出不能通过正向引用；缺陷零容忍与预算停止规则分别保留。

七维计划分母分别为：选工具10、范围9、证据8、逐项支持11、缺证据9、注入5、教学5，维度重叠，总用例24。多轮教学不预填模型回答；合成学生输入不冒充真实家庭反馈。夹具仍为规格，后续需在独立目录装配与冻结有效材料、目录映射和兼容环境，不能把本批结构校验当端到端结果。

Tool 1.2.1 源码 SHA256 `3da7d6a0b9a6575c7fd89e62daf92afde1cce91f3af6cc6c8d0dfe5c0ccb504b`；B11 源包 SHA256 `4b7b5282b9d786725a7683e817598f0fa12380ccbfdc8a281d021f08ad876187`。当前 WebUI 0.12.5 / schema13 不变。

## 独立证据与定向验证

本批目录 `learning_data/verification/c01-offline-preparation-20261108T152941Z/`。编辑前已保存6份文档的当前工作树副本、Git HEAD/状态/索引哈希、只读契约与前批21文件证据封存校验，并冻结本次范围。用例和执行模板先记入 `scenario-freeze.json`，再做离线结构/契约检查；没有真实调用或结果选择。

离线结构/契约及保全检查通过：24情景、6方法、7维度，99运行文件和9静态资源哈希保持；25个任务的四态均未改变。定向检查结果见本批 `preparation-validation.json` 与 `delivery-validation.json`；文档增量见 `offline-preparation-increment.patch` / `increment-manifest.json`，最终公开文件副本在 `source-final/`，全部批次证据清单在 `evidence-manifest.json`。补丁以本批 `baseline-workspace/` 为基底，不直接假设Git HEAD。验证仅检查JSON/覆盖/参数、空结果、状态保留、候选哈希、链接及补丁回放；不重复性能、浏览器或运行单元测试。

原900样本、P95门槛、12秒总截止、身份/证据检查不变。未读正式WebUI数据或受限配置，未调用模型/embedding/OCR，未提交/推送/部署，未改Goal。实际专注工时未知。

## 后续

C01离线情景准备完成；真实执行等待限制变更、提供方/模型版本、公开或合成材料、调用预算、兼容隔离环境及实际复核者/教学阈值明确后另行冻结。B11手机按用户指令暂缓，不重复催验；其他外部验收继续独立保留。 A09发布与家庭反馈、B02真实1/3/7天观察、B05收藏反馈、B04待解图形、B07独立副本和B08独立观察端仍按原台账单列；未获得新外部条件时不代填完成，也不自动启动C02–C05。
