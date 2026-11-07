# W10 故障隔离与认证 WebSocket 停机验证

2026-11-04；承接[停机工具报告](reuse-graceful-shutdown-2026-11-04.md)与[W07–W10交接](../goal/HANDOFF-SESSION-2026-11-04-W07-W10.md)。[机器记录](reuse-fault-isolation-2026-11-04.json)保存各阶段原始聚合结果、信号、退出码、来源 hash 和收尾核对。

## 发现与修改

新隔离组合中，停止网关或 WebUI 后，代理的首次请求曾超过客户端 12 秒截止；随后网关请求返回 502。原配置没有显式 DNS 解析/上游连接超时。现在[nginx 配置](../../deploy/open-webui-reuse/nginx.learning.conf)设置 `resolver_timeout 3s` 和 `proxy_connect_timeout 3s`，在新隔离代理执行配置检查并重新加载。修改后网关停止时学习入口 3.006 秒返回 504；WebUI 停止时聊天入口 3.008 秒返回 504。未单独注入 DNS 服务器故障，3 秒解析超时是配置事实，不是所有网络故障的端到端时限。

新增[阶段编排](../../scripts/probe_reuse_faults.py)和[合成 HTTP/WSS 客户端](../../scripts/reuse_fault_client.py)。编排核对五个服务及独立观察端的标签、固定容器 ID、无宿主端口、项目 internal 网络；同一运行目录的阶段加排他锁，拒绝覆盖已存在的阶段报告。观察端位于独立容器，认证 `user-join` 的返回 ID 必须与合成登录身份相符；不发送聊天、模型、Tool 或学生载荷。客户端 Cookie 恢复保留域与 Secure 属性，避免测试工具自身产生重复 Cookie 名称；报告只输出状态、耗时和固定错误码。

## 实际结果

项目 `dd-learning-reuse-faults-20261104` 使用全新学习/WebUI 卷、两条 internal 网络，无宿主端口。使用既有固定学习镜像、固定 WebUI 0.12.5 与 nginx 镜像；新 WebUI 只创建一个合成账号，可用模型数 0。单独生成的测试 CA 仅供内部客户端使用，未安装系统信任或绑定正式 443。

| 场景 | 观察到的结果 |
| --- | --- |
| 网关停止 | WebUI 认证 HTTP 200、已有认证 WSS 保持连接、Learning 健康 200；学习入口在修改后 3.006 秒返回 504 |
| 网关重启 | 重启前发出的 nonce 在有效期内被拒绝（403 `LOGIN_CSRF_REJECTED`）；新 nonce 登录成功，原 WebUI 身份保持 |
| API/worker 停止 | WebUI HTTP 200；学习入口 503 `LEARNING_UPSTREAM_UNAVAILABLE`；直接 API 健康不可达；重启后原 Cookie 读取同一身份/学习账号 |
| 认证 WSS 下 SIGTERM | 两次 WebUI 分别 5.346、3.993 秒退出 0，OOM=false；事件为 SIGTERM/die0；独立客户端观察到服务端断开，没有靠客户端超时结束 |
| WebUI 停止期间 | 学习入口 503 `AUTH_UPSTREAM_UNAVAILABLE`，直接 API 健康 200；修改后聊天入口约 3 秒返回 504；重启后既有 Cookie 恢复同一身份/学习账号 |
| 受控 SIGKILL | 只对本次新隔离 WebUI 发 SIGKILL；退出 137、OOM=false，事件 signal9/die137，WSS 断开；此记录是故障注入证据，不能称为优雅停机 |
| SIGKILL 后重启 | 原 Cookie/身份/学习账号恢复；新 WebUI 与学习数据库 integrity_check=ok，学习 FK 检查无违规，合成账号/绑定计数保持 |
| 最终收尾 | 独立观察端退出 0；五个 Compose 服务经停止工具核验均退出 0、无 OOM/残留进程；保留全部测试卷、历史故障报告与镜像 |

首次手工网关尝试没有捕获失败断言时的响应，观察端随后自行超时，记为 incomplete，不计入认证 WSS 故障通过证据。首次 WebUI 场景虽正常停止，但 HTTP 等待超时导致阶段 failed；该报告保留。调整超时后的新阶段使用 `-bounded` 文件名，未覆盖原报告。数据库核对时没有并发业务写入；这不是写入中断/正式负载的一致性或 RPO/RTO 证明。

