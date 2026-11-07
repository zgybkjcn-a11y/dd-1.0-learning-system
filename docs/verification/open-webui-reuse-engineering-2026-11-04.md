# DD-1.0：现有 Open WebUI 复用第一批本地工程证据

日期：2026-11-04（Asia/Shanghai）。用户授权开始本地工程，确认沿用当前IP；HTTPS目标为 `https://172.19.116.53` 默认443。没有修改现有 `http://172.19.116.53:53001/`、容器、网络、Tools或正式数据库；没有生成/安装证书、部署生产或调用真实模型/OCR。

## 实际实现

- W01：固定IP/HTTPS开发目标；只读 `ss -ltn '( sport = :443 )'` 未见宿主TCP监听。证书IP SAN/设备信任、IP稳定性、端口/防火墙、旧HTTP策略与运维责任未验证。
- W02：独立默认关闭网关，固定WebUI认证path和token Cookie；有界一次性登录CSRF绑定原Token/subject，60秒服务器声明，逐请求来源身份匹配、最小Cookie/头转发、严格路由；认证故障/切换/解绑拒绝。标准库传输无代理/重定向/重试、64KiB认证响应与连接后总截止3秒（含慢速状态/头）。系统DNS阻塞与目标网络仍未验收。
- W03：migration010撤销无来源的旧会话、保存issuer/subject；登录逐次复核当前绑定。共享上下文CAS、旧版本读写拒绝、SQLite写锁内再验选择/版本/授权、切换消费旧挑战；恢复撤销会话/清空选择/消费挑战，费用暂停及unknown占用保留。
- 安装/绑定CLI：严格manifest、重复/冲突/role/时区/课程校验；validate/plan不开写库或迁移；apply绑定目标/操作人/审核hash，在一个事务中迁移/变更/审计。撤权/解绑/角色变化撤销账号学习会话和上下文；保留资料/成绩。未在正式库应用，只用合成临时库。
- W04基础：固定 `/learning` 浏览器URL/登录链接、上下文版本与缓存命名空间，过期标签页409后需刷新；没有实现整个产品入口、Tools两端同步或完整测验恢复。
- 发布准备：新schema10/35文件白名单；verify继续支持旧schema9/29文件候选，旧包指纹保持。源码封包不等于镜像构建/发布/部署。

实际配置/CLI/缺项详见[操作说明](../open-webui-reuse/04-LOCAL-IMPLEMENTATION-2026-11-04.md)。API契约路径61、schemas22不变，既有learner-context路径增加GET；P0/schema7保持原快照。

## 测试结果

本轮最终 **74 passed in 18.32s**。命令范围：

```text
tests/test_login_gateway.py
tests/test_learner_context.py
tests/test_identity_admin.py
tests/test_gateway_http.py
tests/test_browser_auth.py
tests/test_learning_release.py
tests/test_learning_service.py::test_migration_and_learner_isolation
tests/test_learning_service.py::test_concurrent_fresh_database_migrations_serialize
tests/test_learning_service.py::test_restore_migrates_legacy_tombstone_schema_before_replay
```

覆盖合成网关声明/Cookie/头隔离、Origin/CSRF/重放、身份切换/pending/401/解绑/故障、格式错误身份、路径白名单、nonce容量/到期/重启；共享选择/版本/跨会话、adapter拒绝选择、授权后切换竞态；CLI只读/审阅hash/冲突/回滚/撤权/审计；loopback重定向/代理/响应上限/慢速头总截止；来源迁移、恢复及旧包兼容。

此前101为旧全量、102为前次provider聚焦；与本轮74分开记录，不相加称全量。没有无变更重跑四格式持久化、P0、真实模型/OCR或真实资料质量验证。

Chromium390px/1280px：[机器浏览器记录](reuse-gateway-browser-2026-11-04.json)。表单Origin/nonce/服务器交换通过；只读账号、明确学习者选择、前缀手动错题/小合成PNG上传/页图读取、另一个标签页切换后的旧页409、刷新同步、退出后401/Cookie清除、无横向溢出/页面错误通过。全部页面URL被拦截，WebUI认证为合成响应，Learning API/网关在进程内运行；live_provider_calls=0。

**探针显式模拟303后的导航**：ASGI返回303及固定Location已检查，然后探针主动导航，避免Chromium的fulfilled重定向脱离该拦截路径。它不是实际TLS重定向、正式Cookie或真实WebUI登录的验收。登录页no-referrer使Chromium表单Origin为null的问题经浏览器发现，改为same-origin后表单交换通过。

测试过程中fixture注册、网关factory返回、幂等键和探针响应字段/退出页面断言问题已修正；上文只登记修正后的最终结果。测试机器汇总、指纹、链接/一致性及改动保留核对见[工程JSON](open-webui-reuse-engineering-2026-11-04.json)。

## 未满足的门槛与下一步

W01输入未齐，W02/W03只有本地实现/合成证据；W04基础部分完成。下一批W04完整入口/恢复、W05 Tools上下文/最小结果/固定入口、W06人工变式审核发布；随后W07独立配置/代理/网络重连与新镜像、W08三通道监控费用、W09完整恢复、W10新隔离组合。

实际WebUI账号/Cookie/TLS、正式绑定manifest/操作人/学习库、真实tool call/最终可信回调、provider/账单/预算/网络、脱敏整卷/人工参考和冻结质量、正式维护切换与7–14天真实试用仍缺；P2仍空模板。完整V1不缩减，T24–T26 deferred；T/QA状态不提升，仓库blocked、Goal API null，不创建/complete Goal。

本轮保留全部既有未提交改动，不reset/checkout/clean/提交/push；禁读/禁改根docker-compose.yml和batch_ingest.py，未读正式WebUI数据/环境秘密。OCR/学习模型仍mock、外发关闭、预算0。源码包image_digest=null，未构建新镜像。

## 固定源码候选

新目录 `learning_data/release-preparation/dd-v1-reuse-gateway-20261104`：schema10、35文件，source_set_sha256=`0a5352c5d9bfb22f39a2015c054442c930067ed2d5fcad9891b1316f4a598b85`，archive_sha256=`2b6655c58d7a5af50e8b9712f7268baab50913fc91bf7c36298b0b0a5042a17c`，image_digest=null；新包校验与当前白名单逐文件指纹匹配。旧schema9/29文件候选再次通过兼容校验，原两项SHA不变。两者均为本地源码包，不是构建/签名/部署证据。

## 最终核对

13个变更模块/脚本编译、14份Markdown的86个本地链接（0缺失）、5份JSON及14工作包无环依赖、diff-check通过。任务一致性：26任务、267条evidence路径、26台账行、17 QA行、24 manifest引用，原发布授权边界完整。工程起点87个既有改动文件中，58个指纹保持、29个有意修改，0缺失/意外修改；新增文件另行保留，未覆盖旧包或旧P0。Goal API最后只读仍null，全部T/QA状态保留。
