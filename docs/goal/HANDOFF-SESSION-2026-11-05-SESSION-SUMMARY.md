# DD-1.0 V1 会话总结与续跑交接（家庭数学版）

2026-11-06 当前最新：[自动升档改为四道不同题](../verification/practice-four-2026-11-06.md)。用户认为两道不足，采用3～5中的4道：同档连续独立答对4道不同题才尝试下一档，界面显示累计/剩余数；重复题不累加、错误/提示中断累计，主动重练可重新巩固。已上线Compose `compose-practice-four-20261106.json`，镜像 `sha256:d94346e8ec8fada893f288aac5fddd8f26a1b6078d4eb23b1af9bfd2cc64e6cc`，57文件/schema11。5项相关测试与线上核验通过，74题、原绑定/两档案/53次作答保持，WebUI/代理未重启，provider0。题库和原教材/OCR限制不变；保存当前输入后刷新。下文两题规则与旧Compose为历史，勿覆盖。保留所有未提交改动，不写Goal。

2026-11-06 当前最新：已上线[三档应用题与连续出题](../verification/adaptive-practice-2026-11-06.md)。新增60道生活应用题（二上第二/三/五单元36题，七上第二/五章24题），原14题保留，总74题。可选简单/正常/困难，默认根据独立答对与提示情况自动进阶；“继续出题”不重复本轮已做题，用尽明确提示；每题提示/答后折叠解析。29道来自固定commit开源题库改编、31道助手编写，逐题语义核查与独立复算，并非教师审核；其余章节学科仍未配题。当前Compose `compose-adaptive-practice-20261106.json`、镜像 `sha256:e40cec471ba75bd766d4cb0a9c5f3c9b94587f80238542f4a02c5b5615348e90`，57文件/schema11。40项相关测试及上线核查通过，原题/绑定/53次作答完整保留，13册PDF保持，原WebUI/代理未重启，provider0。家长保存输入后刷新即可，无需重绑。先读验证记录与[项目调研](../verification/math-practice-project-research-2026-11-06.md)，不要重新导入旧题库或用下文旧Compose覆盖。保留所有未提交改动、教材/OCR约定，不写Goal，不调用外部生成模型。

2026-11-06 当前最新布局：[目录缩窄与工具栏合并](../verification/reader-toolbar-layout-2026-11-06.md)。左目录136～168像素，教材页加宽；范围/展开/收起位于翻页跳转栏右侧并自适应换行。五种视口检查通过。当前Compose `compose-reader-toolbar-20261106.json`、镜像 `sha256:82a2388392bc6577a9775d1a6188a21b94924a7c3af87dbfbbf8082d0b3dc9b6`；学习数据及原WebUI/代理保持。此为HTML/CSS布局变更，原统一范围、可选章节和教材审核限制不变；保留未提交改动，不写Goal。下文旧部署为历史。

2026-11-06 当前最新：已上线[统一学习范围与单页教材阅读器](../verification/unified-textbook-reader-2026-11-06.md)。学科/课本统一选择，章节可选、默认整本书；挑战仅使用相应范围已配题，未配题只阅读。左侧教材目录、右侧单页，支持目录点选/前后页/页码跳转；原图点击放大，支持缩放、适应宽度、Esc关闭并保留位置。当前Compose `compose-unified-reader-20261106.json`、镜像 `sha256:417274d9a8da2af3d8982728d06488ded79443ad82e9130722b871c343aafb6e`，54项相关测试和上线检查通过，绑定/两档案/50次作答保持。14道原题未删除或新增，10道明确映射到新版教材；原4道二年级加减题不混入本册挑战。13册和未补教材/OCR双重审核限制保持。后文部署和“四页列表”是历史；保留所有未提交改动，不重绑、不写Goal。

2026-11-06 最新已上线：**多学科教材、章节顺序浏览、整体/单页折叠及每页内容标题**。先读[验证与部署记录](../verification/textbook-subjects-folding-2026-11-06.md)和[教材交接](HANDOFF-SESSION-2026-11-06-TEXTBOOKS.md)。二年级语文/数学/道法，七年级语数英/道法/历史/地理/生物，共13册/1,948片段、98章节区间；用户确认二年级学校暂未开英语，已写入持续约定。无关键词从章节起始页按四页一组浏览，关键词结果按书内页码排序，原图可整体或单页收起。当前Compose `compose-subjects-folding-20261106.json`，镜像 `sha256:32808e7a852fbf23c0e4ef16893cd9d561083ed82f5465b2c823d4b85b1b9434`；46项相关测试及上线核验通过，绑定/两档案/50次作答和其余计数保持，代理/WebUI未重启。刷新即可使用，无需重绑。二下数学仍待OCR双重审核，部分学科下册待补；练习仍原14道数学题，新增学科当前只提供教材阅读，其他年级尚未接入。下文各“当前/最新”均为历史阶段，部署和数量以本段为准；不写Goal，不提交改动，其余限制保持。