10 项新增[编排防护测试](../../tests/test_reuse_faults.py)通过（0.10 秒），覆盖外部/暴露资源拒绝、重叠阶段拒绝、既有证据保留、137/OOM/残留进程不算正常停止以及主动 SIGKILL 137 留证。此前 56 项、停机工具 9 项、W04–W06、P0、四格式及浏览器测试均未重复执行。内部 WSS 客户端不是浏览器模型最终原生回调。

## 使用与保留边界

证据目录：`learning_data/verification/reuse-faults-20261104/`；私有合成凭据/Cookie、测试 CA 和 Compose 输入留在其 `runtime/` 目录，不进入公开报告。观察端采用固定 WebUI 镜像的 Python 入口，镜像自带 WebUI HTTP healthcheck 不适用于该观察端；其存活/连接和最终退出单独核验，不以此 healthcheck 判定业务健康。

后续需要验证新变化时使用新项目/目录；先用 `probe_reuse_runtime.py prepare` 生成隔离配置并显式启动，创建仅连接该项目 internal 网络的观察端，挂载客户端、私有合成输入和状态目录，以 `DD_ISOLATED_FAULT_CLIENT=1` 运行。只在全新学习库植入合成账号/绑定，并完成合成 WebUI 登录与学习登录。阶段工具要求以上前置条件，不会初始化正式库或启动已保留的旧项目。按顺序逐项执行并核对退出码：

```bash
python scripts/probe_reuse_faults.py gateway-outage --runtime <新隔离runtime目录>
python scripts/probe_reuse_faults.py api-outage --runtime <新隔离runtime目录>
python scripts/probe_reuse_faults.py webui-stop --runtime <新隔离runtime目录>
python scripts/probe_reuse_faults.py webui-kill --runtime <新隔离runtime目录>
python scripts/probe_reuse_faults.py finish --runtime <新隔离runtime目录>
```

失败后先保留阶段报告、核对该新项目状态再恢复；工具不自动掩盖故障或删除资源。`--evidence-suffix` 只用于记录变化后的独立尝试，不覆盖已封存结果。不要直接重跑本次目录，部分阶段故意中断服务且凭据/nonce 有效期有限。

## 候选、交接与限制

新 50 文件候选：`learning_data/release-preparation/dd-v1-reuse-faults-20261104`，schema11/profile `reuse-runtime-v1`；相对上一停机候选只改变 nginx 配置。源码集合 SHA256 `6ff57b37a85a233682a8161d9f203d77b8b9b8f9841cf6152650a5c52fe899c7`，归档 SHA256 `d7b3a24373f19417224466113f88b0cdea91d49a4f80383e060ba95a3775587f`。新探针/测试单独记录 hash，不更改冻结的 50 文件 profile；manifest 的 image_digest 仍为 null。

本轮没有新建应用镜像：Dockerfile、锁定依赖、30 个学习代码/迁移文件未改变，继续使用 `sha256:b67894e6bb8a7023d392a4dd4547e77b0c1d9b39912da3ddd1a50aefbd2b8cbb`。旧镜像不是新候选的构建证明。所有旧候选/卷/报告保留。

原两次非主动故障导致的 137 根因仍未充分定位；本次受控 SIGKILL 不能替代该结论。正式 IP 证书/信任/账号、三通道费用与监控、完整架构/秘密恢复与正式 RPO/RTO、模型最终原生回调、人工质量及真实试用仍缺。T/QA/W 状态不提升，仓库 Goal blocked，Goal API 只读 null；无生产变更、真实模型/OCR、真实学生资料外发、Git 提交/push 或 Goal 写入。

收尾核对：起点143个未提交文件中132个hash不变、11个有意更新，0缺失/意外修改；另5个新文件保留。8份Markdown的87个本地链接、26任务/350证据引用/17QA与14工作包无环、3个Python编译和diff-check通过；32个应用镜像输入文件与已构建候选相同。新候选匹配当前源码，两个相邻旧候选自校验通过；HEAD保持，Goal API只读null。
