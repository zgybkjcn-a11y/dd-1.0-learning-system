# W07–W10 独立配置、构建与恢复

2026-11-04；沿用目标 `https://172.19.116.53`，原入口 `http://172.19.116.53:53001/` 保留。当前 schema11 / OpenAPI66/24 / Tools1.1.0；[机器计划](work-plan-2026-11-04.json)与[本轮报告](../verification/reuse-runtime-recovery-2026-11-04.md)记录实际完成程度。

## 独立配置与构建

[sidecar](../../deploy/open-webui-reuse/compose.learning-sidecar.yml)只引用原 `open-webui_default` 网络，不定义或重建原 WebUI。API/worker 共用完整认证、共享上下文、模型/OCR与费用配置；API/worker 仅连接专用 internal 网络，网关/代理另连接上游网络。API不发布宿主端口，代理的目标443属于未来正式接入。模板默认认证桥接关闭、provider mock、外发关闭、预算0。

[HTTPS代理](../../deploy/open-webui-reuse/nginx.learning.conf)支持动态Docker DNS、WebSocket和学习前缀。WebUI上游仅收到内置登录的token Cookie；学习上游由网关选择自己的Cookie。`__Host-` Cookie保留Secure、SameSite=Strict、Path=/、无Domain，代理不重写路径。网关一进程运行，nonce不跨进程共享，关闭访问URL日志。

[运行输入模板](../../deploy/open-webui-reuse/runtime.template.env)必须用显式 `--env-file`；不自动读取项目 `.env`。密钥由显式secret目录的文件提供：`learning_admin_secret`、`learning_adapter_secret`、`learning_browser_auth_secret`，另需 `tls_certificate.pem`、`tls_private_key.pem`。API/worker UID10001；代理UID101。Linux Compose文件secret保留来源文件权限，不能假定Compose的uid/mode设置会改变bind来源：正式文件须由对应UID可读，并由主机权限保护。合成文件位于0700隔离目录，仅为测试设0444；不能复制为正式权限策略。

`*_FILE`支持admin/adapter/browser声明/model key/腾讯OCR两个secret；设置非空明文值和文件值会拒绝，空/多行/超长/非UTF8/目录/末级符号链接会拒绝。异常不返回路径或内容。model/OCR秘密在本轮模板中留空，没有真实密钥。

[配置检查](../../scripts/check_reuse_compose.py)只读取显式sidecar并解析引用，不打开secret。它检验固定镜像、API/worker配置一致、网络/卷/宿主端口、开发开关、mock/外发/零预算与secret引用；隔离模式还拒绝外部网络/卷与所有宿主端口。

```bash
python3 scripts/check_reuse_compose.py
```

[构建脚本](../../scripts/build_learning_candidate.py)先验证新候选，不接受旧profile或已有tag/输出目录。构建输入只含候选白名单、逐文件匹配[完整依赖锁](../../deploy/open-webui-reuse/requirements.lock)的16个wheel，以及校验每个blob和固定基础digest的本地OCI导出。使用[独立Dockerfile](../../deploy/open-webui-reuse/Dockerfile)，`--no-cache --network=none`，pip `--no-index --require-hashes`；不从根目录构建，不读禁读文件或正式数据。

原29/35/38文件候选与hash保持；新50文件profile为`reuse-runtime-v1`，schema仍11。源码封包manifest保留`image_digest=null`，构建证据另记local image ID，不冒称已发布registry digest。初次BuildKit仓库解析尝试停止后，改用固定digest的本地OCI输入；失败候选/日志保留，不覆盖。

## 接入网络重建

[重连工具](../../scripts/reconnect_learning_network.py)默认只读plan，核对原WebUI的Compose标签/原网络、目标学习project与internal网络，计划绑定容器ID、网络ID、已有网络及操作人。已连接返回幂等结果；容器重建或网络/操作人变化使plan hash失效。`--apply-plan-sha256`只用于以后W13已审阅的正式接入，本轮没有运行apply，未连接原容器或修改默认路由。工具复核网络成员，不证明宿主防火墙或模型出网策略。

## 三通道与告警

| 通道 | 本轮控制/证据 | 正式缺项 |
| --- | --- | --- |
| WebUI聊天 | 新隔离WebUI关闭OpenAI/Ollama，全部网络internal；原WebUI配置未读取 | 正式聊天模型、资料范围、价格/预算/停用及账单来源；学习台账不覆盖聊天 |
| 学习诊断/变式 | mock、外发0、模型/key/端点空、费用配置传递一致，既有预留/限额/暂停 | 真实调用许可、价格/账单、网络与运行告警 |
| OCR | mock、外发0、秘密空；费用预留仍由学习台账管理 | 独立OCR许可/资料/价格/质量；当前学习与OCR共用全局学习预算，并非三套独立账单系统 |

