# B07 基本备份与隔离恢复验证记录

日期：2026-11-08（Asia/Shanghai）。本地工程 ready、候选交付、本地验证 passed；独立故障域副本、位置及保管人未落实，验收 pending、B07 总状态 open，实际专注工时 null。用户明确答复“尚未确定，先完成本地演练”。本批完成合成数据演练，没有提交、推送、构建镜像或部署。

## 输入和一致性边界

独立证据目录：`learning_data/verification/b07-backup-recovery-20261108T051822Z/`。HEAD 为 `cd4ad61b44597696d6c59495b489595e68123706`；开始时有 55 个既有未提交文件，另固定 13 个相关输入和 1014 份 B01–B06 历史证据。`inputs-before.json` 与 `baseline-source/`保存本轮开始的工作区；增量相对此基线生成，不按 HEAD 重建旧改动。

`drill-plan-before.json` 在实施前冻结合成范围与 RPO≤86400 秒、RTO≤7200 秒目标，独立副本位置/保管人均为 null。只使用新建学习库、PNG 原页、导出文件、合成教材文本及公开版本标记；未盘点或读取正式数据、秘密、根 Compose、无关配置或 WebUI 数据。正式数据容量、维护窗口与恢复目标另待落实。

新版 v2 备份要求操作者先停止全部写入方，再显式 `--writers-stopped`。实现持有 SQLite 写锁，快照前后检查附件、导出和显式材料的列表/哈希，核验有效数据库引用，并检查源库未被替换。该标记是操作者声明，工具不会停止进程，也不能独立证明任意文件写入方已停止；回执保留 `process_stop_independently_verified=false`。

备份/恢复在暂存目录校验后原子发布，拒绝覆盖已有目录或回执；非法路径、symlink、特殊文件、缺件、哈希错误、未来 schema、并发目标均拒绝。Linux 原子不覆盖发布不可用时明确失败。恢复迁移到 schema13，撤销会话、清空档案上下文、消耗挑战、暂停 provider、将 reserved 改为 unknown 且保留费用；快照内删除重放包括 B06 工作区。业务逐表对账独立于恢复回执。

旧 Python 顺序快照接口保留 v1 行为，CLI 校验/恢复旧包需明确允许历史格式；旧包不能输出“一致性已核验”的监控观察。操作和限制见[备份恢复操作单](../open-webui-reuse/backup-recovery.md)。

## 定向测试

最终 `unit-final.xml`：**51 项通过，0 失败、0 错误、0 跳过，23.62 秒**。其中新备份恢复 24 项、源码交付 15 项、既有恢复相关回归 12 项。仅复用 A03 锁定 Python 环境，无新安装；无 UI/HTTP 契约修改，不重复浏览器测试。

覆盖联合包恢复、锁竞争、复制期间文件新增/变化和源库替换、有效文件引用、重新计算清单哈希仍无法掩盖损坏资产、非法成员、未来 schema、非空/并发目标、恢复复制损坏、三类回执及监控兼容、旧包兼容、删除重放、轮次和文件字节差异。既有 PDF 原页恢复、错题/复习/变式、共享上下文与 provider 暂停回归均通过。

过程原始记录全部保留，复测不累加分母：

- `unit-first.xml`：23 项夹具错误；上传接口本来返回 201，夹具误期望 200，修正夹具后 `unit-second.xml` 23 项通过。
- `unit-regression-first.xml`：2 通过、9 失败；新目标路径限制过宽，阻止历史允许的源目录下独立备份子目录。修正为拒绝源本身/祖先和实际附件、导出树重叠，`unit-regression-second.xml` 12 项通过（增加 PDF 原页回归）。
- 最终加入重哈希损坏资产反例、清单绑定与回执路径检查、新 release profile 后，合并相关组得到上述 51 项通过。

## 独立合成演练

`run-synthetic-drill.py` 在 `drill-final/` 顺序执行真实 backup、verify、restore CLI，源 TestClient 已关闭且没有启动 worker。三种回执位于包和恢复目录之外，权限 0600；`backup-receipt.json`、`verification-receipt.json`、`restore-receipt.json` 均绑定 manifest SHA256 `35a5d9a4daf5040892d94eb1db468a7d79c4205796acbc8a8dcee8c63305a757`。独立保存 `monitor-observation.json`，未启用生产监控。

| 项目 | 实测结果 |
| --- | --- |
| 合成源目录 | 5 文件、684138 字节（含 SQLite 辅助文件），另显式加入 2 个合成材料/版本文件 |
| 归档目录 | 5 个数据文件及 1 个 manifest，共 652697 字节 |
| backup / verify / restore CLI 墙钟耗时 | 0.207359 / 0.080599 / 0.137268 秒 |
| 恢复至完成业务/API/文件对账 | 0.374624 秒，满足本次合成 RTO 目标 |
| 最后合成写入至备份开始 | 0.024972 秒 |
| 备份开始至恢复开始 | 0.290820 秒；仅记录本次样本年龄，不代表灾难发生时的实际 RPO |
| 恢复业务 | 28 组指纹一致，合成业务记录丢失 0；原页 SHA256 一致 |
| 运行状态 | 活动会话、档案上下文、未消耗挑战和 reserved 均归零；provider 暂停，unknown 1 条、费用占用 17 微单位保留 |

原页经内容 API 读取，错答、显式收藏、当前 hard 档会话和提示状态经 API 核对；材料/版本逐文件哈希一致。归档恢复前后逐文件哈希不变。`inventory-before.json`、`inventory-after.json`、`business-comparison.json`、命令退出码与计时、维护窗口、`drill-result.json`分别保留。**正式 RPO/RTO 均为 null、未验收**；约 668 KiB 的本地样本不能外推至实际家庭数据，也不代表独立故障域恢复。

## 源码交付与历史保留

`release-final/` 为 86 文件 schema13 源码候选，profile `reuse-runtime-verified-backup-v1`；archive SHA256 `257e5c3aa59f51423e749e33a4a66545b74c2820345208c0d88f4e044994cb45`。隔离解包后 backup/operations 纯导入不创建库，合成启动健康检查通过，OpenAPI 仍为 76 paths / 37 schemas。历史 B06 85 文件包仍校验通过，且可在合成 schema13 上启动并保留工作区记录。详见 `source-package-validation.json`。

本批增量 17 文件（修改 14、新增 3），8 份共享说明仅插入新段落；其他 24 个任务对象、旧变更日志和交付增量保留。`b07-increment.patch`在仓库外的空 Git 目录重放，对比全部 71 个结果文件哈希，不触碰实际索引。`source-manifest.json`、`evidence-manifest.json`和`delivery-validation.json`分别绑定源码、证据和交付检查；1014 份历史证据保持原哈希。忽略目录中的证据封存只是本地副本，不能称为独立备份。

## 待落实与接续

至少一份独立于原存储故障域的可读副本、具体位置、保管人/访问责任，以及实际数据范围下的维护与恢复实测仍待落实，B07 总状态继续 open。快照后的删除/费用增量、完整 WebUI/秘密/网络恢复均不在本批验收范围。

下一项 **B08 本地最小运行观察**可基于已就绪的回执继续；先核对现有采集器 schema11 与当前 schema13 的兼容，使用合成故障和独立失联检查，不能启用生产监控或发送外部通知。B05 家庭反馈、B04 图形待解、B02 真实延迟观察、A09 发布/家庭设备/家长验收继续单独记录。未调用真实模型/OCR、未写生产向量库或 Goal。
