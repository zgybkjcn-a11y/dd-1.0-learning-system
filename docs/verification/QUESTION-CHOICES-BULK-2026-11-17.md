# 2026-11-17 候选题端点题库单次装载 · 本地实现、发布与验收

把 `GET /api/v1/question-choices` 从"每个候选题版各查一次"改为"每次请求每套题库装载一次"。按用户授权只在本地实现与回归后，同日发布到本机生产：停写备份、切换镜像、逐表比对通过。未迁移数据库、未注册候选批次、未调用外部模型/OCR/embedding，C01 未启动、未重启 proxy 与 open-webui，真实手机验收继续暂缓。

## 根因

`question-choices` 对每个候选题版逐个调用元数据、放置查询、章节/备用题校验，随后 `learner_guidance` 按每条已评分作答再查一次题，两份覆盖报告又各自装载全套题库。`chapter_practice.bank()` 与 `reserve_practice.bank()` 刻意不缓存（每次读盘并校验 sha256），于是家庭库（1145 题、99 次作答）单请求把整套章节题库重复读取数百次：`family-g2` 418 题热请求 5.23 秒。

## 实现

| 文件 | 改动 |
| --- | --- |
| `learning_service/practice.py` | 新增 `banks()`（整库一次装载）与 `questions()`（按前缀惰性批量装载）；`metadata_for()` 复用已装载条目；`learner_guidance(conn, learner_id, questions=None)` 可共用装载 |
| `learning_service/app.py` | 每请求装载一次，候选元数据、放置、校验、难度指导与两份覆盖报告共用；可选题库未安装（如备用题）时回退按需装载，被篡改仍 503 |
| `learning_service/textbooks.py` | `practice_scopes_from()` 承接已装载字典，`practice_scopes()` 委托它 |
| `learning_service/practice_coverage.py`、`subject_coverage.py` | `report(..., questions=None)` 接受共享装载；学科覆盖分节清单仍只统计章节练习题库（行为不变） |
| `learning_service/chapter_practice.py`、`reserve_practice.py` | 校验函数接受可选已装载字典 |
| `scripts/upgrade_readonly_study_tool.py` | `BACKEND` 重钉 `app.py`→`2b3b9288…`、`textbooks.py`→`6bc9c9af…`；Tool 源码与 C01 冻结场景不变 |

新增回归：批量查询与逐题查询逐项相等；`question-choices` 单请求内章节题库恰好装载 1 次，且禁止逐题 `practice.question()`（测试先真实作答一道章节题并评分，覆盖难度指导路径）。

## 验证与生产发布（2026-11-17）

| 项目 | 结果 |
| --- | --- |
| 本地单元/契约回归 | 全量单元 1201 通过；只读工具模块重钉后 53/53 通过；C01 夹具、工具与证据模块 37 通过 |
| 本地浏览器回归 | `tests/test_chapter_practice_browser.py` 两视口 2 通过（213 秒） |
| CI | run 44100899667（commit `af359ae`）单元 1177 通过、浏览器 53 通过 |
| 镜像 | `dd-learning:question-choices-bulk-20261117` = `sha256:9962c9a7…` |
| 隔离冒烟 | 生产数据副本在 `127.0.0.1:31998`：`/health` ok、schema14、integrity ok、1145 题、99 次作答、77 路径；`family-g2` 418 项、覆盖 19 项、分节 30，首请求 0.225 秒、热 0.145 秒 |
| 停写与备份 | api/worker/gateway 停止后备份至 `learning_data/verification/question-choices-bulk-20261117/private/snapshot`，回执 passed、校验 passed（`d59f4b5d…`），schema14 / integrity ok / 外键 0 |
| Compose | `learning_data/deployments/family-question-choices-bulk-20261117/compose.json`（`3902aeed…`），仅换 api/worker/gateway |
| 切换后验收 | `/health` `{"status": true}`、`/learning/ui` 303、api healthy、worker/gateway running；proxy 与 open-webui 未重启 |
| 数据保全 | live 库与备份逐表行哈希：50 表、0 不一致；1145 题、99 次作答、2 名学习者、schema14 不变 |
| 线上接口 | 容器内 77 路径含 `/api/v1/question-choices`；未认证 401 `UNTRUSTED_CONTEXT`；`family-g2` 418 项，首请求 1.224 秒、热中位 0.138 秒（旧版本热 5.23 秒） |
| 回退 | `family-study-path-fix-20261116/compose.json` + 旧镜像 `sha256:539a0dc2…`，保留数据卷 |

证据：`learning_data/verification/question-choices-bulk-20261117/`（`pre-state.txt`、`backup-receipt.json`、`backup-verify.json`、`backup-verify-receipt.json`、`data-preservation.json`、`smoke.json`、`deployment.json`）。

## 边界

不导入候选、不迁移数据库、不改路由与 schema；真实模型/OCR/embedding 调用 0 次；C01 未启动或调用；真实手机验收仍由用户暂缓；教师签署与掌握度声明仍为空。
