# DD-1.0 固定候选与正式认证准备

源码候选manifest与独立构建证据分开保存；W07已有固定基础OCI与16个hash锁定依赖的本地无缓存构建，尚未发布镜像或部署生产。P0 仍运行此前 schema 7 快照；当前工作树新增migration011后为schema11，不能沿用 P0 的源码/契约一致结论。候选包含既有未提交改动，Git HEAD 单独不能代表它。

运行 `python3 scripts/prepare_learning_release.py prepare --destination learning_data/release-preparation/<新目录>` 会只读取 38个白名单源码/契约/模板/说明文件，生成确定性 `source.tar.gz`、逐文件 SHA-256、源码集合与归档校验和。目录必须全新，不覆盖已有文件。`verify --destination ...` 只在归档内核对固定文件集合与校验和，不解压、不构建、不启动服务。校验和提供一致性证据；此包尚未签名。

`production-config.template.env` 是未填写的配置模板：密钥仅由运行时提供，OCR/模型外发关闭、预算为零。它没有实际域名、登录后端、凭据或费用审批。正式发布仍须固定基础镜像与最终应用镜像 digest、审阅全部未提交改动、在独立环境验证新 schema/契约/认证、按实际架构准备磁盘/队列/监控及一致性备份恢复；不直接复用 `/tmp` 的 P0 私有配置。现有原始 Dockerfile 无缓存全新构建仍未证明成功。

现有 `docker-compose.learning.yml` 保持隔离 mock 基线，并未转发新增模型/浏览器会话配置。网关已有本地实现，独立运行配置与目标TLS组合仍需形成具体候选；本轮没有通过放宽 P0 网络、填写真实连接或启动新镜像来联调。provider 配置、费率预留与对账边界见 [`PROVIDER_CONFIGURATION.md`](../PROVIDER_CONFIGURATION.md)。

登录网关先完成真实用户认证，再生成 HS256 JWT：header 严格为 `{"alg":"HS256","typ":"JWT"}`，claims 严格为 `iss/aud/sub/iat/exp/jti`，有效期最多 120 秒、`jti` 一次性。`sub` 只能映射已有 `identity_bindings`，服务端从 `learner_access` 获取权限；网关声明不得携带 account/role。登录签名密钥须独立于 admin/adapter 密钥，不交给浏览器、模型或 Tool Valves。

同源登录入口 `/auth/login` 由受信网关实现，学习服务本身尚未提供真实登录后端。网关通过同源 HTTPS 的 `POST /api/v1/auth/session` 送入 Bearer 声明和配置的 Origin；浏览器收到 Secure/HttpOnly/SameSite=Strict 的不透明会话 cookie 和可读 CSRF cookie。后续 `/ui` 自动读取会话与授权学习者，不要求用户输入账号或共享密钥。所有 cookie 写请求同时校验 Origin 和 `X-CSRF-Token`；退出在数据库撤销会话，权限变更由每次请求重新读取。真实网关/TLS/浏览器入口的最终联调仍待完成，不能把本地 ASGI 或合成声明写成正式认证验收。

备份恢复会撤销所有恢复出的浏览器会话并暂停 provider 调用。恢复后重新登录、核对仍未对账的调用/费用占用、审核配置及运行状态，再由管理员显式恢复调用。费用中断占用不会因 worker lease 超时被自动释放；备份时间以后发生的外部调用还需按真实账单补录/核对，当前恢复不能声称跨外部账单无损。

本轮增加schema10的35文件封包配置；verify同时保留原schema9/29文件白名单，不使用新集合否定旧包。新候选的指纹与边界见[工程报告](../verification/open-webui-reuse-engineering-2026-11-04.md)，旧包未覆盖。网关/绑定CLI和合成浏览器说明见[本地实现](../open-webui-reuse/04-LOCAL-IMPLEMENTATION-2026-11-04.md)。

第二批schema11/38文件候选加入人工审核/冻结迁移与学习教练空配置草稿；verify继续保留schema9/29与schema10/35两个旧profile。当前契约66/24，image_digest=null；实际固定镜像和sidecar/代理组合留W07。证据见[第二批工程报告](../verification/reuse-workbench-tools-review-2026-11-04.md)。

第三批schema11/50文件`reuse-runtime-v1`加入sidecar/HTTPS代理、秘密文件、运维/恢复与独立构建/隔离探针；旧schema9/10/11的29/35/38文件profile保留。源码manifest始终保持image_digest=null、未部署边界；本地镜像ID、基础OCI与依赖SHA见独立build.json，不能冒称registry发布digest。操作与边界见[运行恢复说明](../open-webui-reuse/06-RUNTIME-RECOVERY-2026-11-04.md)。源码变更后在新目录prepare并构建，不覆盖旧候选或tag。
