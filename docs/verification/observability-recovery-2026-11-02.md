# 观测与恢复增量验收

日期：2026-11-02（Asia/Shanghai，历史基线）

本报告只记录隔离临时目录、合成账号和合成资料的确定性验证，不把它们描述成真实 Open WebUI、真实 provider、对象存储或真实学习者验收。当前全量回归为 `91 passed`、schema revision 7；页面修订/复核申请、维护准入、migration 原子性、SQLite 进程恢复和可信 UI callback 超时增量分别见 `docs/verification/maintenance-gate-2026-11-03.md`、`docs/verification/migration-atomicity-2026-11-03.md`、`docs/verification/database-process-recovery-2026-11-03.md` 和 `docs/verification/trusted-ui-timeout-2026-11-03.md`；本文件中的 revision 3 运行细节保持为历史快照。

## 命令与结果

- 历史基线 `pytest -q`：`37 passed`，无 warning；当前全量回归为 `91 passed`，维护准入、migration 原子性、SQLite 进程恢复和可信 UI callback 超时增量见 `docs/verification/maintenance-gate-2026-11-03.md`、`docs/verification/migration-atomicity-2026-11-03.md`、`docs/verification/database-process-recovery-2026-11-03.md`、`docs/verification/trusted-ui-timeout-2026-11-03.md`。
- `python3 -m compileall -q learning_service tests`：通过。
- `python3 -m json.tool docs/goal/TASKS.json`：通过。
- `LEARNING_ADMIN_SECRET=dev LEARNING_ADAPTER_SECRET=adapter docker compose -f docker-compose.learning.yml config --quiet`：通过。
- `docker build -f Dockerfile.learning -t dd-learning:verification-20261102-observability .`：通过。

## 管理员 metrics

`GET /api/v1/admin/metrics` 要求受信管理员上下文，返回任务按状态/类型计数、最老 queued 年龄、过期 running lease、失败页比例、待复核 item/batch、待清理 deletion 和幂等记录数量。响应固定包含 `external_calls.tracked=false`，不虚构 provider 费用。测试确认 student 角色被拒绝，且响应序列化内容不含学习者标识、原图、原始答案或 provider payload。

## Lease 回收

测试写入一个模拟 worker 进程在领取后立即退出留下的 expired `running` job。下一次 worker 领取后：job 成功，`attempts` 从 1 变为 2，lease token 被清除，1 个 import item 和 1 个 source region 被写入，页面只处理一次。该证据验证持久化 lease 协议；没有把确定性状态构造冒充真实 OS 进程 kill 或跨主机 worker 故障。

另一个测试启动真实 Python worker 子进程，令 provider 在外部调用期间阻塞；父进程确认 job claim 已持久化为 `running` 后发送 `SIGKILL`。子进程退出后，没有页面/候选业务写入需要回滚；租约过期后重新领取成功，`attempts` 从 1 变为 2，候选和来源区域各一份。这证明 worker 进程级中断的本地恢复路径，以及 provider 等待不持有 SQLite writer lock，但仍不等同数据库服务进程、对象存储或跨主机故障。

## 备份恢复完整性

恢复前拒绝 manifest 中未列出的额外文件、数据库 checksum 篡改和非空目标目录。正常恢复复制数据库/附件后运行 SQLite `PRAGMA integrity_check`，任何复制、迁移或完整性检查失败都会清理新建的半恢复目录。旧 migration 001 恢复和删除 tombstone 重放仍由服务测试覆盖。

## 未覆盖边界

真实数据库服务进程级中断、对象存储一致性/故障、真实网络 provider 超时与费用、Open WebUI Tools 注册/回调、脱敏整卷人工标注和 T23 7–14 天真实观察仍需要外部测试环境、凭据、预算和授权；本报告不提高这些任务的状态，也不支持将 Goal 标为 `complete`。