2026-11-06 最新：数学教材图片/公式/链接显示已修复并上线。二上/七上/七下检索结果统一展示原PDF页面，放大链接打开命中页；七上115/144页实物验证通过。当前Compose `compose-textbook-pages-20261106.json`，镜像 `sha256:4c068b2200c36d087dd520682aa2121447b0eedaf40484e9f57c4ed037e2d464`。62项相关测试通过、上线前后数据保持，代理/WebUI未重启。详见[展示修复记录](../verification/textbook-page-display-fix-2026-11-06.md)。旧纯文本展示及旧Compose为历史，勿用旧配置覆盖；其他限制不变。

2026-11-06 同日后续：按用户建议核查GitHub，已找到并下载两本二年级新版下册完整PDF。语文采用 `hantang/yuwen` docs分支的可提取文字版，已导入129片段，当前12册/1,875片段；数学106页图片版来自 `LYUGUISONG/Textbooks`，完整图已备齐待OCR及逐页双重审核。详见[GitHub实物核查](../verification/github-textbook-sources-2026-11-06.md)和最新教材交接顶部。此前下载受阻已解除，无需用户处理官网验证码；原部署及其余限制保持。

最新续跑补充（2026-11-06）：先读[人教新版教材与OCR双重审核交接](HANDOFF-SESSION-2026-11-06-TEXTBOOKS.md)及[持续教材约定](TEXTBOOK-POLICY.md)。11本新版/1,746片段已新增入WebUI，原13文件保留归档；家庭版数学教材章节查阅已上线，当前Compose为`compose-textbooks-20261105.json`、镜像`sha256:1ff715a05f242b3b1eb492b36fb8f368906f1ad01702ff0bc034f3c0cd687a00`。二年级数学/语文下册完整下载与逐页双重审核未完成，未入库；三个片段核验不等于全书通过。用户已授权这两册公开教材本机离线OCR，并明确要求独立验证数学/内容正确性，不能仅对上图片。81项相关验证通过，更新前后真实作答50次、绑定/数据保留。既有登录勿重绑；旧Compose勿up；其余限制和完整V1状态不变。

最新续跑补充（2026-11-05 21:44）：**单元 / 章节选择已上线**，先读取 [单元选题交接](HANDOFF-SESSION-2026-11-05-CHAPTERS.md)。当前 Compose 为 `compose-chapters-20261105.json`，按所选单元出题、下一题和到期复习；更新前后学习计数一致。真实两档案已有 43 次已判分作答（二年级 6、七年级 37），错题试用和实际刷新/切换反馈仍待确认。下文旧部署、零作答及待绑定状态均为历史；现有登录绑定保留，所有未提交改动和执行限制继续适用。

最新续跑补充（2026-11-05 20:54）：**家长真实登录与启用码绑定已完成；错题自动知识目标和用户选择的活泼闯关界面已上线**。当前以[数学探险队交接](HANDOFF-SESSION-2026-11-05-GAME-UI.md)为最新入口，Compose 为 `compose-game-ui-20261105.json`，两档案真实练习仍待家长完成。下文首次绑定待办和旧镜像/命令为先前历史，续跑先读取新交接；所有执行限制和完整 V1 状态保持。

日期：2026-11-05（Asia/Shanghai）  
工作目录：`/home/deniskorfei/projects/open-webui`  
分支：`main`；HEAD：`0fa02712ceda049b14d4b556faef3fdb2fa985ed`

本会话的可用交付范围已经收窄为：一个现有 Open WebUI 家长账号，切换七年级和二年级两个数学学习档案。用户明确要求先自己使用、避免过度工程化，并授权继续到家庭版生产上线。家庭版已经部署并运行；设备证书也已安装并通过系统 TLS 校验。下一步是家长真实首次登录、一次启用码绑定和实际使用反馈。

## 已完成的任务

