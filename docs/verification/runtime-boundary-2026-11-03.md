# Fresh production-mode runtime boundary probe

日期：2026-11-03（Asia/Shanghai）  
范围：独立学习服务从空目录启动，不连接或写入现有 Open WebUI 数据。

## 执行方式

使用 `python3 -m learning_service.app` 启动临时子进程，设置 `LEARNING_DEV_MODE=0`、临时端口、临时 `LEARNING_DATA_DIR`/数据库/附件/导出路径，以及临时 admin/adapter secrets。探针轮询 HTTP 服务就绪后立即终止进程，并清理临时目录。本节记录的是 revision 4 的历史快照；后续 revision 5 探针见 `compose-isolation-2026-11-03-revision5.md`，当前 revision 6 Compose 证据见 `compose-isolation-2026-11-03-revision6.md`。

## 结果

```json
{
  "health_status": "ok",
  "schema_revision": 4,
  "bootstrap_status": 404,
  "unauthenticated_business_status": 401,
  "db_under_isolated_dir": true
}
```

- 历史 revision 4 探针中，空目录首次启动完成 migration 001–004，`/health` 返回 200 和 `schema_revision=4`。
- 生产模式 `POST /internal/bootstrap` 返回 404，内部种子入口未暴露。
- 未提供受信适配器/身份的业务请求返回 401，不会绕过可信上下文。
- 数据库、附件和导出目录均创建在临时独立目录；探针结束后目录已清理。

历史 revision 4 探针另行用同样的临时目录和临时密钥执行 `fastapi.testclient.TestClient(create_app()).get('/health')`，返回 HTTP 200、`schema_revision=4`。该探针保留为历史记录，不替代后续 revision 6 Compose、真实 Open WebUI 浏览器或原生 Tools 回调验收。

文档同步阶段的最终复验使用临时 Compose project `dd-learning-finalcheck`、临时端口、临时密钥和独立卷：镜像构建成功，API 与 worker 均启动，`/health` 返回 200、`schema_revision=5`；生产模式 `/internal/bootstrap` 返回 404，未带受信上下文的 `/api/v1/learners` 返回 401。该 revision 5 结果是历史快照；当前 revision 6 Compose 复验见 `compose-isolation-2026-11-03-revision6.md`。临时复验结束后容器、网络和卷均已清理，现有 Open WebUI 容器和数据目录未触碰。

## 边界

这是独立服务的宿主 HTTP 边界探针，不是正式 Open WebUI 浏览器、Tools 注册或原生回调验收；真实 provider、数据库/对象存储故障和真实资料仍按 `docs/goal/BLOCKERS.md` 等待外部条件。
