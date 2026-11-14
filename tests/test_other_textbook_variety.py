"""Cross-subject tasks: source bounds, distinct tasks, preservation and grading."""
from collections import Counter
from fractions import Fraction
import json

from learning_service import chapter_practice as chapter
from learning_service.app import run_worker_once
from learning_service.practice_coverage import report
from learning_service.practice import bank as word_bank
from learning_service.textbooks import BOOKS, learning_scope
from test_family_math import family

BATCHES = ('math_g7_multistep', 'upper_variety', 'remaining_variety')
# These three additive batches were authored before the lower-book catalogue
# existed; lower books are covered by their own chapter batches.
COVERED_BOOKS = {
    'math-g7-upper', 'math-g7-lower', 'chinese-g2-upper', 'chinese-g2-lower',
    'chinese-g7-upper', 'chinese-g7-lower', 'english-g7-upper', 'ethics-g2-upper',
    'ethics-g7-upper', 'history-g7-upper', 'geography-g7-upper', 'biology-g7-upper',
}


def questions():
    return {k:q for batch in BATCHES for k,q in chapter.bank(batch).items()}


def values(q):
    return [f['options'][int(f['answer'])-1] if f['options'] else Fraction(f['answer']) for f in q['responses']]


def test_every_remaining_scope_has_distinct_tasks_and_bounded_sources():
    qs = questions()
    expected = {(b['id'],c['id']) for b in BOOKS if b['id'] in COVERED_BOOKS for c in b['chapters']}
    assert {b['id'] for b in BOOKS if b['id'] in COVERED_BOOKS} == COVERED_BOOKS
    assert {q['book_id'] for q in qs.values()} == COVERED_BOOKS
    counts = Counter((q['book_id'],q['chapter_id']) for q in qs.values())
    assert counts == dict.fromkeys(expected, 2)
    assert len(qs)==180 and len(expected)==90
    assert Counter(q['grade'] for q in qs.values())=={2:44,7:136}
    for scope in expected:
        selected = [q for q in qs.values() if (q['book_id'],q['chapter_id'])==scope]
        assert len({q['design']['family'] for q in selected})==2
        assert len({q['prompt'] for q in selected})==2
    for q in qs.values():
        _, c = learning_scope(f"math-g{q['grade']}-v1",q['book_id'],q['chapter_id'])
        assert all(c['printed_page'] <= p <= c['printed_page']+c['page_end']-c['page_start']
                   for p in q['source']['topic_printed_pages'])
        assert not q['review']['teacher_reviewed']
        assert q['source']['reference_scope']=='topic_location_not_verbatim_question'
        assert chapter.metadata(q)['task_family']==q['design']['family']
        assert q['design']['assessment_limit']
    # Script reading and phonetic symbols must not be reported as heard/spoken.
    for q in qs.values():
        if q['book_id']=='english-g7-upper' and q['chapter_id'] in ('12','13'):
            assert '文字' in q['prompt'] or '纸面' in q['prompt']
            assert '不' in q['explanation'] or '只计文字理解' in q['explanation']


def test_math_answers_satisfy_independent_constraints():
    qs = questions()
    pick = lambda book,ch,key: next(q for q in qs.values() if q['book_id']==book and q['chapter_id']==str(ch) and q['id'].endswith('-'+key+'-v1'))
    v=lambda ch,key: values(pick('math-g7-upper',ch,key))
    positions=(-4,2,5)
    assert v(1,'distances')==[abs(positions[j]-positions[i]) for i,j in [(0,1),(1,2),(0,2)]]
    a,b,total,distance=v(1,'absolute-constraints');assert abs(a)==3 and abs(b)==5 and a<0<b and total==a+b and distance==abs(a-b)
    balances=[];balance=-3
    for change in [7,-5,4]:balance+=change;balances.append(balance)
    assert v(2,'changes')==[balances[1],balances[2],balance+3]
    assert v(2,'operation-order')==[-8,-3,1]
    a,b,cost=v(3,'fare');assert a*3+b==8 and a*4+b==10 and cost==a*6+b
    a,b,count,tables=v(3,'table-pattern');assert [a*n+b for n in range(1,4)]==[4,6,8] and count==a*8+b and a*tables+b==32
    a,b,value=v(4,'coefficients')
    for x in (-9,0,3): assert a*x+b==3*(2*x-1)-2*(x+4)
    assert value==a*(-2)+b
    k,value,choice=v(4,'cancel-variable');assert choice=='仍为8'
    for x in (-7,0,4): assert (k*x+3)-(2*x-5)==value
    a,b,x,left=v(5,'fraction-equation');assert a*3==b*4==12 and (x-1)/3==(x+1)/4==left
    a,b,adult,child=v(5,'tickets');assert adult+child==10 and 18*adult+12*child==150 and a*adult+b==150
    m,bc,bm=v(6,'midpoint');assert m-0==10-m and bc==10-4 and bm==abs(m-4)
    cob,aod,coe,doe=v(6,'angle-bisectors');assert cob+40==120 and aod*2==40 and coe*2==cob and doe==aod+coe
    v=lambda ch,key: values(pick('math-g7-lower',ch,key))
    x,a,b=v(7,'parallel-angles');assert a==3*x+10 and b==5*x+10 and a+b==180
    lo,hi,cube=v(8,'root-bounds');assert hi-lo==1 and lo**2<50<hi**2 and cube**3==-27
    assert v(9,'reflection-shift')==[3,4,5,-1]
    x,y,total=v(10,'system-check');assert x+y==9 and 2*x+3*y==total==23
    bound,count,largest=v(11,'integer-solutions');solutions=[x for x in range(-10,10) if -2*x+3>9 and x>=-6]
    assert -2*bound+3==9 and count==len(solutions) and largest==max(solutions)
    assert v(12,'survey')==[20,50,'不能代表全班']
    assert v(7,'second')==[30,'同位角相等，两直线平行']
    a,b,total=v(8,'second');assert a<0 and b>=0 and a*a==b*b==81 and a+b==total
    x,y,_=v(9,'second');assert (x-4,y+3)==(-1,5)
    assert v(10,'second')==['乙',5,2]
    count,cost,allowed=v(11,'second');assert cost==12+5*count<=32<12+5*(count+1) and allowed=='允许'
    other,chess,ball=v(12,'second');assert other+12+18==40 and chess*40==12*100 and ball*40==18*100


