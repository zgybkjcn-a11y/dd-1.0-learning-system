"""Local, source-backed first inventory for lower books; no installation or mapping changes.

The 61 inherited point rows remain byte-equivalent as JSON values. New entries are
requirements for future authoring, never question evidence or learner completions.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_service.textbooks import BOOKS, PDF_SHA256, SECTION_STARTS

BASE = ROOT / 'learning_data/verification/lower-inventory-20261113'
PLAN = ROOT / 'learning_service/data/family_subject_coverage_plan_v16.json'
SNAPSHOT = ROOT / 'learning_data/verification/upper-subject-review-20261112/review-v17/installed-questions.json'
DEST = ROOT / 'docs/quality/lower-knowledge-inventory-2026-11-13.json'
NEW_BOOKS = {'math-g2-lower', 'ethics-g2-lower', 'english-g7-lower', 'ethics-g7-lower',
             'history-g7-lower', 'geography-g7-lower', 'biology-g7-lower'}

# Each tuple is a concrete initial knowledge/ability slice, not an exhaustive unit.
# title | pages | bounded authoring goal | independently observed manual task
SPECS = {
'math-g2-lower': {
'activity1': [
 ('钟面与时分秒', [2,3], '在完整钟面和明确单位下读时刻，区分时刻与经过时间，使用1时=60分、1分=60秒。', '实际拨钟、测量一分钟活动并记录；说明记录的是时刻还是时长。'),
 ('时间小书', [5,7], '从按顺序给出的时间记录提取起止时刻，计算不跨日的简单经过时间。', '制作自己的时间小书，保留真实记录和修订；不能用选择题替代作品。')],
'1': [
 ('余数的意义与约束', [11,12,15], '由分组材料求商和余数，检验被除数=除数×商+余数及0≤余数<除数。', '用小棒实际分组并解释为什么余数必须小于除数。'),
 ('余数在情境中的处理', [19], '区分求完整组数、剩余数量与至少所需容器数，说明余数是否需要多一组。', '自己提出并解释两种余数处理不同的生活问题。')],
'2': [
 ('倍数与数量关系', [25,27,31], '辨认作为一份的量，用乘除法处理求几倍、求几倍量、已知几倍求一份量。', '用实物或线段图解释“多几”和“几倍”的不同；完整说清单位与比较对象。')],
'3': [
 ('数位与十进制组成', [41,44,50], '读写含零的数，按数位组成分解数，并联系10个一百是一千。', '用计数器或方块表示含零的数，说明零的占位作用。'),
 ('整十整百整千加减', [57], '先统一计数单位，再计算整十整百整千数的简单加减。', '口述相同单位数量相加减的过程，并用计数器核对。')],
'4': [
 ('加减笔算与进退位', [64,65,69], '按相同数位对齐完成加减，定位漏进位或漏退位的错误。', '独立写竖式，解释进退位的数位意义；不能只据最终数值判定过程正确。'),
 ('加减各部分关系', [73], '运用和=加数+加数及加数=和−另一个加数，补全未知量并验算。', '将一道加法改编为对应减法问题，说明数量关系。')],
'activity2': [
 ('数学连环画', [83,84], '检查故事中的数量、问题和算式是否对应。', '自编并绘制数学连环画，讲清故事、问题、算式和结果；保留作品及提示记录。')],
'5': [
 ('数与运算的关联整理', [87,89,92], '综合检验数位、商余数及乘除数量关系，明确每个计算解决的量。', '独立制作关系图并解释至少两种联系，不能把重复计算拆为多个题型族。')],
},
'ethics-g2-lower': {
'1': [
 ('健康、快乐与关心他人', [2,5,9], '依据具体事例区分锻炼、分享快乐和帮助他人的行为。', '口述一次愿意分享的快乐经历，并在角色扮演中回应他人感受。'),
 ('坚持与收获', [12], '在给定过程记录中指出持续行动与结果的关系。', '自选一项适宜的小目标，制定并记录连续行动；未执行时只标计划。')],
'2': [
 ('亲近自然与爱护生命', [16,20], '在明确情境中辨认观察自然与伤害动植物的差别。', '进行不伤害动植物的观察，口述或画出真实发现。'),
 ('水与纸的用途', [24,28], '从给定生活材料归类水和纸的用途；节约做法的具体教材依据仍需展开。', '记录一次用水或用纸的实际情境，提出可行改进并由成人核对。')],
'3': [
 ('勤劳、诚信、自强与榜样', [32,36,39,42], '把故事中的具体行为与相应品质对应，避免只凭人物称号判断。', '讲清一个身边榜样的事实，提出自己可以学习的具体做法。')],
'4': [
 ('梦想与行动', [46,50,54,58], '区分个人梦想、共同愿望及实现梦想所需的学习行动。', '用自己的话提出梦想及近期可执行的一步；实际完成情况另记，不能照抄示例算完成。')],
},
'english-g7-lower': {
'1': [
 ('动物信息与理由', [2,4,5], '读完整动物资料卡，匹配名称、外形、栖息地、食物和能力；使用why/because表达材料中给定的原因。', '自主介绍一种动物，并回答同伴追问；信息准确性和交流表现分别记录。'),
 ('名词复数与描述词', [3,5], '在明确语境下辨认规则与不规则复数，选择与资料一致的形容词。', '朗读词和句子，人工核对复数词尾发音；文字选择不算口语验收。'),
 ('保护动物与证据', [6,7,8], '据短文提取动物面临的问题、原因与保护方法，区分主旨和细节。', '自写动物介绍或设计展示图，解释保护理由；按内容、组织和交流表现复核。')],
'2': [
 ('规则与义务', [9,13], '依据场景辨析祈使句及can、must、have to的使用，保留禁止与没有必要的区别。', '为一个具体场所设计规则标志，并解释规则帮助了谁、为何可行。')],
'3': [
 ('运动频率与物品归属', [17,21], '根据日程表达how often并按明确指代使用名词性物主代词。', '询问同伴运动习惯并转述；频率回答、指代准确与真实交流分别核对。')],
'4': [
 ('饮食与可数性', [25,29], '在具体语境判断名词可数性、数量形式和饮食偏好表达，避免把可数性绝对化。', '角色扮演询问饮食偏好并提供选择，说明搭配理由。')],
'5': [
 ('正在发生的活动', [33,37], '根据当前活动线索使用be+doing的陈述、疑问和否定形式。', '模拟打电话，说明自己和同伴正在做什么，并回应信息。')],
'6': [
 ('天气与时态', [41,45], '用天气线索区分习惯性活动与正在进行的活动，选择一般现在时或现在进行时。', '介绍一个天气情境及相应安排，与同伴交换并回应建议。')],
'7': [
 ('过去事件与日记', [49,53], '根据明确过去时间识别动词时态并按事件先后整理学校活动。', '写一篇连贯日记，说明事件与感受；不能由排序题认定完整写作。')],
'8': [
 ('故事顺序与续写', [57,61], '辨认叙事时态及事件因果；一般现在时叙事的选择必须有上下文口径。', '独立复述或续写故事结尾，保持人物、情节及所选时态一致。')],
'9': [('拓展阅读', [65], '将拓展材料关联原单元，提取资料中可核对的事实。', '选择一段材料解释主旨与支持细节；后续篇目逐篇复核。')],
'10': [('听力脚本', [74], None, '仅供听后核对或教师备课；真实听辨需另有音频和人工观察，脚本文字理解不算听力达标。')],
'11': [('语音参照', [83], None, '用语音表辅助朗读，由人工核对实际发音；字符匹配不能验收口语。')],
'12': [('语法参照', [88], None, '与对应单元的完整语境练习合用，解释规则适用条件；不另计独立覆盖族。')],
'13': [('单元词汇', [97], None, '按单元查词并回到上下文使用，保留多义、词性与发音差别。')],
'14': [('字母序词汇', [106], None, '示范按字母序查找词条，再联系原句确认义项。')],
'15': [('小学衔接词汇', [115], None, '把已学词放回当前单元语境，实际朗读或造句由人工核对。')],
'16': [('不规则动词表', [118], None, '查找原形与过去式，回到第7、8单元应用；双形式应保留，不能凭单一答案表排除变体。')],
},
'ethics-g7-lower': {
'1': [
 ('青春期变化与差异', [2,3,4,5], '根据材料区分生理变化与心理矛盾，识别尊重差异和求助的方法。', '使用虚构情境提出支持建议并说明理由，不要求披露个人发育或隐私。'),
 ('身体边界与求助', [9,10,11], '在虚构情境中识别越界与求助方式，明确遭遇侵害不是受害者的错。', '用假设情境练习表达边界与寻求可信成人帮助；不收集真实遭遇。'),
 ('情绪与情感', [14,15,16,17,19,21], '区分情绪表现、触发因素与稳定情感；比较适合具体情境的调节方法。', '用愿意分享或虚构的事例说明情绪、需要和调节过程，由人工核对表达。')],
'2': [
 ('自尊、自信与自强', [26,27,30,34,35,40,41], '以事实区分自尊与伤害他人、自信与自负自卑，识别目标和行动的关系。', '制定恰当目标并说明能力依据，后续用实际行动记录核对自强表现。')],
'3': [
 ('传统思想与当代表达', [50,51,56,63], '将材料中的思想理念与具体行为对应，区分尊重差异和要求完全相同。', '选择一个传统文化事例，说明来源和当代可行做法，允许多种有依据的表达。')],
'4': [
 ('法律的规范与保障', [76,77,80,85,90], '在题内给足规则和事实时辨别权利义务与公共利益，识别保护知识产权的理由。', '围绕虚构纠纷说明事实、规则和求助路径；后续出题须复核法律适用，不由教材摘句裁定现实案件。')],
},
'history-g7-lower': {
'1': [
 ('隋朝建立、统一与灭亡', [4,6,7], '在时间线上区分581建立、589统一、618灭亡，并据材料联系赋役与社会矛盾。', '以多个材料组织因果说明，不把朝代灭亡归结为一个工程或单一原因。'),
 ('运河与科举', [5,6], '区分工程、制度及其作用，按给定材料说明南北联系和选官方式的变化。', '据有来源的材料说明制度或工程的作用与局限；地图连通关系须另行逐图核对。')],
'2': [('北宋政治初步', [44,45,46], '区分建国与结束五代十国分裂的时间，依据措施比较加强中央集权的作用及代价。', '整理措施—目的—影响关系，引用具体材料；本条不覆盖辽夏金元与全部经济文化内容。')],
'3': [('明朝统治初步', [86,87,88], '对应明朝建立、迁都与强化皇权的措施，区分制度与考试文体。', '用材料比较两项措施的联系与不同，不据名词记忆认定历史解释完成。')],
'4': [
 ('史料与史事要素', [130,131], '区分史料出处、内容与推断，按时间地点人物原因过程结果整理事件。', '选择两则材料互证并说明不能推出的结论。'),
 ('节日起源与传承', [128], '从给定材料识别习俗的延续与变化，不把当代习俗直接外推全部历史。', '完成有来源的节日调查或展示；真实调查与作品由人工验收。')],
'5': [('古代史年表参照', [132], None, '用年表查事件时间并返回相关课文核对；同一史事不因附录重复再计一个族。')],
},
'geography-g7-lower': {
'7': [
 ('亚洲位置、地势与图示', [2,3,5,6], '在完整方向、经纬网、图例条件下描述位置，比较剖面的地势变化。', '独立在地图上定位并解释剖面方向；未看清原图的数据不按文字层猜读。'),
 ('亚洲人口与经济指标', [12,14,16], '依标明年份的数据区别人口总量、密度、经济总量和人均指标。', '选用同口径材料解释地区差异，不能把2020年数据写成当前实时值。')],
'8': [('日本自然环境初步', [20,21], '在给定地图和文字材料中定位岛屿，联系板块位置与火山地震。', '结合可核对的地图说明自然条件与生活的联系；东南亚、印度、俄罗斯后续展开。')],
'activity1': [('东南亚世界遗产项目', [55,56], '检查分类表与地图图例的一致性，保留遗产统计的时间口径。', '自主完成资料表、位置图与线路方案，注明来源并说明保护价值。')],
'9': [('西亚位置初步', [58,59], '根据完整图例判断三洲五海联系，区分里海这个湖泊与海洋。', '独立画出交通联系示意并说明条件；其他地区与西亚资源部分后续展开。')],
'10': [('美国自然条件与农业初步', [90,92], '用给定位置与地形资料分析农业条件，不由单一条件推出全部农业分布。', '据完整地图作自然条件与生产活动的有依据说明；巴西及美国其他内容待展开。')],
'activity2': [('雨林固碳项目', [107,108], '区分森林面积、碳储量与单位面积指标；数字须先经原图复核再出题。', '绘制光合作用和气候关系图，注明统计对象；书中文字层的图中数字乱码，不采用为答案依据。')],
'11': [('南北极比较', [110,111,112], '比较主体海陆、气温降水与生物，说明比较指标和材料范围。', '用表格和地图形成有证据的比较说明，后续补充科考与环境保护要求。')],
'appendix': [('地图图例参照', [118], None, '供本册读图任务查询；本轮仅核对附录位置，具体图形逐项目视核对仍待完成。')],
},
'biology-g7-lower': {
'1': [
 ('种子萌发的条件与过程', [2,3,4,5], '区分环境条件和种子自身条件，辨认单变量对照设计并整理萌发记录。', '实际开展适宜的种子观察，保留分组、时间、重复记录和未萌发结果；模拟表格不算已做实验。'),
 ('根的生长与花的结构', [8,9,16,17,18], '区分根的细胞分裂与伸长，将花的主要结构与传粉过程联系。', '在教师指导下观察结构并绘图；只选结构名称不能验收观察、解剖与实验操作。')],
'2': [('光合作用与呼吸作用初步', [29,31,33,38], '比较物质变化、能量转换与条件，识别对照实验中的变量。', '先解释实验方案；教材涉及酒精加热和腐蚀性试剂的实验由教师组织，当前只记录待观察，后续补水分利用等要求。')],
'activity1': [('植物栽培项目', [51,52], '判断观察指标、记录表与所探究条件是否对应。', '制定方案、分工实施、保留连续记录并据失败修订，报告实际结果；不要求成功开花才算有记录。')],
'3': [('生殖与青春期', [58,60,64], '对应生殖器官功能、受精与胚胎发育的场所，区分一般发育规律与个体差异。', '用教材模型解释过程或虚构情境提出健康建议；不要求提供本人或家人的身体数据。')],
'4': [('营养物质与证据初步', [70,71,74], '依据食物资料区分主要营养物质及作用，比较同条件重复组并计算平均值。', '说明均衡选择食物的依据；实验操作、消化吸收和食品安全需继续逐项展开。')],
'5': [('呼吸系统与通气初步', [92,93,98], '对应呼吸道和肺，联系胸廓变化与吸呼气；不把呼吸运动和细胞呼吸混为一谈。', '制作或使用模型解释呼吸运动，指出模型局限；气体交换全过程后续细化。')],
'6': [('血液组成与功能初步', [103,104,106], '区分血浆和血细胞，结合结构解释红细胞运输氧的作用。', '使用合成检验单或模型解释证据，不收集真实检验单；血管、心脏与循环路线待展开。')],
'7': [('泌尿系统与尿形成', [124,125,127], '区分尿的形成、输送、储存及排出，比较滤过和重吸收及原尿与尿液。', '独立画出流向并解释结构功能，其他排泄途径后续细化。')],
'activity2': [('人体结构模型项目', [130,131], '检查模型结构、功能说明与验证方法是否对应。', '设计、制作、检验并优化模型，记录分工、实际修改和局限。')],
'appendix': [('食物成分表参照', [135], None, '作为营养任务的参考，先核对每列单位、食部与表下注释再取数；本轮不编造或推定每100克口径。')],
},
}

# Additional first-scope review, without silently revising the inherited plan.
OLD_FIRST = {
'math-g7-lower': {'pages':[2,3,4,5,13,14,26,27], 'finding':'旧perpendicular定位p3实际为对顶角例题；垂直定义在p4、作图基本事实在p5。距离部分还需补读。旧映射未据此改为已审。',
 'manual':'实际画垂线和平移图形，标对应点，区分平行判定和性质的推理方向。'},
'chinese-g2-lower': {'pages':[1,2,3,4,8,10,11,12,13,14], 'finding':'第一单元除春景与观察外，p12书写及按提问读句、p13口语交际需独立保留；不能用古诗识别题代表朗读或表达。',
 'manual':'用温和语气实际说一段请求或解释；另行朗读、背诵并书写，记录孩子实际表现。'},
'chinese-g7-lower': {'pages':[1,2,6,7,11,13,15,16,17,18,23,26], 'finding':'第一单元精读要求联系关键语句、细节与人物背景；p23长短句互换、p26写作不能由辨析题替代。文言部分及正式题完整要求仍待逐题复核。',
 'manual':'围绕具体人物事例解释特点，并独立改写句子或写人物片段，核对细节是否支撑中心。'},
}


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def build():
    assert sha(PLAN) == 'f3861070f1081833a47bf5a2cca5dedb714de44f0fc8878eea85ec2d9490189a'
    assert sha(SNAPSHOT) == 'b9a4d858786f65cbf91349ad6950e106a27313cc2ce847888b54f5dc7246c4ce'
    old = json.loads(PLAN.read_bytes())['rows']
    installed = json.loads(SNAPSHOT.read_bytes())
    sources = {r['book_id']:r for r in json.loads((BASE/'source-evidence.json').read_bytes())}
    lower = [b for b in BOOKS if b['id'].endswith('-lower')]
    assert len(lower)==10 and sum(len(b['chapters']) for b in lower)==75
    assert set(SPECS)==NEW_BOOKS
    scopes=[]
    for b in lower:
        bid=b['id']; source=sources[bid]
        assert source['sha256']==PDF_SHA256[bid]
        # Verify originals again with a streaming hash; never load a huge PDF per point.
        assert sha(ROOT/source['source_pdf']) == source['sha256']
        if bid in NEW_BOOKS:
            assert set(SPECS[bid])=={c['id'] for c in b['chapters']}
        for n,c in enumerate(b['chapters']):
            cid=c['id']; start=c['printed_page']; end=c['page_end']-source['offset']
            rows=[r for r in old if (r['book_id'],r['chapter_id'])==(bid,cid)]
            formal=[q['id'] for q in installed if (q.get('book_id'),q.get('chapter_id'))==(bid,cid)]
            points=[]
            for i,(title,pages,bounded,manual) in enumerate(SPECS.get(bid,{}).get(cid,[]),1):
                assert all(start<=p<=end for p in pages)
                points.append({'id':f'{bid}:{cid}:inventory-{i}', 'title':title,
                    'source_printed_pages':pages,'source_pdf_pages':[p+source['offset'] for p in pages],
                    'bounded_candidate_action':bounded,'automatic_grade_evidence':[],
                    'manual_task':{'prompt':manual,'criteria':['说明具体材料或步骤','理由与本条知识相符','保留实际表现及所用提示，不以模板代替'],
                        'automatically_graded':False,'completion':'not_observed','learner_record_created':False},
                    'review_status':'initial_requirements_only','question_candidates':[],
                    'teacher_reviewed':False,'curriculum_standard_crosscheck':'pending'})
            if bid in NEW_BOOKS:
                assert not rows and not formal
            else:
                assert rows and formal
            ref=(bid=='english-g7-lower' and int(cid)>=10) or (bid=='history-g7-lower' and cid=='5') or cid=='appendix'
            kind='reference' if ref else 'extended_reading' if bid=='english-g7-lower' and cid=='9' else 'project' if cid.startswith('activity') else 'unit'
            sample=OLD_FIRST.get(bid) if n==0 else None
            reviewed_pages=sorted({p for pt in points for p in pt['source_printed_pages']} | set(sample['pages'] if sample else []))
            scopes.append({'id':f'{bid}:{cid}', 'book_id':bid,'grade':b['grade'],'chapter_id':cid,
                'title':c['title'],'printed_range':[start,end],'kind':kind,
                'priority':'first_scope' if n==0 or (bid=='math-g2-lower' and cid=='1') else 'later_scope',
                'source_pdf':source['source_pdf'],'source_pdf_sha256':source['sha256'],
                'source_review':{'method':('local_page_image_view_no_OCR' if source['native_text_chars']==0 else 'native_text_selected_passages_no_OCR') if reviewed_pages else 'inherited_plan_not_newly_reviewed',
                    'selected_printed_pages':reviewed_pages,'all_unit_pages_reviewed':False,
                    'figures_and_tables_fully_verified':False},
                'textbook_section_starts':[{'printed_page':p,'title':t} for p,t in SECTION_STARTS.get(bid,{}).items() if start<=p<=end],
                'new_initial_points':points,'inherited_points':deepcopy(rows),
                'inherited_mapping_status':'not_reaudited_this_batch' if rows else 'none',
                'first_scope_review':deepcopy(sample),
                'formal_question_snapshot_ids':formal,'formal_question_count':len(formal),
                'candidate_question_count':0,'point_inventory_complete':False,
                'remaining':'继续按小节核对遗漏知识与动作；逐题复核旧映射或编写新候选；教师签署和真实难度校准仍待完成。'})
    result={'schema':'dd-lower-initial-knowledge-inventory-v1','date':'2026-11-13',
        'status':'local_review_only_not_runtime_coverage',
        'priority_basis':'没有新的校内进度信息，暂按各册起始范围；二下数学同时列入首个正式单元。用户提供进度后调整。',
        'limitations':['75个目录范围有清单，不等于75个范围知识点穷尽。',
            '新增7册只建立抽样原页支撑的初步要求；单元内未列内容仍待展开，未生成下册候选题。',
            '原有3册61条知识点完整沿用subject-v16，映射不在本轮冒称已复核；仅起始范围有补充原页笔记。',
            '参考附录不要求按普通单元凑题；脚本不证明听力、音标不证明发音、认选不证明独立表达或实操。',
            '教材统计值保留原年份；图中乱码数字、未复核的表格口径不得用作出题答案。'],
        'provenance':{'subject_v16_sha256':sha(PLAN),'formal_snapshot_sha256':sha(SNAPSHOT),
            'script_sha256':sha(Path(__file__)),'original_source_index_sha256':sha(BASE/'source-evidence.json')},
        'scopes':scopes,
        'summary':{'books':10,'catalogue_scopes':75,'new_books':7,'new_book_scopes':54,
            'inherited_points':sum(len(s['inherited_points']) for s in scopes),
            'new_initial_points':sum(len(s['new_initial_points']) for s in scopes),
            'first_scopes':sum(s['priority']=='first_scope' for s in scopes),
            'new_lower_questions':0,'new_runtime_mappings':0,'complete_point_inventories':0,
            'formal_question_counts_by_book':dict(Counter(q.get('book_id') for q in installed if q.get('book_id','').endswith('-lower'))),
            'new_book_formal_question_count':0},
        'boundaries':{'production_database_accessed':False,'production_import_deploy':False,'runtime_registry_changed':False,
            'external_model_ocr_embedding_calls':0,'c01_called_or_started':False,'learner_record_created':False,
            'teacher_reviewed':False,'student_difficulty_calibrated':False,'real_phone_acceptance':'deferred'}}
    assert result['summary']['inherited_points']==61
    assert len({s['id'] for s in scopes})==75
    return result


def write_new(path,text):
    if path.exists():
        if path.read_text()!=text:raise ValueError(f'Existing output differs; create a new revision: {path}')
    else:path.write_text(text)


def render(x):
    out=['# 下册初步知识、能力与人工任务清单（本地）','',
        '2026-11-13。10册、75个目录范围；新增7册54范围已建立抽样原页支撑的初步要求。原有3册61条保留原清单，映射待逐题复核。',
        '','**清单不表示配题或达标**：本轮下册新增题数0；没有运行映射、导入或部署。全部范围仍标知识点未穷尽；教师签署和课标复核待完成。',
        '',x['priority_basis'],'',
        '[机器可读清单](../quality/lower-knowledge-inventory-2026-11-13.json) · [原件哈希](../../learning_data/verification/lower-inventory-20261113/source-evidence.json)',
        '','两本二下教材无文字层，已直接查看本地页面图像；其余使用原生文字选段，未使用OCR。图表尚未完整逐图验收。',
        '','| 册 | 范围 | 新初步条目 | 沿用条目 | 正式题快照 |','| --- | ---: | ---: | ---: | ---: |']
    for b in sorted({s['book_id'] for s in x['scopes']}):
        ss=[s for s in x['scopes'] if s['book_id']==b]
        out.append(f"| {b} | {len(ss)} | {sum(len(s['new_initial_points']) for s in ss)} | {sum(len(s['inherited_points']) for s in ss)} | {sum(s['formal_question_count'] for s in ss)} |")
    out+=['','以上题数来自固定正式题快照，未重新访问生产数据库。已有题不自动证明本清单中的完整能力。']
    for s in x['scopes']:
        out += ['',f"## {s['book_id']} / {s['chapter_id']} · {s['title']}",'',
                f"书内范围{s['printed_range']}；类型{s['kind']}；优先级{s['priority']}。本轮选读页：{s['source_review']['selected_printed_pages'] or '沿用旧清单，未新审'}。"]
        if s['first_scope_review']:
            r=s['first_scope_review'];out+=['',r['finding'],'','人工任务补充：'+r['manual']]
        for p in s['new_initial_points']:
            out+=['',f"- **{p['title']}**（书内页{p['source_printed_pages']}）：{p['bounded_candidate_action'] or '参考用途，不单独计自动覆盖。'}",
                  f"- 人工任务：{p['manual_task']['prompt']}（未观察，不自动判分）"]
        if s['inherited_points']:
            out+=['','沿用的知识/能力要求（旧映射未在此重新签署）：','']
            for p in s['inherited_points']:out.append(f"- {p['title']}：{p['requirements']['check']}；人工：{p['requirements'].get('express','见原条目人工任务')}。")
        out+=['','后续：'+s['remaining']]
    out+=['','下一批优先：二下数学有余数除法、七下英语动物信息与理由、七下生物萌发条件；先按完整动作做自编候选和错误反馈，保留实操人工核对。其余单元按真实校内进度调整。',
          '','下册历史目前只展开各大单元起始内容；地理未展开的国家/地区、生物未展开的小节继续保留为清单缺口。不得把每个目录有一条记录当成整章完整。','']
    return '\n'.join(out)


if __name__=='__main__':
    data=build()
    write_new(DEST,json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    write_new(ROOT/'docs/verification/LOWER-KNOWLEDGE-INVENTORY-2026-11-13.md',render(data))
    print(json.dumps(data['summary'],ensure_ascii=False))
