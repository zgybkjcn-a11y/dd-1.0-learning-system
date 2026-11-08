# B02 七上第二章备用练习与延迟观察记录

日期：2026-11-08（Asia/Shanghai）；执行与内容核对角色：assistant。工程候选就绪，真实延迟观察待办，B02 总状态保持 open。未提交、推送、构建或部署，也未取得教师签署或家长实际验收。

## 内容与范围

独立证据目录：`learning_data/verification/b02-reserve-practice-20261108T022042Z/`。开始时 `main` 已有 B01 的 16 个未提交文件，本批保存 `inputs-before.json` 与 `baseline-source/`，增量以这些内容为基线，保留原工作区与历史证据。

新增独立题库 `family_reserve_practice_v1.json`，版本 `2026-11-08-b02-v1`，SHA256 `9de56afa82d70e108b3e0eaab9b319dbce66a7c8057669915d07b3be24f0c4a8`。12 道助手核对的备用题，简单/正常/困难各 4 道，题版与旧 60 道应用题不重叠。9 道新编计算任务、2 道新编情境、1 道旧助手题的数值变式。母题改数明确显示和保存题族，不能算新情境或盲测。试用难度未经学生数据校准。

| 分档 | 题目 | 核对结果 |
| --- | --- | --- |
| 简单 | 倒数、异号乘法、异号除法、负数三次方 | −1/4、−15、−4、−8 |
| 正常 | 分配律、科学记数法指数、按精确度四舍五入、混合运算 | −30、6、2.75米、−14 |
| 困难 | 多因子符号与小数、分数分配律、科学记数法换算、比较两天升温 | −12、−5、480升、3℃ |

逐题检查题干条件、单位、所求对象、提示、解析、来源与覆盖行。`semantic-mathematics-review.json` 保留替代推导；`packet-final/review.json` 保留规范化单题、入库内容哈希、独立表达式和精确数学检查。倒数用逆向乘积，除法反算，科学指数逐次除10，近似值另查有理数区间；数值相等的错误答案不能绕过条件校验。分配律题仅核对最终值，不证明所用方法。全部 `teacher_reviewed=false`、未决内容问题0；这是助手复核，不是独立教师审核。

B01 的覆盖行引用只保存在本批冻结内容，不自动写成旧概念库的精确映射。缺少本地讲解或有效教材片段的关系仍留空。B01 的 12 道分母是应用题，原家庭界面另有 6 道第二章起步题，普通选择共 18 道；[B01 报告](B01-chapter-coverage-2026-11-08.md)增加了有日期的澄清，历史 JSON、HTML 和证据没有重写。

## 候选行为与延迟观察

备用题仅显式安装到调用方选择的数据库；模块导入、服务启动和封包不自动安装。本批全部数据库为合成临时目录，追加安装及再次安装通过，原题、账户、学习者和身份绑定保留。题面或答案、校验器、版本、归属、课程、题族发生漂移时，创建/恢复/提示/提交/判分拒绝继续，判分前漂移不产生新的成绩或复习推进；取消仍可操作。

普通练习保持原范围和分档行为。安装后的七上第二章可选择“未见过的备用题”，每档初始 4 道。服务端按学习者与固定题版检查 `test_items`；创建已返回题面，取消、刷新、切换范围均不恢复未见资格。并发领取同题产生一条题项，返回201/409；其他年级不能越权。浏览器立即减少剩余数，耗尽后无重开备用题轮次，明确显示“本档未见备用题已用完”。匹配的已有复习卡仍受归属、到期和进行中预留约束，重复不算首次见题；合成复习判分验证原调度仅推进一次，不调用提供方。

`packet-final/observation-plan.json` 中基线作答 ID、基线时间，以及1/3/7天窗口的到期、实际观察时间和结果全部为 `null`；实际观察次数0。建议窗口只在取得真实带时区的首轮时间后计算。未提前填日期、作答、家长意见或未来结果；自动化模拟及四题升档不证明掌握。实际观察未完成，因此 `acceptance_state=pending`、`completion_state=open`，可先继续 B03；A09 发布/设备/家长验收不变。

