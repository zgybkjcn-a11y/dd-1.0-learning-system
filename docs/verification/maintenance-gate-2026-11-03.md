# Stage 5 maintenance gate 增量验收

日期：2026-11-03（Asia/Shanghai）

本轮验证维护准入、变式字段迁移和独立部署探针。测试只使用合成账号、合成题目和确定性服务，不代表真实学科判定、真实学习者效果或正式上线。

## 代码与数据约束

- migration 004 为 `question_versions.variant_kind`（默认 `base`）、`variant_group` 和变式索引；migration 005 新增学习者隔离的复核申请表；旧版直接写入题库的代码保持兼容。
- stage 5 卡只有在到期、至少 3 个不同自然日的无提示独立正确、至少 2 个已审核变式、最近学习/提示/练习/教学素材暴露距当前至少 30 个自然日，且当前作答为 `independent` 时才进入 `maintenance`。
- 当前作答不计入暴露间隔；历史 practice session 不计入独立掌握证据；practice 作答不调度复习卡，并返回 `eligible=false` 的门槛证据。
- 维护门槛结果写入 `learning_events.metadata_json` 及 worker 返回值，包含自然日、变式和最近暴露日证据。
- 维护卡继续保持 stage 5、30 天间隔；不满足门槛的卡保持 `review`/stage 5，并在 30 天后复查。

## 自动化结果

- 报告生成时 `pytest -q` 为 `62 passed`；之后全量回归曾为 `76/77/78 passed`，当前为 `91 passed`，无失败；Tools/Agent 安全回归也在全量运行中执行。
- `pytest -q tests/test_learning_service.py`：服务测试通过（当前全量回归中的服务测试子集）。
- `python3 -m compileall -q learning_service tests`：通过。
- 覆盖完整准入、最近暴露不足 30 天、practice 当前作答排除、当前作答不作为暴露，以及 migration 004 两个字段存在性。

## 隔离构建与运行探针

- `LEARNING_ADMIN_SECRET=... LEARNING_ADAPTER_SECRET=... docker compose -f docker-compose.learning.yml config --quiet`：通过；未提供密钥时配置按设计拒绝启动。
- `docker build --file Dockerfile.learning --tag dd-learning:verification .`：通过。
- 独立 Compose project `dd-learning-rev5-check` 使用临时密钥、独立端口和独立卷启动 API/worker；`GET /health` 返回 HTTP 200、`schema_revision: 5`，生产模式 bootstrap 返回 404，未受信业务请求返回 401，随后执行 `down --volumes --remove-orphans` 清理测试资源。该结果是历史 revision 5 快照；revision 6/7 后续证据见 `compose-isolation-2026-11-03-revision6.md` 和 `compose-isolation-2026-11-03-revision7.md`。

## 未覆盖边界

真实 Open WebUI Tools/UI、真实 OCR/model/provider、脱敏整卷人工标注、对象存储/数据库服务故障和 T23 真实 7–14 天试用仍需外部条件。该证据不解除 T03/T04/T05/T20 的外部阻塞，也不改变 T23 `blocked` 状态；T21 的外部数据库/对象存储/真实 provider 故障仍未覆盖，Goal 保持 `active`。

## 后续增量状态（2026-11-03）

本报告上文记录的是 revision 5 阶段快照。当前 schema revision 7，最新完整回归 `pytest -q` 为 91 passed（含 6 项隔离 Compose preflight）；revision 6/7 Compose 隔离证据见 `compose-isolation-2026-11-03-revision6.md` 和 `compose-isolation-2026-11-03-revision7.md`。异步可信 UI callback 超时 fail-closed 回归见 `trusted-ui-timeout-2026-11-03.md`。隔离 Open WebUI 0.12.5 已实际注册 dd_learning_v1 并通过原生 loader 和合成回调探针，见 `open-webui-tools-registration-2026-11-03.md`。真实浏览器组合、最终可信 UI 回调、真实 provider、人工标注和 T23 仍未完成，Goal 保持 blocked。
