"""Task diversity, answer constraints, visual round trips, and old record safety."""
from collections import Counter
from fractions import Fraction
from itertools import permutations
import json

import pytest

from learning_service import chapter_practice as chapter
from learning_service.app import run_worker_once
from learning_service.practice_design import validate_visual
from test_family_math import family


def test_challenge_answers_by_independent_constraints():
    qs = {q['id'].split('-challenge-')[1].removesuffix('-v1'):q for q in chapter.bank('math_g2_challenge').values()}
    expected = [5,3,2,3,9,9,27,5,2,6,8,4,6,16,20,4,2,1,2,3,2,4,4,1,
                1,9,13,6,12,2,45,12,1,46,32,2,7,4,4,21,4,25,4,25,3,12,30,1]
    assert [Fraction(q['answer']) for q in qs.values()] == expected
    assert len(qs) == 48
    assert Counter(q['difficulty'] for q in qs.values()) == {'normal':16,'hard':32}
    assert Counter(q['chapter_id'] for q in qs.values()) == dict.fromkeys(['1','2','3','4','5','6','activity1','activity2'],6)
    # Enumerate solution spaces, not the author's checking expression.
    assert [(large,5-large) for large in range(6) if large*8+(5-large)*6==38] == [(4,1)]
    costs = [boxes*10+max(0,18-boxes*6)*2 for boxes in range(5)]
    assert min(costs)==int(qs['minimum-packages']['answer'])
    fills={tuple(sorted((tuple(sorted((a,b))),tuple(sorted((c,d))))))
           for a,b,c,d in permutations((2,3,4,6)) if a*b==c*d}
    assert len(fills)==int(qs['number-cards']['answer'])
    paths=set(permutations('NNEE'))
    valid=[]
    for path in paths:
        x=y=0;blocked=False
        for direction in path:
            x+=direction=='E';y+=direction=='N'
            if (x,y)==(1,1): blocked=True
        if not blocked:valid.append(path)
    assert len(valid)==int(qs['detour']['answer'])
    array=qs['array-holes']['visual']['rows']
    assert sum(c=='●' for row in array for c in row)==int(qs['array-holes']['answer'])
    assert sum('visual' in q for q in qs.values())==21


def test_old_tiers_corrected_without_rewriting_stored_question():
    old=chapter.bank('math')|chapter.bank('math_g2_depth')
    changed=[q for q in old.values() if chapter.metadata(q)['difficulty']!=q['difficulty']]
    assert len(changed)==35
    assert all(q['book_id']=='math-g2-upper' and q['difficulty']=='hard' for q in changed)
    assert all(chapter.metadata(q)['difficulty'] in ('easy','normal') for q in changed)
    for q in old.values():
        stored=json.loads(chapter.stored(q)['content_json'])
        assert set(stored)=={'prompt','hint','input_type','source','practice_bank'}


