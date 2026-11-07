# SQLite writer process recovery verification

日期：2026-11-03（Asia/Shanghai）  
范围：独立学习服务嵌入式 SQLite/WAL 的写进程中断；不触碰现有 Open WebUI 数据库。

## 验证命令

```bash
pytest -q tests/test_learning_service.py -k 'sqlite_writer_process_kill or process_kill or provider_call_does_not_hold'
python3 -m compileall -q learning_service tests
pytest -q
```

结果：聚焦集当时为 `3 passed, 50 deselected`，编译检查通过；报告生成时全量快照为 62 passed，之后曾为 76/77/78 passed，当前全量回归为 `91 passed`。

## 覆盖内容

- 在独立临时数据库中先提交一行数据，再由真实 Python 子进程打开 WAL、`BEGIN IMMEDIATE` 并写入未提交行。
- 子进程写事务保持打开时发送 `SIGKILL`，确认进程退出码为 `-9`。
- 通过生产 `Database` 连接重新打开数据库，执行 `PRAGMA integrity_check`，确认已提交数据仍在、未提交行不存在，并成功提交新的写入。

该回归证明当前 SQLite/WAL 文件在写进程被强制终止后的本地原子恢复边界。它不替代外部数据库服务、网络文件系统、对象存储或跨主机故障演练；这些仍需独立环境和授权。
