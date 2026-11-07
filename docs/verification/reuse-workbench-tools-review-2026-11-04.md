# W04/W05/W06 复用工程验证

日期：2026-11-04；分支main，Git HEAD仍为`0fa02712ceda049b14d4b556faef3fdb2fa985ed`。当前源码schema11、OpenAPI66 paths/24 schemas、Tools1.1.0。本轮完成工作台/Tools/人工变式审核的本地实现及合成验证，T/QA状态没有提升，仓库Goal仍blocked，Goal API只读null。

## 实现及证据

- W04：今日任务/版本选择/错题详情/上传复核/测验恢复入口，标签内定位缓存、代次/AbortController、原答与文件清理、来源URL撤销、过期上下文/账号拒绝和no-store响应。
- W05：11方法先读服务端选择、固定宿主身份与版本，UserValves不一致拒绝；读取后复核；原生四种操作继续使用原版本，最小投影剔除原件/原答/答案键/个人资料/provider及任意错误正文。固定HTTPS链接与[教练空配置草稿](../open-webui-reuse/learning-coach.template.json)，没有实际分享或模型绑定。
- W06：migration011、受限reviewer/admin队列/approve/reject、当前指纹/人工说明/幂等，事务重读母题/课程/范围/整数并重建答案，生成冻结私有版本；拒绝不入库，重新生成用新job；撤销停止投放、使未提交题项失效，保留pending/已用成绩。审核与私有版本进入授权导出/删除tombstone/副本恢复。

操作和完整边界见[实现说明](../open-webui-reuse/05-WORKBENCH-TOOLS-REVIEW-2026-11-04.md)，源码和证据指纹见[机器记录](reuse-workbench-tools-review-2026-11-04.json)。

## 必要验证

主聚焦命令为：

```text
pytest -q tests/test_reuse_tools.py tests/test_variant_review.py tests/test_learning_tools.py tests/test_open_webui_compat.py tests/test_learner_context.py tests/test_learning_release.py tests/test_login_gateway.py tests/test_learning_service.py::test_migration_and_learner_isolation tests/test_learning_service.py::test_concurrent_fresh_database_migrations_serialize tests/test_learning_service.py::test_restore_migrates_legacy_tombstone_schema_before_replay
```

结果：**89 passed in23.18s**。覆盖上下文/ABA/宿主保留参数/最小输出、回调取消与120秒超时、审核权限/撤权、指纹/题干/答案/域/母题变化、事务回滚、并发仅一个版本、拒绝/重放/冲突/撤销、冻结内容/成绩不改写、schema10升级/新库/副本恢复与路由边界。

封包白名单加入教练草稿后另跑必要契约/provider复核：`tests/test_learning_release.py`、`test_variant_scope_math_and_manual_approval`、`test_variant_worker_rechecks_source_before_persistence`、`test_provider_boundaries_are_explicit_and_variant_stays_reviewable`、`test_test_session_recovery_returns_attempt_state_without_answer`、`test_variant_source_is_approved_scoped_and_objective_consistent`，结果 **19 passed in3.94s**。与主聚焦有重叠，不能相加为新全量。未重跑全量、P0、四格式持久化或无变更OCR验证。

首轮新测试52通过/3失败，失败为HTTP状态码预期；修正为既有拒绝/异步状态后通过。Chromium先通过390px，在1280px发现同一母题请求复用已审核撤销job，补可选幂等新请求后两视口通过；后补账号变化探针遇到注销导航未结束的时序问题，探针等待页面完成后复验。失败日志保留在本机ignored验证目录，不覆盖既有证据。

[Chromium证据](reuse-workbench-browser-2026-11-04.json)：390/1280px均完成今日开始→刷新恢复（原答不缓存）→提交→最终判分→复核→取消，代表PNG上传→候选/原页→人工复核→可信确认，审核UI批准→撤销，延迟旧成功响应→切换清理，跨标签409/刷新同步，注销与合成账号切换401/表单及Cookie清理。页面无异常、无横向溢出，live_provider_calls=0。

页面所有URL拦截，WebUI认证响应合成、Learning API/网关进程内ASGI；303之后主动导航由探针模拟。该证据不代表正式登录/TLS/实际网络/真实模型发起的原生最终回调或人工质量通过。

## 候选与执行边界

本轮新schema11/38文件源码候选在`learning_data/release-preparation/dd-v1-workbench-tools-review-20261104`；确切SHA见机器记录。schema9/29文件及schema10/35文件旧候选均保留并由新verify兼容校验。image_digest全部null，没有构建/签名/发布/部署；P0/schema7没有修改或复验。

本轮开始保存108个既有未提交文件指纹。收尾只允许有意更新的源码、必要测试和台账/文档；缺失/意外修改为0，HEAD不变，无reset/checkout/clean/commit/push。没有读取根docker-compose.yml、batch_ingest.py、正式WebUI data/秘密，没有操作运行容器/网络/Tools/证书信任，没有真实模型/OCR或真实学生资料外发；默认mock、外发关闭、学习预算0保持。

W04/W05/W06仅提升机器工作包的本地工程进度，不提升T/QA/Goal。正式账号/TLS/IP稳定性/HTTP策略与初始化输入，真实母题/审核人/人工资料质量，三通道模型/费用/资料许可，W07新固定镜像/独立sidecar与代理、W08预算网络监控、W09完整恢复、W10新隔离组合仍待落实；W11–W14按真实条件推进，T24–T26不启动。

收尾核对：14个变更Python文件编译、18份Markdown的139个本地链接、6份JSON、14工作包无环、26任务/17QA/303条任务证据及diff-check通过。起点108个既有未提交文件中82个指纹不变、26个有意更新，0缺失/意外修改；另14项新文件或本轮新改动保留，Git HEAD不变。旧候选SHA保持，新候选源码匹配，Goal API只读仍null。
