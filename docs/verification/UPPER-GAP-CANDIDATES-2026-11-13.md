# 上册20项缺口候选复核（本地）

2026-11-13。按主站交接第7节完成，随后已开展下册初步知识清单。

20项均有自编候选、答案、解析、错误反馈、核心动作、难度依据与候选映射。共20题、73个作答项；16题提供完整有界要求的一个直接题型族，4题仅辅助并附人工任务。

**尚未导入或部署**。候选批次未加入运行时BATCHES；正式题快照仍1145题，既有章节源仍1074题（包含之前3道未安装数学候选）。线上仍subject-v5，本地仍math-v15/subject-v16；subject-v17提案只存在于本批审阅包。

## 可审入口

- [逐题审阅页](../../learning_data/verification/upper-gap-candidates-20261113/review-v1/index.html)
- [候选数据](../../learning_service/data/family_chapter_upper_gap_candidates_v1.json)
- [逐项覆盖差异](../../learning_data/verification/upper-gap-candidates-20261113/review-v1/coverage-diff.json)
- [原页与来源边界](../../learning_data/verification/upper-gap-candidates-20261113/review-v1/source-evidence.json)
- [4项人工任务](../../learning_data/verification/upper-gap-candidates-20261113/review-v1/manual-tasks.json)

## 逐题结论

所有“通过”指同一助手的内容复核及工程校验，不是独立教师审核、课标交叉审核或学生真实难度校准。

| point_id | 候选 | 书内依据页 | 复核结果 |
| --- | --- | --- | --- |
| `ethics-g2-upper:4:participate` | 让了解祖国的活动具体起来 | 51, 62, 63 | 只计辅助；独立表达或实操未观察，保留人工缺口 |
| `ethics-g7-upper:2:family` | 需要与家人处境 | 31, 32 | 只计辅助；独立表达或实操未观察，保留人工缺口 |
| `ethics-g7-upper:2:teacher` | 拿事实与老师沟通 | 39, 40 | 只计辅助；独立表达或实操未观察，保留人工缺口 |
| `ethics-g7-upper:2:group` | 比较两种分工的影响 | 53, 54, 55 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `history-g7-upper:2:culture` | 年代、类别与文物信息 | 45, 46, 47 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `history-g7-upper:3:unification` | 秦统一措施的直接作用 | 54, 55 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `history-g7-upper:4:three` | 战争与三国建国时间 | 92, 93, 95 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `history-g7-upper:4:reform` | 从北魏措施分析交融 | 109 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `history-g7-upper:5:map` | 按图例和时点读空间变化 | 123 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `geography-g7-upper:2:space` | 天体类别与所属关系 | 6, 8, 13 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `geography-g7-upper:3:selection` | 用途决定地图选择 | 37, 38 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `geography-g7-upper:5:temperature` | 日较差、年较差与季节 | 73, 74 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `geography-g7-upper:5:rain` | 累计季节降水再比较 | 79, 80 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `geography-g7-upper:6:population` | 总量、密度和自然增长 | 92, 93, 95 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `geography-g7-upper:6:culture` | 从材料比较文化表达 | 103, 104, 105 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `biology-g7-upper:1:observation` | 对照条件与三次记录 | 3, 4, 5 | 只计辅助；独立表达或实操未观察，保留人工缺口 |
| `biology-g7-upper:2:celllife` | 细胞结构各有作用 | 28, 29, 30, 31 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `biology-g7-upper:3:single` | 一个细胞怎样独立生活 | 46, 48, 49 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `biology-g7-upper:6:fungi` | 真菌与细菌的结构和营养 | 104, 110, 111 | 完整有界要求，一个直接族；仍需第二种有效证据 |
| `biology-g7-upper:6:food` | 发酵、保存与灭菌的条件 | 100, 102, 120 | 完整有界要求，一个直接族；仍需第二种有效证据 |

关键复核：秦朝措施明示直接作用分类；三国建国采用教材吴229年的口径；历史空间图为自编虚构图，保留未知区域；温度表完整提供12个月，年较差28℃、日较差10℃；季节降水单位和人口总量/密度/增长分开考查。生物实验模拟数据不算真实实验记录；细胞与微生物比较避免全称误述。

初稿温度表超过既有8列视觉限制，已改为两组六个月。原初稿及发现保存在验证目录；最终4张表与20题页面均通过桌面1280×1000检查，并查看了地图与温度表截图。浏览器阻断HTTP/HTTPS，只读取本地文件；这不是真实手机验收。

## 覆盖口径

| 证据口径 | configured | partial | gap |
| --- | ---: | ---: | ---: |
| 固定正式题ID + 本地subject-v16 | 112 | 288 | 258 |
| 固定正式题ID + 候选映射提案 | 112 | 288 | 258 |
| 假设20题存在时的候选预览 | 112 | 293 | 253 |

这些是本地审阅统计，不是线上subject-v5的新运行统计。16项获得第一个直接族；其中11项已有辅助证据，原先已计partial；5项从gap到partial。4项仍仅辅助。新增configured为0，不能宣称20项已完全补齐。

## 验证与保全

候选7项测试通过（99.56秒）：覆盖结构、逐项算术与语义约束、图表完整性、所有错误选项和缺失/多余/重复字段、人工边界、正式/候选覆盖隔离，以及临时合成库安装幂等性和作答。

合成安装以1145道旧题和所有原表行作基线，增量20题后重复安装新增0；逐题正确作答并检查答案不泄露、跨年级访问隔离和提交幂等性。provider_calls为0。没有访问生产数据库或制造真实学生记录。

交接规定的83项回归初次79通过、4失败；4处旧测试把新增7册54个阅读范围误认为有配题。仅修正测试范围为固定13册98范围，并增加“20册152范围不等于全部有题”的检查，最终84项通过（103.57秒）。合计91项不同检查通过。

- [最终回归JUnit](../../learning_data/verification/upper-gap-candidates-20261113/regression-final.xml)
- [实际测试结果记录](../../learning_data/verification/upper-gap-candidates-20261113/test-results-final.json)
- [桌面布局检查](../../learning_data/verification/upper-gap-candidates-20261113/desktop-review-layout.json)
- [原测试文件备份](../../learning_data/verification/upper-gap-candidates-20261113/preexisting-test-baselines)

沙箱内最小anyio/TestClient线程通信会停住；获准在沙箱外完成测试，根conftest继续隔离临时数据并阻断外网。早先超时与一次诊断进程139退出保留记录，未算作通过。测试有一个既有Starlette/httpx弃用提示，本轮未升级依赖。

既有改动保留；除上述3个测试的定向范围修正外，不改旧源码、题库、计划或发布清单。未提交、未推送、未部署、未启动或调用C01；无外部模型/OCR/embedding，真实手机继续暂缓。

## 后续

[下册清单](LOWER-KNOWLEDGE-INVENTORY-2026-11-13.md)已建立10册75范围的初步记录，新增68条要求、沿用61条旧要求；下册新题0，知识点穷尽仍未完成。下一批先围绕二下有余数除法、七下动物信息和种子萌发等起始范围编制候选，再逐题核对完整能力。

后续会话入口：[本批续办交接](../plans/HANDOFF-SESSION-2026-11-13-QUESTION-QUALITY.md)。