[运维模块](../../learning_service/operations.py)从管理员聚合metrics只输出固定告警码：队列超时、过期lease、页失败、删除待处理、provider暂停、待账单、未知用量。未知字段、学习者、原答、provider正文不复制到告警；本轮没有外发告警。正式接收人/轮询/阈值/容量/网络监控仍待输入，300秒为本地队列阈值。恢复后暂停provider是预期维护状态，不能自动解除或清零未知费用。

## 学习数据恢复

备份使用SQLite backup与附件/导出复制。在线默认只承诺数据库快照加顺序文件复制；`--writers-stopped`只是操作人声明，工具本身不停止进程。本轮新隔离组合由编排脚本停止API/worker并只读检查两者状态，再以只读source卷、新restore卷、`--network none`执行备份恢复；原卷保留。SQLite WAL可能需创建共享内存文件，先按文件hash核对复制到新卷中的工作副本，仅在副本重放WAL，恢复前后核对原卷文件hash不变。正式还须排除其他写进程，明确维护窗口、操作人、保留期与RPO/RTO。

恢复对账核查完整数据库integrity/FK、活跃附件存在、身份/授权、导入/错题、审核/撤销/冻结版本、题项/原答/成绩/调度/复核/幂等及费用计数和预留金额的聚合hash。旧会话撤销、共享选择清空且revision递增、挑战消费、pending费用转unknown并保留占用、provider暂停。恢复后的真实内部TLS请求再次核查旧cookie401、重新登录/选择与冻结成绩可读。

这涵盖独立学习数据库/附件/导出与新隔离进程恢复；原WebUI数据库、秘密和证书信任未备份或改动，正式完整架构恢复/外部服务故障/实际RPO/RTO仍缺。不能把本轮合成17微金额hold称为真实账单。

## 新隔离组合

[编排脚本](../../scripts/probe_reuse_runtime.py)仅接受新的`dd-learning-reuse-*`project及learning_data内新目录，固定新Learning镜像/旧版本WebUI镜像，使用全新卷、两条internal网络、无宿主端口。合成账号、短期测试CA仅供内部TLS；没有安装客户端信任或绑定宿主443。源码中的[HTTP探针](../../scripts/reuse_runtime_http_probe.py)只在显式隔离opt-in下运行。

探针经实际nginx→网关→API与全新WebUI内置Cookie完成登录/303、工作台响应、上下文、代表手动错题/PNG、合成审核冻结/判分/撤销、metrics和恢复。没有模型调用、真实OCR、四格式重跑或P0操作；HTTP客户端不替代真实浏览器、正式IP证书、WebUI Tools分享/模型最终原生回调或人工资料质量。

## 停机补充

隔离编排的stop操作默认60秒宽限并按固定容器ID、归属和实际退出码验收；退出非零/OOM/进程残留/容器集合改变均失败，不再只因Docker命令成功就报成功。对已停止的137重试仍报告失败，不能覆盖历史结果。9项测试和新隔离合成正常停止见[补充报告](../verification/reuse-graceful-shutdown-2026-11-04.md)。该工具修复不定位原137根因，也不替代正式负载/RTO。新源码候选只改宿主编排，未重建应用镜像；旧50文件候选保持。

## W10故障隔离补充

新隔离网关/API/WebUI停机、认证WSS断开、同Cookie恢复和主动SIGKILL137/合成库完整性已有[独立报告](../verification/reuse-fault-isolation-2026-11-04.md)。代理解析/连接超时3秒，保留首次超时失败并在新证据中验证约3秒错误返回。10项新增编排防护通过；六个测试容器最终退出0、卷保留。该证据不覆盖模型最终浏览器回调、并发业务写入、正式容量/完整架构RPO/RTO，也不定位旧137。新候选dd-v1-reuse-faults-20261104只改nginx，未重建应用镜像，全部W/T/QA状态保持。

## 2026-11-05 W08/W09补充

本地周期监控、去重/提醒/解除、容量/合成备份回执和独立失联检查已实现，21项新增聚焦与新隔离组合通过；完整恢复七组件/顺序形成可审阅设计。详见[操作与恢复计划](07-MONITORING-RECOVERY-PLAN-2026-11-05.md)和[证据](../verification/reuse-monitoring-recovery-plan-2026-11-05.md)。SQL只读但SQLite辅助文件需数据卷写权限；原只读挂载失败保留。实际备份/校验/恢复回执衔接、跨备份删除/费用日志、正式权限/阈值/独立值守/来源/密钥/RPO/RTO仍缺。应用候选和镜像不变，状态不提升。
