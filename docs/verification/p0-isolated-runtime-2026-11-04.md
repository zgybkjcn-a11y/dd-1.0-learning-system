# DD-1.0 P0 隔离运行准备与空标注规范执行报告

日期：2026-11-04（Asia/Shanghai）。结论：**P0 本地技术准备已验证，P2 空模板已准备；真实模型、最终浏览器可信回调、provider、资料质量及试用仍未验收。** 对应脱敏机器记录见 [`p0-isolated-runtime-2026-11-04.json`](p0-isolated-runtime-2026-11-04.json)。

## 旧实例核对

旧 `dd-learning-isolated-api-20261103d` / `dd-openwebui-isolated-20261103d` 保持停止，退出码 255。只查看有限脱敏日志模式计数，没有足以确认停止原因的证据；仍记为原因未知，不由退出码推断宿主重启、OOM 或业务故障。

在停止状态下将两个 SQLite 主文件和存在的 WAL/SHM 复制到 `/tmp/dd-p0-20261104/runtime/inspection-copies/`，目录 0700、文件 0600。随后仅在副本中以只读连接查询 schema revision 和 Tool 源码 hash，没有读取身份/密钥字段，也没有写回旧数据库。副本的文件 hash 已记录；这些是 SQLite 检查副本，**不是完整数据库/附件恢复集合或恢复演练**。

- 旧学习服务 schema 实测为 **6**。
- 旧 Tool SHA-256 为 `684052e88c40a5b9a524a67e3148f9a2adc39894d3df90fc82f270246ec16d0d`。
- 当前 Tool SHA-256 为 `2fe165d153f675cc9acd7a1f577e6b018b738780ffdc4829d92cdf855e38433b`；旧注册不能直接算作当前源码就绪。

原实例、原卷和原 Tool 均未启动、迁移、修改或删除。此前报告中的 revision 6/历史 health 不代表本轮当前源码；本轮新环境的 revision 7 以以下实测为准。

## 新候选环境与构建范围

新建 project 为 `dd-learning-p0-20261104`，包含 `learning-api`、`learning-worker`、`open-webui`。使用两个全新命名卷及独立 internal 网络，没有宿主端口发布、正式 `data/` 挂载或原隔离卷复用。报告完成时新环境保持运行，原隔离实例仍停止。

构建上下文仅复制 17 个白名单文件：`Dockerfile.learning`、锁定依赖和 `learning_service` 的 Python/SQL 文件；没有把仓库根作为 Docker 构建上下文，没有读取根目录 `docker-compose.yml`、`batch_ingest.py`、`.env` 或正式数据。

原始 Dockerfile 的离线构建返回失败，未启动服务。最终使用本机缓存学习服务镜像 `sha256:14ea733a5100079b01bfe5be218fb8a55732451858dc656b9d6cb3b3b7b5ef49` 为固定基底，在 `--network none` 的构建中仅复制当前源码；先在 `--network none` 的临时容器中核对六个依赖与 `requirements-learning.txt` 完全一致。没有下载或安装依赖。本次可复现范围依赖这一已缓存且版本匹配的基底，不宣称原始 Dockerfile 的无缓存全新构建通过。

Open WebUI 直接使用本机缓存固定镜像 ID `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd`，不拉取 `:main`。运行时版本由内部 `/api/version` 实测为 0.12.5。

临时 Compose 与凭据保存在 0700 的运行目录，`compose.private.json` 为 0600，不纳入仓库/报告；Compose hash 固定，漂移会拒绝执行。默认 mock 保持原样，staging 腾讯外发开关为 0、凭据为空。Open WebUI 使用 offline 模式，OpenAI/Ollama 连接和持久化配置读取关闭，可用模型实测为 0。没有执行模型/OCR 请求或最终输入/确认回调。

## 已执行检查

