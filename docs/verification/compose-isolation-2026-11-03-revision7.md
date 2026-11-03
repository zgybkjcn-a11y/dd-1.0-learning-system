# DD-1.0 隔离 Compose revision 7：干净启动与恢复证据

日期：2026-11-03（Asia/Shanghai）
范围：独立生产 Compose 的首次启动、边界探针、服务重启、备份恢复和清理；仅使用合成账号、学习者、授权行与附件，不触碰现有 Open WebUI 或既有隔离实例。

## 启动和边界

使用全新 Compose project `dd-learning-restore-check-20261103e`、临时管理员/适配器密钥、独立命名卷和独立 `internal=true` 网络执行。镜像构建成功；API 与 worker 均启动；容器内 `GET /health` 返回 HTTP 200、`schema_revision=6`、`version=0.1.0`；生产模式 `POST /internal/bootstrap` 返回 404。`docker inspect` 显示 API 的 `31010/tcp` 为 `null`（无宿主端口发布），仅加入该 project 的 internal 网络，数据卷为该 project 的独立 `dd_learning_data`。

## 数据恢复和重启

在临时卷内写入合成账号、学习者、`learner_access` 关联和附件后，使用容器内 `learning_service.backup` 完成备份与恢复：

```text
backup format=dd-learning-backup-v1
restore format=dd-learning-backup-v1
restored access rows=1
restored attachment=dd-recovery-probe-synthetic-20261103
PRAGMA integrity_check=ok
```

随后仅重启 API 容器。重启后再次读取到 `schema_revision=6`、同一授权关联 1 行和同一附件字节。恢复目标为空，manifest 文件校验与恢复后的 SQLite integrity check 均由 `learning_service.backup.restore_data` 执行。

## 清理与边界

验证结束后执行 `docker compose ... down --volumes --remove-orphans`；该临时 project 的容器、卷和网络均已删除。现有 `open-webui`、正式数据目录、既有 `dd-openwebui-isolated-20261103d` 与其卷未参与本次验证。

这份证据只覆盖独立本地 Compose 的技术边界和合成数据恢复；不替代真实 Open WebUI 聊天模型 tool call、最终可信浏览器回调、真实 OCR/provider、外部数据库/对象存储故障演练、人工学科裁决或 T23 真实试用。
