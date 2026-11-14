"""Check mathematical constraints, honest mappings and additive delivery of math gaps."""
from collections import Counter
from fractions import Fraction
import json

import pytest

from learning_service import chapter_practice as chapter, subject_coverage
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields
from test_family_math import family


def pick(key):
    return next(q for q in chapter.bank('math_gaps').values() if q['id'].endswith('-'+key+'-v1'))


def values(key):
    result=[]
    for f in pick(key)['responses']:
        if f['kind'] in ('multi','order'):
            result.append([f['options'][int(n)-1] for n in f['answer'].split(',')])
        elif f['kind']=='choice':result.append(f['options'][int(f['answer'])-1])
        else:result.append(Fraction(f['answer']))
    return result


def test_independent_math_and_unique_choice_meanings():
    qs=chapter.bank('math_gaps')
    assert len(qs)==10 and Counter(q['grade'] for q in qs.values())=={2:4,7:6}
    assert sum(len(q['responses']) for q in qs.values())==38
    assert values('division-records')==[['甲','乙'],'份数','每份颗数']
    assert 3*4==2*6==12
    assert len(set((2,4,6)))>1 and sum((2,4,6))==12
    assert values('complete-distributions')==[18/3,18/6,'份数、每份量','不是']
    assert values('regroup-total')==[56/7,56/7,'每组张数变成组数',7*(9-8)]
    assert values('recover-total')==[8*7,(8*7)/7,'不对，会剩7张',56-8*6]
    changed,invariant,relation=values('invariant-table')
    assert set(changed)=={'天数n','总费用C'} and invariant==5 and relation=='C−3n=5'
    for n in range(1,10):assert (5+3*n)-3*n==invariant
    changed,saved,relation,invariant=values('invariant-structure')
    assert set(changed)=={'正方形总个数','小棒总根数'} and saved==3 and relation=='s−3n'
    for n in range(1,10):assert 4+3*(n-1)-3*n==invariant==1
    first,steps,left,right=values('choose-route')
    assert first=='2(2x−1)+12=3(x+5)'
    assert steps==['4x−2+12=3x+15','4x−3x=15+2−12','x=5']
    roots=[x for x in range(-20,21) if Fraction(2*x-1,3)+2==Fraction(x+5,2)]
    assert roots==[5] and left==Fraction(2*5-1,3)+2==right==Fraction(5+5,2)
    repair,x,left,right=values('repair-route')
    assert repair=='从①到②；应为2x−x=4+6' and x==10
    assert left==2*(x-3)==right==x+4 and 2*(-2-3)!=-2+4
    unknown,conditions,relation,equation=values('identify-model')
    assert unknown=='每本笔记本的单价' and set(conditions)=={'3本同价笔记本','笔价5元','共付29元'}
    assert relation=='笔记本总价+笔价=共付款' and equation=='3x+5=29'
    assert 3*8+5==29
    assert values('critique-model')==['乙','(x−4)/3','x+(x−4)/3=44','大桶水量、小桶水量']
    small=Fraction(44-4,4);big=3*small+4
    assert big+small==44 and (big-4)/3==small and big+(3*big+4)!=44


def test_new_mappings_only_and_no_candidate_counted_before_install():
    old=json.loads((subject_coverage.PATH.parent/'family_subject_coverage_plan_v5.json').read_bytes())
    current=json.loads(subject_coverage.PATH.read_bytes())
    new_ids=set(chapter.bank('math_gaps'));all_ids=set(chapter.bank())
    assert current['rows'] and len(current['rows'])==len(old['rows'])==276
    added=[]
    for before,after in zip(old['rows'],current['rows']):
        assert {k:v for k,v in before.items() if k!='mappings'}=={k:v for k,v in after.items() if k!='mappings'}
        if before['book_id'].startswith('math-'):
            before_by_key={(m['question_version_id'],m['task']):m for m in before['mappings']}
            after_by_key={(m['question_version_id'],m['task']):m for m in after['mappings']}
            assert set(before_by_key) <= set(after_by_key)
            for key, mapping in before_by_key.items():
                actual=after_by_key[key]
                reviewed={
                    ('family-chapter-math-g2-upper-2-challenge-unknown-factor-v1','transfer'):
                        ('direct','相邻乘积'),
                    ('family-chapter-math-g2-upper-2-depth-word-understand-2-v1','understand'):
                        ('direct','不代表'),
                    ('family-chapter-math-g2-upper-5-depth-word-understand-2-v1','understand'):
                        ('direct','不代表'),
                    # Reviewed after plan v5: these items compute or recognise
                    # only, so they cannot carry the full distinguish/apply task.
                    ('family-chapter-math-g7-upper-2-depth-subtract-03-v1','distinguish'):
                        ('supporting','不能作为'),
                    ('family-chapter-math-g7-upper-2-depth-multiply-03-v1','distinguish'):
                        ('supporting','零因子'),
                    ('family-chapter-math-g7-upper-4-depth-application-03-v1','distinguish'):
                        ('supporting','没有检查某人'),
                    ('family-chapter-math-g7-upper-6-depth-lines-02-v1','apply'):
                        ('supporting','不能证明'),
                    ('family-chapter-math-g7-upper-6-depth-angle-02-v1','apply'):
                        ('supporting','不能证明'),
                }
                if key in reviewed:
                    role, keyword = reviewed[key]
                    assert actual['role']==role
                    assert keyword in actual['rationale']
                    assert actual['question_sha256']==mapping['question_sha256']
                    continue
                assert actual==mapping
            added.extend(m for m in after['mappings'] if m['question_version_id'] in new_ids)
    assert {m['question_version_id'] for m in added}==new_ids
    assert len(added)==14
    for grade in (2,7):
        before=subject_coverage.report(f'math-g{grade}-v1',all_ids-new_ids)
        after=subject_coverage.report(f'math-g{grade}-v1',all_ids)
        for q in chapter.bank('math_gaps').values():
            if q['grade']!=grade:continue
            def task(report):return next(t for r in report['items'] if r['id']==q['knowledge']['point_id'] for t in r['tasks'] if t['id']==q['knowledge']['task'])
            assert task(before)['family_count']==0
            assert task(after)['family_count']==2 and task(after)['status']=='configured'
        assert all(t['family_count']==0 for r in after['items'] for t in r['tasks'] if t['assessment_mode']=='human')


