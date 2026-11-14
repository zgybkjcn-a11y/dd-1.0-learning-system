# DD-1.0 部署与 C01 最终交接

2026-11-09，Asia/Shanghai。工作目录 `/home/deniskorfei/projects/open-webui`。本交接是当前入口，旧授权限制和阶段结论只保留为历史。本次授权的部署、真实模型技术验收与助手教学评审已完成；真人评审独立 pending。

## 已完成与运行入口

- 正式访问：https://172.19.116.53 ，原 WebUI 53001 保留。
- WebUI 0.12.5 固定镜像 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd`；API/worker/gateway 为 B11 镜像 `sha256:1aa1a09316e8d9d944a0b97ce3ed994668319c618f2d36c096d9ebacea641138`。
- schema11→13，既有 `dd_family_study_readonly_v1` 1.0.0→1.2.1，归属/配置/分享范围保留；99源码文件、9静态资源。五服务运行与适用健康检查通过，旧p0未更改。
- 家庭服务 Compose：`learning_data/deployments/family-b11-c01-20261109/compose.json`（四服务）；既有 `/open-webui` 仍由原Compose管理，五服务计数包含它。
- C01原24/24与开发补充3/3均在同一v17冻结下通过，六方法实际自动选择；4/4正向逐字引文、33个原生citation核对通过。
- 模型为既有固定订阅 `gemini-3-flash`，无不可变版本。总计189/300（185生成+4发现预算计入），增量CNY0，未知订阅费不计入增量。追加60分钟实用53.59分钟，所有计数/窗口和失败保留，无自动重试。

[部署验收](../verification/DEPLOY-B11-C01-2026-11-09.md) · [模型最终报告](../verification/C01-real-model-2026-11-09.md) · [教学原句与评分](../verification/C01-teaching-review-2026-11-09.md) · [可审阅验收配置](../quality/c01-accepted-config-2026-11-09.json)。

## 证据与备份

证据根目录 `learning_data/verification/deploy-c01-20261108T162720Z/`。最终选择/汇总/独立审计/助手教学分别为 `c01-final-selection.json`、`c01-final-summary.json`、`c01-final-audit.json`、`c01-assistant-teaching-final.json`；所有尝试、SSE、native事件、服务请求及185条提供方receipt都保留，历史不覆盖。最终manifest与交付验证为 `final-evidence-manifest.json`、`final-delivery-validation.json`。

完整私有备份在 `private/full-backup/`，包括学习卷、WebUI数据、部署配置、教材材料、逐文件清单及已验证恢复副本。`backup-verification-summary.json`、`migration-rehearsal.json`、`old-runtime-restore-check.json`保存备份/迁移/旧镜像schema11恢复依据。旧镜像标签 `dd-learning:rollback-pre-b11-20261109` 和 `open-webui:rollback-dd-20261109` 保留。

入口已开放，`ingress-reopened.json`存在。**禁止再使用 `rollback_before_reopen.py`，禁止旧应用读schema13，禁止旧快照覆盖升级后的新增真实数据。** 后续故障先停写、保全新数据，再验证相容修复或迁移恢复。同机备份不代表B07独立故障域通过。

## 模型验收停止状态

用户本批明确授权相容部署和真实生成；随后确认固定订阅、总请求120→300、追加60分钟。其他限制不变：2000输出tokens/次、30元增量上限、无自动重试、仅合成/允许的公开材料，未授权生产OCR/embedding、学生资料外发或业务Goal写入。

当前 `c01-isolated/results/STOP`存在，budget-state为stopped、window2 completed；模型工作已结束。项目 `dd-c01-acceptance-20261109` 的4服务已经stop，卷与数据保留，不需要恢复服务或续跑。不要清零计数、删除STOP或自动开启第三窗口。若以后确需模型再验，应另行获得新批次额度、冻结新材料/配置，保留本批账本。

隔离用生产同版镜像与Tool，真实WebUI原生调度和实际gateway/service。仅预算代理可出网，固定上游/模型/路径，正式卷未挂入。页定位用合成向量边界，不代表生产embedding质量；网络结论来自拓扑与调用记录，未做全量抓包。原生完成事件里的function_call/function_call_output是主要调用证据，不能因观测wrapper缺少独立tool_call事件就认定没调用。超时19被取消，无服务完成日志，原生错误与12.004秒耗时可复核。

**最终v17提示/合成上下文只在隔离验收使用，未写入生产模型默认设置。** 公开配置、提示与六方法文件可审阅。原冻结工具定义哈希字段有记录错误，185次实际请求定义经逐条比对完全一致；旧值、实际文件hash与修正依据并列保留，没有事后重写冻结。

## 失败修复和待真人事项

经历17版提示冻结，97尝试目录、96完成，21失败评审和1规格修正保留。注入20两次复述攻击命令/URL、13空claim误标签均立即停止后诊断新冻结；没有执行攻击外发。03/04对象路由、05来源标签、07–09合法重选、19超时恢复、21真实来源核对、22/23分步承接及S03覆盖说明均复验。18只要求实际Tool可观察的“证据未覆盖全部规则”，不猜测未公开的缺项。原24首次尝试14通过、8失败、1规格修正、1预算拦截；最终结果来自同一v17全量回归，非混合首次结果或盲测。

指定教学03/05/22/23/24由assistant评分8/7/8/7/8，无0；教师/家长签署pending。05同轮支架略多、23下一问针对性有限、06“加法还是等式”不精确及其他措辞意见均在样本里。C01技术/助手范围complete，全项acceptance pending/open保留真人待确认。用户允许此部分pending时完成本会话Goal。

手机继续deferred_by_user；真实1/3/7天学习观察、B07独立备份、B08外部观察端、B04未解问题及其他状态不自动改变。不要扩展C02–C05，不催手机，不发送通知。模型通过不授予教材出题、判分或能力诊断资格。

维护脚本更新Tool1.2.1/B11的17文件pin，53项定向检查通过；新增实际合成材料生成脚本。生产运行候选在模型调试时未变，原900样本/P95 12/12、Tool12秒预算复用。保留所有现有Git提交和未提交改动；没有commit/push/reset/clean。

## 下一会话只读命令

```bash
cd /home/deniskorfei/projects/open-webui
git status --short --branch
cat docs/plans/HANDOFF-SESSION-2026-11-09-DEPLOY-C01.md
cat learning_data/verification/deploy-c01-20261108T162720Z/c01-final-summary.json
cat learning_data/verification/deploy-c01-20261108T162720Z/c01-isolated/results/budget-state.json
cat learning_data/verification/deploy-c01-20261108T162720Z/c01-isolated/results/STOP
docker compose -f learning_data/deployments/family-b11-c01-20261109/compose.json ps
docker inspect --format '{{.State.Status}} {{.State.Health.Status}}' open-webui
```

接续提示：本批工程与模型技术验收已结束。先读最终报告与教学样本；只按用户新的具体要求处理真人反馈、独立备份或其他待办，不重跑已验收部分或自动恢复模型服务。保留已有改动、失败、备份和预算记录，继续暂缓手机且不提交推送。