## 定向验证

最终选取 103 个不同单元/契约用例通过，0失败/跳过：

- `unit-regression.xml` 中保留不受夹具修正影响的68项：普通题库、家庭选择、章节、知识参考及既有恢复/判分/取消/提示。
- `unit-final.xml`：22项备用题与12项新旧封包 profile，共34项通过，覆盖内容、追加事务、题版、未见并发、归属、复习卡、延迟空值、纯导入及缺少可选文件的旧选择。
- `contract-final.xml`：1项OpenAPI快照一致，仍为73 paths / 35 schemas，没有新增接口或请求字段。

`verification-selection.json` 逐个列出互不重复的通过用例；不把重跑次数累加成测试分母。`unit-first.xml` 的17项是新复习/漂移用例前的首轮结果。`unit-second.xml` 两处测试夹具引用错误，`unit-regression.xml` 一处合成教材目录未绑定造成503；均修正并在最终34项中通过，原失败JUnit保留。

`browser-final.xml`：4项通过，Chromium145.0.7632.6，390/1280两宽度各含备用题与原闯关回归。合成PDF/数据库、全请求ASGI拦截，无外部请求或页面错误。核对普通18题、备用12题/每档4题、活动题刷新恢复、取消后剩余11题、三档逐题作答、同母题标识、耗尽不可重开、跨档案/章节，以及旧题进阶/提示/再练规则。每宽度备用题展示12道，其中1道取消、11道正确判分；提供方调用0。这些计数仅属于模拟测试，不计入真实观察。

`browser-first.xml` 与 `browser-second.xml` 各保留1个失败：刷新后的测试导航落点假设不稳定，改用常驻首页导航，`browser-third.xml` 4项通过。截图复核随后发现备用题耗尽文案仍称“暂未配题/只有起步题”，修正为空题组专用提示并加断言，最终4项再次通过。所有历史截图保留；最终截图在 `browser-final/`，复核手机母题说明、桌面选择和耗尽状态，无水平溢出。

环境复用A03锁定Python3.12.12和Chromium，无新安装；没有重跑全套历史验收或实物教材组。定向命令：

```bash
python -m pytest -q tests/test_reserve_practice.py tests/test_learning_release.py --fail-on-skip
python -m pytest -q tests/test_runtime_passages.py::test_openapi_snapshot_matches_current_routes --fail-on-skip
python -m pytest -q -m browser tests/test_reserve_practice_browser.py tests/test_family_practice_browser.py --fail-on-skip
python -m scripts.prepare_reserve_practice --output-dir learning_data/verification/NEW-INDEPENDENT-DIRECTORY
```

## 封包与保全

源码候选 `release-final-r2/`：profile `reuse-runtime-practice-reserve-v1`，81个白名单文件，schema11。包含备用模块/题库、B01覆盖数据和离线冻结生成器所需输入；保留所有早期profile校验分支。`release-validation-r2.json` 记录逐文件/归档校验、解包后的备用模块与冻结生成器可用、缺少备用可选文件时当前基础源码仍可显示原30道七年级选择。后者是当前基础源码缺文件兼容检查，不冒称所有历史源码可读取新增数据。未构建镜像，`image_digest=null`。

`source-manifest.json`、`increment-manifest.json` 和 `b02-increment.patch` 单列本批源码与基于B01工作区的增量。补丁在仓库外独立临时Git目录回放，逐文件哈希一致；`delivery-validation.json` 核对旧60题、概念库、B01内容/代码和全部B01历史证据不变，A09任务记录相等。两份B01说明仅追加口径澄清，旧内容与快照可回查。当前在线状态仍沿用A01，没有重新读取正式Tool/WebUI数据或无关配置。

实际工时保持null。回退边界与使用方法见 [备用练习说明](../open-webui-reuse/practice-reserve.md)。下一项本地工程为B03一个原生PDF片段的并排复核与版本/启停；B02真实日期观察和A09家庭验收继续分别记录。
