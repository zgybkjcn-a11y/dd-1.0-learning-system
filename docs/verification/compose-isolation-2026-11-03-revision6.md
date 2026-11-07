# DD-1.0 隔离 Compose revision 6 证据

日期：2026-11-03（Asia/Shanghai）  
范围：Learning API/worker 的独立生产模式运行边界；使用独立网络、独立卷和合成数据。

## 配置检查

对 `docker-compose.learning.yml` 使用临时环境变量执行 `docker compose config`，结果为：

```text
api_ports []
worker_ports []
network_internal True
api_networks ['learning-internal']
compose_config_rc=0
```

Compose 文件不发布宿主端口；仅 `docker-compose.learning.local-ui.yml` 为明确的本地调试覆盖提供 `127.0.0.1` 端口。生产 Compose 固定 `LEARNING_DEV_MODE=0`，admin/adapter secret 由运行时环境提供，值不进入本报告。

## 正在运行的隔离实例

隔离验证实例：

- Open WebUI：`dd-openwebui-isolated-20261103d`
- Learning API：`dd-learning-isolated-api-20261103d`
- 网络：`dd-openwebui-isolated-20261103d`，Docker `internal=true`
- API `31010/tcp`：无宿主端口映射

宿主网络检查确认隔离网络只有这两个 DD 容器；现有正式 `open-webui` 使用其他网络和端口，未挂载到该 Learning 卷。

## HTTP 边界探针

```text
GET  /health              -> 200, schema_revision=6
POST /internal/bootstrap  -> 404 (LEARNING_DEV_MODE=0)
```

容器内未授权的业务请求仍按受信身份边界返回 401。此前在开发模式创建的合成身份仅存在于 disposable 隔离卷；生产模式不会重新开放 bootstrap。

## 复验与限制

本报告生成时 `pytest -q` 为 76 passed；之后增加测验工作台回归，曾为 77/78 passed，当前全量结果为 91 passed（服务 71、Tools 11、Open WebUI 兼容 3、隔离 Compose preflight 6）。`python3 -m compileall -q learning_service tests scripts` 通过。该报告覆盖 revision 6 migration、Compose 网络/端口边界和生产 bootstrap 关闭；它不替代真实 Open WebUI 浏览器组合、真实 provider、外部数据库/对象存储故障演练、真实资料或正式上线授权。
