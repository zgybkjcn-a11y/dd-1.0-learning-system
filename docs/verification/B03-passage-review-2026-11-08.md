# B03 片段复核工作台验证记录

日期：2026-11-08（Asia/Shanghai）；工程执行与内容复核角色：assistant。本批完成一个原生 PDF 片段的本地复核工作台，工程 ready、本地验收 passed、候选交付，B03 本地出口 complete。未提交、推送或部署；主站运行接入、教师签署、完整页审核与家庭设备体验不在本次通过范围。

## 范围与实现

独立证据目录：`learning_data/verification/b03-passage-review-20261108T030856Z/`。开始时 `main` 有 B01/B02 的28个未提交文件；`inputs-before.json` 与 `baseline-source/` 保存原内容，另固定318个 B01/B02/五片段历史证据文件。新代码独立存放在 `passage_review.py`、`passage_review_web.py`、`passage_review_ui.py` 和 `scripts/passage_review_workbench.py`，使用新的工作目录与审核 SQLite 日志，纯导入不建库。没有修改家庭运行服务、A07运行模块、旧质量校验器、旧题库/概念库或B02实现。

工作台提供原图、转写、上下文与独立推导三栏；手机顺序排列，可放大原页。输入来自固定A07有效片段，但新工作目录先置待核，不沿用旧通过标志。新修订保存修改原因，绑定文本、上下文、PDF来源、双页码、原图及原生提取文字哈希。原生抽取文字明确标为未审核比对资料，不据其自动通过。

转写复核必须记录逐字/数字/符号、边界与完整性、版面与分式行列依据；独立内容核验必须有推导、条件、单位、图形依赖和带关联说明的完整算式。精确核算复用 `textbook_quality.check_arithmetic_claim`；错误等式、除零、分列拼接、代码、缺依据或图形依赖不能通过。本批不把一般论断的有限样例当成证明；推导仍由实名类型为助手的审核记录承担。仅勾选、泛称“已看”或提交一个正确但无说明的算式不能代替审核。

新增/解决问题都清空当前两种审核并停用；未决问题不能启用或导出。改文、改上下文、改原页均生成新内容修订，旧证据失效。停用保留依据，再启用生成新证据ID；撤回必须新建修订重审。每次写入追加完整快照，记录序号、前序哈希、操作者、时间、原因和内容；事务中比较`expected_seq`，并发只允许一个结果成功，另一方409且表单保留。日志哈希用于发现意外修改，不冒充外部签名。

接口只属本机维护工具，CLI固定回环地址，Host/Origin/会话令牌拦截跨站请求；客户端不能提交审核者身份、延期日期或来源pin。`human`仅表示人工操作者自述，不授予教师身份。本批实际记录均为assistant。素材或来源损坏时停止原图/证据读取；日志仍有效时保留停用/撤回能力。图片加载前后比较当前序号，未保存的文字或来源编辑不能直接审核/导出。

启用范围为 `local_review_workspace_only`，当前证据前缀 `dd-review-`。导出仅为有明确历史属性的 `dd-passage-review-snapshot-v1` 审核包，不能当作A07运行清单；后续撤回不改写历史快照，当前有效性需查工作台。主站五片段、Tool与原发布pin未变，没有把本地启用记成上线。当前流程仅支持七上第二章原生PDF的无图形依赖片段；二下完整页与图形需要B04另行复核，不扩大自动通过范围。

## 实际一个片段的复核

样本ID `g7-ch2-reciprocal-definition`，书内40页 / PDF47页。原教材SHA256 `d995a2072c2b00418eacf1fdfc7a00234953592f5fba61a4b227731c8a19fdd8`，A07清单SHA256 `d1bf256db814afcf35ff22f28ad32fd4577b4608e12f9d069b7f72cfc8cacd63`。导入按当前日期核验，原页重新本地渲染；原始A07图片和所有旧材料未覆盖。有效期继承来源，至2026-12-07（北京时间，含当天），无客户端历史日期或自动延期。

`reciprocal-workspace/`中先保存待核修订1；本批补清有理数适用范围及排除内容，形成修订2，定义原句不改。实际查看渲染原图，核对蓝色定义的数字1、两个数和互为关系，核对页码与所在行，未把上方分数例题、下方登山/练习/探究并入审核。

