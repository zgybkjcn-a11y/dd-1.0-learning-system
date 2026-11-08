# DD-1.0 当前状态与交付清单

最新执行（2026-11-08）：A09 本地静态交付准备已完成，工程 ready，发布与家长设备验收 pending，总状态 open；下一项可继续 **B01**。[本地验收](../verification/A09-static-samples-2026-11-08.md)记录 30 项定向检查和隔离 nginx 候选 4 / 回退 3 条路由通过；[交付与设备检查表](../open-webui-reuse/static-samples-delivery.md)已就绪。九文件固定提交与旧样本一致，当前 A07 桥接未混入。以下各批次更新保留历史语境。

最新本地进度：**A08已完成，下一项A09**。[54项与原生迁移/六方法/历史/缓存验证](../verification/A08-tool-lifecycle-2026-11-07.md)通过，[升级回退操作单](../open-webui-reuse/tool-upgrade-rollback.md)与独立维护包就绪。正式Tool未读取或升级，A07服务/Tool1.2.0候选保持原样；下方各批次结果保留历史语境。

最新本地进度：**A07已完成，Tool候选1.2.0，下一项A08**。五片段已接入服务/网关/Tool及引用回链，默认关闭、未部署；688项单元/契约、6项浏览器、原生六方法/4引用通过。[A07验收](../verification/A07-runtime-passages-2026-11-07.md)与[运行契约](../open-webui-reuse/textbook-passages-runtime.md)。下方线上观察时间保持A01，不冒称刷新生产。

核对时间：2026-11-07 17:00:50–17:00:53（Asia/Shanghai）。任务：A01。机器可读事实见 [current-manifest.json](current-manifest.json)，本次核对方法和验收见 [A01 验证记录](../verification/A01-current-state-2026-11-07.md)。这是带时间的状态快照，不是新发布记录。

执行更新：A03 已完成[可移植测试基础](../TESTING.md)，干净环境 **503 项单元/契约 + 12 项浏览器通过，零失败、零跳过**，详见[A03 验证](../verification/A03-portable-tests-2026-11-07.md)。GitHub 自动检查为本地候选，远端未执行；实物教材组未运行。下方运行状态仍沿用 A01 的观察时间，A03 未再次查询运行组件或改变部署。A02 已完成[两组候选整理](A02-candidate-delivery-2026-11-07.md)，[本地验证](../verification/A02-candidate-delivery-2026-11-07.md)通过、待提交。A02 没有修改代码或重跑测试。A04 已完成[故障分类与恢复](../open-webui-reuse/study-error-recovery.md)，[552 项单元/契约及原生六方法验证](../verification/A04-study-errors-2026-11-07.md)通过，候选 Tool 1.1.1；本批未重跑浏览器。A06 已完成[冻结评测与基线](../verification/A06-retrieval-evaluation-2026-11-07.md)，73 项合成测试通过；新试点召回 2/20、无依据拒绝 2/10，质量未达标。A05 已完成[有界检索与不足判定](../verification/A05-chapter-retrieval-2026-11-07.md)，补充集召回 20/20、拒绝 10/10、泄漏 0/10，241 项单元/契约、4 项浏览器及原生六方法通过；A05当时Tool候选1.1.2、下一项A07；当前已由上方A07更新。

当前仓库为 `main`，HEAD `deef3199f558ba72bbe3f2ff0c704586674a2232`；本地 `origin/main` 指向同一提交，本次未访问远端。开始时有 19 个未提交/未跟踪文件，逐文件 SHA256 保存在清单的 `workspace.input_dirty_files`。这是本批开始前的指纹，不包含后来修改的 A01 文档，也不代表线上版本。原有业务候选保持原样。

## 组件状态

