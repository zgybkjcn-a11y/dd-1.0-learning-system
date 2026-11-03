# Compose 隔离与重启验收

日期：2026-11-02（Asia/Shanghai，历史 revision 3 快照）

本记录使用纯合成账号、学习者和 PNG，不包含真实学生资料。Compose 使用独立 project `dd-learning-verification` 与独立卷 `dd-learning-verification_dd_learning_data`，未挂载现有 Open WebUI `data/`。

revision 4 的独立 Compose `/health` 探针（临时 project/卷/端口）是历史快照；本文件的宿主 HTTP/重启闭环保持为历史记录。当前 revision 5 隔离探针见 `docs/verification/compose-isolation-2026-11-03-revision5.md`。

当前 Compose 明确向 API 和 worker 传入 `LEARNING_EXPORT_DIR`、`LEARNING_DOCUMENT_PROVIDER`、`LEARNING_DIAGNOSIS_PROVIDER` 和 `LEARNING_VARIANT_PROVIDER`；provider 默认值为确定性 mock，不能被描述为真实 OCR/模型接入。

## 生产模式身份与健康探针

启动命令：

```bash
LEARNING_ADMIN_SECRET=dev LEARNING_ADAPTER_SECRET=adapter \
  docker compose -f docker-compose.learning.yml up -d
```

容器环境设置 `LEARNING_DEV_MODE=0`。在容器内一次性写入合成 `acct-compose`、`learner-compose`、`local/verification/compose-user` 身份绑定和学习者授权；生产模式的 `/internal/bootstrap` 不作为初始化入口。

结果：

- 隔离服务本地 health endpoint 返回 HTTP 200，`schema_revision: 3`，`version: 0.1.0`；宿主端口已从公开记录中省略。
- `GET /ui` 返回 HTTP 200，响应 12207 bytes，包含整卷上传、创建批次和候选复核入口。
- 带 `X-Admin-Secret: dev` 调用生产模式 `/internal/bootstrap` 返回 HTTP 404 `NOT_FOUND`。
- 受信请求头 `X-Adapter-Secret: adapter`、`X-Trusted-Provider: local`、`X-Trusted-Issuer: verification`、`X-Trusted-Subject: compose-user`、`X-Learner-Id: learner-compose` 可列出合成学习者。

## 宿主 HTTP 闭环

通过受信身份头从宿主执行：

1. 上传 8x6 合成 PNG，返回 `document_id`、`page_count: 1`、`failure_code: null`。
2. 创建整卷批次，返回 `status: draft`、`total_pages: 1`。
3. 请求分析，返回 `status: queued` 和持久化 `job_id`。
4. worker 领取任务后，批次变为 `awaiting_review`，`processed_pages: 1`、`failed_pages: 0`。
5. 候选读取成功：1 项，`verdict: undetermined`、`verification_status: needs_review`、页状态 `processed`。

该结果证明隔离 Compose 的真实宿主 HTTP、共享卷和 worker 协作路径；合成 PNG 不代表 OCR、学科判定或真实卷面质量。

## 可信复核与错题入库

在重启恢复后的同一批次上，使用合成教师证据通过宿主 API 完成：

1. `PATCH /api/v1/import-items/{item_id}`：revision 1 → 2，判定为 `incorrect`，证据来源为 `synthetic-teacher-review`，绑定 `objective-compose`。
2. 创建 `confirm_import` 挑战并提交一次性 nonce 和 revision 2。
3. 带 `Idempotency-Key: compose-confirm-1` 批量确认，返回 `status: completed`、`confirmed_count: 1`、`failed: []`。
4. 批次变为 `completed`；`GET /api/v1/mistakes` 返回 1 个 `active` 错题，目标为 `subtract-negative`。

这是可信复核、挑战消费和正式错题来源的合成验收，不是模型或教师对真实题目的学科裁决。

## 重启恢复

执行：

```bash
LEARNING_ADMIN_SECRET=dev LEARNING_ADAPTER_SECRET=adapter \
  docker compose -f docker-compose.learning.yml down
LEARNING_ADMIN_SECRET=dev LEARNING_ADAPTER_SECRET=adapter \
  docker compose -f docker-compose.learning.yml up -d
```

未使用 `-v`。重启后 API/worker 均恢复，`/health` 仍为 schema revision 3，受信身份仍可列出 `learner-compose`。容器内 SQLite 计数和最近业务状态为：

```text
accounts 1
identity_bindings 1
learners 1
source_documents 1
import_batches 1
import_items 1
jobs 1
batch ('batch_...', 'awaiting_review', 1, 0)
item ('undetermined', 'needs_review', 'needs_review')
```

