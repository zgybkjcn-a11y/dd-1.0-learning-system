# C01 离线Tool协议夹具验证

C01离线Tool协议夹具完成：合成PDF/PNG、书章符号绑定及完整回包已固定，六个只读方法的22个预设Tool步骤通过，10项定向检查通过。24个模型情景仍全部not_run；本批没有运行真实网关/服务/模型，不是选工具或教学质量验收。B11手机继续按用户指令暂缓，桌面与打印结果保持；运行候选、原性能基线和12秒预算不变。

记录时间`2026-11-08T15:45:25.591245+00:00`。本批范围依据用户“继续”，继续C01允许的离线准备；手机暂缓不变，真实调用限制没有改变。

## 产物和验证范围

[准备/回放脚本](../../scripts/prepare_c01_tool_fixtures.py)提供prepare与verify命令；[定向检查](../../tests/test_c01_tool_fixtures.py)验证材料一致性、旧目录不覆盖、当日有效性、原Tool拒绝外部主机和写路由、完整引文/双页码被篡改时能发现，以及注入文本不会使Tool新增外部请求。[操作说明](../open-webui-reuse/real-model-acceptance.md)已更新。

本批先保存工作树/HEAD/索引、前批封存和24情景哈希，再冻结计划与脚本v1。`packet-v1/`包含5页自编合成PDF、3张PNG、正文/上下文、合成审核条件和显式ID映射；PDF通过文本提取比对，没有读取真实教材、学生资料或执行OCR。哈希一致性仅证明合成协议绑定，不是实际内容审核。

Tool详情路径限制只接受固定书册ID格式。因此保持原情景`c01-synthetic-v1`不变，在单独binding.json把syn_math_a→math-g7-upper、章A1→2、章A2→5、书B→math-g2-upper、书C→biology-g7-upper，概念/题版映射至synthetic-*。合成原页1/PDF3及原页2/PDF4仍按冻结情景；不借用正式教材内容、真实映射或审核结论。

实际执行Tool 1.2.1的六个public方法及其_fetch/_read/_project、前后身份/范围复核、片段详情回读/最终集合复核和citation；只在私有导入里替换HTTPConnection为内存协议响应，不改全局http.client，不连接实际服务。网关/服务/PDF审核装载尚未执行；Tool协议通过不能外推端到端环境就绪。

## 结果和未执行项

| 范围 | 结果 |
| --- | --- |
| 定向检查 | 10 passed，0 failed/skipped |
| 预设Tool步骤 | 22/22通过，覆盖六方法 |
| 无预设Tool步骤 | C01-07、09，标no_tool_step_specified，不作模型判定 |
| 模型情景 | 24项全部not_run，实际执行0 |
| 模型调用 / 真实网络连接 | 0 / 0 |
| 模型引用与教学成绩 | null |
| 实际网关/服务 | 未执行 |

C01-10中途切档→CONTEXT_CHANGED，14过期和15篡改→REFERENCE_INVALID，19注入传输超时→RETRIEVAL_TIMEOUT，均无旧内容/引用事件。正常与多片段引文、双页码及详情/最终复核通过；no_evidence/low_relevance/insufficient_evidence/incomplete分别记录。此处是工具行为，不证明模型会正确解释这些状态或拒绝提示注入。

Tool预算仍12秒；本批没有测量12秒实际耗时或改动P95。服务端过期材料可能先被过滤，端到端错误层需另测，本批不把Tool投影层故障结果冒充真实服务输出。

## 首次失败与环境差异

同一v1在沙箱内首次回放的4次内存请求已完成、预算头仍约11989ms，随后异步返回停滞并最终得到SERVICE_TIMEOUT。保留`replay-v1/C01-01.json`；同时运行的沙箱pytest未形成JUnit，被中断，退出130，不计通过。随后按工具环境要求在沙箱外运行相同代码：10项检查通过，22步完整回放通过；未为通过而改源码、预算或冻结情景。无法仅凭此确定沙箱底层原因，记录为环境相关停滞，不作为性能缺陷归因或新增基准。

## 证据和保全

独立目录`learning_data/verification/c01-tool-fixtures-20261108T153801Z/`：`inputs-before.json`、`plan-before.json`、`harness-freeze-v1.json`、`packet-v1/manifest.json`、`fixtures-v1-unsandboxed.xml`、`replay-v1-unsandboxed/summary.json`、`execution-attempts.json`。公开增量和回放见`fixture-preparation-increment.patch`/`increment-manifest.json`，定向保全见`delivery-validation.json`，封存见`evidence-manifest.json`。补丁仅基于本批baseline-workspace，不直接套Git HEAD。

B11的99运行文件、9静态资源和设备矩阵不变；原24情景与空白执行模板不变，25项任务四态及其他24个任务对象保持。HEAD/索引、既有未提交修改、前批29文件封存保留；不重跑性能/浏览器/既有全套测试，无新提交/推送/部署。

## 后续

C01离线用例及Tool协议夹具已准备；真实执行仍等待明确改变调用限制、提供方/模型版本、公开或合成材料范围、预算与实际复核者/教学阈值。届时先另建隔离服务/网关环境并冻结材料与提示，再执行；本批不能代替端到端环境或真实模型验收。手机暂缓，不重跑未变检查。
