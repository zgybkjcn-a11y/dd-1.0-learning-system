# Revision 5 Compose 隔离运行验收

日期：2026-11-03（Asia/Shanghai）

本次使用临时密钥、独立 Compose project、独立网络、独立卷和端口完成生产模式探针。没有挂载或写入现有 Open WebUI `data/`，没有停止现有 `open-webui` 容器；provider 仍为确定性 mock。

## 执行参数

```text
project: dd-learning-rev5-check
port: ephemeral host port omitted -> service port 31010
volume: dd-learning-rev5-check_dd_learning_data
secrets: supplied only through temporary environment; values not persisted in this report
```

执行了：

```bash
# The temporary host port and secret values are omitted; this is an evidence excerpt, not a replay command.
LEARNING_ADAPTER_SECRET=redacted-not-a-real-secret \
LEARNING_ADMIN_SECRET=redacted-not-a-real-secret \
docker compose -p dd-learning-rev5-check -f docker-compose.learning.yml up -d --build
```

镜像构建、API/worker 启动和健康依赖通过。`docker compose config` 在提供两个必需临时密钥时通过；不提供密钥时仍按 Compose 必需变量拒绝解析。

## 宿主 HTTP 结果

```text
GET /health
HTTP 200
{"status":"ok","service":"learning-api","schema_revision":5,"version":"0.1.0"}

POST /internal/bootstrap  (生产模式，带 admin header)
HTTP 404
{"error":{"code":"NOT_FOUND","message":"资源不存在","retryable":false}}

GET /api/v1/learners  (无受信上下文)
HTTP 401
{"error":{"code":"UNTRUSTED_CONTEXT","message":"缺少受信适配器上下文","retryable":false}}
```

重启 `learning-api` 后再次 `GET /health` 返回 HTTP 200 和 `schema_revision=5`，证明独立卷中的 migration 状态可重启读取。API 和 worker 均以 `dd-learning-rev5-check` project 运行。

## 清理与边界

测试结束执行：

```bash
docker compose -p dd-learning-rev5-check -f docker-compose.learning.yml down --volumes --remove-orphans
```

复核后未发现该 project 的容器、卷或网络；现有 `open-webui` 容器仍在运行。该证据是独立学习服务的 revision 5 隔离和运行边界，不替代真实 Open WebUI 浏览器/Tools 注册、原生回调、真实 provider、外部数据库/对象存储故障演练或正式上线验收。

## 最终一致性复验

同日再次使用全新临时 project `dd-learning-finalcheck2`、端口 `32190`、临时密钥和独立卷执行 `config --quiet`、镜像构建、API/worker 启动及宿主 HTTP 探针：`GET /health` 返回 HTTP 200、`schema_revision=5`；生产模式 `POST /internal/bootstrap` 返回 404；无受信上下文的 `GET /api/v1/learners` 返回 401。随后执行 `down --volumes --remove-orphans`，容器、卷和网络均清理完成。

## 当前工作树复验

随后使用全新临时 project `dd-learning-livecheck-20261103b`、端口 `32192`、临时密钥和独立卷再次启动已有镜像（Compose 配置、API/worker 健康依赖和宿主 HTTP 探针均通过）：

```text
GET /health                              HTTP 200, schema_revision=5
POST /internal/bootstrap (生产模式)      HTTP 404
GET /api/v1/learners (无受信上下文)       HTTP 401
```

探针结束后执行 `down --volumes --remove-orphans`；该 project 的容器、卷和网络均已清理。此次请求使用了与路由一致的 `POST` 方法，现有 Open WebUI 容器和数据目录未触碰。
