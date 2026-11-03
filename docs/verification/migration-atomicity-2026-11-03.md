# Migration atomicity and concurrent bootstrap verification

日期：2026-11-03（Asia/Shanghai）  
范围：独立学习服务 SQLite schema migration，不触碰现有 Open WebUI 数据库。

## 验证命令

```bash
pytest -q tests/test_learning_service.py -k migration
python3 -m compileall -q learning_service tests
```

结果：该次聚焦回归为 `3 passed, 50 deselected`；编译检查通过。当时全量快照为 62 passed；之后全量回归曾为 76/77 passed，最新 `pytest -q` 为 78 passed。双进程首次启动压力复跑 20 轮（每轮两个进程）均成功。

## 覆盖内容

- 从空数据库执行 migration 001–005，最终 `schema_migrations` revision 为 5。
- 注入一个先建表、后执行失败 `ALTER TABLE` 的 migration；初始化失败后，探针表和 version 5 记录均不存在，证明 DDL 与版本记录在同一事务中回滚。
- 修复失败 migration 后重新初始化同一数据库，migration 可重试并成功写入表和 version 5。
- 两个独立进程同时首次初始化新数据库；`BEGIN IMMEDIATE` 串行化迁移，两个进程均退出成功，最终 revision 为 5，未出现重复 `ALTER TABLE` 或半迁移状态。
- WAL 协商也有 15 秒有界重试；在并发首次打开数据库的压力复跑中，短暂 `SQLITE_BUSY` 不会把服务启动误报为迁移失败。
- `_execute_migration()` 按完整 SQL statement 执行，避免 `sqlite3.executescript()` 在 migration 中隐式提交。

## 边界

这份证据只覆盖本地 SQLite 迁移并发和事务原子性。它不替代生产数据库进程级故障、对象存储故障或真实升级窗口演练；这些仍列在 `docs/goal/BLOCKERS.md`。