def test_import_visual_restore_grade_and_all_old_rows_preserved(family):
    _,db,api,headers=family
    for name in chapter.BATCHES:
        if name!='math_g2_challenge':chapter.install(db,name)
    with db.session() as conn:
        before={r[0]:{tuple(v) for v in conn.execute('SELECT * FROM "'+r[0]+'"')}
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert chapter.install(db,'math_g2_challenge')['added']==48
    assert chapter.install(db,'math_g2_challenge')['added']==0
    with db.session() as conn:
        delta={}
        for table,old in before.items():
            current={tuple(r) for r in conn.execute('SELECT * FROM "'+table+'"')}
            assert old<=current
            if current-old:delta[table]=len(current-old)
        assert delta=={'questions':48,'question_versions':48,'audit_events':1}
    h={**headers,'X-Learner-Id':'family-g2'}
    choices=api.get('/api/v1/question-choices',headers=h)
    assert choices.status_code==200 and 'numeric_answer' not in choices.text and 'explanation' not in choices.text
    rows={r['question_version_id']:r for r in choices.json()['items']}
    foreign=api.get('/api/v1/question-choices',headers={**headers,'X-Learner-Id':'family-g7'}).json()
    assert not set(chapter.bank('math_g2_challenge')) & {r['question_version_id'] for r in foreign['items']}
    seen=set()
    for q in chapter.bank('math_g2_challenge').values():
        assert rows[q['id']]['practice']['task_form']==q['design']['form']
        response=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id']})
        assert response.status_code==201
        item=response.json()['items'][0]
        assert item.get('visual')==q.get('visual') and 'answer_key' not in item
        restored=api.get('/api/v1/test-sessions/'+response.json()['session_id'],headers=h).json()['items'][0]
        assert restored.get('visual')==q.get('visual')
        fetched=api.get('/api/v1/test-items/'+item['test_item_id'],headers=h).json()
        assert fetched.get('visual')==q.get('visual')
        if q['chapter_id'] in seen:continue
        seen.add(q['chapter_id'])
        token=api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",headers=h).json()
        result=api.post(f"/api/v1/test-items/{item['test_item_id']}/answers",headers={**h,'Idempotency-Key':q['id']},json={
            'challenge_id':token['challenge_id'],'nonce':token['nonce'],'raw_answer':q['answer']})
        assert result.status_code==202
        run_worker_once(db,api.app.state.settings)
        assert api.get('/api/v1/attempts/'+result.json()['attempt_id'],headers=h).json()['outcome']=='correct'
    assert len(seen)==8


def test_reclassified_round_does_not_block_restarting_new_tier(family, monkeypatch):
    from learning_service import practice_design
    _,db,api,headers=family
    chapter.install(db,'math')
    q=next(q for q in chapter.bank('math').values() if q['title']=='同一物品两种分法')
    h={**headers,'X-Learner-Id':'family-g2'}
    # Reproduce an attempt made before the editorial correction.
    original=practice_design.presentation
    monkeypatch.setattr(practice_design,'presentation',lambda q:{})
    state=api.put('/api/v1/practice-workspace',headers=h,json={
        'expected_revision':0,'book_id':q['book_id'],'chapter_id':q['chapter_id'],'difficulty':'hard','pool':'initial'}).json()
    result=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],
        'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id'],'workspace_revision':state['revision']}).json()
    item=result['items'][0]['test_item_id']
    token=api.post(f'/api/v1/test-items/{item}/submission-challenges',headers=h).json()
    answer=api.post(f'/api/v1/test-items/{item}/answers',headers={**h,'Idempotency-Key':'old-tier'},json={
        'challenge_id':token['challenge_id'],'nonce':token['nonce'],'raw_answer':q['answer']})
    assert answer.status_code==202
    run_worker_once(db,api.app.state.settings)
    assert api.get('/api/v1/practice-workspace',headers=h).json()['completed_ids']==[q['id']]
    monkeypatch.setattr(practice_design,'presentation',original)
    state=api.get('/api/v1/practice-workspace',headers=h).json()
    assert q['id'] not in state['completed_ids']
    restart=api.put('/api/v1/practice-workspace',headers=h,json={'expected_revision':state['revision'],
        'book_id':q['book_id'],'chapter_id':q['chapter_id'],'difficulty':'normal','pool':'initial','restart_round':True})
    assert restart.status_code==200
    assert api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],
        'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id'],'workspace_revision':restart.json()['revision']}).status_code==201
    with db.session() as conn:
        assert conn.execute('SELECT count(*) FROM attempts').fetchone()[0]>=1
        assert conn.execute('SELECT difficulty FROM practice_rounds r JOIN test_items i ON i.practice_round_id=r.id WHERE i.id=?',(item,)).fetchone()[0]=='hard'


@pytest.mark.parametrize('visual',[
    {'kind':'html','caption':'x','html':'<script>alert(1)</script>'},
    {'kind':'ruler','caption':'x','maximum':12,'segments':[{'label':'x','start':8,'end':2}]},
    {'kind':'table','caption':'x','rows':[['x'],['a','b']]},
    {'kind':'grid','caption':'x','rows':[['x']],'url':'https://example.invalid'},
])
def test_unsafe_or_inconsistent_diagrams_rejected(visual):
    with pytest.raises(ValueError):validate_visual(visual)
