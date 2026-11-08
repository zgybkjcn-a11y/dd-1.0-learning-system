# A01：现状核对与交付清单验证

日期：2026-11-07（Asia/Shanghai）。执行角色：工程执行者（Codex）。任务输入：[实施方案 A01](../plans/DD-1.0-NEXT-IMPLEMENTATION-2026-11-07.md)、[工作计划](../plans/DD-1.0-WORK-PLAN-2026-11-07.md)、计划初始台账及相应历史验证记录。

交付：[当前状态说明](../releases/current-state.md)、[机器清单](../releases/current-manifest.json)，并同步文档总入口、复用入口、release 历史入口、计划进度和续接指令。仅完成 A01 本地文档交付，不表示其他候选上线或家长/真实模型验收。

## 输入与观察

仓库 HEAD `deef3199f558ba72bbe3f2ff0c704586674a2232`。初始 19 个脏文件逐文件哈希在本批独立忽略目录 `learning_data/verification/a01-current-state-20261107T0858Z/workspace-before.json`。其中原有业务源码、测试和历史验证保持；本批允许修改的计划/入口文档保存修改前副本至 `documents-before/`，可只撤销 A01 编辑而不覆盖之前的改动。

观察窗口为 17:00:50–17:00:53。`observations.json` 保存字段白名单结果，`collect.py` 保存实际收集步骤；重新观察必须使用新的证据目录，不能覆盖这次结果。命令范围：

```bash
git status --short --branch
git rev-parse HEAD
git diff --stat
docker compose --env-file /dev/null -p dd-family-math \
  -f learning_data/deployments/family-math-20261105/compose-main-study-20261106.json ps
```

另外定向 `docker inspect --format` 读取五个目标容器的名称、ID、镜像、状态、启动时间、health；没有输出完整 inspect、环境或 Compose config。首次模板访问缺省 Health 字段失败，改用 `index .State "Health"` 后成功，缺 healthcheck 保持 null。没有因此修改或重启容器。

仅匿名 GET `/static/loader.js`、`/static/custom.css`、`/static/dd-family-bridge.js`；使用本地公开根证书验证 TLS，禁用环境代理和重定向，不附 Cookie。读取活动 nginx 的 alias 和变量形式主站上游；读取候选/源码封包/历史构建清单并计算文件哈希。没有查询模型、embedding、生产检索或账号/聊天 API，没有读取正式数据库和秘密。

## 本批验证结果

| 核对 | 结果与限制 |
| --- | --- |
| 运行目标 | 五容器 running，API 和 WebUI healthy；另外三个无 healthcheck。镜像符合计划基线 |
| 静态发布身份 | 三份 HTTPS 文件均 200 / no-store，逐字节哈希等于 chat 快照；没有观察到静态样本发布 |
| 家庭镜像来源 | 70 文件源码封包的 source set / archive 与历史 build.json 一致，实际归档哈希一致，image ID 匹配当前三服务；没有重新构建或重读运行源码 |
| 三样本候选 | 9/9 文件的 HEAD、工作树、候选快照和原验证哈希一致；候选 before 配置与活动配置一致 |
| 页级证据与离线样本代码 | 7 + 2 = 9 个文件匹配各自原验证 source manifest；不重复跑历史 117 / 29 项业务测试 |
| 五片段材料 | 清单和源 PDF 哈希匹配；五个 enabled/revision/复核日期/有效期记录可定位；不包含新学科复核或整页通过结论 |
| 本地 API 契约 | JSON 71 paths / 24 schemas；未读取运行 schema 或调用正式契约端点 |
| 文档与台账 | 入口同指当前清单；引用有效、组件状态/证据齐全、25 项编号和依赖无环、仅 A01 完成，下一项 A03；详细结果见本批 `validation.json` |
| 原工作区保护 | 按初始逐文件哈希核对；除本批明确修改的入口/计划文件外，所有初始文件一致；未修改业务代码或 Goal 文件 |

本次清单/链接/哈希/状态一致性检查 **29 项通过、0 项失败**，`git diff --check` 通过；执行器和逐项结果在本批 `validate.py` / `validation.json`。14 个非本批编辑的初始文件逐文件哈希不变，另外 5 个初始文件仅更新入口/计划/接续；其余 24 项任务逐字段不变。本次没有新增业务测试，collected/passed/failed/skipped 不适用，不能把文档检查计入业务通过数；历史测试结果在机器清单中均标记 `rerun_in_A01=false`。

## 差异、未核对项与后续

未发现镜像、静态快照、Tool 候选或片段清单偏离计划基线。需要校正的是入口的历史语境：11-04 的未部署、11-05 的 14 题以及旧交接的“三样本尚未实现”不再代表当前交付状态；原历史文件保留，入口明确指向本次清单。

正式 Tool 当前源码/分享范围、运行数据库 schema/题量、真实家长设备体验和真实模型引用效果均未在本批重验，未知项显式 null 并说明原因。旧 Tool 配新后端属于兼容设计，仍待 A07 独立验证；新 Tool 配旧后端不受支持。静态候选不依赖片段接入，可在 A03 后由 A09 单独推进。

本批未提交、推送、发布、注册或重绑 Tool，未重建卷、更新向量、调用真实模型/OCR、通知他人或写 Goal。A01 文档回退仅按 `documents-before/` 对照撤销本批编辑，并移除本批新增说明/清单；不要 reset/clean 工作区。线上没有本批变更需回退。

下一项为 A03，先审计测试依赖、固定浏览器路径与真实教材材料依赖，再建立原创合成夹具、必要测试分组和干净环境复现入口。原 P1 58–101 小时估算保留；A01 实际耗时另写台账，不把一次文档核对速度外推到后续工程任务。
