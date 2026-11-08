# B08 最小运行观察

本批提供本地采集器兼容修复、合成故障演练和独立进程失联检查。正式监控、独立观察调度、责任人及通知尚未落实；没有启用容器、修改卷权限或读取正式学习/WebUI数据。[独立验收](../verification/B08-minimal-monitor-2026-11-08.md)与[B07备份恢复](backup-recovery.md)分别记录实际范围。

## 已知事实与数据来源

2026-11-08 定向查询当前 Docker context 中 Compose service 标签为 `learning-monitor` 的容器（含已停止）没有结果。历史[监控模板](../../deploy/open-webui-reuse/compose.monitor.template.yml)为显式启用的可选 profile。这只能证明本次命名范围内没有该容器，不能推断其他主机、服务或其他命名的监控不存在。用户随后确认外部独立监控“没有，后续再安排”；状态记为尚未配置，具体观察端位置、责任人及正式调度待落实。

复用 `scripts/collect_learning_monitor.py`；不新增 HTTP 端点。采集四类信号：学习库固定聚合 SQL、固定内部 `/health`、指定文件系统的可用字节/inode，以及 B07 独立校验生成的备份观察回执。兼容已核验 schema11/12/13，其他版本拒绝；不使用“版本更大就兼容”的推断。无效队列时间、未来排队时间（超过60秒容差）、缺失/无效运行租约和关键控制记录均报告不可用。

SQL 使用 `mode=ro`、`query_only`、读取事务与截止，不迁移或修改业务行。活跃 WAL 的已提交状态必须可见，不能用 `immutable=1` 绕过。**SQLite 可能需要创建/维护 WAL/SHM 辅助文件**；历史模板因此具有学习卷文件系统写权限。本批只在合成目录验证，未接受或扩大生产权限。正式采用模板前须明确该能力；若要求严格文件系统只读，应另行设计最小聚合接口。

健康探测只允许 `learning-api` 或 loopback 的显式 HTTP 端口；固定 `/health`，无代理、Cookie、凭据或重定向。健康响应上限4096字节，HTTP截止2秒、子进程总截止4秒（覆盖DNS）。输出仅包含固定告警码、时间、序号和状态转换，不输出路径、源响应、账号、原题/答案、聊天或模型凭据。

## 本地冻结阈值

以下是本轮开发/演练默认值，正式值未批准。真实采样周期为采集耗时加等待时间，不等同于固定60秒调度保证。

| 信号 | 默认条件 | 结果 |
| --- | --- | --- |
| 采样间隔 | 每次采样完成后等60秒 | 写入最新心跳 |
| 独立观察 | 心跳年龄大于180秒、缺失或来自未来 | `MONITOR_STALE` |
| API | 超时、异常响应、错误服务或未知schema | `API_UNAVAILABLE` |
| 数据库 | 缺失、不可读、无效队列/租约时间或关键记录缺失 | `METRICS_UNAVAILABLE` |
| schema | 不属于11/12/13 | `DATABASE_SCHEMA_UNSUPPORTED`及不可用 |
| 队列 | 最老排队超过300秒 / 运行租约过期 | `QUEUE_AGE_EXCEEDED` / `WORKER_LEASE_EXPIRED` |
| 人工复核 | 待核项超过100 | `REVIEW_BACKLOG_EXCEEDED` |
| 空间 | 可用字节小于1GiB，或可用比例小于10% | `STORAGE_BYTES_LOW` |
| inode | 可用数小于10000 / 总数未知 | `STORAGE_INODES_LOW` / `STORAGE_INODES_UNKNOWN` |
| 备份 | 核验回执超过86400秒 | `BACKUP_STALE` |
| 备份异常 | 缺失、失败、无效或未核验回执 | 对应 `BACKUP_*` 告警 |
| 持续提醒 | 同一告警持续3600秒 | `reminder`事件 |

故障消失产生解除码；持续相同告警不重复生成事件。状态以同目录临时文件、fsync、原子替换写入 `latest.json`，目录0700/文件0600，固定结构不无限追加。单目录排他锁拒绝第二采集器；损坏时间、未来事件水位、时钟倒退均不能报告正常。

## 本地操作与独立观察

下面的路径必须替换为已授权的隔离数据目录。默认命令一次采样；没有自动安装定时任务、容器或通知：

```bash
python scripts/collect_learning_monitor.py collect \
  --db /isolated/source/learning.db --storage /isolated/source \
  --state-dir /isolated/monitor-state \
  --backup-receipt /isolated/receipts/monitor-observation.json \
  --upstream http://127.0.0.1:31010

python scripts/collect_learning_monitor.py status \
  --state-dir /isolated/monitor-state --stale-seconds 180
```

第二条应由独立观察进程执行，只需读取最新聚合状态，不读取源数据库/回执，不探测 API，不写回心跳。它能识别采集器停止；同一宿主整体失效则需要另一故障域的观察端。正式观察端及自身失联监督尚未配置，不能将两个本机进程写成外部监控已上线。

退出码0为无告警，2为 attention，1为执行失败，3为同目录已有采集器。调度器需分别处理；退出2不是进程崩溃。状态缺失/权限错误也必须报警，不以空结果视为正常。

B07 的 `monitor-observation.json` 来自独立 verify，保留 manifest 哈希。采集器读取受控回执的声明，不重新核验归档、恢复业务或证明独立副本保管；备份、校验、恢复三种证据不可互换。旧观察格式继续兼容，回执文件的可信写入与权限是运维责任。学习 provider 暂停、unknown/费用占用及待对账均继续报警，不自动恢复调用或清零；WebUI 聊天费用和全栈恢复不在覆盖范围。

维护源码包独立于 B07 的86文件运行包；后者保持原哈希。B08本地故障验收与正式启用/阈值/独立值守分开记录。后续 B09 可继续本地模块和类型契约工作；B07独立副本、B05家庭反馈、B04图形待解、B02跨日观察和A09发布/家庭验收不因此关闭。
