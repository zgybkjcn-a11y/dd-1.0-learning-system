# W07–W10 独立运行与恢复工程证据

2026-11-04；[机器记录](reuse-runtime-recovery-2026-11-04.json)、[操作说明](../open-webui-reuse/06-RUNTIME-RECOVERY-2026-11-04.md)、[续跑交接](../goal/HANDOFF-SESSION-2026-11-04-W07-W10.md)。单执行者，原Git HEAD `0fa02712ceda049b14d4b556faef3fdb2fa985ed` 保持。

## 实际结果

| 范围 | 本轮证据 | 未覆盖 |
| --- | --- | --- |
| W07 | sidecar/HTTPS代理、secret文件、API/worker配置一致、重连plan工具；50文件白名单候选、固定基础OCI/16个hash依赖、无缓存/无网络安装镜像 | 正式443/证书信任、正式秘密/身份/网络接入、镜像签名与registry发布 |
| W08 | 默认mock/外发0/学习预算0；新隔离两条internal网络；聚合告警不复制私人字段，未知费用hold保留 | 原WebUI聊天费用、正式出网/告警轮询/接收人/容量、三通道实际账单 |
| W09 | 停API/worker并核验状态；只读源hash核对、副本WAL重放、新卷恢复；实际内部TLS旧Cookie401/新登录选择/冻结成绩回读 | 原WebUI/秘密/证书、完整架构恢复、外部服务故障与正式RPO/RTO |
| W10 | 新project/独立卷/无宿主端口；实际WebUI内置合成账号Cookie、nginx→网关→API、303/前缀/代表PNG/审核判分撤销；11方法原生loader与共享上下文最小投影 | 正式IP信任、真实浏览器最终原生回调/模型、正式分享与人工质量；WebUI优雅停机时限 |

当前schema11 / OpenAPI66 paths、24 schemas / Tools1.1.0。以上状态是本地工程和新隔离合成运行证据，全部T/QA行状态保持，仓库Goal仍blocked，只读Goal API为null。

## 固定候选与构建

最终源码目录：`learning_data/release-preparation/dd-v1-reuse-runtime-20261104-final`。

- profile：`reuse-runtime-v1`，50文件，schema11。
- 源码集合SHA256：`5e5dae5d58c0d04b8e7f91632e2eb6ececad7765163dd89df5aae6f404d8bd20`。
- 归档SHA256：`c0caf5fd20e1a92943b6ae3b51cf810c72a8d0fbc1ab11882580f5f49b40e7bd`。
- 本地镜像：`dd-learning:reuse-runtime-20261104-final`，ID `sha256:b67894e6bb8a7023d392a4dd4547e77b0c1d9b39912da3ddd1a50aefbd2b8cbb`。
- 基础：`python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30`；本机OCI导出逐blob校验，16个公共PyPI wheel完整hash锁定；构建 `--no-cache --network=none`，pip `--no-index --require-hashes`。
- 证据：`learning_data/verification/w07-w10-20261104/build-final/build.json`及`build.log`；基础OCI导出/依赖wheel SHA在机器记录。源码manifest保持`image_digest=null`，本地image ID不等于registry发布digest。

旧schema9/29、schema10/35、schema11/38候选verify通过且原hash保持。新增a/b/c/d中间候选、日志与本地镜像保留，没有覆盖或改写为成功：a的仓库元数据解析受阻；b修正nginx只读临时目录和探针上传路径；c改只读WAL源为hash核对工作副本；d之后固定发布说明形成最终包。原Dockerfile没有无缓存成功证据，本轮成功的是独立Dockerfile和本地固定OCI/wheel输入，不能互相替代。

最终API/worker/gateway的运行image ID等于上述构建ID；API容器内30个学习Python/迁移文件逐项匹配候选，运行契约66/24。其余源码/配置由最终候选核对；Tools补充探针不在应用包中，其自身hash及所复用原生loader协议文件hash在机器记录单列。

## 测试与隔离链路

