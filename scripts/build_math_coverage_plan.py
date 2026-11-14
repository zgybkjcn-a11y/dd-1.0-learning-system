"""Freeze a draft inventory and explicit question/task relationships for two books.

Page numbers identify topic locations, never quotations or grading sources.
Rows and requirements are an assistant-authored checklist pending curriculum
standard/teacher cross-review. Question difficulty does not determine task type.
"""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.textbooks import learning_scope, PDF_SHA256
from learning_service.practice import bank as initial
from learning_service.reserve_practice import bank as reserve
from learning_service.chapter_practice import bank as supplement

ROOT = Path(__file__).resolve().parents[1]
TASKS = {'understand': '概念理解', 'apply': '直接应用', 'distinguish': '易错辨析', 'transfer': '综合迁移'}

# chapter | topic key | title | location | concrete understanding/application/error/transfer requirements
SPEC = {
'math-g2-upper': '''
1|classify|分类标准与整理|1|说清分类标准|按一种标准分类计数|区分总数与分类数量|换标准核对总数不变
1|compare|分类结果的比较|2|读懂分类记录|比较各类多少|区分多几与共几|从记录提出并解决问题
2|meaning|乘法的意义|11|说明几个相同加数|加法与乘法互写|辨认能否直接用乘法|从情境说明每份量与份数
2|tables|1～6乘法口诀|16|说明口诀与算式联系|用口诀求积|辨析口诀和乘积错误|利用已知积求相邻积
2|word|乘法解决问题|28|辨认每份量和份数|求相同几份总量|辨析多余条件和所求量|乘法与加减法组合解决问题
3|equal|平均分与除法意义|31|辨认平均分及两种分法|求每份量或份数|区别平均分和任意分|比较两种分法表达同一总量
3|quotient|用口诀求商|41|解释乘除联系|用2～6口诀求商|核对除数和商的含义|用乘法检验除法结果
3|word|除法解决问题|46|识别总量与分组条件|解决单步平均分问题|辨析先留出还是先平均分|分组与增减组合问题
activity1|direction|东南西北|50|辨认相对方向|根据朝向判断左右|区别自身左右与固定方向|转身后判断方向
activity1|route|校园路线|49|说明路线参照位置|描述沿途方向|发现描述缺少起点|设计并解释一条校园路线
4|units|厘米和米|55|选择合适长度单位|换算米和厘米|辨析单位不一致|结合情境选择单位和计算
4|ruler|直尺测量与线段|55|说明尺子起点和刻度|读出两端刻度差|辨析未从零刻度起量|画指定长度线段并测量验证
4|estimate|长度估测|55|建立厘米和米的表象|估测并记录长度|比较估测与实测|解释估测方法并改进
activity2|body|身体尺的使用|69|说明拃步等身体尺|用校准后的身体尺测量|辨析不同人的身体尺差异|比较身体尺与标准尺测量
6|relations|运算的复习与关联|91|解释加减乘除联系|选择合适运算求值|辨析算式与情境是否匹配|综合使用运算解决问题
6|organize|整理与表达|91|说明知识图中的联系|整理本册方法|检查分类与单位错误|提出问题并解释方法
5|tables|7～9乘法口诀|73|说明口诀对应关系|用7～9口诀求积|辨析积与因数关系|根据已知积推导另一积
5|quotient|7～9表内除法|81|说明乘除互逆|用口诀求商|辨析求份数与每份量|同一总量换分法
5|word|乘除综合问题|87|辨认情境数量关系|解决单步应用问题|检查单位与所求量|组合乘除加减解决问题
''',
'math-g7-upper': '''
1|signed|正负数与基准|2|解释零和基准|用正负数表达相反意义|区别绝对量与变化量|解释允许偏差等情境
1|rational|有理数分类|7|说明整数分数与有理数|按类别分类数|辨析零和负分数归类|用多种标准分类并说明
1|line|数轴|8|说明数轴三要素|由点读数或按数描点|检查不合规范数轴|用位置关系求距离
1|opposite|相反数|11|解释数轴对称|求一个数的相反数|辨析零和负号的意义|用相反数关系求未知数
1|absolute|绝对值|13|解释到原点距离|求绝对值|辨析绝对值相同的两个数|结合位置约束确定原数
1|order|有理数大小比较|14|解释负数比较规则|比较有理数大小|辨析绝对值大与数值大|综合数轴和绝对值排序
2|add|有理数加法|25|解释同号异号相加|按法则计算|辨析符号与绝对值错误|用加法解释多次变化
2|subtract|有理数减法|30|解释减法转化|计算有理数差|辨析减去负数|用差表达变化与比较
2|multiply|有理数乘法|38|解释乘积符号|计算乘积|辨析多个负因子和零|情境中的连续倍率变化
2|laws|乘法运算律|38|解释交换结合分配律|用运算律简算|检查分配律漏乘或符号|分数混合运算选择策略
2|divide|除法与倒数|43|解释倒数与除法转乘法|计算商或倒数|辨析零无倒数及符号|多步运算中的乘除选择
2|power|乘方|51|解释底数指数与幂|计算有理数乘方|区别负数乘方与幂的相反数|按次序计算混合运算
2|scientific|科学记数法|54|说明系数和指数范围|大数与科学记数法互写|检查系数范围与指数|科学记数法结合单位换算
2|approximate|近似数|55|解释精确度|按要求取近似值|辨析近似数与准确数|根据测量要求解释取值
2|binary|进位制探究（选学）|63|解释进位规则|按给定规则换算|辨析不同进位制数码含义|解释一种换算策略
3|expression|列代数式|69|解释字母与运算含义|由数量关系列式|辨析书写和数量对应错误|从新情境表达数量关系
3|value|代数式的值|79|解释代入求值|按给定值计算|检查负数代入括号|整体代入或规律求值
3|pattern|规律表达|83|识别变化与不变量|用式表达简单规律|用特例检查猜想|说明一般式为何成立
4|polynomial|单项式与多项式|89|解释系数次数项|识别整式的项与次数|辨析负号常数项次数|由条件确定整式结构
4|like|同类项与合并|95|解释同类项条件|合并同类项|辨析字母指数不同的项|结合参数条件处理同类项
4|bracket|去括号|95|解释括号前符号作用|正确展开括号|检查漏变号或漏乘|去括号合并后求值
4|application|整式加减应用|105|说明式的数量含义|求两个整式的和差|检查减去整个式|用整式说明数量关系
5|equation|方程与方程的解|111|解释方程及解的含义|代入检验一个解|辨析一元一次方程定义|从数量关系列方程
5|equality|等式的性质|115|说明等式变形条件|按性质变形|辨析乘除零等错误|用性质说明解题步骤
5|solve|解一元一次方程|120|解释移项和系数化1|解含括号分母的方程|查出去分母移项错误|选择步骤并代入检验
5|model|实际问题与方程|133|识别未知量和等量关系|列方程并求解|辨析单位基数和无效解|解释结果是否符合情境
6|shapes|立体图形与平面图形|151|辨认常见图形|联系实物与图形|辨析平面与立体|从不同观察角度说明图形
6|elements|点线面体|155|说明基本元素联系|辨认组成元素|辨析概念混淆|解释生活中的点线面体关系
6|lines|直线射线线段|162|解释端点与延伸|区分并表示三种线|辨析长度与表示方法|结合条件判断位置关系
6|segments|线段比较与运算|164|解释中点和距离|计算线段长度|检查点的先后顺序|中点与线段关系综合求解
6|angle|角的概念与度量|170|解释顶点两边与角度|读写或测量角度|辨析边长与角大小|不同角单位或测量问题
6|bisect|角的比较与运算|173|解释角平分线|求角和差或一半|检查内外射线位置|组合角关系求未知角
6|complement|余角和补角|176|解释90度180度关系|求余角补角|辨析相等角和互余互补|结合多个角关系推理
6|design|场地设计实践（综合）|189|说明设计所需量|计算实际长度|检查测量与比例单位|给出方案并说明约束
'''}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def build():
    questions = initial() | reserve() | supplement()
    rows = []
    for book, text in SPEC.items():
        for line in text.strip().splitlines():
            chapter, key, title, page, *tasks = line.split('|')
            _, ch = learning_scope(f"math-g{book.split('-g')[1].split('-')[0]}-v1", book, chapter)
            page = int(page)
            assert ch['printed_page'] <= page <= ch['printed_page'] + ch['page_end'] - ch['page_start']
            rows.append({'id': f'{book}:{chapter}:{key}', 'book_id': book, 'chapter_id': chapter,
                         'title': title, 'printed_page': page, 'location_kind': 'topic_location_not_quote',
                         'requirements': dict(zip(TASKS, tasks, strict=True)), 'mappings': []})
    by_id = {row['id']: row for row in rows}

    def link(book, chapter, key, task, titles):
        row = by_id[f'{book}:{chapter}:{key}']
        for title in titles.split('|'):
            matched = [q for q in questions.values() if (q['book_id'], q['chapter_id'], q['title']) == (book, chapter, title)]
            assert matched, title
            for q in matched:
                row['mappings'].append({'question_version_id': q['id'], 'question_sha256': hashlib.sha256(canonical(q)).hexdigest(),
                                        'task': task, 'family': book+':'+chapter+':'+title,
                                        'rationale': '核对题干与解析：'+title+'，对应要求：'+row['requirements'][task]})

    g2, g7 = 'math-g2-upper', 'math-g7-upper'
    links = [
        (g2,'1','classify','apply','按颜色整理'),(g2,'1','classify','transfer','同一物品两种分法'),
        (g2,'1','compare','apply','分类后比较'),
        (g2,'2','word','apply','小剧场排座位|文具店买铅笔|小组去春游|体育室数皮球'),
        (g2,'2','word','transfer','植树后再添两棵|整理小书架|整盒和零散的笔|彩笔和橡皮|找出空座位|两种买法谁多|少了两块的方阵|买练习本找零'),
        (g2,'3','equal','apply','把苹果平均分|把铅笔平均分|把积木平均分|把书平均分'),
        (g2,'3','word','transfer','还要装几袋球|分贴纸再分享|送出整袋橘子|拿出两盒小球|找回总数|先留再分|两队人数一样吗|丢失的一袋'),
        (g2,'activity1','direction','apply','认方向|面对方向找右边'),(g2,'activity1','direction','transfer','转身后辨方向'),
        (g2,'4','ruler','apply','尺子不从零开始'),(g2,'4','units','apply','米和厘米'),(g2,'4','units','transfer','两次截取'),
        (g2,'activity2','body','apply','用自己的拃测量|整拃和剩余长度'),(g2,'activity2','body','distinguish','身体尺要先校准'),
        (g2,'5','word','apply','礼堂座位|领取练习本|餐厅摆碗|分发卡片'),
        (g2,'5','word','transfer','花园搬走几棵花|退回一本练习本|一起包饺子|拿走一份气球|买票找零|补齐空位|换一种分法|找出多分的'),
        (g2,'6','relations','apply','复习乘除关系'),(g2,'6','relations','transfer','先分再合|不同包装凑总数'),
        (g7,'1','opposite','apply','相反数'),(g7,'1','line','transfer','数轴的距离'),(g7,'1','absolute','transfer','绝对值与位置'),
        (g7,'2','add','apply','清晨到中午|潜水员上升'),(g7,'2','subtract','apply','记录一天温差'),
        (g7,'2','add','transfer','知识竞赛积分|水库三天的变化|仓库出入货|闯关积分规律|机器人回到哪里'),
        (g7,'2','subtract','transfer','两地温差|两天的温度变化|比较两天升温'),
        (g7,'2','multiply','transfer','冷库降温|往返运输路程|多个因子与小数'),(g7,'2','multiply','apply','确定两数乘积'),
        (g7,'2','divide','apply','负数的倒数|除法的符号'),(g7,'2','power','apply','负数的三次方'),
        (g7,'2','power','transfer','先乘方再乘除'),(g7,'2','laws','apply','用分配律计算'),(g7,'2','laws','transfer','分数与分配律'),
        (g7,'2','scientific','apply','科学记数法的指数'),(g7,'2','scientific','transfer','科学记数法与换算'),
        (g7,'2','approximate','apply','按精确度取近似值'),
        (g7,'3','value','apply','代入求值|从数量关系到值'),(g7,'3','value','transfer','代数式的整体代入'),
        (g7,'4','like','apply','合并同类项的系数'),(g7,'4','bracket','transfer','括号前的负号|合并后再代入'),
        (g7,'5','model','apply','班级人数|商店打折|通话费用|两车相遇'),
        (g7,'5','model','transfer','追上先出发的人|打折后还盈利|两种租车方案|合作完成任务|配套生产安排|先独做再合作|尚未相遇的距离|利润率的基数'),
        (g7,'6','segments','apply','线段中点'),(g7,'6','segments','transfer','线段上的顺序'),(g7,'6','bisect','apply','角平分线'),
    ]
    for args in links:
        link(*args)
    data = {'format': 'dd-math-coverage-plan-v1', 'version': '2026-11-09-v1',
            'status': 'assistant_draft_not_exhaustive', 'teacher_reviewed': False,
            'curriculum_standard_crosscheck': 'pending', 'inventory_complete': False,
            'pdf_sha256': {book: PDF_SHA256[book] for book in SPEC}, 'task_labels': TASKS, 'rows': rows}
    raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
    (ROOT/'learning_service/data/family_math_coverage_plan_v1.json').write_bytes(raw)
    print(len(rows), hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    build()