| 任务 | 当前结果 | 证据 |
| --- | --- | --- |
| 交接与状态核对 | 已读取旧会话总结、续跑文件、W04/W06、W07/W10、STATUS/TASKS/BLOCKERS/DECISIONS、QA、Git 和只读 Goal API | 本文件及旧交接文件 |
| W04/W05/W06 | 工作台、共享上下文/Tools、人工变式审核/冻结版本已本地实现并有合成验证；本会话没有重跑 | [`HANDOFF-SESSION-2026-11-04-W04-W06.md`](HANDOFF-SESSION-2026-11-04-W04-W06.md) |
| W07/W08/W09/W10 | 独立 sidecar/代理、固定本地镜像、隔离故障/停止、局部恢复、监控设计和新隔离组合已有本地证据；完整架构恢复和正式运维仍不是家庭版前置 | [`HANDOFF-SESSION-2026-11-04-W07-W10.md`](HANDOFF-SESSION-2026-11-04-W07-W10.md) |
| 家庭数学版部署 | `dd-family-math` 独立 Compose 已部署；API、worker、gateway、proxy 均保持运行；现有 WebUI 容器、数据库、模型和 Tools 未改 | [`HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md`](HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md)、[`deployment-final.json`](../../learning_data/deployments/family-math-20261105/deployment-final.json) |
| HTTPS 与根证书 | 入口 `https://172.19.116.53/learning/auth/login`；根证书已安装到 Windows `CurrentUser\\Root`；Windows 默认 TLS 校验通过，IP SAN 和证书链验证通过 | [`windows-certificate-trust.json`](../../learning_data/verification/family-pilot-20261105/windows-certificate-trust.json)、[`production-final-checks.json`](../../learning_data/verification/family-pilot-20261105/production-final-checks.json) |
| 数学内容 | 已准备 14 道编写起步题：二年级 8 道（100 以内加减、表内乘法），七年级 6 道（减去负数） | 家庭版交接与部署数据库检查 |
| 家庭功能 | 档案切换、选题、提交判分、刷新恢复、手动错题本已覆盖；上传/OCR、诊断、变式入口隐藏，学习模型/OCR 外发关闭，预算为 0 | [`browser-final-report.json`](../../learning_data/verification/family-pilot-20261105/browser-final-report.json) |

## 当前可以使用的入口

- HTTPS：`https://172.19.116.53/learning/auth/login`
- 原 Open WebUI HTTP 入口仍保留：`http://172.19.116.53:53001/`
- 当前数据卷：`dd-family-math_data`
- 当前部署规模：1 个家长账号预建记录、2 个学习档案、14 道题；首次绑定前 `identity_bindings=0`、`attempts=0`、`provider_calls=0`。
- 四个服务当前状态可用以下命令查看：

```bash
cd /home/deniskorfei/projects/open-webui
docker compose --env-file /dev/null -p dd-family-math \
  -f learning_data/deployments/family-math-20261105/compose.json ps
```

## 还没有完成的事项

### 家庭版真正开始使用前

1. 在已安装证书的 Windows 设备打开 HTTPS 入口。
2. 用已有 Open WebUI 家长账号登录；这一步尚未输入真实凭据。
3. 从私有文件 [`家长首次使用.txt`](../../learning_data/deployments/family-math-20261105/家长首次使用.txt) 读取一次启用码完成绑定。不要把启用码写入公开文档或聊天记录。
4. 选择七年级数学和二年级数学各做一道题，确认判分、刷新恢复、档案切换和手动错题本。
5. 记录实际使用中需要补充的数学题型、年级范围和界面问题；这比继续做商业化或复杂运维更优先。

证书安装已完成，但家长首次绑定和真实学习观察仍未完成。其他设备若需要访问，应在该设备导入同一根证书；不要把根证书私钥或部署目录中的秘密文件外发。

### 完整 V1 暂缓项

这些项目不阻塞当前两人数学版：真实模型/OCR、学生资料外发、真实 provider 账单、完整跨组件 RPO/RTO、复杂监控、商业化功能、其他学科、正式 Tools 模型回调、人工质量抽检和 7–14 天正式试用。原完整 V1 的 T/QA 状态保留，不能因为家庭版部署而整体改成 verified 或 complete。

W04/W05/W06 的本地实现不等于正式模型回调验收；W07/W10 的隔离证据不等于完整生产恢复验收。旧 P0、四格式验证和旧候选均保留，不需要无变更重跑。

