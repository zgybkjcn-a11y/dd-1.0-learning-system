"""Sixteen authored tasks that check multiple quantities or judgments together."""
import json
from chapter_practice_authoring import Batch


def build():
    b = Batch('math_g2_multistep')

    def field(label, answer, check, unit='', options=()):
        return dict(label=label, answer=str(answer), independent_check=check,
                    units=([unit, 'cm'] if unit == '厘米' else [unit]) if unit else [], options=list(options))

    def table(caption, rows):
        return dict(kind='table', caption=caption, rows=rows)

    def add(ch, key, level, title, stem, fields, hint, explanation, page, point, task, role, family, visual=None):
        b.add('math-g2-upper', ch, level, title, stem+'\n请分别完成下面各项。', 0, '0', hint, explanation)
        q = b.questions[-1]
        q['id'] = f'family-chapter-math-g2-upper-{ch}-multistep-{key}-v1'
        for i, f in enumerate(fields): f['id'] = chr(97+i)
        q['responses'] = fields
        q['answer'] = json.dumps({f['id']: f['answer'] for f in fields}, ensure_ascii=False, separators=(',', ':'))
        del q['independent_check']
        q['source'].update(basis='既有教材主题核对；分步任务为本地自编，非教材原题', topic_printed_pages=[page])
        q['design'] = dict(form='多项判断' if any(f['options'] for f in fields) else '分步填空',
                           family=family, priority=2, order=len(b.questions),
                           demand='分别完成多个关键结果或判断，所有项目正确才算本题通过',
                           assessment_limit='只检查所填结果和所选判断，不替代独立口述、作图和实测。')
        q['coverage'] = dict(point_id=f'math-g2-upper:{ch}:{point}', task=task, role=role, family=family,
                             rationale='按完整任务要求标记对应或辅助；增加填空数量不作为新增题型或能力达标的依据。')
        if visual: q['visual'] = visual

    add('1','two-standards','normal','分别按颜色和形状整理',
        '每张卡片只有一种颜色和一种形状。按表中的记录，先算红色卡片总数，再算方形卡片总数。',
        [field('红色卡片共几张',10,'6+4','张'),field('方形卡片共几张',7,'4+3','张')],
        '按颜色看一行，按形状看一列。','红色有6+4=10张；方形有4+3=7张。两次使用的分类标准不同。',3,'classify','apply','direct','g2:classification:cross-table-count',
        table('卡片记录（张）',[['颜色','圆形','方形'],['红色','6','4'],['蓝色','5','3']]))
    add('1','changed-cards','hard','变了颜色也变了形状',
        '表中18张卡片互不重复。取出其中3张红色圆形卡，逐张改成蓝色方形卡后放回。卡片数量没有增加。分别填写变化后的四类数量。',
        [field('红色共几张',7,'6+4-3','张'),field('蓝色共几张',11,'5+3+3','张'),field('圆形共几张',8,'6+5-3','张'),field('方形共几张',10,'4+3+3','张')],
        '每次只看一种标准。变化的3张从哪一类减少，又给哪一类增加？',
        '红色10−3=7，蓝色8+3=11；圆形11−3=8，方形7+3=10。按颜色7+11=18，按形状8+10=18，总数都不变。',3,'classify','transfer','direct','g2:classification:cross-table-conservation',
        table('变化前（张）',[['颜色','圆形','方形'],['红色','6','4'],['蓝色','5','3']]))
    add('2','array-count','normal','先补完整再数圆片',
        '图中每行有6个位置，共4行。●表示圆片，空表示缺少圆片的位置。分别填完整方阵、缺少和实际摆出的圆片数。',
        [field('摆满全部位置需要几片',24,'4*6','片'),field('现在缺少几片',5,'5','片'),field('现在实际有几片',19,'6+6+6+1','片')],
        '可以先算摆满时的数量，再减去空位；也可以逐行数后相加。',
        '摆满需要4×6=24片；最后一行空5格，实际24−5=19片。用6+6+6+1也能核对。',11,'meaning','understand','supporting','g2:multiply:incomplete-array',
        dict(kind='grid',caption='4行、每行6个位置',rows=[['●']*6,['●']*6,['●']*6,['●','空','空','空','空','空']]))
    add('2','neighbor-products','hard','用一个积推另外两个积',
        '已知5组圆片，每组6片，共30片。每组仍是6片，分别把组数变成6组和4组。请利用30片的记录填写结果。',
        [field('6组共几片',36,'30+6','片'),field('4组共几片',24,'30-6','片'),field('每增加或减少1组，数量相差几片',6,'6','片')],
        '组数每变1组，就是多或少6片。','6组比5组多1组，30+6=36；4组少1组，30−6=24。两次与30的差都是6。',23,'tables','transfer','direct','g2:multiply:adjacent-groups')
    add('3','two-divisions','normal','同一批彩笔的两种分法',
        '24支彩笔，一种分法是每盒装4支，另一种是每盒装6支。分别填写需要的盒数，并判断总支数是否改变。',
        [field('每盒4支，需要几盒',6,'24/4','盒'),field('每盒6支，需要几盒',4,'24/6','盒'),field('换分法后总支数',1,'1',options=['不变','变多','变少'])],
        '每盒支数乘盒数，都应该是24。','24÷4=6盒；24÷6=4盒。4×6和6×4都是24，盒数变化了，彩笔总数没有变。',34,'equal','transfer','supporting','g2:divide:compare-group-sizes')
    add('3','extra-round','hard','先分一轮再分剩下的',
        '30张贴纸分给6个小组。先给每组4张，再把剩下的平均分给这6组。请按顺序填写。',
        [field('第一轮共分出几张',24,'6*4','张'),field('第一轮后剩下几张',6,'30-24','张'),field('第二轮每组又分到几张',1,'6/6','张')],
        '先求已经分出去多少，再求剩下多少，最后把剩下的平均分。','第一轮6×4=24张；剩30−24=6张；第二轮每组6÷6=1张。每组最后5张，6×5=30可核对。',46,'word','transfer','direct','g2:divide:subtract-then-share')
    campus=dict(kind='grid',caption='上北下南，左西右东；每相邻格之间有路',rows=[['实验室','花园','图书馆'],['小路','操场','小路'],['校门','小路','食堂']])
    add('activity1','route-directions','normal','分段说出校园路线',
        '从校门先沿最下面一行走到食堂，再沿最右边一列走到图书馆。分别选择这两段路的方向。',
        [field('校门到食堂，向哪里走',1,'1',options=['东','南','西','北']),field('食堂到图书馆，向哪里走',4,'4',options=['东','南','西','北'])],
        '方向以地图标注为准，每次从这一段的起点看终点。','校门到食堂向右，是向东；食堂到图书馆向上，是向北。',50,'route','apply','supporting','g2:direction:segmented-route',campus)
    add('activity1','check-routes','hard','逐条检查绕开操场的路线',
        '从校门到图书馆，每次只走到相邻一格，不能进入中间的操场。分别判断下面三条路线能否按要求到达。',
        [field('北→北→东→东',1,'1',options=['能到达且避开操场','不能满足要求']),field('北→东→北→东',2,'2',options=['能到达且避开操场','不能满足要求']),field('东→东→北→北',1,'1',options=['能到达且避开操场','不能满足要求'])],
        '每走一步就在图中找当前位置，检查是否进入操场。','第一条沿左侧和上侧到达；第二条第2步进入操场；第三条沿下侧和右侧到达。第1、3条满足要求，第2条不满足。',51,'route','distinguish','direct','g2:direction:trace-obstructed-routes',campus)
    add('4','two-lengths','normal','分别测量再比较',
        '图中单位是厘米。甲从刻度2到7，乙从刻度5到11。填写两条线段的长度，再求乙比甲长多少。以刻度为准，不要直接量屏幕。',
        [field('甲长几厘米',5,'7-2','厘米'),field('乙长几厘米',6,'11-5','厘米'),field('乙比甲长几厘米',1,'6-5','厘米')],
        '每条线段都用右端刻度减左端刻度，然后比较长度。','甲7−2=5厘米，乙11−5=6厘米，乙长6−5=1厘米。',57,'ruler','apply','direct','g2:ruler:compare-offset-segments',
        dict(kind='ruler',caption='两条线段在同一把尺子上（厘米）',maximum=12,segments=[dict(label='甲',start=2,end=7),dict(label='乙',start=5,end=11)]))
    add('4','ribbon-plan','hard','彩带够不够再剪四段',
        '1米彩带，先剪3段，每段12厘米，再剪去25厘米。剩下的还想剪4段，每段10厘米。填写已用长度、剩余长度和还差的长度。',
        [field('前两次共用掉几厘米',61,'12+12+12+25','厘米'),field('剩下几厘米',39,'100-61','厘米'),field('再剪4段各10厘米，还差几厘米',1,'40-39','厘米')],
        '先把1米换成100厘米。最后比较剩余长度和40厘米。','先用12+12+12=36厘米，再用25厘米，共61厘米；剩39厘米。4段各10厘米需要40厘米，还差1厘米。',58,'units','transfer','direct','g2:measurement:unit-cutting')
    add('activity2','calibrate-span','normal','先校准再用身体尺',
        '小宁用标准尺校准，1拃约18厘米。每次手掌张开一样大，连续测量时没有空隙或重叠。按这个标准，填写3拃和5拃的长度。',
        [field('3拃约几厘米',54,'18+18+18','厘米'),field('5拃约几厘米',90,'18+18+18+18+18','厘米')],
        '3拃和5拃分别用3个、5个18厘米相加。','3拃约18+18+18=54厘米；5拃约18+18+18+18+18=90厘米。这里采用题目给定的校准值，实际测量仍需验证。',70,'body','apply','supporting','g2:body:calibrate-then-estimate')
    add('activity2','compare-measures','hard','估测和实测放在一起比',
        '小宁用校准后的身体尺估测一条彩带：1拃约18厘米，彩带约4拃。用标准尺复测是68厘米。填写估测值、误差大小，并判断估测偏大还是偏小。',
        [field('估测约几厘米',72,'18+18+18+18','厘米'),field('估测值与实测值相差几厘米',4,'72-68','厘米'),field('这次估测',1,'1',options=['偏大','偏小','相等'])],
        '先把4拃换成厘米，再与68厘米比较。','4拃约72厘米，比标准尺测得的68厘米多4厘米，所以估测偏大。',71,'body','transfer','supporting','g2:body:compare-estimation-errors',
        table('两次记录',[['方法','记录'],['身体尺','1拃约18厘米；共4拃'],['标准尺','68厘米']]))
    add('5','array-removal','normal','拿走两列以后还有多少',
        '一共有7行、每行8个圆片，摆成方阵。拿走最右边的2整列。分别填写原有、拿走和剩余的数量。',
        [field('原来共有几个',56,'7*8','个'),field('拿走了几个',14,'7*2','个'),field('剩下几个',42,'56-14','个')],
        '每列7个。拿走2列，每行就少2个。','原有7×8=56个，拿走7×2=14个，剩56−14=42个；7行每行6个也是42个。',75,'tables','transfer','direct','g2:tables:array-partition')
    add('5','bead-plan','hard','两种手串分步做',
        '54颗珠子，先做3条手串，每条用8颗；再把剩下的全部做成每条6颗的手串。填写每一步的数量，最后求手串总条数。',
        [field('先用掉几颗珠子',24,'3*8','颗'),field('剩下几颗珠子',30,'54-24','颗'),field('后来做了几条手串',5,'30/6','条'),field('两次一共做了几条手串',8,'3+5','条')],
        '珠子数与手串条数要分清。最后把两次的条数相加。','先用24颗，剩30颗，后来做30÷6=5条，总共3+5=8条。',83,'word','transfer','direct','g2:tables:multiply-subtract-divide')
    add('6','budget-steps','normal','先买本子再买彩笔',
        '有50元，先买4本本子，每本8元；剩下的钱买彩笔，每盒彩笔9元。按顺序填写，彩笔只能整盒购买。',
        [field('买本子花几元',32,'4*8','元'),field('买完本子剩几元',18,'50-32','元'),field('最多还能买几盒彩笔',2,'18/9','盒')],
        '先算花费，再算余额，最后求余额里有几个9。','本子花32元，剩18元，18÷9=2盒，刚好用完。',92,'relations','apply','direct','g2:review:multiply-subtract-divide')
    add('6','compare-packages','hard','核对两种整盒购买方案',
        '4组同学，每组需要6支同样的铅笔。甲包装每盒8支、9元，乙包装每盒6支、7元。方案甲只买甲包装，方案乙只买乙包装，两种方案都正好买够。填写两种花费，再比较。',
        [field('方案甲共花几元',27,'24/8*9','元'),field('方案乙共花几元',28,'24/6*7','元'),field('选哪种方案更省钱',1,'1',options=['方案甲','方案乙']),field('省几元',1,'28-27','元')],
        '先求一共需要几支，再分别求盒数和花费。别只比较一盒的价格。','共需4×6=24支；甲需3盒，3×9=27元；乙需4盒，4×7=28元。甲便宜1元，虽然甲每盒价格更高。',92,'relations','transfer','direct','g2:review:enumerate-minimum-cost',
        table('包装信息',[['包装','每盒支数','每盒价钱'],['甲','8支','9元'],['乙','6支','7元']]))
    assert len(b.questions) == 16
    return b


if __name__ == '__main__':
    build().write()
