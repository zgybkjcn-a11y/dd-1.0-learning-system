# 数学单一解题动作与映射复核

2026-11-12依据正式已安装题ID，继续复核二上与七上数学单一直接题型族要求。该数学审阅快照使用math-v15/subject-v14，位于`learning_data/verification/math-single-action-20261112/review-v15/`；后续subject-v15映射更新见[上册语文英语与科目缺口复核](UPPER-SUBJECT-KNOWLEDGE-REVIEW-2026-11-12.md)。正式题ID快照仍为`available-ids.json`（二年级418、七年级727）。既有冻结题版没有改动；数学映射作了修订，并新增一道未安装的本地候选题。

## 已审映射

| 教材 / 要求 | 修订 | 依据 |
| --- | --- | --- |
| 二上乘法解决问题：辨认每份量和份数 | 将“3辆玩具车、每辆4个轮子”由辅助改为直接 | 题目要求辨认3组和每组4个；仍只算有界识别，不代表能口述乘法意义。 |
| 二上乘除综合：辨认换分包装中保持不变的量 | 将“6盒、每盒8颗改为每袋4颗”由辅助改为直接 | 直接识别改变每份量与份数后，总颗数不变；与按每份量计算总数不同。 |
| 二上1～6乘法口诀：用口诀求积 | 将已安装“先补完整再数圆片”映射为直接 | 需以4行、每行6个的位置模型求总数，再扣空位；不同于直接回忆乘积。多作答项仍只算一道题。 |
| 二上口诀求商：用2～6口诀求商 | 将同章已安装的“把苹果平均分”映射为直接 | 已知总量与份数求每份量，与已有题“已知每份量求份数”是两种不同除法模型，无需重编题。 |
| 七上正负数：表达相反意义 | 将“允许偏差”题映射为另一直接动作 | 实测值减标准值后判断偏差方向，与从“取出/低于”直接确定负号不同。 |
| 七上绝对值：求绝对值 | 将“数轴上点到原点距离”题映射为另一直接动作 | 直接应用绝对值的距离定义，与计算给定绝对值表达式不同。 |

其余二上单一族项目中，分类记录读取、相对方向、单位选择、除法意义等候选目前只能支持原要求的一部分；“用乘法验商”要求本身限定单一检验动作。均保留现有直接/辅助区分。七上第1章同范围题中，换数字重复、只测相关概念、或无法完整满足要求的题没有升为直接题型。

## 七上第二章复核

逐项审阅有理数加减乘、运算律、除法、乘方、科学记数法、近似数和进位制共36项要求，并对照本地正式题ID快照中的全部同章题。24项bounded要求中，5项达到两种不同直接题型族的编辑目标，19项部分覆盖；另12项为human，仍须由观察者核验，不能由自动选择题代替。

| 已安装题 / 要求 | v12 映射 | 依据 |
| --- | --- | --- |
| `family-chapter-math-g7-upper-2-depth-subtract-03-v1`：减法辨析 | 在“辨析减去负数”中降为辅助；新增到“计算有理数差”作直接，题型族为`g7:subtract:negative-subtrahend` | 题目只要求算`5−(−3)=8`，没有辨认错误或说明理由；它直接检验减去负数的计算动作。 |
| `family-chapter-math-g7-upper-2-depth-multiply-03-v1`：多个负因子 | 在“辨析多个负因子和零”中降为辅助；新增到“计算乘积”作直接，题型族为`g7:multiply:negative-factor-parity` | 题目只算三个非零负因子的积，既不含零因子也不要求找错；奇偶判断属于与两因数相乘不同的计算动作。 |

确有直接辨析缺口，因此新增两个本地候选：`family-chapter-math-g7-upper-2-01-v1`检查“减去负数误算成减去正数”；`family-chapter-math-g7-upper-2-02-v1`同时检查三个负因子的奇偶与零因子。题干、答案与解析见[候选题源](../../learning_service/data/family_chapter_math_g7_action_candidates_v1.json)。两题教师签署为false，尚未安装，也不在正式ID快照；本次正式覆盖统计不计这两题。它们即使纳入，也只为各自辨析要求增加一种直接题型，不能算完成两族目标。

同章其他单一族要求未因改数、换故事、只识别概念，或使用未安装的备用题而升为直接映射。科学记数法“检查系数范围与指数”已有两种符合要求的直接题型；减法变化比较、连续倍率变化也各有两种已安装直接题型。

## 七上第三章复核

同一正式题ID快照也逐项审阅了列代数式、代数式的值和规律表达共12项要求。6项bounded要求中，2项达到两种不同直接题型族目标，4项仍为部分覆盖；另6项是human，不按自动题统计。

未发现应更改的直接/辅助角色。代数式整体代入题的多个数字版本沿用同一“已知整体关系再变形求值”动作，不能算作多种题型；规律题中的特例反例直接检验全称猜想，已正确映射为辨析；拼接图形/表格任务只完成部分规律表达要求，保留为辅助；列式、独立表达与一般式说明仍由人工任务核验。没有为达到两族计数而新增或误升映射。

## 七上第四章复核

按同一正式题ID快照审阅整式、同类项、去括号和整式应用。math清单该章16项要求为3 configured、13 partial；subject清单为6 configured、10 partial，均无gap。

| 已安装题 / 要求 | 修订 | 依据 |
| --- | --- | --- |
| `family-chapter-math-g7-upper-4-depth-application-03-v1`：整式减法 | 在“检查减去整个式”中降为辅助；新增到“求两个整式的和差”作直接 | 题目只计算整式差，没有要求检查他人步骤；用它覆盖辨析会夸大能力证据。 |
| `family-chapter-math-g7-upper-4-math_g7_multistep-coefficients-v1`：多步系数 | 新增到“正确展开括号”作直接 | 同时展开正、负系数乘括号并合并同类项；与单一去括号后代值属于不同动作。 |

