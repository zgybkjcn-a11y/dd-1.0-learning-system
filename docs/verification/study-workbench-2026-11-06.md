# 理解工坊接入家庭工作台

2026-11-06，承接[服务与 Tools 参考验证](math-reference-tools-2026-11-06.md)。用户要求继续，已把参考能力直接接入家庭工作台。正式 Open WebUI 数据读写限制保持，原生 Tool 仍为可导入候选，未注册到正式 WebUI。

**当前已上线。** Compose：`learning_data/deployments/family-math-20261105/compose-study-workbench-20261106.json`；镜像：`sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`。入口仍为 `https://172.19.116.53/learning/auth/login`，无需重绑。保存输入后刷新，在课本操作区点击“打开理解工坊”。

当前课本操作区新增“打开理解工坊”。展开后显示当前范围的三个阅读步骤；数学已映射范围另有知识卡、先修参考、本册原页放大和参数演示。支持下载当前范围的 Markdown 学习卡和 Mermaid 文本。

档案切换会清空并收起面板；换书/章节会清空旧内容并按新范围重新读取。旧范围的延迟响应不能覆盖新范围；下载也检查当前档案/书/章节。二上第二单元仅演示乘法，第三单元才展示两种除法；七上第五章展示方程及等式性质参考，不显示数轴。其他学科标明仅阅读问题串，不提供未核对的答案或精确概念页码。

`learning_service/study_ui.py` 为可信界面的本地片段，CSS/HTML/JS注入已有工作台；接口沿用共享选择与上下文版本。服务响应的概念及先修资料直接来自版本冻结的数学参考，没有新增判分权。用户文本不经过innerHTML，下载只含本地编写的公共参考。演示参数不写库、不影响作答或难度。

已通过手机390/桌面1280两个实际工作台浏览器测试：登录及两档案、章节刷新恢复、七学科、延迟响应隔离、乘除/数轴算术、原页解码放大、两类下载、0横向溢出、0页面异常、0新增作答、0provider。证据在 `learning_data/verification/math-reference-tools-20261106/workbench-browser/`。

最终125项相关服务/Tools/参考范围/网关/上下文/打包/题库测试通过，日志 `learning_data/verification/study-workbench-20261106/service-tests.log`。另有2项工作台浏览器、2项既有四题升档/连续练习浏览器回归、2项最新离线页浏览器通过。原生OpenWebUI0.12.5加载15方法的合成测试亦通过；测试没有真实模型调用。

此前封装的source-v1/镜像/Compose候选保持历史，未用于覆盖当前部署。本次工作台版本另行封装为新候选，基于当前四题Compose只换API/worker/gateway镜像；保留卷、绑定、已有题目和作答、proxy与正式WebUI。实际构建/上线状态及验证记录以 `learning_data/verification/study-workbench-20261106/` 为准。

新source候选为 `learning_data/releases/dd-study-workbench-20261106-source-v2`，70文件，schema11，source set `ad18b0aa5e0670e694939facb018ab5ca8380fa04849e1f71347f03e8bd9b727`。使用本机固定依赖和已核查的OCI基镜像，`--network=none`无缓存构建；镜像在临时合成库中启动实际HTTP服务后验证通过。历史数学参考/practice/textbook/schema候选继续可验证。

上线前在线备份：`learning_data/family-backups/family-study-workbench-preupdate-20261106`，SHA256与SQLite integrity通过。上线前后题目/版本74、档案2、绑定1、作答/判分67、provider0一致；原记录ID完整保留，原题内容和绑定哈希一致；所有13册PDF哈希有效。正式WebUI与proxy的容器ID和启动时间不变。HTTPS健康200、登录跳转正常。没有重建卷、重绑、重跑题库导入或写生产向量。

部署证据：`preupdate.json`、`deployed-verification.json`及`build/build.json`位于同证据目录。新学习API已发布；正式WebUI Tools记录仍未写入，不能把原生加载器合成验证等同正式Tools已注册。
