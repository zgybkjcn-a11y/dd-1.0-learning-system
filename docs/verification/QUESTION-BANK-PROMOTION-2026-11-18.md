# 候选题库进入正式题库并发布（2026-11-18）

## 结论

按用户决定跳过教师签署、由助手完成课标交叉核对后，9 个候选批次共 81 题已进入正式题库并安装到本机生产：正式库由 1145 题增至 1226 题，`family-g2` 可选题由 418 项增至 436 项。停写备份、逐表行哈希比对、切换后健康与路由冒烟全部通过。教师签署仍为 `false`，真实难度未校准，覆盖计划未升版。

## 核对与登记

- 交叉核对：[CURRICULUM-CROSSCHECK-2026-11-18](CURRICULUM-CROSSCHECK-2026-11-18.md)，81 接受 / 0 拒绝，76 直接族 / 5 辅助族，59 题带人工跟进；依据是本地 subject-v16、math-v15 与下册初步清单的要求表述，**不是国家课标原文**。
- 登记：`learning_service/chapter_practice.py` 的 `BATCHES` 新增 9 批与 sha256，`chapter.bank()` 1074→1155 题、98→142 个范围；安装入口 `scripts/install_registered_batches.py` 逐批调用 `chapter.install`，只新增缺失题版。

## 生产发布

| 项目 | 结果 |
| --- | --- |
| 旧版本 | 镜像 `sha256:9962c9a7…`，Compose `family-question-choices-bulk-20261117/compose.json` |
| 新版本 | 镜像 `dd-learning:question-bank-20261118` = `sha256:d6e9883f…`；Compose `family-question-bank-20261118/compose.json`（`f6411496…`），仅换 api/worker/gateway |
| 停写与备份 | api/worker/gateway 停止后备份至 `learning_data/verification/question-bank-promotion-20261118/private/snapshot`；回执 passed、校验 passed（`c7329aa0…`），schema14 / integrity ok / 外键 0 |
| 安装预演 | `--dry-run` 读盘校验 9 批共 81 题 |
| 安装结果 | 9 批各新增 20/7/9/9/9/9/7/7/4 题，合计新增 81；回执 `install-receipt.json` |
| 重复安装 | 同一入口再跑一次，9 批新增均为 0；题版仍 1226、审计事件仍 28 |
| 切换 | `docker compose -p dd-family-math -f …/compose.json up -d`；proxy 与 open-webui 未重启 |
| 切换后 | `/health` `{"status": true}`、`/learning/ui` 303、api healthy、worker/gateway running |
| 数据保全 | live 与备份逐表按行哈希：50 表、45 表完全一致；仅 `questions`/`question_versions` 各 +81、`knowledge_points`/`review_objectives` 各 +44、`audit_events` +9；备份每一行都仍在 live 中 |
| 题库 | `question_versions` 1226、`questions` 1226、`attempts` 99、`learners` 2、schema14、integrity ok、外键 0 |
| 线上接口 | 容器内 OpenAPI 仍 77 路径；未认证 `question-choices` 401 `WEBUI_LOGIN_REQUIRED`；`family-g2` 200、436 项 |
| 统一入口 | 网关未认证 `study-path` 返回 401 `WEBUI_LOGIN_REQUIRED`（转发生效，旧版本为 404 `ROUTE_REJECTED`）；`family-g2` `study-path` 200，步骤 `resume`+`practice`，15 分钟 |

证据：`learning_data/verification/question-bank-promotion-20261118/`（`pre-state.txt`、`post-state.txt`、`install-receipt.json`、`smoke.json`、`deployment.json`、`data-preservation.json`，备份在 `private/`）。

## 与主站 P1 的关系

同一镜像包含 `GET /api/v1/study-path` 的网关白名单修复，因此家庭页自己的“今天从这里开始”经网关不再 404。主站静态资源（`study.js`/`study.css` 的第四档与统一入口）只做了本地实现与合成浏览器验收，**未发布到生产**；生产主站页面内容仍是 11-17 版本。

## 语义与边界

- 安装题库不等于改写覆盖计划：subject-v16 / math-v15 未升版，configured/partial/gap 不因本次安装变化；已登记候选行的 `candidate_only` 标记保持。
- 3 道既有 `math-g7` 动作候选仍只登记未安装，与本次无关。
- 未迁移数据库、未调用外部模型/OCR/embedding、C01 未启动、真实手机验收继续暂缓。
- 教师签署为 `false`；助手结构核对与答案复算不替代真人教学审核，也不能写成“课标已全部对齐”。

## 回退

`docker compose -p dd-family-math -f learning_data/deployments/family-question-choices-bulk-20261117/compose.json up -d learning-api learning-worker learning-gateway`，保留当前数据卷；旧镜像仍在。代码回退不会删除已安装题版，也不会改动作答记录。