## 下一步顺序

1. 新会话先读取本文件，再读取家庭版交接、STATUS/TASKS/BLOCKERS/DECISIONS 和 Git/只读 Goal 状态。
2. 只做家庭版首次使用支持：确认服务仍运行，协助家长登录/启用码绑定，观察两个档案各自的题目和进度。
3. 根据真实反馈补充少量数学题或修复直接影响使用的问题；每次变更后只运行相关的最小验证。
4. 需要备份时使用已有 SQLite 快照命令；停止/恢复使用家庭版交接中的 `stop --timeout 60` 与 `start`，不要删除 `dd-family-math_data`。
5. 只有用户另行提供真实模型/OCR、资料许可、预算、人工审核和正式运维条件时，才恢复完整 V1 的后续门槛。

## Git、Goal 与执行限制

- 工作区有大量既有未提交改动，全部保留；不 `reset`、`checkout`、`clean`、`commit` 或 `push`。
- 本会话未修改根 `docker-compose.yml`、`batch_ingest.py`、既有 WebUI 数据或环境秘密。
- 只读 Goal API 当前返回 `goal: null`；不要创建、更新或完成 Goal。仓库中的完整 V1 Goal 状态仍是历史 `blocked`，不因家庭版部署而提升。
- 不调用真实模型/OCR，不外发真实学生资料；家庭版继续使用 mock、外发关闭、学习预算 0。WebUI 原有聊天费用不属于学习服务台账。
- 保持当前 IP 和现有 HTTP 入口，不自行改变正式容器、网络、证书或 Tools；家庭版服务按现有部署记录保持运行。
- 本总结没有重跑 P0、四格式、旧全量或已通过的 W04/W10 验证；引用的是已有证据。

## 新会话续跑命令

把下面整段复制到新会话即可：

```text
继续 DD-1.0 V1 家庭数学测试版。工作目录：/home/deniskorfei/projects/open-webui。

先读取 docs/goal/HANDOFF-SESSION-2026-11-05-SESSION-SUMMARY.md，再读取 docs/goal/HANDOFF-SESSION-2026-11-05-FAMILY-MATH.md、docs/goal/STATUS.md、TASKS.json、BLOCKERS.md、DECISIONS.md，并检查 git status --short --branch、家庭版 Compose 状态和只读 Goal API。

当前交付范围是一个现有 Open WebUI 家长账号切换七年级/二年级两个数学档案。家庭版 dd-family-math 已部署在 https://172.19.116.53/learning/auth/login，四个服务保持运行；旧 HTTP 53001、现有 WebUI 容器/数据库/模型/Tools 未改。设备根证书已安装到 Windows 当前用户 Trusted Root，Windows 默认 TLS 校验通过；现在只剩真实家长首次登录、一次启用码绑定和实际使用反馈。不要重复导入证书或重建数据卷。

先帮助完成首次使用：已有 Open WebUI 家长账号登录，从 learning_data/deployments/family-math-20261105/家长首次使用.txt 读取启用码一次完成绑定，然后测试两个档案各一道数学题、判分、刷新恢复、切换和手动错题本。不要在公开输出中打印启用码。

数学版目前有二年级 8 道、七年级 6 道编写起步题；上传/OCR/诊断/变式入口隐藏，mock/外发关闭/学习预算 0。根据真实反馈补少量题目或直接影响使用的修复即可，不要过度工程化。

保留全部未提交改动；不要 reset/checkout/clean/commit/push；不要读取或修改根 docker-compose.yml、batch_ingest.py、既有 WebUI data/环境秘密；不要调用真实模型/OCR、外发学生资料、创建/更新/完成 Goal；不要重跑 P0、四格式或无变化的旧验证。完整 V1 的商业化、复杂监控、完整恢复、其他学科和真实 provider 继续暂缓。
```

## 收尾核对

本次仅新增本交接和续跑指令，没有改业务代码、运行配置或生产数据。已有最终检查显示：运行镜像为 `sha256:6432f2175659cd3f496b05efb8fdffe69969c9b12dff8d48962850a752f8336a`，schema revision 11，数据库 integrity `ok`，既有 WebUI 未变，真实模型/OCR调用为 0，服务保持运行。证书安装和 TLS 结果以 `windows-certificate-trust.json` 为准；生产检查当时的 `user_login_and_device_CA_import_pending=true` 是历史检查时点，之后证书安装已完成，家长登录仍待完成。
