"""Build a new math editorial revision; leave historical plans/questions intact."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_service.chapter_practice import bank as chapters
from learning_service.practice import bank as initial

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'learning_service/data/family_subject_coverage_plan_v2.json'

# Explicit editorial decisions, not keyword-based grading of learner work.
HUMAN = {
    'math-g2-upper:1:classify': 'understand',
    'math-g2-upper:1:compare': 'transfer',
    'math-g2-upper:2:meaning': 'understand transfer',
    'math-g2-upper:2:tables': 'understand',
    'math-g2-upper:3:equal': 'transfer',
    'math-g2-upper:3:quotient': 'understand',
    'math-g2-upper:activity1:route': 'understand apply transfer',
    'math-g2-upper:4:ruler': 'understand transfer',
    'math-g2-upper:4:estimate': 'understand apply transfer',
    'math-g2-upper:activity2:body': 'understand apply transfer',
    'math-g2-upper:6:relations': 'understand',
    'math-g2-upper:6:organize': 'understand apply transfer',
    'math-g2-upper:5:tables': 'understand',
    'math-g2-upper:5:quotient': 'understand',
    'math-g7-upper:1:signed': 'understand transfer',
    'math-g7-upper:1:rational': 'understand transfer',
    'math-g7-upper:1:line': 'understand apply',
    'math-g7-upper:1:opposite': 'understand',
    'math-g7-upper:1:absolute': 'understand',
    'math-g7-upper:1:order': 'understand',
    'math-g7-upper:2:add': 'understand transfer',
    'math-g7-upper:2:subtract': 'understand',
    'math-g7-upper:2:multiply': 'understand',
    'math-g7-upper:2:laws': 'understand',
    'math-g7-upper:2:divide': 'understand',
    'math-g7-upper:2:power': 'understand',
    'math-g7-upper:2:scientific': 'understand',
    'math-g7-upper:2:approximate': 'understand transfer',
    'math-g7-upper:2:binary': 'understand transfer',
    'math-g7-upper:3:expression': 'understand apply transfer',
    'math-g7-upper:3:value': 'understand',
    'math-g7-upper:3:pattern': 'apply transfer',
    'math-g7-upper:4:polynomial': 'understand',
    'math-g7-upper:4:like': 'understand',
    'math-g7-upper:4:bracket': 'understand',
    'math-g7-upper:4:application': 'understand transfer',
    'math-g7-upper:5:equation': 'understand transfer',
    'math-g7-upper:5:equality': 'understand transfer',
    'math-g7-upper:5:solve': 'understand',
    'math-g7-upper:5:model': 'apply transfer',
    'math-g7-upper:6:shapes': 'transfer',
    'math-g7-upper:6:elements': 'understand transfer',
    'math-g7-upper:6:lines': 'understand apply',
    'math-g7-upper:6:segments': 'understand',
    'math-g7-upper:6:angle': 'understand apply',
    'math-g7-upper:6:bisect': 'understand',
    'math-g7-upper:6:complement': 'understand',
    'math-g7-upper:6:design': 'understand transfer',
}

# Each task has a concrete trigger and observable criteria, including process.
TASKS = {
    'math-g2-upper:1:classify': ('用红圆3张、红方1张、蓝圆2张、蓝方2张卡片，先按颜色、再按形状整理，说清每次标准。', '红4蓝4；圆5方3；两次均8张，不漏不重。'),
    'math-g2-upper:1:compare': ('根据苹果5个、梨3个、橘子4个的记录，自己提出一个求总数问题和一个比较问题，写式并解释。', '总数12；比较问题允许多解，问题、算式、单位与记录对应。'),
    'math-g2-upper:2:meaning': ('摆3组、每组6个物件，自己画图、写乘法，说清相同加数、每份量、份数、总量；再换为6组、每组3个。', '两次均18个；区分每份量与份数；合理的乘数书写顺序均接受。'),
    'math-g2-upper:2:tables': ('选“三六十八”和“四五二十”，各写两个乘法算式，并用分组图说明口诀中的三个数。', '3×6与6×3均18；4×5与5×4均20；解释联系，不能只背结果。'),
    'math-g2-upper:3:equal': ('把18个物件分别摆成每组3个和平均分3组，画出两种分法，写除法并比较。', '18÷3=6中的3在两种情境分别为每份量、份数；总数不变。'),
    'math-g2-upper:3:quotient': ('用24个物件摆4组，自己写一个乘法和两个除法算式，解释如何用乘法检验商。', '4×6=24、24÷4=6、24÷6=4；各数含义与分组一致。'),
    'math-g2-upper:activity1:route': ('纸上标北：校门在下方，花坛在其正北，阅览室在花坛正东，体育馆在校门正东、阅览室正南。自己画两条从校门到阅览室的路线，逐段带家长走。', '可经花坛或体育馆；起终点、每段参照位置和方向一致；自己的路线和说明必须实际出现。'),
    'math-g2-upper:4:ruler': ('自己画4厘米线段，标端点，用直尺测量；再让左端对齐2厘米刻度复测，说明起点和刻度差。', '线段画直、端点清楚；复测右端约在6厘米；实际测量记录不得用理论4替换。'),
    'math-g2-upper:4:estimate': ('先用熟悉的1厘米或1米参照估计橡皮和书长，保留估计及单位；再实测，比较差距并说明改进。', '先估后量；两种记录都保留；能说明参照及差距；物品不同不设统一长度答案。'),
    'math-g2-upper:activity2:body': ('孩子与家长各校准自己一拃，再用自己的身体尺估测同一桌边，记录整拃及余量，最后用标准尺复测并比较。', '身体尺大小分别实测；摆放不漏缝不重叠；解释拃数差异；保留原始估测和复测。'),
    'math-g2-upper:6:relations': ('自己画12个物件的分组图，联系加法、乘法和除法；再拿走3个，用加减关系检验，解释各式含义。', '例如4+4+4=12、4×3=12、12÷3=4，12−3=9与9+3=12；含义与图一致，允许其他合理分组。'),
    'math-g2-upper:6:organize': ('自己画本册知识图，整理分类、乘除法、方向、长度和身体尺，至少解释两处联系，再提出并解决一个实际问题。', '方法分类合理；联系有说明及例子；自己提出的问题、条件和解法对应；不照抄预给知识图。'),
    'math-g2-upper:5:tables': ('选“七八五十六”和“八九七十二”，自己画分组示意图并写相应乘法，解释口诀中的数。', '7×8=56、8×7=56；8×9=72、9×8=72；分组量和总量一致。'),
    'math-g2-upper:5:quotient': ('用56个物件或自己画的图解释7×8、56÷7、56÷8的联系，说明怎样检验商。', '商分别8、7；检验使用乘数与商的乘积；须说明，不只报结果。'),
    'math-g7-upper:1:signed': ('解释温度0与温度变化0的区别；零件标准20厘米、允许偏差±0.2厘米，说明19.7和20.1厘米是否合格及理由。', '偏差−0.3不合格、+0.1合格；零表示所选基准，不是没有温度。'),
    'math-g7-upper:1:rational': ('将−3、−1/2、0、2先按整数/分数、再按正/零/负分类，解释分类标准与有理数范围。', '整数−3、0、2；分数−1/2；零非正非负；不得将负分数排除在有理数外。'),
    'math-g7-upper:1:line': ('独立画数轴，标−3、−1/2、0、2，再从自己的图读数并解释数轴三要素。', '原点、正方向、单位长度齐全；间距统一；按数描点须看实际图，线上读数不能替代。'),
    'math-g7-upper:1:opposite': ('自己画数轴标−3与3、0，解释相反数和关于原点对称的联系，再给一个反例。', '相反数和为0、距原点相同、符号相反（0的相反数为0）；反例说明为何不成立。'),
    'math-g7-upper:1:absolute': ('画数轴解释|−3|、|3|和|0|的含义，说明为什么绝对值非负。', '到原点的距离分别3、3、0；不能把绝对值等同于原数。'),
    'math-g7-upper:1:order': ('用数轴与绝对值两种说法解释为什么−5<−2，再给一个负数比较例子。', '数轴左边数较小；负数绝对值越大数反而越小；例子及必要条件一致。'),
    'math-g7-upper:2:add': ('温度从−5℃先升9℃再降6℃，自己写式解释符号；分别举同号、异号相加例子说明规则。', '−5+9−6=−2℃；同号绝对值相加保留符号；异号比较绝对值，等大时得0。'),
    'math-g7-upper:2:subtract': ('解释4−(−3)=4+3，并自举减去正数、减去负数两个例子说明减法转化。', '减去一个数等于加其相反数；不能只将所有负号删掉。'),
    'math-g7-upper:2:multiply': ('解释两个负数相乘、三个负数相乘与含零因子的积的符号，各给一例。', '非零负因子偶数个为正、奇数个为负；有零因子则积为0；计算与说明一致。'),
    'math-g7-upper:2:laws': ('自举交换律例子；展示25×(4×7)的结合律变形；用两种方法计算(−1/4)×36+(−1/4)×4并解释分配律。', '交换与结合区分；后一式=−10；分配律须作用于每一项，不以报结果代替说明。'),
    'math-g7-upper:2:divide': ('用乘积为1解释−2/3的倒数，再说明除以−2/3如何转成乘法，并讨论0。', '倒数−3/2；除以非零数等于乘其倒数；0无倒数且不能作除数。'),
    'math-g7-upper:2:power': ('用连乘分别说明(−2)^3与−2^2中的底数、指数、幂，解释括号影响。', '前者底数−2、指数3、幂−8；后者是2^2的相反数−4，不能说底数为−2。'),
    'math-g7-upper:2:scientific': ('自己把560000写成a×10^n，解释系数与指数；再解释56×10^4为什么等值却不规范。', '5.6×10^5；1≤|a|<10，本例n=5；解释小数点移动与数量级。'),
    'math-g7-upper:2:approximate': ('测得2.486米，精确到0.01米，自己写记录并说明舍入理由；再比较2.5与2.50表示的精确度。', '2.49米；看千分位6进位；2.5到十分位、2.50到百分位，数值相等但记录精确度不同。'),
    'math-g7-upper:2:binary': ('把(1011)₂转成十进制，写每位权值并解释满二进一；再选一个十进制整数反向转换。', '8+0+2+1=11；权值按2的幂排列；反向转换须说明过程并可复核。'),
    'math-g7-upper:3:expression': ('独立设字母写3本同价本子加5元运费的总费，再为“起步8元含3千米、此后每千米2元”自行写x≥3整数千米的费用，解释定义与适用范围。', '例如3x+5；后一式8+2(x−3)=2x+2；字母、单位、范围说明齐全，等价式均接受。'),
    'math-g7-upper:3:value': ('给2x−3代入x=−2，自己写步骤，解释代入负数为什么需要括号。', '2×(−2)−3=−7；括号保留负数整体；用另一数值再示范。'),
    'math-g7-upper:3:pattern': ('亲手摆一排共边正方形的前3项，独立写n个所需小棒数，解释一般式为什么对每个正整数n成立。', '3n+1或4+3(n−1)；每新增一个只增3根；须有结构解释，不以少数数值验证代替。'),
    'math-g7-upper:4:polynomial': ('自己用−4a^2b与3x^2−2x+5解释系数、单项式次数、多项式项及次数，再自举一例。', '系数−4、次数3；多项式3项、次数2；常数项与符号保留；须解释而非选择定义。'),
    'math-g7-upper:4:like': ('自己列一对同类项和一对容易混淆的非同类项，解释条件，并示范合并。', '字母相同且各字母指数相同；系数可不同；合并只加系数，不改变字母指数。'),
    'math-g7-upper:4:bracket': ('独立化简5x−(2x−4)，逐项解释外部负号作用，再代x=−2核对。', '3x+4；括号内两项均变号；代入结果−2，与原式一致。'),
    'math-g7-upper:4:application': ('长方形长x+3、宽x且x>0，自列周长式并解释每项，说明为什么不是面积。', '2[(x+3)+x]=4x+6；面积x(x+3)；单位与意义正确；等价式接受。'),
    'math-g7-upper:5:equation': ('解释x+3=7与式子x+3的区别，代入检查x=4；再独立设未知量，为“原价打八折售48元”列方程。', '方程含等号且有未知数；解须使等式成立；0.8x=48，明确原价及元。'),
    'math-g7-upper:5:equality': ('独立解(x+5)/3=4，每步说明两边做了什么以及使用性质的条件。', '两边同乘非零3得x+5=12，再同减5得x=7；不能只改一边，也不能用同除0。'),
    'math-g7-upper:5:solve': ('用2x−3=7说明“移项”与“系数化1”的依据，再自解一题，写检验。', '两边同加3、同除非零2，x=5；移项变号不是任意更换符号。'),
    'math-g7-upper:5:model': ('原价打八折售48元，独立设未知量、写等量关系、列方程、求解、代回检验；再说明票价问题算出负值时怎样检查。', '0.8x=48，原价60元；检验0.8×60=48；结合数量意义检查模型与运算，不能直接删负号。'),
    'math-g7-upper:6:shapes': ('实际观察一个盒子，分别从正面、侧面、上面画轮廓，解释平面图形与立体实物的关系。', '方向与盒子实际形状相符；保留三幅观察图；不规定所有盒子都画成正方形。'),
    'math-g7-upper:6:elements': ('观察盒子，指出顶点、棱、面、体各对应什么，解释实物到数学抽象的差别，再换一个物体举例。', '能联系点线面体；不把实物厚度当作数学面有厚度；解释来自观察。'),
    'math-g7-upper:6:lines': ('自己画A、B两点，分别画并标线段AB、射线AB、直线AB，说清端点、延伸与表示顺序。', '线段2端点、射线1端点且AB以A为端点、直线无端点；后两者无有限全长。'),
    'math-g7-upper:6:segments': ('画18厘米线段AB并标中点M，再在M与B间标NB=4厘米的N，说明中点、两点距离和MN的关系。', 'AM=MB=9厘米、MN=5厘米；解释中点必须在线段上且等分；实际图需检查。'),
    'math-g7-upper:6:angle': ('自己用量角器画86°的角，标顶点和两边，读写角度并复测；延长两边，说明角度为何不变。', '量角器中心及0刻度线摆正，读正确内外圈；保留实测及误差；两边张开程度决定角大小。'),
    'math-g7-upper:6:bisect': ('画86°角，用折纸或测量作角平分线并复测两部分，解释平分线条件。', '从顶点出发、位于角内、两部分约43°；只满足“看起来在中间”不够。'),
    'math-g7-upper:6:complement': ('自己用40°举例解释余角与补角，再讨论两个相等的角是否必定互余或互补。', '余50°、补140°；和分别90°、180°；仅相等不能推出互余互补。'),
    'math-g7-upper:6:design': ('为12米×8米区域按图上1厘米表示2米画草图，安排一个不越界的小活动区，说明需要的量、工具和约束。', '外框6厘米×4厘米；内部方案允许多解，尺寸、单位、比例和边界核对齐全；不等同完整田径场设计。'),
}


def build():
    data = json.loads(BASE.read_bytes())
    data['version'] = 'subject-coverage-v3-math-quality'
    rows = {r['id']: r for r in data['rows']}
    questions = initial() | chapters()
    changes = []
    for row in data['rows']:
        if row['book_id'] not in ('math-g2-upper', 'math-g7-upper'):
            continue
        human = set(HUMAN.get(row['id'], '').split())
        assert human <= row['requirements'].keys()
        row['assessment_modes'] = {task: 'human' if task in human else 'bounded' for task in row['requirements']}
        if human:
            prompt, criterion = TASKS[row['id']]
            row['manual_task'] = {
                'title': row['title'] + '：独立表达或操作', 'automatically_graded': False,
                'prompt': prompt + ' 逐项核对：' + '；'.join(row['requirements'][t] for t in row['requirements'] if t in human) + '。先独立完成，观察者保留实际过程及提示。',
                'criteria': [criterion, '逐项记录实际观察到的表达、草图或测量；未观察的要求保持待练习。', '区分独立完成、需要提示、待练习；选对线上答案不证明这些要求已完成。'],
            }
        for m in row['mappings']:
            if m['task'] in human and m.get('role', 'direct') == 'direct':
                before = deepcopy(m)
                m.update(role='supporting', rationale='题目只核对给定信息的辨认或计算；本要求含独立表达、作图或实测，必须另按人工任务观察。')
                changes.append({'point_id': row['id'], 'before': before, 'after': deepcopy(m)})

    def mapping(point, task, qid, family, rationale, role='direct'):
        row, q = rows[point], questions[qid]
        assert (row['book_id'], row['chapter_id']) == (q['book_id'], q['chapter_id'])
        assert task in row['requirements'] and (role != 'direct' or row['assessment_modes'][task] == 'bounded')
        raw = json.dumps(q, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        new = dict(question_version_id=qid, question_sha256=hashlib.sha256(raw).hexdigest(), task=task,
                   family=family, role=role, rationale=rationale)
        found = next((m for m in row['mappings'] if (m['question_version_id'], m['task']) == (qid, task)), None)
        if found:
            before = deepcopy(found)
            found.clear(); found.update(new)
        else:
            before = None
            row['mappings'].append(new)
        changes.append({'point_id': point, 'before': before, 'after': deepcopy(new)})

    for i in (3, 6, 9, 12):
        mapping('math-g2-upper:activity2:body', 'distinguish', f'family-chapter-math-g2-upper-activity2-{i:02d}-v1',
                'math-g2-upper:activity2:身体尺要先校准',
                '本题只求小安若干拃的总长，小乐的一拃虽给出却无需使用；未实际辨析不同人的身体尺差异，只计辅助。', role='supporting')

    # Recognizing information is directly assessed only when recognition itself is the requirement.
    mapping('math-g2-upper:1:compare', 'understand', 'family-chapter-math-g2-upper-1-depth-compare-understand-1-v1', 'g2:classification:read-category-entry', '把“梨3个”对应到该类别数量，直接检验读懂记录；不据此宣称会独立解释分类方法。')
    mapping('math-g2-upper:2:word', 'understand', 'family-chapter-math-g2-upper-2-depth-word-understand-1-v1', 'g2:multiply:identify-group-and-size', '同时辨认每份4颗、6袋两个量；仅计辨认每份量和份数，不计独立口述。')
    mapping('math-g2-upper:3:word', 'understand', 'family-chapter-math-g2-upper-3-depth-word-understand-1-v1', 'g2:divide:identify-total-and-group-size', '明确识别18张总量与每袋3张两个分组条件，符合本项识别要求。')
    mapping('math-g2-upper:activity1:direction', 'understand', 'family-chapter-math-g2-upper-activity1-depth-direction-understand-1-v1', 'g2:direction:opposite-cardinal-pair', '辨认南北相对，直接考查相对方向；转身后的独立理由不在此映射中。')
    mapping('math-g2-upper:5:word', 'understand', 'family-chapter-math-g2-upper-5-depth-word-understand-1-v1', 'g2:tables:recognize-total-relation', '从7盒每盒8支辨认总量关系，符合辨认要求；不替代自己建立新关系。')
    # A genuine no-mapping requirement already has both division models installed.
    for i in range(1, 5):
        mapping('math-g2-upper:3:word', 'apply', f'family-word-g2-share-{i}-v1', 'g2:division:find-share-size', '已知总量与份数求每份量的单步平均分；四题只是变数与情境，合计一种解题动作。')
    mapping('math-g2-upper:3:word', 'apply', 'family-chapter-math-g2-upper-3-depth-quotient-apply-a01955df4637-v1', 'g2:division:find-number-of-groups', '已知30颗、每袋5颗，求袋数；与已知份数求每份量区别，题已安装，无需重编。')
    mapping('math-g2-upper:4:units', 'understand', 'family-chapter-math-g2-upper-4-depth-estimate-understand-2-v1', 'g2:units:choose-from-magnitude', '门高在2厘米与2米之间选择，直接核对选择合适长度单位，不证明实际估测或测量。')

    mapping('math-g7-upper:6:shapes', 'understand', 'family-chapter-math-g7-upper-6-depth-shapes-01-v1', 'g7:shapes:recognize-plane-shape', '本项要求辨认常见图形，区分三角形与立体图形直接符合；不据此完成观察作图。')
    mapping('math-g7-upper:4:polynomial', 'apply', 'family-chapter-math-g7-upper-4-depth-polynomial-01-v1', 'g7:polynomial:count-terms', '从符号划分3x²、−2x、5并求项数；与原有求单项式次数为不同解题动作。')
    mapping('math-g7-upper:4:polynomial', 'transfer', 'family-chapter-math-g7-upper-4-challenge_variety-012-v1', 'g7:polynomial:cancel-leading-coefficient', '由平方项系数2−k=0确定结构，且返回一次项系数；未要求用整式独立解释实际数量。')
    mapping('math-g7-upper:1:absolute', 'transfer', 'family-chapter-math-g7-upper-1-challenge_variety-009-v1', 'g7:absolute:two-positions-from-distance', '距−3为2给出−5和−1两个位置，再结合中点选距离；直接核对位置约束，不计数轴作图。')
    # These challenge questions share the solving action with existing tasks; no extra family.
    mapping('math-g2-upper:1:classify', 'transfer', 'family-chapter-math-g2-upper-1-challenge_variety-001-v1', 'g2:classification:cross-table-conservation', '同一批卡片更换类别后核对两种分类及总量；与既有更换卡片题共用题型，不因多选增加题型。')
    mapping('math-g7-upper:2:power', 'transfer', 'family-chapter-math-g7-upper-2-challenge_variety-010-v1', 'math-g7-upper:2:先乘方再乘除', '分别计算A、B、C后排序求差，按运算次序直接求值；与既有运算顺序题共用题型。')
    mapping('math-g7-upper:6:bisect', 'transfer', 'family-chapter-math-g7-upper-6-challenge_variety-014-v1', 'g7:angle:two-bisectors', '内射线顺序确定，先求80°再平分，夹角为20°+40°；与既有两条平分线题共用题型。')

    assert len([r for r in data['rows'] if r['book_id'] in ('math-g2-upper','math-g7-upper')]) == 53
    return data, changes


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--changes', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists() or args.changes.exists():
        raise FileExistsError('use new output paths; previous evidence is preserved')
    data, changes = build()
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    args.output.write_bytes(raw)
    args.changes.write_text(json.dumps(changes, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(), 'mapping_decisions':len(changes), 'new_questions':0}))
