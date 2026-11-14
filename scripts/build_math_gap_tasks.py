"""Author the five reviewed bounded math gaps; never change an installed version."""
import hashlib
import json
from copy import deepcopy

from chapter_practice_authoring import Batch, ROOT
from knowledge_task_authoring import N, C, E
from challenge_task_authoring import M, O
from varied_task_authoring import table
from learning_service.textbooks import learning_scope


class GapTasks(Batch):
    def task(self, book, ch, key, point, task, title, prompt, fields, explanation,
             family, rationale, *, level='normal', visual=None):
        self.add(book, ch, level, title,
                 prompt+'\n完成所有作答项；多选需选全且不多选，排序按指定推导顺序。',
                 0, '0', '先检查条件和所求量，再逐项核对；方程检验要代回原方程。', explanation)
        q=self.questions[-1]
        q['id']=f'family-chapter-{book}-{ch}-{self.name}-{key}-v1'
        for i,f in enumerate(fields):
            f['id']=chr(97+i)
            if f['options']:
                correct=[f['options'][int(n)-1] for n in f['answer'].split(',')]
                shift=hashlib.sha256((q['id']+f['id']).encode()).digest()[0]%len(f['options'])
                if f['kind']=='order':shift=1+shift%(len(f['options'])-1)
                f['options']=f['options'][shift:]+f['options'][:shift]
                f['answer']=','.join(str(f['options'].index(x)+1) for x in correct)
                if f['kind']=='choice':f['independent_check']=f['answer']
        q['responses']=fields
        q['response_protocol']='structured-fields-v3'
        q['answer']=json.dumps({f['id']:f['answer'] for f in fields},ensure_ascii=False,separators=(',',':'))
        del q['independent_check']
        _,chapter=learning_scope(f'math-g{q["grade"]}-v1',book,ch)
        pages={('math-g2-upper','3'):31,('math-g2-upper','5'):81,
               ('math-g7-upper','3'):83}
        page=pages.get((book,ch),120 if point=='solve' else 133)
        q['source'].update(topic_printed_pages=[page],
                           reference_scope='topic_location_not_verbatim_question',
                           basis='固定教材目录与主题核对；题干、记录及图表为本地原创，非教材原题')
        q['knowledge']=dict(point_id=f'{book}:{ch}:{point}',task=task,role='direct',
                            family=f'{book}:{ch}:{family}',rationale=rationale)
        q['design']=dict(form=title,family=q['knowledge']['family'],priority=4,
                         order=len(self.questions),skills=[point],demand=rationale,
                         assessment_limit='只核对指定辨认、计算和检验；独立口述、建模、作图及实操仍按人工任务核对。')
        if visual:q['visual']=visual