@pytest.mark.parametrize('key',['division-records','complete-distributions','regroup-total','recover-total','invariant-table','invariant-structure','choose-route','repair-route','identify-model','critique-model'])
def test_each_field_required_and_feedback_checked(key):
    q=pick(key);answer=json.loads(q['answer']);private=json.loads(chapter.stored(q)['answer_key_json'])
    assert grade_short_fields(q['answer'],private)[0]=='correct'
    for f in q['responses']:
        bad=answer|{f['id']:''}
        assert grade_short_fields(json.dumps(bad),private)[0]=='incorrect'
        if f['kind']=='multi':
            extra=next(str(n) for n in range(1,len(f['options'])+1) if str(n) not in f['answer'].split(','))
            bad[f['id']]=f['answer']+','+extra
            assert grade_short_fields(json.dumps(bad),private)[0]=='incorrect'
        if f['kind']=='order':
            bad[f['id']]=','.join(reversed(f['answer'].split(',')))
            assert grade_short_fields(json.dumps(bad),private)[0]=='incorrect'
        for e in f.get('errors',[]):
            bad=answer|{f['id']:e['answer']}
            outcome,feedback=grade_short_fields(json.dumps(bad),private)
            assert outcome=='incorrect' and e['message'] in feedback and e['action'] in feedback


def test_additive_install_api_restore_isolation_idempotency_and_collection(family):
    _,db,api,headers=family
    for batch in chapter.BATCHES:
        if batch!='math_gaps':chapter.install(db,batch)
    with db.session() as c:
        before={r[0]:{tuple(x) for x in c.execute('SELECT * FROM "'+r[0]+'"')} for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert chapter.install(db,'math_gaps')['added']==10
    assert chapter.install(db,'math_gaps')['added']==0
    with db.session() as c:
        delta={}
        for table,old in before.items():
            current={tuple(x) for x in c.execute('SELECT * FROM "'+table+'"')};assert old<=current
            if current-old:delta[table]=len(current-old)
        assert delta=={'questions':10,'question_versions':10,'audit_events':1}
    for q in chapter.bank('math_gaps').values():
        h={**headers,'X-Learner-Id':f"family-g{q['grade']}"}
        choices=api.get('/api/v1/question-choices',headers=h)
        assert q['id'] in {r['question_version_id'] for r in choices.json()['items']}
        opened=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id']})
        assert opened.status_code==201,opened.text
        data=opened.json();item=data['items'][0]
        restored=api.get('/api/v1/test-sessions/'+data['session_id'],headers=h)
        assert item['response_fields']==restored.json()['items'][0]['response_fields'] and data['answer_key'] is None
        assert not any(s in choices.text+opened.text+restored.text for s in ('field_answers','independent_check','"errors"','numeric_answer'))
        foreign={**headers,'X-Learner-Id':'family-g7' if q['grade']==2 else 'family-g2'}
        assert api.get('/api/v1/test-sessions/'+data['session_id'],headers=foreign).status_code in (403,404)
        token=api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",headers=h).json()
        raw=q['answer']
        wrong=q['id']==pick('repair-route')['id']
        if wrong:raw=json.dumps(json.loads(raw)|{'b':'-2'})
        body={'challenge_id':token['challenge_id'],'nonce':token['nonce'],'raw_answer':raw}
        url=f"/api/v1/test-items/{item['test_item_id']}/answers";hh={**h,'Idempotency-Key':q['id']}
        response=api.post(url,headers=hh,json=body);assert response.status_code==202,response.text
        aid=response.json()['attempt_id']
        assert api.post(url,headers=hh,json=body).json()['attempt_id']==aid
        run_worker_once(db,api.app.state.settings)
        result=api.get('/api/v1/attempts/'+aid,headers=h).json()
        assert result['outcome']==('incorrect' if wrong else 'correct')
        if wrong:
            assert '移项' in result['feedback']
            preview=api.get(f'/api/v1/attempts/{aid}/collection-preview',headers=h).json()
            saved=api.post(f'/api/v1/attempts/{aid}/collection',headers={**h,'Idempotency-Key':'gap-collect'},json={'confirmed':True,'preview_sha256':preview['preview_sha256']})
            assert saved.status_code==201
    with db.session() as c:assert c.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0