| 组件 | 当前状态 | 依据与验收范围 |
| --- | --- | --- |
| 家庭 API / worker / gateway | 已部署；三者同一镜像 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0` | 本次定向检查均 running，API healthy；另两者没有 Docker healthcheck，不能记为 healthy |
| 主站 Open WebUI | 已部署；镜像 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd` | 本次 running / healthy；0.12.5 版本号沿用固定镜像的[既有原生验证](../verification/main-chat-study-2026-11-07.md)，没有读取正式 data |
| nginx 代理 | 已部署；镜像 `sha256:1d13701a5f9f3fb01aaa88cef2344d65b6b5bf6b7d9fa4cf0dca557a8d7702ba` | 本次 running；主站实际 `set $webui http://open-webui:8080` 后 `proxy_pass $webui`，不能只搜索直接写出的 proxy_pass 判断目标 |
| 主站静态资源 | 在线 `chat-20261107` | 三条 alias 与匿名 HTTPS 文件哈希一致，均 200 / no-store；未发送登录或聊天请求 |
| 三个静态样本 | 样本源码已提交、A09准备脚本未提交；未上线 | 九文件来自固定 `deef3199`，与历史样本一致；新独立包与原资源回退已验证。工作树 A07 桥接另属片段候选。[A09验收](../verification/A09-static-samples-2026-11-08.md)记录30项及4+3路由通过；家长反馈 pending |
| 私有 Tool `dd_family_study_readonly_v1` | 历史发布记录为 1.0.0 | 仅沿用注册/验证记录，正式源码和分享范围本次未重读，当前值为 unknown；不得据此重跑注册或重绑 |
| 页级证据链 / Tool 1.2.0 | 未提交、未部署候选 | A07默认关闭片段接入；688项单元/契约、6项浏览器、原生六方法/4引用通过。A05的1.1.2结果保留历史；候选镜像尚无 |
| 七上第二章五片段 | 已接本地候选服务/Tool，默认关闭 | 书内 27/31/40/41/42 页，PDF 34/38/47/48/49 页；清单及源 PDF 哈希匹配；助手复核、非整页/教师审核、非判分依据 |
| 离线检索评测 | A06 本地交付完成、未提交 | 40 问冻结试点，召回 2/20、拒绝 2/10、泄漏 0/10、来源/引文 11/11；两次结果一致，质量改进待 A05 |
| 五片段检索改进 | A05算法原样抽取，A07已接本地服务 | A06 回归 40/40、补充集 40/40；召回 20/20、拒绝 10/10、范围泄漏 0/10、来源/引文 22/22。整册向量召回仍不完整 |
| 既有Tool维护候选 | A08本地通过、未正式应用 | 54项及固定WebUI原生schema/历史/缓存验证，操作单与独立维护包就绪 |
| 教材与题库 | 历史清单：13 册 / 98 目录区间 / 74 题 / 20 题映射 18 概念 | 沿用[项目评审](../PROJECT-REVIEW-2026-11-07.md)，本次不重计正式数据库；二下 OCR 106 页已完成，整页双重审核通过 0 页 |
| API 契约 | A07本地快照73 paths / 35 schemas | 临时服务OpenAPI与快照一致；不代表已上线 |
| 可移植测试基础 | A03 本地验收通过、未提交 | 27 个依赖及分发哈希锁定、合成 PDF、根测试隔离、可配置 Chromium 和 515 项必要检查；GitHub workflow 已编写、远端未运行 |

当前 Compose 固定为 `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`。主站入口 `https://172.19.116.53/`；活动代理配置为同目录的 `main-study-20261106/nginx.conf`。不用旧 P0 容器或旧 Compose 推断/替换这组部署。

## 源码、构建与内容身份

家庭服务对应的历史源码封包为 `learning_data/releases/dd-study-workbench-20261106-source-v2/`，profile `reuse-runtime-study-workbench-v1`，70 文件，声明 schema11。封包时 Git SHA 为 `0fa02712ceda049b14d4b556faef3fdb2fa985ed`，**当时工作树也有改动**，因此以源码集合哈希定位：

- source set：`ad18b0aa5e0670e694939facb018ab5ca8380fa04849e1f71347f03e8bd9b727`。
- source archive：`baf54a0124c02bfe61047346cd9e4dc524a868cfa673c8d41270110276907b8e`，本次实际归档哈希匹配。
- 构建记录：`learning_data/verification/study-workbench-20261106/build/build.json`，源码集合/归档与封包对应，image ID 与当前三服务对应。

封包 manifest 自身的 `image_digest=null` / 未部署措辞保留封包时语境；运行结论来自独立[构建与发布记录](../verification/study-workbench-2026-11-06.md)和本次容器观察。当前运行数据库 schema 未读，镜像的 registry digest 未知，不以本机 image ID 冒称仓库发布 digest。

| 对象 | SHA256 | 本次核对方式 |
| --- | --- | --- |
| 线上 study.js | `6e2325ad44c246351e00f4f8bc480dbcdcef4912f90085696793b208524db7e4` | HTTPS 字节与 chat 快照一致 |
| 线上 study.css | `b7ea956e897b0bf12a26f55e0213b794a924ff8c10e02647e83de8027514627a` | HTTPS 字节与 chat 快照一致 |
| A01线上及当时样本 family-bridge.js | `8bfe564373befe4d3bb64cfc4d91b67880545217f00d293da415938cce4f0347` | HTTPS / 快照 / HEAD / 候选一致 |
| 样本 study.js | `fe26d4d4ae6834944fd093d9954808b118b7706daeb1aa42df459090cf75518d` | HEAD / 工作树 / 候选 / 原记录一致 |
| 样本 study.css | `952fddccb9e5366d350b0bd9bebf88fe76ebeea6861bed9b6d9fa7e697af292a` | HEAD / 工作树 / 候选 / 原记录一致 |
| Tool 1.0.0 | `733ad01dc38ed6b09fcae69047ff731e0eb83d59b0a2dd2432595a3508c6a650` | **历史注册证据，非本次正式库回读** |
| A05历史Tool 1.1.2 | `a158f47774062a454d6c12bb9944d1b480542ddafba384b71fd0103987afedd1` | A05 本地候选、149 文件副本及原生加载结果一致；旧 1.1.1 保存于 A04/A06 包 |
| A07当前Tool 1.2.0 | `23fc5c2558a0141750031acaee434f7b0abd81d884974e8d15ee781c1f2404d7` | 本地源码与原生六方法/4citation一致 |
| A07候选family-bridge.js | `876cb599ea7c1729bde5964138b4f22d5fdcd8ea6a580004c6b4807b4f3c7ab7` | 新增片段回链；历史静态样本快照不改，部署本桥接需配套A07服务 |
| 五片段 passages.json | `d1bf256db814afcf35ff22f28ad32fd4577b4608e12f9d069b7f72cfc8cacd63` | 本地忽略目录中的文件哈希 |

