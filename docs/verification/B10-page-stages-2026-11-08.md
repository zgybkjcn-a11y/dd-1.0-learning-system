# B10 原页阶段归因与两项隔离试验

日期：2026-11-08（Asia/Shanghai）。**3组450个请求全部成功、原页PNG hash与原基线一致、各组合成数据库前后指纹相同。只读连接初始化及GET围栏透传两变体均未达到预先冻结的并发P95采纳条件，均未应用到工作区运行代码。原验收保持10/12，B10仍in_progress / candidate_only / pending / open，B11未启动。**

## 输入与冻结

证据目录：`learning_data/verification/b10-page-stages-20261108T125320Z/`。`inputs-before.json`封存183个输入、4179份历史文件hash、HEAD/索引及其余24项任务；开始时11个本地提交、24个未提交文件保留。前批portal/HTTP和历史失败证据未改写。

本批仍以`reuse-runtime-study-read-connections-v1`的97文件schema13包为唯一原候选，archive SHA256 `b045997b9027dffa838eb127c8e42c54c1fdaa7b7b71ea75319ae2130a95889c`。在新目录独立解包，每次运行核对源码和脚本hash；已有锁定Python3.12.12、CPU affinity0–13、8,388,598字节合成PDF和五条合成片段保持。真实教材/学生材料、提供方及正式服务均未访问。

`plan-before.json`先冻结原两项未达配置：单请求冷缓存30波/30请求、四并发暖缓存30波/120请求。冷每波清应用缓存，暖排除一波4请求预热；OS文件缓存不受控。保持原按请求TestClient和SyntheticBridge调用序列；不采用前批持续portal或HTTP拓扑。P50/P95仍为nearest-rank，全部失败保留。

`tests/benchmark_study_page_stages.py`通过ContextVar为每个请求关联span，记录单调时钟开始/耗时；SQL只含SELECT/PRAGMA类别和PRAGMA名称，没有SQL参数、Cookie、文件正文或响应正文。覆盖连接开关、worker排队/函数体、网关跳转、文件读取/sha256/fingerprint、锁等待及PyMuPDF打开/加载/光栅化/PNG编码。桩包装调用原实现，不替代校验。数据库通过逻辑dump的hash检查前后不变。

沿用已保存沙箱限制证据，经执行授权使用沙箱外进程；测试启动时清除真实提供方配置，限制非loopback连接。三组串行，没有浏览器或其他负载测试并行，未安装依赖。

## 对照阶段结果

冷原页材料处理P50/P95为54.16/86.55ms。其中PDF打开27.22/41.33ms、PNG编码11.79/28.46ms、PDF哈希8.95/16.17ms、文件读取1.44/9.34ms；它们是不同span的分位数，不能相加。30个冷请求各打开/哈希/渲染一次，原PNG hash相同。

四并发暖缓存120请求没有PDF读取、哈希、打开、光栅化或PNG编码，材料处理P50/P95为11.92/21.57ms。每请求仍4条连接、12次SELECT，连接均关闭；每条连接调用busy_timeout/foreign_keys/journal_mode/query_only。对照的单条journal_mode P50/P95为4.01/8.70ms，连接初始化整体10.32/21.31ms。

逐请求计算服务worker函数体时间区间的并集，再从该请求墙钟耗时中扣除，得到函数体外耗时；没有用阶段P95相加或相减：

| 对照配置 | 服务函数体并集 P50/P95 ms | 函数体外 P50/P95 ms | 材料 P50/P95 ms |
| --- | --- | --- | --- |
| 单请求冷原页 | 61.35 / 103.17 | 47.10 / 102.40 | 54.16 / 86.55 |
| 四并发暖原页 | 164.28 / 214.49 | 319.90 / 416.13 | 11.92 / 21.57 |

“函数体外”包括TestClient、请求/响应、中间件、队列和线程调度等未被所列服务函数体覆盖的区间，不能直接解释为某一函数或纯CPU开销。函数体墙钟也包含被调度等待时间；只有后续线程CPU/等待证据才能进一步区分。

## 两项隔离试验

先根据连接初始化证据冻结`readonly-trial-plan-before.json`：从原97文件副本只改study_read_db.py，每个只读作用域用新的mode=ro连接，保留autocommit、15秒SQLite等待策略、foreign_keys/query_only、authorizer和原查询次序；合并连接设置、避免反复协商journal_mode，无连接池。该变体的executescript设置未独立插桩，因此不能用SELECT/PRAGMA子事件数量推算它节省的总初始化时间；端到端和完整服务函数体时间仍包含这段工作。

