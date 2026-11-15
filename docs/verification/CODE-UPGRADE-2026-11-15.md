# 2026-11-15 家庭学习服务代码升级 · 生产部署验收

按用户授权，将 2026-11-14 会话完成并推送到 `ea95d1b` 的服务代码部署到本机生产环境。**未注册或安装任何下册候选批次，未导入题目，未迁移数据库**；正式题仍 1145 题，schema 仍 14。

## 范围

| 项目 | 说明 |
| --- | --- |
| 变更 | `learning_service` 当前源码：study deadline/cancellation、material caches、identity_admin、practice response/design、subject coverage v16、math coverage v15 |
| 服务 | `learning-api`、`learning-worker`、`learning-gateway` 三个家庭服务镜像 |
| 不变 | proxy、`open-webui`、C01 四容器；数据卷；`BATCHES`；题库与使用记录 |
| 可见变化 | 学科覆盖清单由 subject-v5 切到 v16、数学覆盖由 v13 切到 v15；行数仍 276 / 53，部分状态与理由按 11-12/11-13 复核更新 |

## 镜像与隔离验证

- 构建：`docker build -f Dockerfile.learning -t dd-learning:reuse-upgrade-20261115 .`，镜像 `sha256:6f6ad8a1…`。
- 冒烟：用生产数据副本在 `127.0.0.1:31999` 启动新镜像，`/health` 返回 `ok`、schema 14、1145 题、`PRAGMA integrity_check=ok`；未触碰运行中服务。

## 切换步骤

1. 记录切换前状态：三容器镜像 `sha256:6014a237…`、1145 题、99 次作答、schema 14。
2. `docker compose -p dd-family-math -f learning_data/deployments/family-textbook-completion-20261112/compose.json stop learning-api learning-worker learning-gateway`。
3. 停写后一致性备份到 `learning_data/verification/code-upgrade-20261115/private/snapshot`，回执 `status=passed`，校验 `schema_revision=14, integrity=ok, foreign_key_errors=0`。
4. 生成新 Compose `learning_data/deployments/family-code-upgrade-20261115/compose.json`（仅替换三服务镜像，绝对路径、密钥与网络保持）。
5. `docker compose -p dd-family-math -f …/family-code-upgrade-20261115/compose.json up -d learning-api learning-worker learning-gateway`。

## 验收结果

- `https://172.19.116.53/health` 返回 `{"status": true}`；`/learning/ui` 返回 303（按预期跳转登录）。
- API 容器 healthy；worker、gateway running；proxy 与 `open-webui` running/healthy，启动时间未变。
- 数据库：1145 题、99 次作答、2 名学习者、schema 14、`integrity_check=ok`。
- **数据保全**：live 库与备份快照逐表按行哈希比较，50 张表、0 张不一致。
- 未调用外部模型/OCR/embedding；C01 未启动；真实手机验收仍暂缓。

## 回退

```bash
docker compose -p dd-family-math \
  -f learning_data/deployments/family-textbook-completion-20261112/compose.json \
  up -d learning-api learning-worker learning-gateway
```

旧镜像 `sha256:6014a237…` 仍在本机；保留当前数据卷与切换后新增写入，禁止用备份覆盖新数据。

## 边界

- 下册第五至八批仍是本地候选：`BATCHES` 未改、未安装，学生看到的题目数量不变。
- 覆盖清单为编辑状态清单，`teacher_reviewed=false`、课标 crosscheck pending，不代表课标完整率或学生掌握率。
- 本次镜像由 git 提交 `ea95d1b` 的工作树构建，未另建 134 文件发布包；manifest 中的 `runtime_source_identity` 已注明。

证据：`learning_data/verification/code-upgrade-20261115/deployment.json`、`backup-receipt.json`、`backup-verify.json`。
