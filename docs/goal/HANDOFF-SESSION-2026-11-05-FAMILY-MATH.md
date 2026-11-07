# 两人数学测试版：已部署与首次使用

最新界面（2026-11-05 20:54）：按用户选择的活泼闯关风格，数学探险队已上线，二年级森林/七年级星球主题、三个主入口和真实进度显示。当前使用 `compose-game-ui-20261105.json`；详见[新界面交接](HANDOFF-SESSION-2026-11-05-GAME-UI.md)。家长已绑定，真实两档案作答试用仍待进行。

最新续跑（2026-11-05 19:49）：**家长真实登录和一次启用码绑定已完成，错题知识目标自动匹配已上线**。当前使用新固定镜像与 `compose-auto-objective-20261105.json`；旧配置和记录保留为历史。真实两档案作答/错题试用仍待家长操作。最新功能、运行命令、验证及备份限制见[续跑交接](HANDOFF-SESSION-2026-11-05-AUTO-OBJECTIVE.md)，下文部署时的待办和镜像为历史时点。

最新补充（2026-11-05）：专用根证书已安装到 Windows 当前用户的 `Trusted Root Certification Authorities`（`CurrentUser\\Root`），Windows 默认 TLS 校验已通过。原文中“设备证书导入待用户操作”是部署收尾时的历史状态；当前仍待完成的是家长真实首次登录和一次启用码绑定。

更新：2026-11-05。当前交付范围是一个现有家长账号、七年级和二年级两个学习档案、数学。用户明确要求先供自己使用，并授权“继续，不要停，直到完成生产上线的任务”。该授权覆盖本次家庭测试版部署，替代旧交接中对此范围的禁止生产部署限制；真实模型/OCR、学生资料外发及 Goal 写入仍未授权。

服务已在当前 IP 上运行，入口为 **<https://172.19.116.53/learning/auth/login>**。原来的 <http://172.19.116.53:53001/> 保持可用。原 Open WebUI 容器、数据库、模型配置和 Tools 未修改。

## 首次使用

1. 证书已在当前 Windows 使用设备导入并验证通过。其他设备仍需自行导入[专用根证书](../../learning_data/deployments/family-math-20261105/家庭数学测试-根证书.crt)；不要外发根证书私钥或部署目录中的秘密文件。
2. 打开上述 HTTPS 入口，使用已有 Open WebUI 家长账号登录。
3. 按[私有首次使用说明（含启用码）](../../learning_data/deployments/family-math-20261105/家长首次使用.txt)输入一次启用码；以后该家长账号无需再填。启用码不写入公开报告。
4. 选择“七年级数学”或“二年级数学”，点击一道题开始练习，也可以手动记错题。

**真实家长首次绑定和实际学习尚待用户操作**；部署通过不代表这些已完成。地址沿用当前 IP，其他设备需要能访问这台主机。

## 当前能用的内容

- 一个家长账号切换两档案，练习进度、错题和课程范围分别保存。
- 二年级 8 道起步题：100 以内加减法、表内乘法；七年级 6 道起步题：减去负数。共 14 道编写题，来源 `authored_family_starter_math_v1`，没有将其标成模型生成变式或完整年级题库。
- 选题、提交、判分、刷新恢复；手动录入题干、作答、参考答案、知识目标与备注，查看错题详情。
- 隐藏上传/OCR、诊断、变式审核入口；默认 mock、外发关闭、学习预算 0。WebUI 原有聊天的费用不属于学习台账。

复杂监控、跨快照增量日志、全架构 RPO/RTO、商业化功能、其他学科和真实模型/OCR均暂缓，不再作为两人版上线前置。后续先收集这两个档案实际使用的问题与题目需求。

## 已执行验证

- 功能聚焦两组分别为 **46 passed**（family/identity/variant）和 **41 passed**（family/browser-auth/gateway）；有重叠，不相加为全量。包括课程隔离、题目计算、已有目录保护、一次性家长绑定及不可重复认领。
- 390px/1280px 合成浏览器覆盖首次绑定、后续无代码登录、两年级选题、提交判分、刷新恢复、手动错题和档案切换清理。最后修正了 flex 样式覆盖 `hidden` 导致诊断控件仍显示的问题，重新验证两种宽度通过；无页面错误或横向溢出。证据：[最终浏览器记录](../../learning_data/verification/family-pilot-20261105/browser-final-report.json)。所有 URL 被合成 ASGI 拦截，303 后由探针导航，不能写成真实家长登录验收。
- 实际部署经专用 CA 校验 IP 证书链/主机名：`/health` 200、WebUI 登录页 200、学习入口 303 到登录页、未登录的会话 API 401；新学习 API 内部 health 200、schema11、数据库完整性通过。初次部署及最终镜像复核均为 accounts=1、learners=2、questions=14、identity_bindings/attempts/provider_calls=0。证据：[生产检查](../../learning_data/verification/family-pilot-20261105/production-final-checks.json)。
- 实际 Chromium 访问生产学习入口并自动跳到 WebUI 登录页，邮箱/密码表单可见；未输入凭据。该临时浏览器上下文忽略证书错误，证书链/IP 另由上面的 HTTPS 检查验证，未改设备信任。证据：[生产登录页](../../learning_data/verification/family-pilot-20261105/production-login-browser.json)。
- 旧 P0、四格式验证和全量测试未重跑。旧候选、失败记录和未提交改动保留。Git HEAD 为 `0fa02712ceda049b14d4b556faef3fdb2fa985ed`；只读 Goal API 为 null，未创建、更新或完成 Goal。