最后聚焦 **56 passed in 19.28s**，日志 `learning_data/verification/w07-w10-20261104/pytest-final.txt`。覆盖secret文件加载/拒绝、sidecar变异边界、重连plan、告警投影、新恢复对账、release profile兼容，以及因config/secret/backup变化相关的gateway/会话/恢复回归。前面的19/3与最终56有重叠，不累加为新全量；本轮没有P0或四格式重跑。

最终project `dd-learning-reuse-20261104-final`，五服务，WebUI0.12.5固定镜像、两条新的internal网络，独立学习/WebUI/恢复卷，无宿主端口，无正式网络成员。测试CA只放入合成HTTP客户端的SSLContext；测试证书含目标IP和内部代理DNS SAN，没有修改系统信任或绑定宿主443。

实际HTTP客户端通过nginx完成内置账号登录Cookie、网关csrf/303与固定Location、两个学习Cookie的Secure/Strict/Path=/、上下文选择、工作台响应、手动错题幂等、一个8×8合成PNG上传、合成母题/变式审核幂等、冻结版本投放、worker正确判分、撤销后成绩保留、管理员metrics、旧上下文409和禁止浏览器内部交换/seed路径。provider/model/OCR调用为0；不是浏览器UI验收。

Tools通过新隔离WebUI原生API注册本次源码，原生loader发现11方法，保留参数未暴露；宿主身份/UserValves、服务端共享上下文、learner_count与固定入口、错题/进度最小投影通过；模型列表为空。最初探针沿用旧`items`断言而失败，改为现有W05的数量投影后通过，业务Tools源码未改。实际模型发起/最终原生浏览器callback和正式分享依旧未验收。

## 恢复对账

停止新隔离API与worker后分别读取State确认非running，source卷只读挂载；逐文件hash复制到新恢复卷的工作副本，在副本打开WAL，再调用SQLite backup和附件/导出复制。恢复前后源文件hash不变；新库integrity=ok、FK错误0、活跃附件缺失0。

运行夹具中实际存在并保持hash：1条审核、1条撤销、1条冻结私有版本、1条原始作答、1条正确成绩、2个测验session/item、1个PNG文档/页、1条手动错题/来源、身份绑定/授权和4条幂等记录。未填充的导入候选/人工judgment/复核申请/调度review_events在对账中计数为0；相关旧证据保留，不把空表hash当作本轮非空业务验证。

恢复前存在活跃学习会话/共享选择/未消费挑战及1条合成reserved费用。恢复后会话/选择/挑战均失效，reserved→unknown、17微金额占用保持，provider暂停；没有登记真实账单。新API/worker改用恢复卷启动，经实际TLS确认旧Cookie401、新登录要求重新选择、冻结正确成绩仍可读取。

最终及调试两个新project均已停止，学习/API/worker/gateway/proxy退出0；新隔离WebUI在Compose stop后退出137、OOMKilled=false。该结果不证明优雅关闭成功，后续需单独验证WebUI停止宽限时间/后台任务退出；没有为此操作正式WebUI。全部本轮卷/本地镜像和私有证据保留，未执行`down -v`或清理旧实例。

## 限制与后续

正式IP稳定性/443/防火墙/IP SAN证书与客户端信任、旧HTTP53001策略、issuer/身份清单/操作人/正式学习库仍待输入。聊天费用不属于学习台账；学习诊断/变式和OCR仍共用现有全局学习预算。正式网络/监控/容量、完整架构RPO/RTO、真实provider许可/预算/人工资料质量、W13具体发布授权、W14同意及7–14自然日观察仍分别保留。

根Compose、batch_ingest、正式WebUI data/秘密没有读取或修改；未生产部署、未真实调用/学生资料外发、未Git提交/push/丢弃改动、未创建/更新/完成Goal。最终未提交文件保留、Markdown链接、JSON/任务/QA/依赖与候选hash核对结果见机器记录的`final_audit`和`checks`。
