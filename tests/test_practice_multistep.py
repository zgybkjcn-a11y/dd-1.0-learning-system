"""Multi-field grading, frozen answer privacy, and additive installation."""
import json
from collections import Counter
from copy import deepcopy

import pytest

from learning_service import chapter_practice as chapter
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_fields, validate_fields
from test_family_math import family


def test_multistep_content_and_separate_constraints():
    qs = list(chapter.bank('math_g2_multistep').values())
    assert len(qs) == 16
    assert Counter(q['chapter_id'] for q in qs) == dict.fromkeys(['1','2','3','activity1','4','activity2','5','6'],2)
    # Independently count intersections, moved cards, and the incomplete array.
    cards = [('red','circle')]*6 + [('red','square')]*4 + [('blue','circle')]*5 + [('blue','square')]*3
    assert [int(f['answer']) for f in qs[0]['responses']] == [sum(c=='red' for c,s in cards),sum(s=='square' for c,s in cards)]
    for _ in range(3):cards.remove(('red','circle'));cards.append(('blue','square'))
    assert [int(f['answer']) for f in qs[1]['responses']] == [sum(c=='red' for c,s in cards),sum(c=='blue' for c,s in cards),sum(s=='circle' for c,s in cards),sum(s=='square' for c,s in cards)]
    array = qs[2]['visual']['rows']
    assert [int(f['answer']) for f in qs[2]['responses']] == [sum(map(len,array)),sum(c=='空' for row in array for c in row),sum(c=='●' for row in array for c in row)]
    expected = [[36,24,6],[6,4,1],[24,6,1],[1,4],[1,2,1],[5,6,1],[61,39,1],
                [54,90],[72,4,1],[56,14,42],[24,30,5,8],[32,18,2],[27,28,1,1]]
    assert [[int(f['answer']) for f in q['responses']] for q in qs[3:]] == expected
    for directions, response in zip(['NNEE','NENE','EENN'], qs[7]['responses']):
        x=y=0; blocked=False
        for d in directions:
            x += d=='E'; y += d=='N'; blocked |= (x,y)==(1,1)
        assert int(response['answer']) == (1 if (x,y)==(2,2) and not blocked else 2)
    # Check package totals rather than repeating the author's expressions.
    for size,price,answer in [(8,9,27),(6,7,28)]:
        solutions=[(n,n*price) for n in range(10) if n*size==4*6]
        assert len(solutions)==1 and solutions[0][1]==answer


@pytest.mark.parametrize('raw', ['{}','[]','null','5','{"a":"5"}',
    '{"a":"5","b":"6","extra":"0"}', '{"a":"5","a":"5","b":"6"}',
    '{"a":5,"b":"6"}', '{"a":"5","b":""}', '{"a":"5","b":"6米"}',
    '{"a":"5","b":"5+1"}', '{"a":"5","b":true}'])
def test_no_partial_missing_duplicate_or_malformed_response_passes(raw):
    key={'field_answers':[{'id':'a','label':'甲','numeric_answer':'5','units':['厘米','cm']},
                          {'id':'b','label':'乙','numeric_answer':'6','units':['厘米','cm']}], 'explanation':'说明'}
    assert grade_fields(raw,key)[0]=='incorrect'
    assert grade_fields('{"b":"６厘米","a":"5cm"}',key)[0]=='correct'
    outcome, feedback=grade_fields('{"a":"5","b":"7"}',key)
    assert outcome=='incorrect' and '1项正确' in feedback and '请重看：乙' in feedback


def test_invalid_field_metadata_rejected():
    q=next(iter(chapter.bank('math_g2_multistep').values()))
    fields=json.loads(chapter.stored(q)['content_json'])['response_fields']
    for mutate in ('answer','duplicate','script','oversized','options'):
        data=deepcopy(fields)
        if mutate=='answer':data[0]['answer']='10'
        elif mutate=='duplicate':data[1]['id']=data[0]['id']
        elif mutate=='script':data[0]['id']='<script>'
        elif mutate=='oversized':data[0]['label']='x'*101
        else:data[0]['options']=['same','same']
        with pytest.raises(ValueError):validate_fields(data)