## 运行与版本

独立项目 `dd-family-math`：API、worker、gateway、proxy，数据卷 `dd-family-math_data`，内部网络 `dd-family-math_internal`。代理和网关复用现有 `open-webui_default`，仅代理发布 `172.19.116.53:443`。四个服务设置 `restart: unless-stopped`，保留运行。

实际配置与私有材料位于 `learning_data/deployments/family-math-20261105/`。不读取根 Compose 或既有 WebUI 秘密。最终候选 `learning_data/release-preparation/dd-v1-family-math-20261105-final` 为 schema11、50 文件；源码集合 SHA256 `d42f0df3bde94830028db9dbe26f1e02bc3199e1538222dde32bcab7993ecec3`，归档 SHA256 `d2da6979d6c28f0894b105cb1b9035058add11c3cc7a59772052b407ea132d56`。契约仍为 66 paths / 24 schemas。

最终运行镜像 ID 为 `sha256:6432f2175659cd3f496b05efb8fdffe69969c9b12dff8d48962850a752f8336a`。固定镜像见[构建记录](../../learning_data/verification/family-pilot-20261105/build-final/build.json)，实际运行镜像、Compose hash 和初始化脚本 hash 见[部署记录](../../learning_data/deployments/family-math-20261105/deployment-final.json)。使用固定本地 OCI 基础、16 个校验依赖，无缓存构建且安装阶段无网络。源码 manifest 的 `not_built_not_deployed` 和 build 记录中的 `deployed_to_production=false` 是各阶段的不可变历史；后续部署以独立部署记录为准。

`docs/verification/release-manifest-2026-11-03.json` 属于原完整 V1 技术交付，其授权字段保留，不代表本家庭版仍未获准。完整 V1 的 T01–T26、QA01–QA17、原 Goal 状态未提升。

## 简单运维

仅需查看服务时，在项目目录运行：

```bash
docker compose --env-file /dev/null -p dd-family-math -f learning_data/deployments/family-math-20261105/compose-game-ui-20261105.json ps
```

需要手动备份学习记录时，复用已有备份工具；当前手动错题/练习都在 SQLite 中，在线快照无需停止使用。不包含 WebUI 数据库或部署秘密：

```bash
umask 077
family_snapshot="family-math-$(date +%Y%m%d-%H%M%S)"
mkdir -p learning_data/family-backups
docker exec dd-family-math-learning-api-1 python -m learning_service.backup backup /var/lib/dd-learning "/var/lib/dd-learning/backups/$family_snapshot"
docker cp "dd-family-math-learning-api-1:/var/lib/dd-learning/backups/$family_snapshot" "learning_data/family-backups/$family_snapshot"
```

如需停止或恢复本测试版，使用以下命令；这些命令未在收尾时执行，不删除卷：

```bash
docker compose --env-file /dev/null -p dd-family-math -f learning_data/deployments/family-math-20261105/compose-game-ui-20261105.json stop --timeout 60
docker compose --env-file /dev/null -p dd-family-math -f learning_data/deployments/family-math-20261105/compose-game-ui-20261105.json start
```

## 下一次继续

先读本文，再读 STATUS/TASKS/BLOCKERS/DECISIONS、机器计划、部署输入、QA 与 Git/只读 Goal。优先处理用户首次使用反馈和数学内容需求；不要自动恢复旧监控/完整恢复工程，不重跑旧 P0/四格式，不停止本项目做“测试清理”，不要重新初始化已使用的数据卷。

保持单执行者、保留全部未提交改动，不 reset/checkout/clean/commit/push；禁读改根 `docker-compose.yml`、`batch_ingest.py` 及既有 WebUI 数据/环境秘密；不调用真实模型/OCR、不外发学生资料、不写 Goal。当前实际启用与试用情况以新的真实记录为准，不编造自然日观察或家长操作。

收尾核对：起点 155 个未提交文件中 135 个指纹不变，20 个有意更新，0 缺失；新增初始化脚本、家庭版测试和本交接。最终 50 文件候选与当前源码一致，初始化脚本 hash 保持，26 任务/17 QA/364 证据引用和 diff 检查通过。私有[收尾核对记录](../../learning_data/verification/family-pilot-20261105/final-audit.json)记录运行镜像与链接核查；生产服务保持运行。
