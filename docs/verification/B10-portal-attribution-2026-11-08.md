# B10 portal 生命周期归因与异步依赖试验

日期：2026-11-08（Asia/Shanghai）。**3组450个请求全部成功，原页PNG hash与原基线一致，各组合成数据库前后指纹一致。持续portal使四并发暖原页P95下降37.22%；隔离异步依赖变体未达到预设采纳条件，因此没有改工作区运行代码。原性能验收仍10/12通过，B10保持in_progress / candidate_only / pending / open，B11未启动。**

## 输入、冻结与范围

独立证据：`learning_data/verification/b10-portal-attribution-20261108T112240Z/`。本批核对前批源码清单、全部证据清单，再封存181个当前输入和3430份历史文件hash、HEAD与索引、其余24项任务；原11个本地提交和22个未提交文件保留。`inputs-before.json`、`baseline-workspace/`为本批输入，旧HTTP目录和此前封存不改写。

候选为原`reuse-runtime-study-read-connections-v1`，97文件、schema13，archive SHA256 `b045997b9027dffa838eb127c8e42c54c1fdaa7b7b71ea75319ae2130a95889c`。本批在新目录解包，复用锁定Python3.12.12与相同合成PDF/五片段，材料hash、CPU affinity0–13、计时与nearest-rank算法和前批一致。旧HTTP结果仅作历史背景，本批重新测量对照。

`plan-before.json`先冻结两组次序：按请求portal→持续portal；仅暖原页、并发1/4、各30波，每组150样本。两组复用同一原始HTTP诊断脚本的TestClient分支、SyntheticBridge、调用序列、身份/档案/证据检查及缓存预热。新增`tests/benchmark_study_portals.py`只包裹客户端生命周期、记录portal创建/关闭及逻辑数据库hash。持续组用TestClient上下文管理器保留服务和网关的两个portal；检查服务/网关无startup/shutdown处理器。退出与预热均不计入请求耗时。portal次数包括两配置共5个预热请求。

基于前批已保存的沙箱卡住证据，本批经执行授权沿用沙箱外运行；conftest在导入前隔离数据目录/环境，非loopback网络禁令持续有效。全部为临时合成数据，没有真实模型/OCR、正式服务、外部通知或部署；性能采样串行，没有并行浏览器/负载测试。

## portal结果与后续试验

前两组300请求成功。按请求portal创建/关闭各620次（155请求×4），持续组各2次；两个配置的每请求连接仍4次、SELECT仍12次。四并发暖原页P95由561.10降至352.25ms，证明重复portal生命周期及伴随的线程/循环复用影响测试延迟。此结果不能充作服务代码优化或替换原验收。

阶段trace显示两个仅返回`app.state.settings/db`的内存函数仍触发worker派发。随后另冻结`async-trial-plan-v2-before.json`与`async-trial-freeze-v2.json`，在独立`async-trial-source/`只将get_settings/get_db的def改为async def，其单个return函数体及其余源码不变；归一化AST一致。工作区运行代码未改。

采纳条件在试验前固定：两并发档P95均不得变差、四并发P95至少改善5%、全部请求/输出正确、连接和SELECT不变、两项worker派发消失。最初计划把run标签误填为portal模式，执行前修正为per_request并另存v2；原v1计划保留，当时没有运行或采样。试验继续使用按请求portal，保证唯一运行变量为两个async声明。

| 配置 | 并发 | 样本 | P50 ms | P95 ms |
| --- | --- | --- | --- | --- |
| 按请求 portal 对照 | 1 | 30 | 52.90 | 114.88 |
| 按请求 portal 对照 | 4 | 120 | 490.23 | 561.10 |
| 持续 portal 实验 | 1 | 30 | 41.52 | 86.46 |
| 持续 portal 实验 | 4 | 120 | 274.90 | 352.25 |
| 按请求 portal + 异步内存依赖试验 | 1 | 30 | 50.16 | 55.63 |
| 按请求 portal + 异步内存依赖试验 | 4 | 120 | 475.01 | 580.47 |

异步试验的单请求P95下降，但四并发P95为580.47ms，对照561.10ms，比值1.0345，未满足不得变差和至少改善5%的条件。两个worker派发确实消失；连接4/SELECT12、portal620、输出及数据库不变，仍不能据此称为性能改善。`async-trial-decision.json`记录**不采纳**；保留全部样本，不重跑相同变体挑选结果。

## 验证与边界

`portal-comparison.json`核对三组JUnit各1通过、零失败/跳过（3个benchmark用例，非450个单元测试）；每组样本键完整且唯一、原PNG hash相同、材料/计划/脚本hash一致。每配置连接关闭完整、SELECT与worker派发计数符合预期。每组分别比较数据库前后指纹；随机会话/时间导致不同组的数据库字节不要求相同。三个结果和时间戳、原始trace/portal事件均可复核。

同一主机按固定次序单次采样，后台负载和OS缓存不受控；本次可确认portal创建次数及相应实测差异，不把百分比外推线上或家庭设备。portal复用也改变线程复用/事件循环共享，不能把全部差值当作单纯线程启动成本。阶段span嵌套，不相加P95。

原性能900样本（SHA256 `69d6680c67a0790d55cf463c6ed35976884332037658f3ff63433846c3d3e88a`）、12秒总预算、冷≤1.25/暖原页≤0.85/暖检索与Tool≤1.20门槛保持；前批单请求冷原页156.74ms>153.47ms、四并发暖原页572.67ms>528.17ms继续未达。未拿本批暖样本更新原10/12结论。

因为运行变体被拒绝，未运行仅对采纳变体才需启动的正确性组和原900请求矩阵；未重复历史166单元/契约、2浏览器或原生容器，不冒称它们新通过。本批公开新增一个显式benchmark和本记录，更新台账及入口；97文件运行包、UI/Tool/OpenAPI、current-manifest.json保持本批输入字节，无源码包重建或迁移。

## 证据与接续

三组目录为`per_request/`、`persistent/`、`async_trial/`，各含`run-before.json`、150行`samples.jsonl`、两份`spans-*.json`和`portal-lifecycle.json`；JUnit/日志/exit回执独立保留。`analyze-portals.py`按冻结条件计算，不对旧证据写入。`delivery-validation.json`、`increment-manifest.json`、`source-manifest.json`和`evidence-manifest.json`记录历史/索引/其他任务不变、增量回放及本批保全；旧seal脚本不重跑。

继续B10：按原两项未达配置冻结原页阶段归因，细分SQLite连接初始化/读取、冷PDF校验/渲染/PNG及请求调度，保留原调用序列和校验。已测portal改善属于测试拓扑，异步get_settings/get_db变体未达采纳条件，不重跑择优；只有新测量支持明确实现变化时才跑相关正确性与原900请求验收，原基线/12秒/P95门槛不变。

B07/B08外部条件、A09/B02/B05家庭验收和B04待解沿用原状态。实际专注工时null；本批没有提交或推送。
