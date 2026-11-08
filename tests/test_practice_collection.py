"""Explicit collection, immutable presentation binding, isolation and scheduling."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
import sqlite3

import pytest

from learning_service.app import _scheduled_due, run_worker_once
from learning_service.db import Database, json_dumps, utc_now
from learning_service.practice import bank, install
from test_family_math import family


@pytest.fixture
def practice(family):
    directory, db, api, headers = family
    install(db)
    headers = {**headers, 'X-Learner-Id':'family-g7'}
    question = next(q for q in bank().values() if q['grade']==7 and q['chapter_id']=='2')
    return db, api, headers, question


def answer(practice, *, raw='999999', hint=False, card=None, mistake=None, grade=True):
    db, api, headers, question = practice
    body = {'question_version_id':question['id']}
    if card: body['card_id']=card
    if mistake: body['mistake_id']=mistake
    result=api.post('/api/v1/test-sessions',headers=headers,json=body)
    assert result.status_code==201,result.text
    item=result.json()['items'][0]['test_item_id']
    if hint: assert api.post(f'/api/v1/test-items/{item}/hints',headers=headers).status_code==200
    challenge=api.post(f'/api/v1/test-items/{item}/submission-challenges',headers=headers).json()
    response=api.post(f'/api/v1/test-items/{item}/answers',headers={**headers,'Idempotency-Key':item},
                      json={k:challenge[k] for k in ('challenge_id','nonce')}|{'raw_answer':raw})
    assert response.status_code==202,response.text
    attempt=response.json()['attempt_id']
    if grade: run_worker_once(db,api.app.state.settings)
    return attempt,item


def preview(practice, attempt):
    _,api,headers,_=practice
    response=api.get(f'/api/v1/attempts/{attempt}/collection-preview',headers=headers)
    assert response.status_code==200,response.text
    return response.json()


def collect(practice, attempt, data=None, key='collect', **changes):
    _,api,headers,_=practice
    data=data or preview(practice,attempt)
    return api.post(f'/api/v1/attempts/{attempt}/collection',headers={**headers,'Idempotency-Key':key},
                    json={'confirmed':True,'preview_sha256':data['preview_sha256'],**changes})


def rows(db):
    with db.session() as conn:
        return {t:[tuple(r) for r in conn.execute('SELECT * FROM '+t)] for t in
                ('mistake_entries','mistake_sources','review_cards','interaction_challenges','idempotency_records',
                 'diagnoses','learning_events','audit_events','test_sessions','test_items','attempts','grade_versions','review_events')}


def test_preview_cancel_is_read_only_and_confirmation_is_bound(practice):
    db,api,h,q=practice
    attempt,item=answer(practice,hint=True,raw='<script>throw 1</script>')
    before=rows(db)
    data=preview(practice,attempt)
    assert data['question_text']==q['prompt'] and data['student_answer']=='<script>throw 1</script>'
    assert data['assistance']=='hint' and not data['assessment_eligibility'] and data['diagnosis'] is None
    assert data['textbook_scope']=={'book_id':'math-g7-upper','chapter_id':'2'}
    assert 'answer_key_json' not in data and 'numeric_answer' not in data
    assert preview(practice,attempt)==data and rows(db)==before
    assert collect(practice,attempt,data,confirmed=False).status_code==422
    assert collect(practice,attempt,data,confirmed='true').status_code==422
    assert collect(practice,attempt,data,student_answer='forged').status_code==422
    assert rows(db)==before
    result=collect(practice,attempt,data);assert result.status_code==201,result.text
    result=result.json()
    with db.session() as c:
        m=c.execute('SELECT * FROM mistake_entries').fetchone()
        content=json.loads(m['content_json'])
        assert content['question_text']==q['prompt'] and content['student_answer']==data['student_answer']
        assert content['question_version_id']==q['id'] and content['grade_id']==data['grade_id']
        assert m['diagnosis_status']=='draft' and content['diagnosis'] is None
        source=c.execute('SELECT * FROM mistake_sources').fetchone()
        assert source['source_kind']=='test_attempt' and source['attempt_id']==attempt and source['item_locator']==item
        card=c.execute('SELECT * FROM review_cards').fetchone()
        assert card['due_at']==_scheduled_due(m['created_at'],1,'Asia/Shanghai')==result['due_at']
        assert not c.execute('SELECT * FROM diagnoses').fetchall()
        assert not c.execute('SELECT * FROM provider_calls').fetchall()
    assert api.get('/api/v1/review-tasks',headers=h).json()['items']==[]


def test_duplicate_confirmation_same_or_different_keys_does_not_shift_due(practice):
    db,_,_,_=practice;attempt,_=answer(practice);data=preview(practice,attempt)
    first=collect(practice,attempt,data).json();before=rows(db)
    assert collect(practice,attempt,data).json()==first
    assert collect(practice,attempt,data,key='second-click').json()==first
    assert rows(db)==before
    attempt2,_=answer(practice);second=collect(practice,attempt2).json()
    assert second['review_card_id']==first['review_card_id'] and second['due_at']==first['due_at']


def test_parallel_different_keys_create_one_source_and_card(practice):
    db,_,_,_=practice;attempt,_=answer(practice);data=preview(practice,attempt)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda key:collect(practice,attempt,data,key=key),['left','right']))
    assert [r.status_code for r in results]==[201,201]
    assert results[0].json()==results[1].json()
    with db.session() as c:
        for table in ('mistake_entries','mistake_sources','review_cards'):
            assert c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==1


@pytest.mark.parametrize('state',['correct','pending','undetermined'])
def test_non_wrong_final_result_cannot_be_collected(practice,state):
    db,api,h,q=practice
    attempt,_=answer(practice,raw=q['answer'] if state=='correct' else 'bad',grade=state!='pending')
    if state=='undetermined':
        with db.session(write=True) as c:c.execute("UPDATE grade_versions SET outcome='undetermined' WHERE attempt_id=?",(attempt,))
    before=rows(db)
    assert api.get(f'/api/v1/attempts/{attempt}/collection-preview',headers=h).status_code==409
    assert rows(db)==before


def test_grade_change_and_wrong_profile_or_missing_identity_cannot_confirm(practice):
    db,api,h,_=practice;attempt,_=answer(practice);data=preview(practice,attempt)
    wrong={**h,'X-Learner-Id':'family-g2'};before=rows(db)
    assert api.get(f'/api/v1/attempts/{attempt}/collection-preview',headers=wrong).status_code==404
    assert api.post(f'/api/v1/attempts/{attempt}/collection',headers={**wrong,'Idempotency-Key':'wrong'},
        json={'confirmed':True,'preview_sha256':data['preview_sha256']}).status_code==404
    assert api.post(f'/api/v1/attempts/{attempt}/collection',json={'confirmed':True,'preview_sha256':data['preview_sha256']}).status_code in (401,403)
    assert rows(db)==before
    with db.session(write=True) as c:
        c.execute("UPDATE grade_versions SET feedback='revised feedback' WHERE attempt_id=?",(attempt,))
    assert collect(practice,attempt,data).status_code==409
    assert collect(practice,attempt).status_code==201


@pytest.mark.parametrize('field',['content_json','answer_key_json','validator_version'])
def test_frozen_question_drift_stops_collection_and_review(practice,field):
    db,api,h,q=practice;attempt,_=answer(practice);data=preview(practice,attempt)
    saved=collect(practice,attempt,data).json()
    with db.session(write=True) as c:
        c.execute('UPDATE question_versions SET '+field+'=? WHERE id=?',('changed',q['id']))
        c.execute("UPDATE review_cards SET due_at='2020-01-01T00:00:00+00:00'")
    assert collect(practice,attempt,data).status_code==409
    tasks=api.get('/api/v1/review-tasks',headers=h).json()['items']
    assert tasks[0]['saved_practice'][0]['available'] is False
    assert tasks[0]['saved_practice'][0]['prompt']==q['prompt']
    response=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],
        'card_id':saved['review_card_id'],'mistake_id':saved['mistake_id']})
    assert response.status_code==409
    original=api.get('/api/v1/mistakes',headers=h).json()['items'][0]
    assert original['content']['question_text']==q['prompt']


def test_snapshot_cannot_change_and_drift_before_answer_stops_submission(practice):
    db,api,h,q=practice
    result=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id']}).json()
    item=result['items'][0]['test_item_id']
    with pytest.raises(sqlite3.IntegrityError):
        with db.session(write=True) as c:c.execute('UPDATE test_items SET question_snapshot_json=NULL WHERE id=?',(item,))
    with db.session(write=True) as c:c.execute("UPDATE question_versions SET content_json='{}' WHERE id=?",(q['id'],))
    for path in [f'/api/v1/test-items/{item}/submission-challenges',f'/api/v1/test-items/{item}/hints']:
        assert api.post(path,headers=h).status_code==409
    assert api.get('/api/v1/test-sessions/'+result['session_id'],headers=h).status_code==409


def test_retraction_never_resurrects_and_isolated_notebook(practice):
    db,api,h,_=practice;attempt,_=answer(practice);data=preview(practice,attempt)
    result=collect(practice,attempt,data).json()
    other={**h,'X-Learner-Id':'family-g2'}
    assert api.get('/api/v1/mistakes',headers=other).json()['items']==[]
    assert api.get('/api/v1/review-tasks',headers=other).json()['items']==[]
    assert api.get('/api/v1/mistakes/'+result['mistake_id'],headers=other).status_code==404
    assert api.post('/api/v1/mistakes/'+result['mistake_id']+'/retractions',headers=h).status_code==200
    before=rows(db)
    assert collect(practice,attempt,data).status_code==409
    assert collect(practice,attempt,data,key='new').status_code==409
    assert rows(db)==before


@pytest.mark.parametrize('outcome,hint,stage,days',[('correct',False,1,2),('incorrect',False,0,1),('correct',True,0,None)])
def test_due_original_review_and_existing_schedule(practice,outcome,hint,stage,days):
    db,api,h,q=practice;attempt,_=answer(practice);saved=collect(practice,attempt).json()
    card_id=saved['review_card_id'];mistake_id=saved['mistake_id']
    body={'question_version_id':q['id'],'card_id':card_id,'mistake_id':mistake_id}
    assert api.post('/api/v1/test-sessions',headers=h,json=body).status_code==409
    with db.session(write=True) as c:
        c.execute("UPDATE review_cards SET due_at='2020-01-01T00:00:00+00:00',timezone_snapshot='America/New_York' WHERE id=?",(card_id,))
    tasks=api.get('/api/v1/review-tasks',headers=h).json()['items']
    assert tasks[0]['saved_practice'][0]['question_version_id']==q['id']
    review_attempt,_=answer(practice,raw=q['answer'] if outcome=='correct' else 'wrong',hint=hint,card=card_id,mistake=mistake_id)
    with db.session() as c:
        card=c.execute('SELECT * FROM review_cards WHERE id=?',(card_id,)).fetchone()
        submitted=c.execute('SELECT submitted_at FROM attempts WHERE id=?',(review_attempt,)).fetchone()[0]
        assert card['stage']==stage
        assert card['due_at']==(_scheduled_due(submitted,days,'America/New_York') if days else '2020-01-01T00:00:00+00:00')
        assert c.execute('SELECT count(*) FROM review_events').fetchone()[0]==(0 if hint else 1)
    # Worker retry does not advance a second time; hinted review stays due.
    before=rows(db);run_worker_once(db,api.app.state.settings);assert rows(db)==before
    assert len(api.get('/api/v1/review-tasks',headers=h).json()['items'])==(1 if hint else 0)


def test_card_objective_and_saved_version_cannot_be_swapped(practice):
    _,api,h,q=practice;attempt,_=answer(practice);saved=collect(practice,attempt).json()
    other=next(x for x in bank().values() if x['grade']==7 and x['chapter_id']=='5')
    assert api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':other['id'],
        'card_id':saved['review_card_id'],'mistake_id':saved['mistake_id']}).status_code==422


def test_legacy_schema_migration_preserves_rows_and_legacy_attempt_not_guessed(family,tmp_path):
    directory,db,api,headers=family
    # Dedicated disposable clone, never a production or historical evidence DB.
    clone=tmp_path/'legacy.sqlite'
    with db.session() as c,sqlite3.connect(clone) as target:c.backup(target)
    with sqlite3.connect(clone) as c:
        c.execute('DROP INDEX practice_round_items')
        c.execute('ALTER TABLE test_items DROP COLUMN practice_round_id')
        c.execute('ALTER TABLE test_items DROP COLUMN practice_round_generation')
        c.execute('DROP TABLE practice_workspaces')
        c.execute('DROP TABLE practice_rounds')
        c.execute('DROP TRIGGER test_item_question_snapshot_immutable')
        c.execute('ALTER TABLE test_items DROP COLUMN question_snapshot_json')
        c.execute('DELETE FROM schema_migrations WHERE version>=12')
        baseline={t:c.execute('SELECT * FROM '+t).fetchall() for t in ('accounts','learners','questions','question_versions')}
    upgraded=Database(clone)
    with upgraded.session() as c:
        assert c.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==13
        for t,expected in baseline.items():assert [tuple(r) for r in c.execute('SELECT * FROM '+t)]==expected
    # A real legacy row remains readable as a test but is not retrospectively
    # certified from the current question bank for collection.
    from learning_service.app import create_app
    from fastapi.testclient import TestClient
    now=utc_now()
    with upgraded.session(write=True) as c:
        qid=c.execute('SELECT id FROM question_versions ORDER BY id').fetchone()[0]
        c.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES ('legacy-session','family-g2','independent','completed',?)",(now,))
        c.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,status) VALUES ('legacy-item','legacy-session','family-g2',?,'graded')",(qid,))
        c.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,submitted_at,status,idempotency_key) VALUES ('legacy-attempt','legacy-item','family-g2','bad',?,'graded','legacy')",(now,))
        c.execute("INSERT INTO grade_versions(id,attempt_id,outcome,feedback,rubric_version,validator_version,created_at) VALUES ('legacy-grade','legacy-attempt','incorrect','old','exact','exact',?)",(now,))
    client=TestClient(create_app(api.app.state.settings,upgraded))
    h={**headers,'X-Learner-Id':'family-g2'}
    assert client.get('/api/v1/test-sessions/legacy-session',headers=h).status_code==200
    response=client.get('/api/v1/attempts/legacy-attempt/collection-preview',headers=h)
    assert response.status_code==409 and response.json()['error']['code']=='PRACTICE_SNAPSHOT_MISSING'


def test_confirmation_write_fence_rechecks_profile_after_authorization(practice,monkeypatch):
    from fastapi.testclient import TestClient
    from learning_service.app import create_app
    from learning_service.db import write_context
    from learning_service.learner_context import select_context
    from test_browser_auth import assertion,csrf
    db,api,h,_=practice;attempt,_=answer(practice)
    settings=replace(api.app.state.settings,browser_auth_enabled=True,shared_learner_context_enabled=True,
        browser_auth_secret='synthetic-gateway-key-0123456789abcdef',browser_auth_issuer='synthetic-gateway',
        browser_identity_issuer='family-pilot-webui',browser_origin='https://collection.example.invalid')
    client=TestClient(create_app(settings,db),base_url=settings.browser_origin)
    assert client.post('/api/v1/auth/session',headers={'Origin':settings.browser_origin,
        'Authorization':'Bearer '+assertion(settings,changes={'sub':'synthetic-parent'})}).status_code==201
    assert client.post('/api/v1/learner-context',headers=csrf(settings,client),
        json={'learner_id':'family-g7','expected_revision':0}).status_code==200
    headers={**csrf(settings,client),'X-Learner-Context-Version':'1','Idempotency-Key':'fenced'}
    data=client.get(f'/api/v1/attempts/{attempt}/collection-preview',headers=headers).json()
    original=db.session
    with original() as c:account=c.execute('SELECT account_id FROM account_contexts').fetchone()[0]
    @contextmanager
    def racing_session(write=False):
        if write and write_context.get():
            token=write_context.set(None)
            try:
                with original(write=True) as c:select_context(c,account,'family-g2',1)
            finally:write_context.reset(token)
        with original(write=write) as c:yield c
    monkeypatch.setattr(db,'session',racing_session)
    response=client.post(f'/api/v1/attempts/{attempt}/collection',headers=headers,
        json={'confirmed':True,'preview_sha256':data['preview_sha256']})
    assert response.status_code==409,response.text
    with original() as c:
        for table in ('mistake_entries','mistake_sources','review_cards'):
            assert c.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


def test_drift_after_submission_blocks_grading_and_collection(practice):
    db,api,h,q=practice;attempt,_=answer(practice,grade=False)
    with db.session(write=True) as c:c.execute("UPDATE question_versions SET answer_key_json='{}' WHERE id=?",(q['id'],))
    run_worker_once(db,api.app.state.settings)
    with db.session() as c:
        assert c.execute('SELECT count(*) FROM grade_versions WHERE attempt_id=?',(attempt,)).fetchone()[0]==0
    assert api.get(f'/api/v1/attempts/{attempt}/collection-preview',headers=h).status_code==409


def test_missing_key_inactive_card_and_stopped_question_do_not_write(practice):
    db,api,h,q=practice;attempt,_=answer(practice);data=preview(practice,attempt)
    before=rows(db)
    assert api.post(f'/api/v1/attempts/{attempt}/collection',headers=h,
        json={'confirmed':True,'preview_sha256':data['preview_sha256']}).status_code==422
    assert rows(db)==before
    saved=collect(practice,attempt).json()
    another,_=answer(practice)
    with db.session(write=True) as c:c.execute('UPDATE review_cards SET active=0 WHERE id=?',(saved['review_card_id'],))
    before=rows(db)
    assert collect(practice,another).status_code==409 and rows(db)==before
    with db.session(write=True) as c:c.execute("UPDATE question_versions SET approval='needs_review' WHERE id=?",(q['id'],))
    assert api.get(f'/api/v1/attempts/{another}/collection-preview',headers=h).status_code==409