随后完成上述合成复核后，独立卷中的最终业务状态为 `batch.status=completed`、`import_item.status=confirmed`、`mistake_entries=1`；再次读取这些资源无需 bootstrap。重启过程未删除独立卷，也未停止或修改现有 `open-webui` 容器。该证据覆盖本地隔离环境的启动、宿主 HTTP 闭环、可信确认和业务状态恢复，不覆盖真实 Open WebUI 浏览器、Tools 注册或真实提供商调用。

验收结束后执行 `docker compose ... down`（未使用 `-v`）；学习服务容器已停止，独立卷仍保留，现有 `open-webui` 容器保持 healthy。

## 当前重建复验

使用上述独立 project 完成了当前代码的实际重建、生产模式探针、宿主 HTTP 闭环和不删卷重启：

- 镜像重新构建成功；API/worker 均使用独立卷并未挂载现有 WebUI 数据目录。
- `/health` 返回 `schema_revision=3`；生产模式 `/internal/bootstrap` 返回 404；`/ui` 返回 200，并包含整卷上传、批次创建和候选确认控件。
- 受信合成身份成功列出学习者；宿主 multipart PNG 上传、批次创建、分析排队和 worker 处理后得到 `needs_review` 候选，证据明确 `ocr_performed=false`。
- `docker compose restart` 后同一批次和候选仍可读取，schema revision 保持 3；随后执行 `down --remove-orphans`，未触碰现有 `open-webui` 容器（探针结束时其状态为 running/healthy）。

本次闭环仍是合成资料和确定性 mock provider，不能替代真实 Open WebUI 浏览器/Tools、真实 OCR/模型或学科人工验收。

## 2026-11-02 最终重建复验

使用独立 Compose project `dd-learning-verification-final`、宿主端口 `32110` 和独立卷 `dd-learning-verification-final_dd_learning_data` 再次从当前源码构建并启动。现有 `open-webui` 容器未停止、未挂载、未写入。

- 镜像重建成功；`GET /health` 返回 HTTP 200，`schema_revision=3`、`version=0.1.0`。
- 生产模式 `POST /internal/bootstrap` 返回 HTTP 404；`/ui` 返回 HTTP 200，响应 11609 bytes，包含整卷上传和候选复核入口。
- 通过容器内一次性写入的合成身份和宿主受信请求完成 PNG 上传、批次创建、分析排队和 worker 处理；批次为 `awaiting_review`，1 页 `processed`，候选为 `undetermined/needs_review`，证据 `ocr_performed=false`。
- `docker compose restart` 后同一批次、页面和候选仍可读取，健康检查仍为 schema revision 3；随后执行 `down --remove-orphans`，未使用 `-v`，独立卷保留。

该复验仍只证明隔离部署和确定性状态机可恢复，不证明真实 OCR、学科判定、Open WebUI 浏览器/Tools 或真实资料验收。

## 独立 Compose 浏览器 UI 闭环

使用独立 Compose project `dd-learning-browser-20261102`、宿主端口 `32120`、独立卷 `dd-learning-browser-20261102_dd_learning_data` 和合成身份 `acct-browser` / `learner-browser`，通过 Playwright 在 Chromium 中访问当前服务 `/ui`。测试注入合成 PNG 字节，避免宿主路径注入在 Snap Chromium 下产生空文件；未设置代理环境变量。

- 页面加载、账号/学习者上下文和上传控件可用；整卷上传后创建批次并触发分析。
- worker 完成后浏览器读取候选；候选复核控件可选择判定、填写目标 ID/证据，并以当前 revision 调用 `PATCH /api/v1/import-items/{item_id}`。
- 浏览器保存 `incorrect` 复核、目标 `obj-browser` 和合成证据，随后获取一次性可信确认挑战并完成批量确认。
- 错题本读取到 1 个 `active` 条目；移动视口 390px 探针无横向溢出，上传和确认控件仍存在。
- 脱敏证据：[browser-ui-2026-11-02.json](browser-ui-2026-11-02.json)；截图：[browser-ui-2026-11-02.png](browser-ui-2026-11-02.png)。

该闭环验证的是独立服务自己的本地受信工作台和服务端权限/状态机，不是正式 Open WebUI 前端、真实 Tools 注册/回调、真实 OCR/模型或真实学生资料验收。验证后保留独立卷作为证据，并按交接步骤停止容器；未使用 `-v`。

清理探针：`docker compose -p dd-learning-browser-20261102 ... down --remove-orphans` 已完成；`dd-learning-browser-20261102_dd_learning_data` 仍存在，浏览器 Compose 容器和网络已移除。既有 Open WebUI 容器未受影响；本机端口和可达地址已从公开报告中省略。