def test_cross_subject_facts_and_numeric_readings():
    qs = questions()
    v=lambda book,ch,key: values(next(q for q in qs.values() if q['book_id']==book and q['chapter_id']==str(ch) and q['id'].endswith('-'+key+'-v1')))
    assert v('geography-g7-upper',2,'coordinates')==['北半球','西半球','不是']
    assert v('geography-g7-upper',3,'scale')==[2000,2,'向西']
    assert v('geography-g7-upper',6,'population')==[2000,1500,'甲地']
    assert v('geography-g7-upper',5,'second')[:2]==[22,140]
    assert v('biology-g7-upper',2,'microscope')==[100,400,'变少']
    assert v('biology-g7-upper',4,'plant-evidence')[:2]==['蕨类植物','被子植物']
    assert v('biology-g7-upper',5,'second')==['环节动物','节肢动物','不能']
    assert v('biology-g7-upper',7,'classification')==['A与B',1,2,3]
    assert v('history-g7-upper',4,'second')==[2,1,3]
    assert v('history-g7-upper',6,'second')==[2,3,'不是']
    assert v('english-g7-upper',16,'second')==[2,3,1]
    assert v('english-g7-upper',12,'second')==['Wednesday','5:30']
    assert v('chinese-g2-lower',3,'second')==['氵',9]


def test_editorial_tiers_do_not_call_lookup_or_single_inference_hard():
    from learning_service.practice_design import presentation
    qs=questions()
    assert Counter(presentation(q)['difficulty'] for q in qs.values())=={'easy':20,'normal':152,'hard':8}
    old=[q for batch in ('upper','remaining') for q in chapter.bank(batch).values() if q['difficulty']=='hard']
    assert len(old)==78
    assert Counter(presentation(q)['difficulty'] for q in old)=={'easy':15,'normal':63}
    for q in old:
        assert q['difficulty']=='hard' and q['extension'] is True  # frozen bytes retained
        assert presentation(q)['extension'] is False
    # Existing mathematics demand levels are not flattened by subject expansion.
    assert all(presentation(q)['difficulty']==q['difficulty'] for q in chapter.bank('math_g7_multistep').values())


def test_additive_install_and_all_new_tasks_launch_restore_and_grade(family):
    _,db,api,headers=family
    for batch in chapter.BATCHES:
        if batch not in BATCHES:chapter.install(db,batch)
    with db.session() as c:
        before={r[0]:{tuple(x) for x in c.execute('SELECT * FROM "'+r[0]+'"')} for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    for batch in BATCHES:
        assert chapter.install(db,batch)['added']==len(chapter.bank(batch))
        assert chapter.install(db,batch)['added']==0
    with db.session() as c:
        delta={}
        for table,old in before.items():
            current={tuple(x) for x in c.execute('SELECT * FROM "'+table+'"')};assert old<=current
            if current-old:delta[table]=len(current-old)
        assert delta=={'questions':180,'question_versions':180,'audit_events':3}
    qs=questions()
    for grade in (2,7):
        response=api.get('/api/v1/question-choices',headers={**headers,'X-Learner-Id':f'family-g{grade}'})
        assert response.status_code==200 and 'field_answers' not in response.text
        items={r['question_version_id']:r for r in response.json()['items']}
        for q in qs.values(): assert (q['id'] in items)==(q['grade']==grade)
    for q in qs.values():
        h={**headers,'X-Learner-Id':f"family-g{q['grade']}"}
        response=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id']})
        assert response.status_code==201, response.text
        data=response.json();item=data['items'][0]
        restored=api.get('/api/v1/test-sessions/'+data['session_id'],headers=h).json()['items'][0]
        assert item['response_fields']==restored['response_fields']
        assert data['answer_key'] is None
        for field in item['response_fields']:assert set(field)=={'id','label','units','options'}
        token=api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",headers=h).json()
        result=api.post(f"/api/v1/test-items/{item['test_item_id']}/answers",headers={**h,'Idempotency-Key':q['id']},json={'challenge_id':token['challenge_id'],'nonce':token['nonce'],'raw_answer':q['answer']})
        assert result.status_code==202
        run_worker_once(db,api.app.state.settings)
        assert api.get('/api/v1/attempts/'+result.json()['attempt_id'],headers=h).json()['outcome']=='correct'
    with db.session() as c:
        assert c.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0


def test_g7_coverage_preserves_expression_and_template_limits():
    ids=set(chapter.bank())|set(word_bank())
    rows={r['id']:{t['id']:t for t in r['tasks']} for r in report('math-g7-v1',ids)['items']}
    for point,task in [('3:expression','apply'),('3:pattern','transfer'),('5:model','transfer'),('2:add','transfer')]:
        t=rows['math-g7-upper:'+point][task]
        assert t['family_count']==0 and t['supporting_question_count']>0
    assert rows['math-g7-upper:1:line']['transfer']['family_count']==1
    assert rows['math-g7-upper:6:bisect']['transfer']['family_count']==2