独立推导记录：由有理数乘积等于1得两数均非零，分别除以非零因子得到互为倒数；反向证明非零有理数与其倒数之积为1，因此零没有倒数。6个精确核算包含正数、负数、原页负分数例子、±1边界与零乘积。有限算例只作为辅助核对，一般结论来自代数推导；没有单位或图形依赖。

本地启用后保存`reciprocal-snapshot-first/`，实际执行停用并验证旧ID返回404，再启用生成新ID，最终记录序号7、内容修订2，保存`reciprocal-snapshot-final/`。全过程见`selected-excerpt-validation.json`和快照中的完整审核日志。实际仅复核1个定义片段，`teacher_reviewed=false`、完整页审核0、判分资格false。未执行OCR、模型、向量写入、生产数据读取或发布。

## 定向验证

`unit-final.xml`：50 passed / 0 failed / 0 skipped，包含26项新工作台测试与24项原质量门槛测试。覆盖待核导入/保全、具体双重依据、忠实转写但原文等式错误时拒绝、修改文本/上下文/来源、问题清零后重审、启停/撤回、旧证据404、并发409、审核者记录、日期过期、越界、素材/配置/日志漂移、损坏后撤回、历史快照、同源边界与纯导入。`unit-first.xml`的49项和`unit-second.xml`的26项保留为中间运行，不累加分母。

`browser-final.xml`：2 passed / 0 failed / 0 skipped，Chromium145.0.7632.6，390/1280两宽度。合成原页、独立临时库、全请求ASGI拦截；验证未保存修改阻断审核/导出、错误核算不写记录、具体依据保存、候选启用、快照、问题与解决后重审、另一编辑页409保留表单、撤回刷新恢复、重审新版本，以及原图损坏后可撤回。无外部请求、页面错误或文档水平溢出。最终截图在`browser-final/`。

首轮`browser-first.xml`失败1项：Python普通字符串把JavaScript的换行转义转成实际换行，脚本无法解析；保存`ui-script-first.js`，经`node --check`定位后改用原始字符串。`browser-second.xml`两项通过；随后新增未保存内容导出拦截和材料损坏后撤回流程，最终两项再次通过。失败与中间截图全部保留。

实际片段另做只读显示核对，`selected-excerpt-browser/report.json`记录390/1280两宽度均正确显示原图、双页码、修订2/记录7和助手核验依据，全请求拦截、写入0、外部请求0、页面错误0。原图、桌面实际并排和手机合成布局已视觉查看；这不算家庭实机或教师验收，也不合并进合成浏览器用例计数。

环境复用A03的Python3.12.12、锁定依赖和Chromium，无新安装。没有重复整个历史服务/Tool/题库验收；未变的B02运行源码包通过逐文件哈希保全。定向入口：

```bash
python -m pytest -q tests/test_passage_review.py tests/test_textbook_quality.py --fail-on-skip
python -m pytest -q -m browser tests/test_passage_review_browser.py --fail-on-skip
```

## 交付与接续

`maintenance-source/`是16文件独立维护源码包，含三个工作台模块、CLI、必需纯依赖、说明、相关测试和锁定依赖声明。归档SHA256 `f525dfc9fbb68714cf8fa2db0a3cbf7f23c5ab1bc8fdea48ed98f69a7b64b1f4`；`maintenance-package-validation.json`记录全部文件哈希、隔离解包后无数据库导入及CLI帮助通过，不含教材/学生/运行资料。B02的81文件运行profile保持原样；没有新增运行迁移或OpenAPI端点。

本批源码与文档增量见`source-manifest.json`、`increment-manifest.json`、`b03-increment.patch`与`delivery-validation.json`。补丁以本轮开始时的B01/B02工作区为基线，在仓库外独立临时Git目录回放并逐文件核对；旧源码、历史材料及A09/B01/B02任务对象分别校验保全。已有修改不暂存/提交，`git diff --check`通过。未创建独立故障域备份，实际专注工时保持null。

使用、范围和回退见[工作台说明](../open-webui-reuse/passage-review-workbench.md)。下一项 **B04**：从已有二下OCR材料选择连续5个完整教学页，分别记录完整转写和独立数学/图形核验；未解决的页保持待核，不重跑整册OCR、不提前承诺通过数量。B02真实1/3/7天观察和A09发布/家庭设备与家长验收继续独立待办。
