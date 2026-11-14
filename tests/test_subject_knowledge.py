"""Bounded language answers, independently checked tasks and honest coverage."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import hashlib
import json

import pytest

from learning_service import chapter_practice as chapter, subject_coverage as coverage
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields, validate_short_key
from practice_catalogue import PRACTICE_BOOKS
from test_family_math import family


def pick(book, ch, key=None):
    return next(q for q in chapter.bank('subject_knowledge').values()
                if q['book_id']==book and q['chapter_id']==str(ch)
                and (key is None or q['knowledge']['point_id'].endswith(':'+key)))


def answer_values(q):
    return [f['options'][int(f['answer'])-1] if f['kind']=='choice' else
            Fraction(f['answer']) if f['kind']=='number' else f['answer'] for f in q['responses']]


def test_all_subjects_and_independent_mathematical_constraints():
    qs=chapter.bank('subject_knowledge')
    assert len(qs)==67 and len({q['prompt'] for q in qs.values()})==67
    assert {q['book_id'] for q in qs.values()}=={b['id'] for b in PRACTICE_BOOKS}
    assert Counter(q['grade'] for q in qs.values())=={2:14,7:53}
    g2=lambda ch: answer_values(pick('math-g2-upper',ch))
    assert g2(1)==[8,3] and g2(2)==[18,1,1]
    initial,second,diff=g2(3);assert initial*4==24 and second==initial+2 and diff==second-(initial-2)
    length,right=g2(4);assert 3+length==11 and right-5==length
    v=lambda ch: answer_values(pick('math-g7-upper',ch))
    opposite,inverse,product=v(1);assert opposite+Fraction(-2,3)==0 and inverse*Fraction(-2,3)==product==1
    a,n,_=v(2);assert 1<=a<10 and a*10**n==560000
    for x in (-5,0,7):
        y=2*x-3;assert v(3)==[6*x-3*y+4,y-2*x]
    step,a,b=v(4);assert step==1
    for x in (-3,0,2):assert a*x+b==5-2*(x-3)
    constant,x,left=v(5);assert constant==6 and left==(x-1)/2+1==(x+2)/3
    x,comp,supp=v(6);assert x+comp==90 and x+supp==180 and supp==3*comp
    v=lambda ch: answer_values(pick('math-g7-lower',ch))
    assert v(7)[0]==min([5,7,9]) and v(8)==['有理数','有理数','无理数']
    assert v(9)==['y','x',2]
    coeff,x,y=v(10);assert 2*x+3*y==12 and 3*x-2*y==5 and coeff*x==2*12+3*5
    low,high,count=v(11);solutions=[x for x in range(-20,20) if 3*x-2>=4 and -2*x>-10]
    assert (low,high,count)==(min(solutions),max(solutions),len(solutions))
    data=[10,12,15,15,18,20,22,25];first,second,third,rate=v(12)
    assert [first,second,third]==[sum(lo<=x<hi for x in data) for lo,hi in [(10,15),(15,20),(20,26)]]
    assert rate==100*Fraction(second,len(data))


def test_language_and_science_answers_against_separate_facts():
    v=lambda b,ch,key=None:answer_values(pick(b,ch,key))
    assert v('english-g7-upper',2)==['are','is','on']
    assert v('english-g7-upper',3)==['This','Those','That']
    assert v('english-g7-upper',4)==['Is','is','is']
    assert v('english-g7-upper',5)==['Her','Their','my']
    assert v('english-g7-upper',6)==['is','are','are']
    assert v('english-g7-upper',7)==['What','Why','When']
    assert v('english-g7-upper',8)==['swim','Can','can']
    assert v('english-g7-upper',9)==['plays','play','play']
    assert v('english-g7-upper',10)==['third','twenty-first']
    assert v('english-g7-upper',14)==['has','have','have']
    assert v('english-g7-upper',17)==['children','boxes','women']
    assert v('english-g7-upper',18)[:2]==['twelve','twelfth']
    assert v('chinese-g7-upper',2)==['约定','舍弃']
    assert v('chinese-g7-upper',3)[:2]==['迷惑','危险']
    assert v('chinese-g7-upper',5)[:2]==['看','狗']
    assert v('chinese-g7-lower',1)==['只是','粗略地阅读','历史']
    assert v('chinese-g7-lower',3)[:2]==['只是','罢了']
    assert v('chinese-g7-lower',4)[:2]==['这','品德美好']
    assert v('chinese-g7-lower',6)==['靠近','完成',2]
    assert v('history-g7-upper',2)[:2]==['墨家','法家']
    assert v('history-g7-upper',3,'science')[:2]==['伦','仲景']
    assert v('history-g7-upper',4)[:2]==['贾思勰','祖冲之']
    assert v('history-g7-upper',5)==[len([-3,-2,-1,1,2])-1,2]
    assert v('history-g7-upper',6)[0]==221-202
    assert v('geography-g7-upper',2)==['东半球','西半球','南半球']
    km,cm,_=v('geography-g7-upper',3);assert km*100000==Fraction('3.5')*200000==cm*50000
    assert v('geography-g7-upper',4)[:2]==['平原','高原']
    assert v('geography-g7-upper',5)[:2]==['南半球',26-10]
    assert v('geography-g7-upper',7)[:2]==[600/300,400/100]
    assert v('biology-g7-upper',2)==[10*20,'左上方','变小']
    assert v('biology-g7-upper',3)==[2**3,'分化','分裂']
    assert v('biology-g7-upper',4)[:2]==['苔藓植物','蕨类植物']
    assert v('biology-g7-upper',5)[:2]==['两栖动物','爬行动物']
    assert v('biology-g7-upper',6)==['无','有','是']
    assert v('biology-g7-upper',7)==[len({'甲','甲','乙','丙'}),len({'一','一','一','二'}),'A与B']


@pytest.mark.parametrize('raw',['{}','[]','null','5','{"a":"are"}',
    '{"a":"are","a":"are","b":"is","c":"on"}',
    '{"a":"are","b":"is","c":"on","d":"extra"}',
    '{"a":true,"b":"is","c":"on"}',
    '{"a":"are","b":"is","c":""}', '{"a":"are","b":"is","c":"on or under"}'])
def test_short_answers_reject_invalid_or_extra_guesses(raw):
    key=json.loads(chapter.stored(pick('english-g7-upper',2))['answer_key_json'])
    assert grade_short_fields(raw,key)[0]=='incorrect'
    assert grade_short_fields(json.dumps({'a':' ＡＲＥ ','b':'IS','c':'  on  '}),key)[0]=='correct'
    outcome,feedback=grade_short_fields(json.dumps({'a':'is','b':'is','c':'on'}),key)
    assert outcome=='incorrect' and '2项正确' in feedback and '复数主语' in feedback and '下一步' in feedback
    assert '相符，请对照自己的步骤检查' in feedback


def test_aliases_case_sensitivity_and_feedback_are_explicit():
    q=pick('chinese-g7-upper',2);key=json.loads(chapter.stored(q)['answer_key_json'])
    assert grade_short_fields('{"a":"约","b":"丢下"}',key)[0]=='correct'
    q=pick('english-g7-upper',2);key=json.loads(chapter.stored(q)['answer_key_json'])
    key['field_answers'][0]['case_sensitive']=True
    assert grade_short_fields('{"a":"ARE","b":"is","c":"on"}',key)[0]=='incorrect'
    for q in chapter.bank('subject_knowledge').values():
        key=json.loads(chapter.stored(q)['answer_key_json'])
        assert grade_short_fields(q['answer'],key)[0]=='correct'
        for field in key['field_answers']:
            for err in field.get('errors',[]):
                raw=json.loads(q['answer']);raw[field['id']]=err['answer']
                outcome,feedback=grade_short_fields(json.dumps(raw),key)
                assert outcome=='incorrect' and err['message'] in feedback and err['action'] in feedback


@pytest.mark.parametrize('bad',['missing_kind','duplicates','missing_answer','empty_alias','wrong_kind','correct_error','extra_error_key'])
def test_malformed_frozen_keys_fail_closed(bad):
    key=json.loads(chapter.stored(pick('english-g7-upper',2))['answer_key_json'])
    f=key['field_answers'][0]
    if bad=='missing_kind':key['response_fields'][0].pop('kind')
    elif bad=='duplicates':f['accepted']=['are','ARE']
    elif bad=='missing_answer':f.pop('accepted')
    elif bad=='empty_alias':f['accepted']=[' ']
    elif bad=='wrong_kind':f['kind']='number'
    elif bad=='correct_error':f['errors'][0]['answer']='are'
    else:f['errors'][0]['unexpected']='x'
    assert grade_short_fields('{}',key)[0]=='undetermined'
    with pytest.raises(ValueError):validate_short_key(key['response_fields'],key['field_answers'])


def test_subject_inventory_and_human_boundaries():
    plan=json.loads(coverage.PATH.read_bytes());ids=set(chapter.bank())
    reports=[coverage.report(f'math-g{g}-v1',ids) for g in (2,7)]
    rows=[r for p in reports for r in p['items']]
    assert len(rows)==276 and sum(len(r['tasks']) for r in rows)==658
    assert len({r['id'] for r in rows})==276
    scopes=[s for p in reports for s in p['section_inventory']]
    assert len(scopes)==98 and {s['book_id'] for s in scopes}=={b['id'] for b in PRACTICE_BOOKS}
    assert all(s['point_inventory_complete'] is False for s in scopes)
    assert sum(s['unmapped_available_questions'] for s in scopes)>0
    for r in rows:
        for t in r['tasks']:
            assert set(t['question_ids'])<=ids
            if t.get('assessment_mode')=='human':
                assert t['family_count']==0 and t['status']!='configured'
        if 'manual_task' in r:assert r['manual_task']['automatically_graded'] is False
    # Historical v2 retains math-v6 verbatim; v3 explicitly reviews roles.
    old=json.loads((coverage.PATH.parent/'family_math_coverage_plan_v6.json').read_bytes())
    historical=json.loads((coverage.PATH.parent/'family_subject_coverage_plan_v2.json').read_bytes())
    math_gaps=json.loads((coverage.PATH.parent/'family_subject_coverage_plan_v4.json').read_bytes())
    for before,after in zip(old['rows'],historical['rows']):
        assert before['id']==after['id'] and before['requirements']==after['requirements']
        assert after['mappings'][:len(before['mappings'])]==before['mappings']
    assert math_gaps['rows'][53:]==historical['rows'][53:]
    empty=coverage.report('math-g7-v1',set())
    assert all(t['status']=='gap' and t['question_count']==0 for r in empty['items'] for t in r['tasks'])
    from learning_service.practice_coverage import render_report
    altered=deepcopy(plan)
    row=next(r for r in altered['rows'] if r.get('assessment_modes') and r['mappings'])
    row['assessment_modes'][row['mappings'][0]['task']]='human';row['mappings'][0]['role']='direct'
    with pytest.raises(ValueError,match='manual performance'):render_report(altered,'math-g'+row['book_id'].split('-g')[1][0]+'-v1',ids)
    # Repeated mappings from the same family cannot satisfy the two-family goal.
    row=next(r for r in altered['rows'] if r['book_id']=='math-g7-lower' and len(r['mappings'])==2)
    altered=deepcopy(plan);row=next(r for r in altered['rows'] if r['id']==row['id'])
    for m in row['mappings']:m['family']='same-template'
    result=render_report(altered,'math-g7-v1',ids)
    task=next(r for r in result['items'] if r['id']==row['id'])['tasks'][0]
    assert task['family_count']<=1 and task['status']!='configured'


def test_reviewed_upper_subject_questions_map_only_to_bounded_checks():
    plan=json.loads(coverage.PATH.read_bytes())
    expected={
        'ethics-g2-upper:1:safety':'family-chapter-ethics-g2-upper-1-03-v1',
        'history-g7-upper:1:civilization':'family-chapter-history-g7-upper-1-upper_variety-second-v1',
        'history-g7-upper:2:reform':'family-chapter-history-g7-upper-2-upper_variety-second-v1',
        'geography-g7-upper:9:application':'family-chapter-geography-g7-upper-9-challenge_variety-091-v1',
        'biology-g7-upper:2:plant':'family-chapter-biology-g7-upper-2-upper_variety-second-v1',
        'biology-g7-upper:5:fish':'family-chapter-biology-g7-upper-5-upper_variety-animal-classify-v1',
        'biology-g7-upper:6:bacteria':'family-chapter-biology-g7-upper-6-upper_variety-microbes-v1',
        'ethics-g7-upper:4:setback':'family-chapter-ethics-g7-upper-4-challenge_variety-076-v1',
        'history-g7-upper:3:recovery':'family-chapter-history-g7-upper-3-upper_variety-policies-v1',
        'history-g7-upper:6:cause':'family-chapter-history-g7-upper-6-challenge_variety-082-v1',
        'geography-g7-upper:1:scale':'family-chapter-geography-g7-upper-1-challenge_variety-083-v1',
        'geography-g7-upper:4:change':'family-chapter-geography-g7-upper-4-02-v1',
        'biology-g7-upper:3:plantlevels':'family-chapter-biology-g7-upper-3-upper_variety-second-v1',
        'biology-g7-upper:5:mammal':'family-chapter-biology-g7-upper-5-upper_variety-animal-classify-v1',
    }
    rows={row['id']:row for row in plan['rows']}
    ids=set(chapter.bank())
    for row_id,qid in expected.items():
        row=rows[row_id]
        mapping=next(m for m in row['mappings'] if m['question_version_id']==qid and m['task']=='check')
        assert row['assessment_modes']['check']=='bounded'
        assert mapping['role']=='direct'
        assert qid in ids
    plans=[coverage.report(f'math-g{grade}-v1',ids) for grade in (2,7)]
    checked={row['id']:row for report in plans for row in report['items']}
    for row_id,qid in expected.items():
        check=next(t for t in checked[row_id]['tasks'] if t['id']=='check')
        assert qid in check['question_ids']


def test_partial_subject_evidence_and_repeated_classification_do_not_inflate_coverage():
    report=coverage.report('math-g7-v1',set(chapter.bank()))
    rows={row['id']:row for row in report['items']}
    checks={row_id:next(t for t in row['tasks'] if t['id']=='check')
            for row_id,row in rows.items() if any(t['id']=='check' for t in row['tasks'])}
    mammal=checks['biology-g7-upper:5:mammal']
    assert mammal['question_count']==3 and mammal['family_count']==1
    assert mammal['status']=='partial'
    # Each population task addresses only part of the combined requirement.
    population=checks['geography-g7-upper:6:population']
    assert population['family_count']==0 and population['supporting_question_count']==3
    for row_id in ('ethics-g7-upper:2:teacher','ethics-g7-upper:2:group',
                   'history-g7-upper:2:culture','history-g7-upper:4:reform',
                   'geography-g7-upper:5:rain','geography-g7-upper:6:culture'):
        task=checks[row_id]
        assert task['family_count']==0 and task['supporting_question_count']==1
        assert task['status']=='partial'
    assert checks['geography-g7-upper:4:change']['family_count']==1
    assert checks['geography-g7-upper:4:change']['supporting_question_count']==1
    assert checks['biology-g7-upper:1:observation']['family_count']==0
    # The review changes mappings only; inventory and human assessment stay fixed.
    previous=json.loads((coverage.PATH.parent/'family_subject_coverage_plan_v15.json').read_bytes())
    current=json.loads(coverage.PATH.read_bytes())
    assert [{k:v for k,v in row.items() if k!='mappings'} for row in current['rows']]==[
        {k:v for k,v in row.items() if k!='mappings'} for row in previous['rows']]


def test_plan_tampering_fails_closed(tmp_path,monkeypatch):
    p=tmp_path/'plan.json';p.write_bytes(coverage.PATH.read_bytes()+b' ')
    monkeypatch.setattr(coverage,'PATH',p)
    with pytest.raises(ValueError,match='plan changed'):coverage.report('math-g2-v1',set())
    data=json.loads(p.read_bytes());data['teacher_reviewed']=True;raw=json.dumps(data).encode();p.write_bytes(raw)
    monkeypatch.setattr(coverage,'SHA256',hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError,match='boundary'):coverage.report('math-g2-v1',set())


def test_install_all_new_tasks_grade_restore_isolate_and_collect(family):
    _,db,api,headers=family
    for batch in chapter.BATCHES:
        if batch!='subject_knowledge':chapter.install(db,batch)
    with db.session() as c:
        before={r[0]:{tuple(x) for x in c.execute('SELECT * FROM "'+r[0]+'"')} for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert chapter.install(db,'subject_knowledge')['added']==67
    assert chapter.install(db,'subject_knowledge')['added']==0
    with db.session() as c:
        delta={}
        for table,old in before.items():
            current={tuple(x) for x in c.execute('SELECT * FROM "'+table+'"')};assert old<=current
            if current-old:delta[table]=len(current-old)
        assert delta=={'questions':67,'question_versions':67,'audit_events':1}
    for grade in (2,7):
        response=api.get('/api/v1/question-choices',headers={**headers,'X-Learner-Id':f'family-g{grade}'})
        assert response.status_code==200 and response.json()['subject_coverage_plan']['status']=='draft'
        assert not any(term in response.text for term in ('field_answers','accepted','case_sensitive','"errors"'))
        ids={r['question_version_id'] for r in response.json()['items']}
        for q in chapter.bank('subject_knowledge').values():assert (q['id'] in ids)==(q['grade']==grade)
        for q in chapter.bank('subject_gaps').values():assert (q['id'] in ids)==(q['grade']==grade)
    def submit(q,raw,nonce):
        h={**headers,'X-Learner-Id':f"family-g{q['grade']}"}
        response=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id']})
        assert response.status_code==201,response.text
        data=response.json();item=data['items'][0]
        restored=api.get('/api/v1/test-sessions/'+data['session_id'],headers=h)
        assert item['response_fields']==restored.json()['items'][0]['response_fields']
        assert data['answer_key'] is None
        assert not any(term in response.text+restored.text for term in ('field_answers','accepted','case_sensitive','"errors"'))
        for f in item['response_fields']:assert set(f)=={'id','kind','label','units','options'}
        foreign={**headers,'X-Learner-Id':'family-g7' if q['grade']==2 else 'family-g2'}
        assert api.get('/api/v1/test-sessions/'+data['session_id'],headers=foreign).status_code in (403,404)
        token=api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",headers=h).json()
        body={'challenge_id':token['challenge_id'],'nonce':token['nonce'],'raw_answer':raw}
        url=f"/api/v1/test-items/{item['test_item_id']}/answers";hh={**h,'Idempotency-Key':nonce}
        response=api.post(url,headers=hh,json=body);assert response.status_code==202,response.text
        assert api.post(url,headers=hh,json=body).json()['attempt_id']==response.json()['attempt_id']
        run_worker_once(db,api.app.state.settings)
        aid=response.json()['attempt_id'];result=api.get('/api/v1/attempts/'+aid,headers=h).json()
        return aid,result,h
    for q in chapter.bank('subject_knowledge').values():assert submit(q,q['answer'],q['id'])[1]['outcome']=='correct'
    for q in chapter.bank('subject_gaps').values():assert submit(q,q['answer'],q['id'])[1]['outcome']=='correct'
    q=pick('english-g7-upper',2);wrong={'a':'is','b':'is','c':'on'}
    aid,result,h=submit(q,json.dumps(wrong),'short-wrong')
    assert result['outcome']=='incorrect' and '下一步' in result['feedback']
    preview=api.get(f'/api/v1/attempts/{aid}/collection-preview',headers=h).json()
    collected=api.post(f'/api/v1/attempts/{aid}/collection',headers={**h,'Idempotency-Key':'short-collect'},json={'confirmed':True,'preview_sha256':preview['preview_sha256']})
    assert collected.status_code==201
    with db.session() as c:
        snapshot=json.loads(c.execute('SELECT content_json FROM mistake_entries WHERE id=?',(collected.json()['mistake_id'],)).fetchone()[0])
        assert snapshot['response_fields']==preview['response_fields'] and json.loads(snapshot['student_answer'])==wrong
        assert all(f['kind']=='text' for f in snapshot['response_fields'])
        assert c.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0