def test_install_all_fields_restore_grade_and_previous_rows_preserved(family):
    _,db,api,headers=family
    for batch in chapter.BATCHES:
        if batch!='math_g2_multistep':chapter.install(db,batch)
    with db.session() as c:
        before={r[0]:{tuple(x) for x in c.execute('SELECT * FROM "'+r[0]+'"')} for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert chapter.install(db,'math_g2_multistep')['added']==16
    assert chapter.install(db,'math_g2_multistep')['added']==0
    with db.session() as c:
        delta={}
        for table,old in before.items():
            current={tuple(x) for x in c.execute('SELECT * FROM "'+table+'"')};assert old<=current
            if current-old:delta[table]=len(current-old)
        assert delta=={'questions':16,'question_versions':16,'audit_events':1}
    h={**headers,'X-Learner-Id':'family-g2'}
    foreign=api.get('/api/v1/question-choices',headers={**headers,'X-Learner-Id':'family-g7'}).json()
    assert not set(chapter.bank('math_g2_multistep')) & {r['question_version_id'] for r in foreign['items']}
    for q in chapter.bank('math_g2_multistep').values():
        response=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id']})
        assert response.status_code==201
        data=response.json();item=data['items'][0]
        assert len(item['response_fields'])==len(q['responses'])
        for f in item['response_fields']:assert set(f)=={'id','label','units','options'}
        restored=api.get('/api/v1/test-sessions/'+data['session_id'],headers=h).json()['items'][0]
        fetched=api.get('/api/v1/test-items/'+item['test_item_id'],headers=h).json()
        assert item['response_fields']==restored['response_fields']==fetched['response_fields']
        assert all('numeric_answer' not in json.dumps(x) and 'field_answers' not in json.dumps(x) for x in [data,restored,fetched])
        token=api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",headers=h).json()
        body={'challenge_id':token['challenge_id'],'nonce':token['nonce'],'raw_answer':q['answer']}
        result=api.post(f"/api/v1/test-items/{item['test_item_id']}/answers",headers={**h,'Idempotency-Key':q['id']},json=body)
        assert result.status_code==202
        retry=api.post(f"/api/v1/test-items/{item['test_item_id']}/answers",headers={**h,'Idempotency-Key':q['id']},json=body)
        assert retry.json()['attempt_id']==result.json()['attempt_id']
        run_worker_once(db,api.app.state.settings)
        assert api.get('/api/v1/attempts/'+result.json()['attempt_id'],headers=h).json()['outcome']=='correct'
    # All fields are required for independent correctness, not only the final value.
    item=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id']}).json()['items'][0]
    token=api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",headers=h).json()
    wrong=json.loads(q['answer']);wrong['a']='999'
    result=api.post(f"/api/v1/test-items/{item['test_item_id']}/answers",headers={**h,'Idempotency-Key':'one-wrong'},json={'challenge_id':token['challenge_id'],'nonce':token['nonce'],'raw_answer':json.dumps(wrong)})
    assert result.status_code==202
    run_worker_once(db,api.app.state.settings)
    assert api.get('/api/v1/attempts/'+result.json()['attempt_id'],headers=h).json()['outcome']=='incorrect'

    aid=result.json()['attempt_id']
    preview=api.get(f'/api/v1/attempts/{aid}/collection-preview',headers=h)
    assert preview.status_code==200
    assert preview.json()['response_fields']==json.loads(chapter.stored(q)['content_json'])['response_fields']
    collected=api.post(f'/api/v1/attempts/{aid}/collection',headers={**h,'Idempotency-Key':'collect-fields'},json={'confirmed':True,'preview_sha256':preview.json()['preview_sha256']})
    assert collected.status_code==201
    with db.session() as c:
        snapshot=json.loads(c.execute('SELECT content_json FROM mistake_entries WHERE id=?',(collected.json()['mistake_id'],)).fetchone()[0])
        assert snapshot['response_fields']==preview.json()['response_fields']
        assert json.loads(snapshot['student_answer'])==wrong
