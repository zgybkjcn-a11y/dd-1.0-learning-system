# Revision 4 Compose 隔离与浏览器验收

日期：2026-11-03（Asia/Shanghai）

本轮使用独立 Compose project、网络、卷和端口完成复验：

- 浏览器工作台：project `dd-learning-rev4-fixed`，端口 `32160`，独立卷 `dd-learning-rev4-fixed_dd_learning_data`。
- 生产模式探针：project `dd-learning-rev4-production-check`，端口 `32162`，独立卷 `dd-learning-rev4-production-check_dd_learning_data`。
- 两个 project 均未挂载现有 Open WebUI `data/`，未停止或修改现有 `open-webui` 容器。
- provider 使用确定性 `mock-*`，资料为合成 PNG；不代表真实 OCR、模型调用、学科判定或真实学习效果。

## 生产模式探针

使用临时环境变量 `LEARNING_ADMIN_SECRET=prod-check-admin`、`LEARNING_ADAPTER_SECRET=prod-check-adapter` 启动后：

- 隔离服务本地 health endpoint 返回 HTTP 200，`schema_revision=4`，`version=0.1.0`；宿主临时端口已从公开记录中省略。
- 带 `X-Admin-Secret` 调用生产模式 `POST /internal/bootstrap` 返回 HTTP 404 `NOT_FOUND`。
- API 和 worker 均健康运行，数据写入独立卷。

## Chrome `/ui` 合成闭环

使用 `/usr/bin/google-chrome` headless、独立 dev-mode workbench 和合成身份完成：

1. 账号/学习者上下文建立。
2. PNG 上传、整卷批次创建和 worker 分析。
3. 候选读取，判定改为 `incorrect`，填写复核证据并保存 revision `1 -> 2`。
4. 获取并消费可信确认挑战，批量确认返回 `status=completed`。
5. 错题本读取到 `active` 条目。

脱敏结果和截图：

- [browser-ui-2026-11-03.json](browser-ui-2026-11-03.json)
- [browser-ui-2026-11-03.png](browser-ui-2026-11-03.png)

桌面 `1280x900` 和移动 `390x844` 的 `documentElement.scrollWidth` 均等于 viewport 宽度，`horizontal_overflow=false`。此前移动溢出的根因是动态状态 JSON 未断词；修复为 `.status { overflow-wrap: anywhere; word-break: break-word; }` 后重新构建镜像并复验。

该证据只覆盖独立服务 `/ui` 本地受信工作台，不提升为真实 Open WebUI UI/Tools 注册、真实回调或真实 provider 验收。

## 清理

复验完成后应执行：

```bash
LEARNING_ADMIN_SECRET=dev-admin LEARNING_ADAPTER_SECRET=dev-adapter \
  docker compose -p dd-learning-rev4-fixed -f docker-compose.learning.yml \
  -f /tmp/dd-rev4-browser-compose.yml down --remove-orphans
LEARNING_ADMIN_SECRET=prod-check-admin LEARNING_ADAPTER_SECRET=prod-check-adapter \
  docker compose -p dd-learning-rev4-production-check -f docker-compose.learning.yml \
  -f /tmp/dd-rev4-prod-compose.yml down --remove-orphans
```

清理不会删除独立卷，且不触碰现有 `open-webui` 容器。
