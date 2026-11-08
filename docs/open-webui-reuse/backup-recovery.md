# 学习数据备份与隔离恢复

B07本地候选。正式数据备份、独立故障域副本及家庭运行恢复仍待落实。用户本轮明确选择“尚未确定，先完成本地演练”；独立位置与保管人保持null，不以同磁盘临时副本代替。

## 范围与一致性

`learning_service.backup`只处理明确指定的学习数据目录：`learning.db`、`attachments/`、`exports/`。教材私有包、公开源码/配置版本清单通过逐个`--include NAME=PATH`显式加入`materials/`或`versions/`；不递归扫描项目配置、不读取秘密或正式WebUI数据。包中含学习数据库与私有附件，应放在受控私有位置；归档根目录0700、回执0600。它没有提供加密或独立存储保管功能。

新CLI备份必须显式`--writers-stopped`。操作者先停止API、worker及其他文件写入方，并记录维护窗口和已停止进程；该参数不会停止进程。随后实现持有`BEGIN IMMEDIATE`锁，用第二个连接执行SQLite快照，复制前后核对全部附件/导出/指定材料列表和哈希，再按数据库的有效资产/导出记录核验大小、哈希与原页关联。写锁不可获得、源库被替换、文件出现/消失/变化或缺失引用均拒绝发布新包。

数据库锁不能阻止数据库之外的任意文件写入，前后哈希也不能代替停写事实。`operator_stopped_sqlite_write_lock_verified_files`明确依赖操作者停写断言，`process_stop_independently_verified=false`，不得把它写成工具自动核验所有进程停写。

文件先复制到独立暂存目录、完整校验并fsync，再用Linux `renameat2(RENAME_NOREPLACE)`原子发布；不支持此操作的平台明确失败，不降级成覆盖。恢复拒绝源/目标重叠、symlink/特殊文件、非法成员路径、缺件、hash错误、未来schema和非空目标。正式恢复必须选择新的隔离空目标，不能对活动目录运行。

## 三种回执

| 动作 | 回执及其证明范围 |
| --- | --- |
| backup | `dd-learning-backup-receipt-v1`：备份包已生成，绑定manifest SHA256、时间和耗时；尚未恢复 |
| verify | `dd-learning-backup-verification-v1`：独立重新读取包，检查成员、哈希、SQLite完整性/外键及有效文件引用；尚未恢复 |
| restore | `dd-learning-restore-receipt-v1`：指定包已在隔离目标完成复制、迁移、快照内删除重放和运行状态失效；业务逐表对账仍需独立`verify_recovery`记录 |

回执写入新文件，原子发布、不覆盖历史，必须位于源、包、恢复目录之外。失败不生成成功回执。三个回执的`manifest_sha256`应一致。verify可额外生成`dd-learning-backup-observation-v1`，兼容现有监控的`learning_only/verified/finished_at`；它只证明备份核验，`recovery_performed=false`，不能代替恢复验收或独立副本可读性。

以下仅为操作形式；路径须替换为已授权的维护/演练目标，不能直接套用于正式库：

```bash
python -m learning_service.backup backup /isolated/source /isolated/archive \
  --writers-stopped \
  --include materials/textbook.pdf=/isolated/named/textbook.pdf \
  --include versions/source-manifest.json=/isolated/named/source-manifest.json \
  --receipt /isolated/receipts/backup.json
python -m learning_service.backup verify /isolated/archive \
  --receipt /isolated/receipts/verify.json \
  --observation /isolated/receipts/observation.json
python -m learning_service.backup restore /isolated/archive /isolated/restored \
  --receipt /isolated/receipts/restore.json
```

恢复副本先迁移到当前schema13，撤销浏览器会话、清空共享档案选择、消耗旧挑战、暂停provider；在途`reserved`调用改为`unknown`并保留费用占用。快照内删除记录重放包含B06工作区，不重新开放已删除档案。旧API/worker、Tools、网关和代理均不自动启动或切换。

Python旧`backup_data(..., writers_stopped=False)`仍生成明确标注顺序复制的v1历史格式，兼容旧调用。新版CLI的verify/restore默认要求v2一致性包，旧包需显式`--allow-legacy-sequential`；该例外不能生成一致性已核验的监控回执。历史包内容保持不变。

## 验收与后续缺口

本轮先冻结演练目标RPO≤24小时、RTO≤2小时，仅用于小型合成样本；记录真实耗时、样本规模和恢复后的缺失记录数，正式RPO/RTO仍未验收。`operations.recovery_inventory/verify_recovery`比较原页附件、错题/复习卡、冻结作答/题版、B06轮次/工作区、导出及身份记录，并检查会话失效、provider暂停、费用预留不丢失。恢复造成的预期删除须单列，不能把删除差异混成数据完整保留。

本地演练结果见[B07独立验收](../verification/B07-backup-recovery-2026-11-08.md)。实际库/附件/教材包的最新容量、维护窗口、来源清单，以及至少一份独立故障域可读副本、保管人和访问责任尚未完成，B07总状态保持open。备份后新增的删除/费用增量不在本批范围，完整WebUI/秘密/网络配置恢复也未验收，沿用[完整恢复计划](07-MONITORING-RECOVERY-PLAN-2026-11-05.md)的限制。

下一项B08可先使用本批回执与合成库验证监控，尤其需要核对现有采集器schema11限制与当前schema13，不启用生产监控或外部通知。