五片段复核记录均为 revision 1、2026-11-07 至 2026-12-07，enabled=true、未解决问题 0；本次日期处于该区间。A01只核对元数据与PDF哈希；A07已执行完整材料校验和既有题集回归，未重新学科复核或教师签署。使用时按服务器当前日期验证，到期停止并复核，不能用历史 `--as-of`；A07已冻结北京时间valid_until含当天、次日零点失效。保留 `teacher_reviewed=false`、`fully_reviewed_pages=0`、`eligible_as_grading_basis=false`、`can_answer_from_textbook=false`。教材正文和图片继续仅存本地忽略目录。

## 兼容组合与回退

| 组合 | 可据以开展的工作 | 尚未证明或禁止混用的部分 |
| --- | --- | --- |
| 当前家庭镜像 + WebUI 0.12.5 + chat 静态 + 历史 Tool 1.0.0 | 保留当前运行组合；容器/静态已复核 | 正式 Tool 本次未回读；真实聊天/设备反馈未新增 |
| 当前后端 + 三个静态样本 + 原 Tool | A09 可独立交付准备，已有隔离浏览器/nginx 证据 | 未上线；先满足 A03，不必等待片段服务或 Tool 升级 |
| 页级服务/覆盖不足候选 + Tool 1.1.2 | A05 241 项单元/契约、4 项浏览器与原生六方法支持本地接续 | 未封包为镜像、未部署；完整错误细分需相容网关/服务，不能单独把新 Tool 装到当前旧后端 |
| A07后端 + 历史Tool 1.0.0/1.1.2 | 使用hash一致的历史源码独立检查通过 | 只保留页定位，不获得片段正文权限；未回读正式Tool |
| 五片段 + A07服务/Tool1.2.0 | 本地接入与回链通过，默认关闭 | 未部署；真实模型/家长体验未验收，继续A08 |
| Tool1.2.0 + A05页级服务 | A05源码副本仅替换Tool，原30项集成检查通过 | 不等于缺少页级字段的历史线上服务兼容 |

静态样本回退基线是 `chat-20261107` 和 `learning_data/verification/main-study-samples-20261107/candidate/nginx.before.conf`；该文件哈希 `fcb3e8131090dbc5f89ad2b07186b0d17b897658a1c8cf9e18562bd3b7d0676a` 与本次活动配置一致。候选 `nginx.candidate.conf` 哈希 `e6c6b11d1696b79a766249c57baa6de237b4296f2dd0bec58c31d95678b19756`，仅作为后续 A09 的候选引用；正式应用/回退仍需检查当时配置和候选操作单，本次没有 reload。

家庭镜像保留上述当前 image ID/Compose 作为未来升级的输入；跨数据库/附件恢复仍待 B07。A08既有ID升级与哈希保护回退已在临时库通过，正式应用仍未执行，不能用注册脚本覆盖不同源码。片段尚无线上部署可回退。以上回退引用没有冒充本次已完成恢复演练。

## 接续

A01 验收“现状、身份、兼容、回退引用和入口一致”，A03 验收本地可移植测试与自动检查候选，其他任务的发布/实际体验状态分别保留。A02 本地交付整理已通过，46 个文件组成 U1/U2 两组，提交 SHA 均为 null，总状态保留 open。A04 本地故障分类与恢复验收通过，作为 A02 后的独立增量保存；A02 清单哈希只对应其固定审阅包。A06 本地评测交付已完成，基线检索质量未达标，独立增量与真实材料仍分开保存。A05 已完成本地有界试点与旧路径覆盖不足提示，质量结论仅限所测范围。A07已完成本地接入；A08已完成本地机制；下一项 **A09：三个静态样本交付与设备体验**；提交等待不阻塞本地工作。材料盘点不等于备份/恢复通过。进度以[25 项台账](../plans/dd-next-work-tracker.json)为准，继续指令见[续接文件](../plans/RESUME-NEXT-WORK.txt)。