def build():
    b=GapTasks('math_gaps')
    b.task('math-g2-upper','3','division-records','equal','understand','分配记录辨认',
        '把12颗珠子全部分完。甲：分成3份，每份4颗；乙：每份3颗，分成4份；丙：分成3份，分别2、4、6颗。',[
            M('哪些记录是平均分？',['甲','乙'],'甲','乙','丙'),
            C('甲是先确定什么？','份数','份数','每份颗数','剩下颗数'),
            C('乙是先确定什么？','每份颗数','份数','每份颗数','剩下颗数')],
        '甲、乙每份都一样多，是平均分；丙每份不一样多。甲先定3份求每份4颗；乙先定每份3颗求4份。',
        'classify-complete-distribution-records','比较完整分配记录，既辨认平均分，也区分先定份数与先定每份量。')
    b.task('math-g2-upper','3','complete-distributions','equal','understand','补全分配方案',
        '有18块积木，每次都要全部分完。方案一平均分给3个盒子；方案二每盒装6块。另有人将18块分为3堆：4、6、8块。',[
            N('方案一每盒几块？',6,'18/3','块'),N('方案二需几个盒子？',3,'18/6','个'),
            C('方案一的3、方案二的6分别表示什么？','份数、每份量','份数、每份量','每份量、份数','都表示总量'),
            C('4、6、8块这三堆是平均分吗？','不是','是','不是','只要全部分完就是')],
        '18÷3=6（块），18÷6=3（个）。两方案都平均分；3是指定份数，6是指定每份量。4、6、8不相等，因此不是平均分。',
        'complete-partitions-under-two-constraints','按两种已知条件补全分配并核对角色，同时排除总数相同但不平均的方案。')
    b.task('math-g2-upper','5','regroup-total','quotient','transfer','同一批卡片改分',
        '56张卡片，先每组7张，全部分完；收回所有卡片，再平均分成7组。全程不增加、不拿走卡片。',[
            N('第一次分成几组？',8,'56/7','组'),N('第二次每组几张？',8,'56/7','张'),
            C('两次算式56÷7=8中，7的意义怎样变？','每组张数变成组数','每组张数变成组数','始终是每组张数','始终是组数'),
            N('第二次每组再增加1张，需要补进几张？',7,'7*(9-8)','张',
              errors=[E(1,'每一组都要增加1张。','先数共有几组，再求需要补进的总数。')])],
        '第一次56÷7=8组；第二次56÷7=8张。总量仍为56，但除数7从每组张数变为组数。7组各补1张，共补7张。',
        'forward-regroup-and-test-change','固定总量完成两种分法，区分同算式中量的角色，再检验增加每份量对总量的影响。')
    b.task('math-g2-upper','5','recover-total','quotient','transfer','从分组记录反推',
        '同一批贴纸，第一次每袋8张，正好装满7袋；第二次全部取出后每袋7张，仍正好装完。有人说第二次也只需7袋。',[
            N('这一批共有几张？',56,'8*7','张'),N('第二次需几袋？',8,'8*7/7','袋'),
            C('“第二次只需7袋”的说法怎样？','不对，会剩7张','不对，会剩7张','对，袋数总不变','不对，还差7张才能装满'),
            N('若改为每袋8张、只装6袋，会剩几张？',8,'8*7-8*6','张')],
        '先反推8×7=56张，再算56÷7=8袋。7袋只能装49张，还剩7张；6袋每袋8张共48张，剩8张。',
        'recover-total-and-audit-regrouping','从第一次分法反推守恒总量，再核对另一分法及错误方案，区别于给定总量直接换分。')
    b.task('math-g7-upper','3','invariant-table','pattern','understand','表格中的变化与不变',
        '租用同一种工具，费用规则固定：一次基础费5元，另按每天3元计费。表中n是天数，C是总费用。',[
            M('随n改变而改变的量有哪些？',['天数n','总费用C'],'天数n','总费用C','每天费用3元','基础费5元'),
            N('每条记录的C−3n都等于多少？',5,'(3*4+5)-3*4','元'),
            C('规则不变时，哪个关系对所有正整数n成立？','C−3n=5','C−3n=5','C÷n=3','C−n=5')],
        'n与C变化；每天3元和一次基础费5元固定。扣去随天数变化的3n，剩下的C−3n始终是5。',
        'separate-variable-columns-and-invariant-residual','由费用规则和表格区分变量与固定参数，并识别跨行保持的数量关系。',
        visual=table('工具租用记录',[['天数n','1','2','4'],['总费用C（元）','8','11','17']]))
    b.task('math-g7-upper','3','invariant-structure','pattern','understand','拼接结构中的不变量',
        '用小棒把n个同样大小的正方形横向排成一行（n为正整数），相邻两个恰好共用一条边，每条边用1根小棒。第一个需4根，每增加1个正方形只增加3根。',[
            M('增加正方形时，哪些量改变？',['正方形总个数','小棒总根数'],'正方形总个数','小棒总根数','每增加1个所增的小棒数'),
            N('与n个互不共边的正方形相比，n=4时少用几根？',3,'4*4-(4+3*(4-1))','根'),
            C('若小棒总数为s，哪个量保持不变？','s−3n','s−3n','s−n','s÷n'),
            N('上项不变的量等于多少？',1,'(4+3*(5-1))-3*5')],
        '正方形个数与总根数变化，每增加1个所增3根固定。4个连排共用3条边，少3根。s=4+3(n−1)=3n+1，故s−3n=1始终不变。',
        'compare-connected-and-separated-structures','比较共边与不共边结构，识别增长动作及总量扣除增长部分后的不变量；一般式的独立解释仍是人工。')
    b.task('math-g7-upper','5','choose-route','solve','transfer','选择求解路径并检验',
        '解原方程(2x−1)/3+2=(x+5)/2。以下排序使用“先去分母、再去括号、再移项、最后合并”的指定路径。',[
            C('两边同乘6后，哪一步正确？','2(2x−1)+12=3(x+5)','2(2x−1)+12=3(x+5)','2(2x−1)+2=3(x+5)','2(2x−1)+12=x+5'),
            O('把后续三步按指定路径排序','4x−2+12=3x+15','4x−3x=15+2−12','x=5'),
            N('把所得解代回原方程，左边等于多少？',5,'(2*5-1)/3+2'),
            N('把所得解代回原方程，右边等于多少？',5,'(5+5)/2')],
        '同乘6时常数2也要乘6。去括号得4x−2+12=3x+15，移项得4x−3x=15+2−12，故x=5。代回原方程左、右都等于5。',
        'choose-and-sequence-equivalent-transformations','自主选择合法去分母步骤、按指定路径排序，并分别算原方程两边检验，完整核对步骤选择与代入。',level='hard')
    b.task('math-g7-upper','5','repair-route','solve','transfer','纠正路径后回原式检验',
        '原方程2(x−3)=x+4。小林记录：①2x−6=x+4；②2x−x=4−6；③x=−2。请找首个错误、选择修正步骤，再重新求解检验。',[
            C('首个错误及对应的正确修正是什么？','从①到②；应为2x−x=4+6','从①到②；应为2x−x=4+6','从原式到①；应为2x−3=x+4','从②到③；应为x=2'),
            N('修正后x等于多少？',10,'4+6',errors=[E(-2,'−2来自错误移项。','−6移到右边后应变成+6，再重新计算。')]),
            N('把修正后的解代回原方程，左边等于多少？',14,'2*(10-3)'),
            N('把修正后的解代回原方程，右边等于多少？',14,'10+4')],
        '去括号正确；从①到②把−6移到右边应变+6。2x−x=4+6，x=10。代回原式，2(10−3)=14，10+4=14；错误的−2不能使原式相等。',
        'repair-first-invalid-step-and-recheck-original','定位已有求解路径的首个失效步骤，选择修正、重新求解，并在原方程双边验算；与顺推路径选择分开。',level='hard')
    b.task('math-g7-upper','5','identify-model','model','understand','辨认未知量与等量关系',
        '买3本同价笔记本和1支5元的笔，共付29元，求每本笔记本的单价。商店还标着“每天9点开门”。设x表示题目所求的量。',[
            C('x表示什么（单位：元）？','每本笔记本的单价','每本笔记本的单价','3本笔记本总价','笔的单价'),
            M('建立等量关系要用哪些条件？',['3本同价笔记本','笔价5元','共付29元'],'3本同价笔记本','笔价5元','共付29元','9点开门'),
            C('哪个等量关系符合情境？','笔记本总价+笔价=共付款','笔记本总价+笔价=共付款','笔记本单价+笔价=共付款','笔记本总价=共付款+笔价'),
            C('哪个方程对应所设未知量？','3x+5=29','3x+5=29','x+5=29','3(x+5)=29')],
        '所求是每本单价x元，3本同价笔记本共3x元，加笔价5元等于共付款29元。开门时间与此等量关系无关。',
        'select-relevant-conditions-and-quantity-relation','从原情境同时辨认所求未知量、有效条件与等量关系，排除无关信息；不计独立建模。')
    b.task('math-g7-upper','5','critique-model','model','understand','核对不同设元的模型',
        '大桶水量比小桶的3倍多4升，两桶共44升。甲设x为小桶水量，列x+(3x+4)=44；乙设x为大桶水量，却也列x+(3x+4)=44。两桶水量均为正数。',[
            C('谁的未知量定义与所列方程不匹配？','乙','甲','乙','两人都匹配'),
            C('沿用乙的设元，小桶水量应怎样表示？','(x−4)/3','(x−4)/3','3x+4','(x+4)/3'),
            C('沿用乙的设元，哪个方程符合总量关系？','x+(x−4)/3=44','x+(x−4)/3=44','x+3x+4=44','x+(x+4)/3=44'),
            C('沿用乙的设元，x和(x−4)/3分别是什么？','大桶水量、小桶水量','大桶水量、小桶水量','小桶水量、大桶水量','总水量、大桶水量')],
        '甲设小桶为x，大桶为3x+4，方程正确。乙设大桶为x，必须逆向得到小桶为(x−4)/3，再按“大桶+小桶=44”列x+(x−4)/3=44。未知量定义一变，表达式也须改变。',
        'audit-unknown-definition-and-invert-relation','比较两个设元方案，查出未知量与表达式错配，逆向识别小桶表达式并匹配等量关系。',level='hard')
    return b


if __name__=='__main__':
    batch=build()
    target=ROOT/'learning_service/data/family_chapter_math_gaps_v1.json'
    plan_path=ROOT/'learning_service/data/family_subject_coverage_plan_v4.json'
    if target.exists() or plan_path.exists():raise FileExistsError('preserve frozen output')
    from learning_service.chapter_practice import _parse
    _parse(json.dumps({'format':'dd-family-chapter-practice-v1','batch':batch.name,
                      'questions':batch.questions},ensure_ascii=False).encode())
    plan=json.loads((ROOT/'learning_service/data/family_subject_coverage_plan_v3.json').read_bytes())
    plan['version']='subject-coverage-v4-math-gaps'
    for q in batch.questions:
        k=deepcopy(q['knowledge']);point=k.pop('point_id')
        row=next(r for r in plan['rows'] if r['id']==point)
        assert row['assessment_modes'][k['task']]=='bounded'
        row['mappings'].append(dict(question_version_id=q['id'],question_sha256=hashlib.sha256(
            json.dumps(q,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),**k))
    raw=(json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode()
    batch.write()
    plan_path.write_bytes(raw)
    print('subject-v4',hashlib.sha256(raw).hexdigest())