| 检查 | 实测结果与边界 |
| --- | --- |
| Learning API `/health` | HTTP 200，version 0.1.0，schema revision **7** |
| Open WebUI `/health` / `/api/version` | HTTP 200，实际版本 0.12.5 |
| 生产模式 `POST /internal/bootstrap` | HTTP 404 |
| 无受信上下文 `GET /api/v1/learners` | HTTP 401 |
| 合成账号/学习者授权读取 | HTTP 200，仅返回 1 个授权合成学习者 |
| 同账号跨学习者读取 | HTTP 404，`LEARNER_NOT_FOUND` |
| 实际容器挂载/网络/端口 | 每个容器仅使用本 project 命名卷、仅加入本 project internal 网络，无宿主端口发布 |
| 当前源码与运行镜像 | `learning_service` 的所有 Python/SQL 文件 hash 与候选快照完全一致 |
| OpenAPI | 完整内容与仓库快照一致，56 paths / 20 schemas |
| 依赖版本 | fastapi 0.136.1、uvicorn 0.44.0、pydantic 2.12.5、python-multipart 0.0.26、Pillow 12.1.1、PyMuPDF 1.27.2.2 |
| 当前 Tool 同步 | 仅在新隔离实例、合成管理员账号中通过原生 Tools API 写入当前源码和临时 Valves/UserValves |
| 原生 `get_tools` loader | 11 个公开方法；模型 schema 排除保留参数；宿主身份与 UserValves 映射到授权合成学习者 |
| 新环境停止/恢复 | 执行 stop → resume，卷保留；恢复后 API/完整契约检查通过，未重新注册的 Tool 原生 loader/身份/学习者读取通过 |
| 空标注模板 | 五份 CSV 均为 0 条记录；JSON 样本数组为空、结果为 null、人工签核/阈值未填写 |

新脚本编译检查和现有 Compose 静态 preflight 通过。本轮不重跑四格式导入持久化或全量 pytest，最近 **101 passed** 仍是此前合成/mock 回归基线。停止/恢复检查仅覆盖本轮新环境的配置、合成身份和 Tool，不替代已有完整备份恢复或外部系统故障矩阵。

最终文档一致性与 `git diff --check` 通过：`tasks=26, evidence paths=149, backlog task rows=26, QA matrix rows=17, manifest path references=22, release authorization boundaries intact`。实测 start 拒绝覆盖已有 project 资源。进度文档之外的 38 个既有改动文件 SHA-256 与本轮开始时一致，源码、测试、配置保持原样；所有 26 项任务状态和原 unmet 字段未改变。Goal API 最后读取仍为 `goal: null`。

## 续跑入口

运行配置：`/tmp/dd-p0-20261104/runtime/`；不要打印其中的 `compose.private.json` 或复制其凭据到公开文件。此目录可能随 `/tmp` 清理消失，不能当作长期凭据备份。

当前环境的操作命令：

```bash
python3 scripts/prepare_isolated_runtime.py verify --run-dir /tmp/dd-p0-20261104/runtime
python3 scripts/prepare_isolated_runtime.py check-tools --run-dir /tmp/dd-p0-20261104/runtime
python3 scripts/prepare_isolated_runtime.py stop --run-dir /tmp/dd-p0-20261104/runtime
python3 scripts/prepare_isolated_runtime.py resume --run-dir /tmp/dd-p0-20261104/runtime
```

创建另一个 disposable 环境时使用新的 `--run-dir` 和 `dd-learning-p0-` project 名，依次执行 `prepare`、`start`、`verify`、`tools`。prepare 会拒绝非空运行目录，start 会拒绝已有 project 资源；不覆盖或清理原环境。该准备流程依赖旧隔离实例仍存在且停止，以及已缓存的匹配镜像。

空标注规范与模板见 [`docs/quality/README.md`](../quality/README.md)。实际资料应复制到独立受控目录，示例 `learning_data/quality/...` 已经 `git check-ignore` 核对为忽略路径；此目录只有空规范，不包含真实学生资料。

## 未满足门槛

P1 仍需可调用测试模型、明确调用范围、可信浏览器入口与最终原生回调验证。新环境当前没有宿主浏览器入口；未来按获准范围准备受控 loopback/代理，不开放可伪造身份的公共入口。

P2/T04 仍缺获准脱敏整卷、逐题人工参考、题型覆盖及审核人；P3/T05 仍缺真实调用许可、运行时凭据、预算和 endpoint/出网范围；外部数据库/对象存储/provider 故障及 T23 真实条件继续按 BLOCKERS 保留。本会话禁止真实 API、资料外发和生产部署的限制未改变。

本轮证据是实际隔离组件、合成身份和 mock 配置的技术准备，不是模型发起的 tool call、真实浏览器可信回调、真实 OCR/学科质量或正式验收。Goal API 仍与仓库 blocked 状态分开记录，不创建或完成 Goal。