随后基于函数体外区间冻结独立`fence-trial-plan-before.json`：再次从原97文件出发，只在app.py让伴学GET及auth/session GET透传没有写入工作的BaseHTTP围栏层，保留write_context(None)的set/reset；其他请求仍调用原围栏dispatch。原写围栏、get_context、resolve_context、private_no_store函数体静态AST相同，身份/最终证据与总截止代码未删改。两变体不叠加，也未包含前批已拒绝的async依赖。

两次采纳门槛均在各自执行前冻结：所有请求/输出一致、4连接/12SELECT、冷单请求P95比值≤1.05、四并发暖P95比值≤0.95（至少改善5%）。这些只是隔离试验采纳条件，不代替原验收门槛。

| 实现 | 并发 | 缓存 | 样本 | P50 ms | P95 ms |
| --- | --- | --- | --- | --- | --- |
| 原97文件对照 | 1 | cold | 30 | 110.18 | 205.57 |
| 原97文件对照 | 4 | warm | 120 | 483.03 | 580.09 |
| 只读连接初始化试验 | 1 | cold | 30 | 105.97 | 186.51 |
| 只读连接初始化试验 | 4 | warm | 120 | 467.14 | 585.60 |
| GET围栏透传试验 | 1 | cold | 30 | 103.87 | 131.15 |
| GET围栏透传试验 | 4 | warm | 120 | 481.42 | 620.66 |

只读连接变体的暖P95比值1.0095，GET围栏变体1.0699，均高于0.95；各自冷缓存结果较低，但不能仅挑改善项采纳。两项决定分别保存于`readonly-trial-decision.json`和`fence-trial-decision.json`，均为selected=false。工作区运行代码保留原样，不重跑同一变体挑选达标结果。这里仅完成隔离性能试验和静态差异核对，未宣称两个变体已通过完整安全/正确性验收。

## 验证和限制

3个显式benchmark用例通过（各150请求，共450），零失败/跳过；样本键完整唯一，输出hash与原基线相同，材料/hash/计划/脚本匹配，trace均归属有效请求且落在请求计时范围内。每组4连接/12SELECT、冷/暖材料调用次数和数据库前后hash通过。不同组含随机会话/时间，数据库字节不跨组要求相同。

同一设备按固定次序单次测量，后台负载和OS缓存不受控，插桩本身有开销。观察到冷缓存变体改善不等同于稳定因果结论；全部对照/退步结果保存。逐请求区间并集只消除嵌套重复，不会自动得到CPU时间，也不能由本机TestClient外推HTTP或家庭设备性能。

原始优化前900样本（SHA256 `69d6680c67a0790d55cf463c6ed35976884332037658f3ff63433846c3d3e88a`）、12秒总预算、冷≤1.25/暖原页≤0.85/暖检索与Tool≤1.20门槛均保持。前批原验收单请求冷原页156.74>153.47ms、四并发暖原页572.67>528.17ms仍未达；本次没有替换它们。

两变体都未采纳，因此没有触发仅对采纳候选才需要的定向正确性和原900请求矩阵；未重跑历史166单元/契约、2浏览器、原生容器或重新prepare/verify源码包。97文件运行候选、UI/Tool/OpenAPI及current-manifest.json保持本批输入hash。

## 证据与接续

`diagnostic/`、`readonly-trial/`、`fence-trial/`各有原始samples、两个配置的spans、逐请求区间derived、run-before和数据库hash回执；各组日志、JUnit及exit回执独立保存。`analyze-stages.py`及其首份汇总保留，`analyze-stages-v2.py`增加第三组完整核验，结果为`page-stage-comparison.json`。本批清单、增量回放和保全见`delivery-validation.json`、`source-manifest.json`、`evidence-manifest.json`，不运行旧seal脚本。

继续B10：先冻结原TestClient执行环境/线程调度归因（保留当前材料、门户生命周期和身份/证据调用），区分墙钟耗时、线程CPU及等待；本批两个变体和前批async变体均未采纳，不重复相同候选择优。原始900样本、12秒预算和P95门槛不变；只有新证据支持运行实现变化后再做正确性与原矩阵验收。

此前11个本地提交保留，本批没有提交、推送、部署、生产监控、真实模型/embedding/OCR或外部通知。B07/B08外部条件、A09/B02/B05真实验收及B04待解保持；实际专注工时null。