另编候选`family-chapter-math-g7-upper-4-action-subtract-expression-v1`，要求辨认减去整式时常数项漏变号并给出正确结果。该题未安装，正式统计继续排除；因此“检查减去整个式”仍只有辅助题，状态为partial。候选题源见`learning_service/data/family_chapter_math_g7_chapter4_action_candidates_v1.json`。本地章节题源为1074道；review-v15仍只导出正式快照中的1145道题。

## 七上第五章复核

第五章逐项检查一元一次方程、等式性质、解方程与实际建模。math视图16项中2 configured、14 partial；subject视图3 configured、13 partial（9 bounded、7 human）。没有把单选辨认题升为独立列方程或解释步骤的直接证据；人工建模与推理要求继续保留。

## 七上第六章复核

第六章涵盖几何图形、点线面体、直线/射线/线段、线段中点、角、角平分线、余角补角和比例图纸。math视图32项中4 configured、28 partial；subject视图5 configured、27 partial（20 bounded、12 human）。

| 已安装题 / 要求 | v14 映射 | 依据 |
| --- | --- | --- |
| `family-chapter-math-g7-upper-6-depth-angle-02-v1`：读写或测量角度 | 在math视图由直接降为辅助 | 单选只能读出一个度分秒记法，不证明能独立读写角度或用量角器测量；subject视图本来就标为辅助，人工任务保留。 |
| `family-chapter-math-g7-upper-6-depth-lines-02-v1`：区分并表示三种线 | 在math视图由直接降为辅助 | 单选只判断一条射线的表示，不能证明会独立画写线段、射线和直线；subject视图仍要求人工观察。 |
| `family-chapter-math-g7-upper-6-depth-shapes-01-v1`：辨析平面与立体 | 在math与subject视图新增直接映射 | 题目要求从平面/立体选项中辨认平面图形，直接对应有界分类；不同观察角度画图仍是human要求。 |

第六章subject口径32项中20项bounded（5 configured、15 partial），12项human未由自动题代替。没有新增题；只修订映射角色并补用已安装题。

## 二上数学复核

按相同418道二年级正式题ID逐项核对第1至6章、校园导游和身体尺两个活动范围。没有新增题；原有人工任务继续保留，例如乘法意义的口头说明、路线描述、身体尺的现场测量和提出问题。活动2中给定身体尺数据后只计算长度的题，以及只使用一人的尺长、未比较两人身体尺的题，不直接证明会实测或比较，已在math清单改为辅助。

## 跨清单角色复核

逐项比较math与subject清单中共享的“要求-题号”映射，修正了math清单中13个与subject角色不一致的题：二上活动2八道身体尺计算题、四道未比较两人身体尺的题，以及七上第1章一道只读数轴现成刻度的题，均降为辅助。五项二上的有界记录/数量关系识别，以及七上第6章常见图形识别改为直接，与subject清单保持一致。当前共享映射的直接/辅助角色一致；human与bounded属性没有改变。

## 候选统计

本数学review-v15生成时使用`family_math_coverage_plan_v15.json`和`family_subject_coverage_plan_v14.json`。当时math专用统计为65 configured、140 partial、7 gap；subject全学科为112 configured、275 partial、271 gap，含308 human、350 bounded。后续当前本地候选已升级subject-v16，详见[科目缺口复核](UPPER-SUBJECT-KNOWLEDGE-REVIEW-2026-11-12.md)；本数学快照按原时点保留。七上第二章24项bounded要求中5项configured、19项partial；第三章6项bounded要求中2项configured、4项partial；第4章subject口径10项bounded要求中6项configured、4项partial；第6章20项bounded要求中5项configured、15项partial。所有数字只表示编辑映射，不是课程标准完整率、掌握率或教师签署。

历史review-v14使用math-v14/subject-v13；下一数学快照review-v15的统计见本节上方math-v15/subject-v14摘要。review-v11 JSON逐项合计为107/280/271；较早交接中的107/281/270为加总错误。所有数字仅描述编辑映射，不是课程标准完整率、掌握率或教师签署。

此前映射候选和每次审阅快照均保留。上述三道第2/4章纠错题仍是本地候选；review-v15仍使用SHA256为`853ed5521fc5bc134575c6151e2b76937dae968d7aeedd8e514f847cceeaa15b`的正式ID快照，导出1145道正式题。线上仍为subject-v5、1145题/schema14，题版及作答行未改，发布清单以`docs/releases/current-manifest.json`为准。

## 验证与边界

运行内容、覆盖、章节题库与挑战档定向组：

```text
pytest tests/test_math_single_action_coverage.py tests/test_chapter_practice.py tests/test_practice_coverage.py tests/test_subject_knowledge.py tests/test_knowledge_quality.py tests/test_challenge_tier.py
82 passed
```

覆盖题号可用性、映射哈希、直接/辅助角色、distinct-family去重、候选题协议与章节作用域、人工任务隔离、正式题版不变和既有挑战题断言。旧断言按13个configured统计，未考虑二上身体尺活动中的8道纯长度计算题已降为辅助；测试现改为核验12个configured，并显式断言该项有8道supporting题、0个direct family。第2章两题和第4章一题共三道本地候选；章节题源为1074道，正式安装题数仍未变化。未导入题目、未迁移数据库、未部署或重启服务，未调用模型/OCR/embedding。C01四个容器保持停止；真实手机验收继续暂缓；未提交或推送。
