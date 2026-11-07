# 页面修订与复核申请增量验收

日期：2026-11-03（Asia/Shanghai）

本报告记录 migration 005 和页面修订/复核申请在独立临时数据库中的确定性回归。测试使用合成账号、合成页面和合成作答，不代表真实 Open WebUI、真实 OCR/模型、人工学科裁决或真实学习效果。

## 实现边界

- `learning_service/migrations/005_review_requests.sql` 创建学习者隔离的 `review_requests` 表，状态为 `requested`、`in_review`、`resolved`、`dismissed` 或 `cancelled`，同一作答最多一个申请。
- `PATCH /api/v1/documents/{document_id}/pages` 采用完整页面集合和 `expected_revision` compare-and-swap；要求页序连续、旋转仅允许 0/90/180/270，页面资产属于当前学习者且未删除，原始资料资产保持不变。
- 页面修订递增资料 revision，并使关联批次、候选和未完成分析 job 失效；旧 challenge 不能确认新 revision。
- 学习者可通过 `POST /api/v1/attempts/{attempt_id}/review-requests` 申请复核；同键同载荷幂等，同键异载荷冲突，重复申请拒绝，跨学习者不可见。
- `admin` 或对该学习者有 reviewer 范围授权的账号可记录 `in_review`、`resolved` 或 `dismissed` 裁决；申请与裁决均显式保持 `grade_unchanged=true`。
- 导出、删除 tombstone 和备份恢复重放包含 `review_requests`；删除将未关闭申请置为 `cancelled`，恢复重放不会重新公开已删除申请。

## 自动化证据

执行：

```text
pytest -q tests/test_learning_service.py -k 'review_request or migration'
5 passed, 48 deselected
python3 -m compileall -q learning_service tests
passed
```

新增回归 `test_review_request_backup_delete_and_restore_lifecycle` 验证：

1. 复核申请在备份/恢复后保留 `requested` 状态和理由；
2. 学习者删除会生成复核申请 tombstone、将状态设为 `cancelled` 并完成清理；
3. 删除后的备份恢复与 tombstone 重放仍保持 `cancelled`。

页面修订、旧 revision 拒绝、完整页集合、跨学习者/无关资产拒绝和旧批次/候选/job 失效由同文件既有回归覆盖。

## 报告生成时的全量结果

```text
pytest -q
62 passed（当时快照；之后全量回归曾为 76/77/78 passed，当前为 91 passed）
python3 -m compileall -q learning_service tests
passed
OpenAPI snapshot: 55 paths, 19 schemas
```

该报告只证明独立服务的代码、SQLite 迁移、权限、生命周期和确定性状态机行为；真实 Open WebUI Tools 注册/回调、真实 provider、人工标注和 T23 仍保持外部阻塞。
