from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json
import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

from learning_service.app import _variant_snapshot, create_app, run_worker_once
from learning_service.backup import backup_data, restore_data
from learning_service.db import Database, json_dumps, utc_now, write_context
from learning_service.learner_context import select_context
from learning_service.providers import ProviderResult
from test_learning_service import env
from test_learner_context import shared_env, choose
from test_browser_auth import auth_env, csrf


def seed_source(db):
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES ('source','shared','approved','obj-1',?)", (utc_now(),))
        content = {'template_id':'signed_number_subtraction','prompt':'-3 - (-5) = ?', 'parameters':{'start':-3,'subtrahend':-5},'domain':'integers','unit':None}
        conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES ('source-v1','source',1,?,?,'exact-text-v1','approved',?)", (json_dumps(content), '{"accepted":["2"]}', utc_now()))


def draft_result(snapshot):
    return {'draft': {'objective_id':'obj-1','source_question_version_id':'source-v1',
        'content': {'template_id':'signed_number_subtraction','prompt':'-4 - (-7) = ?', 'parameters':{'start':-4,'subtrahend':-7},'domain':'integers','unit':None},
        'answer_key':{'accepted':['3']},'validator_version':'exact-text-v1','approval':'draft'},'approval_required':True}


@pytest.fixture
def review_env(env, monkeypatch):
    s, db, app = env
    seed_source(db)
    class SyntheticVariant:
        def generate(self, snapshot):
            return ProviderResult('synthetic-variant', 'needs_review', draft_result(snapshot), {'external_call':False,'mode':'synthetic_fixture'})
    monkeypatch.setattr('learning_service.app.variant_provider', lambda *_: SyntheticVariant())
    c = TestClient(app)
    h = {'X-Adapter-Secret':'adapter', 'X-Account-Id':'acct-a', 'X-Learner-Id':'learner-a'}
    r = c.post('/api/v1/variant-jobs', json={'objective_id':'obj-1','source_question_version_id':'source-v1'}, headers=h)
    assert r.status_code == 202
    job = r.json()['job_id']
    assert run_worker_once(db, s)['status'] == 'succeeded'
    detail = c.get('/api/v1/admin/variant-jobs/' + job, headers=h)
    assert detail.status_code == 200 and detail.json()['source_current']
    return s, db, c, h, job, detail.json()


def decide(e, decision='approve', key='human-review', changes=None):
    _, _, c, h, job, detail = e
    body = {'decision':decision, 'result_fingerprint':detail['result_fingerprint'], 'note':'合成人工说明：核对母题、目标、整数和程序答案。'}
    body.update(changes or {})
    return c.post('/api/v1/admin/variant-jobs/'+job+'/review', headers={**h,'Idempotency-Key':key}, json=body)


def test_approve_is_atomic_private_frozen_idempotent_and_deliverable(review_env):
    s, db, c, h, job, detail = review_env
    assert c.get('/api/v1/question-choices',headers=h).json()['items'] == [{
        'question_version_id':'source-v1','version':1,'variant_kind':'base','objective_id':'obj-1',
        'textbook_scope':None,'practice':None}]
    generic = c.get('/api/v1/jobs/'+job,headers=h)
    assert 'answer_key' not in generic.text and 'result_json' not in generic.text
    r = decide(review_env); assert r.status_code == 200
    approved = r.json(); v = approved['question_version_id']
    assert decide(review_env).json() == approved
    assert decide(review_env,changes={'note':'different'}).status_code == 409
    assert decide(review_env,key='different-key').status_code == 409
    assert v in [x['question_version_id'] for x in c.get('/api/v1/question-choices',headers=h).json()['items']]
    assert c.post('/api/v1/test-sessions',headers=h,json={'question_version_id':v}).status_code == 201
    foreign = {'X-Adapter-Secret':'adapter','X-Account-Id':'acct-b','X-Learner-Id':'learner-b'}
    assert c.post('/api/v1/test-sessions',headers=foreign,json={'question_version_id':v}).status_code == 404
    with db.session() as conn:
        q = conn.execute('SELECT q.*,v.answer_key_json FROM questions q JOIN question_versions v ON v.question_id=q.id WHERE v.id=?',(v,)).fetchone()
        assert q['learner_id'] == 'learner-a' and q['visibility'] == 'private'
        assert json.loads(q['answer_key_json']) == {'accepted':['3']}
        assert conn.execute('SELECT COUNT(*) FROM variant_reviews').fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE operation='review_variant'").fetchone()[0] == 1
    for sql, args in [("UPDATE question_versions SET content_json='{}' WHERE id=?",(v,)),("UPDATE question_versions SET answer_key_json='{}' WHERE id=?",(v,)),("UPDATE questions SET visibility='shared' WHERE id=(SELECT question_id FROM question_versions WHERE id=?)",(v,)),("UPDATE jobs SET result_json='{}' WHERE id=?",(job,)),("UPDATE variant_reviews SET note='revised' WHERE job_id=?",(job,))]:
        with pytest.raises(sqlite3.IntegrityError), db.session(write=True) as conn: conn.execute(sql,args)


def test_reject_never_publishes_and_cannot_be_reapproved(review_env):
    _, db, _, _, _, _ = review_env
    r = decide(review_env,decision='reject'); assert r.status_code == 200
    assert r.json()['question_version_id'] is None
    assert decide(review_env,decision='reject').json() == r.json()
    assert decide(review_env,key='new-key').status_code == 409
    with db.session() as conn: assert conn.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1


@pytest.mark.parametrize('mutation', ['fingerprint','note','boolean','answer','prompt','scope','domain','unit','unchanged','approval','source_revoked','source_changed','foreign_source','curriculum','cancelled'])
def test_changed_or_invalid_candidates_do_not_publish(review_env, mutation):
    _, db, _, _, job, detail = review_env
    changes = {}
    if mutation == 'fingerprint': changes['result_fingerprint'] = '0'*64
    elif mutation == 'note': changes['note'] = '   '
    else:
        with db.session(write=True) as conn:
            result = json.loads(conn.execute('SELECT result_json FROM jobs WHERE id=?',(job,)).fetchone()[0])
            draft = result['payload']['draft']
            if mutation == 'boolean': draft['content']['parameters']['start'] = True
            if mutation == 'answer': draft['answer_key'] = {'accepted':['999']}
            if mutation == 'prompt': draft['content']['prompt'] = 'untrusted prompt'
            if mutation == 'scope': draft['objective_id'] = 'foreign'
            if mutation == 'domain': draft['content']['domain'] = 'reals'
            if mutation == 'unit': draft['content']['unit'] = 'kg'
            if mutation == 'approval': draft['approval'] = 'approved'
            if mutation == 'unchanged': draft['content']['parameters'] = {'start':-3,'subtrahend':-5}
            if mutation == 'source_revoked': conn.execute("UPDATE question_versions SET approval='draft' WHERE id='source-v1'")
            if mutation == 'source_changed': conn.execute("UPDATE question_versions SET answer_key_json='{}' WHERE id='source-v1'")
            if mutation == 'foreign_source': conn.execute("UPDATE questions SET visibility='private',learner_id='learner-b' WHERE id='source'")
            if mutation == 'curriculum': conn.execute("UPDATE learners SET curriculum_id='another' WHERE id='learner-a'")
            if mutation == 'cancelled': conn.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(job,))
            conn.execute('UPDATE jobs SET result_json=? WHERE id=?',(json_dumps(result),job))
            # Review the current fingerprint, except when specifically testing
            # stale fingerprints, so every semantic guard is exercised.
            from learning_service.variant_review import fingerprint
            changes['result_fingerprint'] = fingerprint(conn.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone())
    r = decide(review_env,changes=changes); assert r.status_code in {403,404,409,422}
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM variant_reviews').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1


def test_student_guardian_foreign_reviewer_and_revoked_reviewer_rejected(review_env):
    _, db, c, h, job, _ = review_env
    for role in ['student','guardian']:
        with db.session(write=True) as conn: conn.execute('UPDATE learner_access SET role=? WHERE account_id=?',(role,'acct-a'))
        assert decide(review_env).status_code == 403
        assert c.get('/api/v1/admin/variant-jobs',headers=h).status_code == 403
    with db.session(write=True) as conn: conn.execute("UPDATE learner_access SET role='reviewer' WHERE account_id='acct-b'")
    foreign = {**h,'X-Account-Id':'acct-b','X-Learner-Id':'learner-b'}
    assert c.get('/api/v1/admin/variant-jobs/'+job,headers=foreign).status_code == 404
    with db.session(write=True) as conn: conn.execute("UPDATE learner_access SET active=0 WHERE account_id='acct-a'")
    assert decide(review_env).status_code == 404


def test_revoke_invalidates_unsubmitted_items_and_preserves_pending_and_final_grades(review_env):
    s, db, c, h, _, _ = review_env
    approved = decide(review_env).json(); v=approved['question_version_id']
    first = c.post('/api/v1/test-sessions',headers=h,json={'question_version_id':v}).json()['items'][0]['test_item_id']
    pending = c.post('/api/v1/test-sessions',headers=h,json={'question_version_id':v}).json()['items'][0]['test_item_id']
    unused = c.post('/api/v1/test-sessions',headers=h,json={'question_version_id':v}).json()['items'][0]['test_item_id']
    def answer(item,key):
        ch=c.post('/api/v1/test-items/'+item+'/submission-challenges',headers=h).json()
        return c.post('/api/v1/test-items/'+item+'/answers',headers={**h,'Idempotency-Key':key},json={'challenge_id':ch['challenge_id'],'nonce':ch['nonce'],'raw_answer':'3'}).json()['attempt_id']
    a=answer(first,'first'); run_worker_once(db,s)
    before=c.get('/api/v1/attempts/'+a,headers=h).json()
    b=answer(pending,'pending')
    ch=c.post('/api/v1/test-items/'+unused+'/submission-challenges',headers=h).json()
    path='/api/v1/admin/variant-reviews/'+approved['review_id']+'/revoke'
    r=c.post(path,headers={**h,'Idempotency-Key':'revoke'},json={'note':'合成撤销说明'})
    assert r.status_code==200 and r.json()['prior_grades_unchanged']
    assert c.post(path,headers={**h,'Idempotency-Key':'revoke'},json={'note':'合成撤销说明'}).json()==r.json()
    assert c.post(path,headers={**h,'Idempotency-Key':'revoke'},json={'note':'different'}).status_code==409
    assert c.post('/api/v1/test-sessions',headers=h,json={'question_version_id':v}).status_code==404
    assert c.post('/api/v1/test-items/'+unused+'/answers',headers={**h,'Idempotency-Key':'invalid'},json={'challenge_id':ch['challenge_id'],'nonce':ch['nonce'],'raw_answer':'3'}).status_code in {404,409,410}
    assert run_worker_once(db,s)['status']=='succeeded'
    assert c.get('/api/v1/attempts/'+a,headers=h).json()==before
    assert c.get('/api/v1/attempts/'+b,headers=h).json()['outcome']=='correct'
    with pytest.raises(sqlite3.IntegrityError), db.session(write=True) as conn: conn.execute("UPDATE question_versions SET approval='approved' WHERE id=?",(v,))


def test_approval_failure_rolls_back_version_review_audit_and_idempotency(review_env,monkeypatch):
    _,db,_,_,_,_=review_env
    def fail(*_):raise RuntimeError('synthetic audit fault')
    monkeypatch.setattr('learning_service.app.review_audit',fail)
    with pytest.raises(RuntimeError):decide(review_env)
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM variant_reviews').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM idempotency_records').fetchone()[0]==0


def test_backup_restore_retains_frozen_review_and_delete_replay(review_env,tmp_path):
    s,db,c,h,_,_=review_env; approved=decide(review_env).json();v=approved['question_version_id']
    backup_data(s.data_dir,tmp_path/'snapshot');restore_data(tmp_path/'snapshot',tmp_path/'restore')
    restored=Database(tmp_path/'restore/learning.db')
    with restored.session() as conn:
        assert conn.execute('SELECT question_version_id FROM variant_reviews').fetchone()[0]==v
        assert json.loads(conn.execute('SELECT answer_key_json FROM question_versions WHERE id=?',(v,)).fetchone()[0])=={'accepted':['3']}
    deletion=c.post('/api/v1/admin/deletions',headers=h,json={'learner_id':'learner-a'})
    assert deletion.status_code==202
    backup_data(s.data_dir,tmp_path/'deleted');restore_data(tmp_path/'deleted',tmp_path/'deleted-restore')
    restored=Database(tmp_path/'deleted-restore/learning.db')
    with restored.session() as conn:assert conn.execute('SELECT approval FROM question_versions WHERE id=?',(v,)).fetchone()[0]=='retracted'


def test_shared_review_requires_browser_and_version_even_for_admin(shared_env):
    s,db,c=shared_env;choose(s,c,'learner-a',0)
    assert c.get('/api/v1/admin/variant-jobs',headers={'X-Learner-Context-Version':'1'}).status_code==200
    assert c.get('/api/v1/admin/variant-jobs',headers={'X-Learner-Context-Version':'0'}).status_code==409
    adapter=TestClient(c.app)
    headers={'X-Adapter-Secret':s.adapter_secret,'X-Trusted-Provider':'open-webui','X-Trusted-Issuer':'open-webui','X-Trusted-Subject':'subject-a','X-Learner-Context-Version':'1'}
    assert adapter.get('/api/v1/admin/variant-jobs',headers=headers).status_code==403
    assert c.get('/api/v1/admin/variant-jobs',headers={'X-Learner-Context-Version':'1'}).headers['cache-control']=='no-store'


def test_concurrent_approval_creates_only_one_frozen_version(review_env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    _,db,_,_,_,_=review_env
    barrier=Barrier(2)
    def approve(key):
        barrier.wait();return decide(review_env,key=key)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(approve,['parallel-a','parallel-b']))
    assert sorted(r.status_code for r in responses)==[200,409]
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM variant_reviews').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0]==2


def test_reviewer_revocation_after_authorization_is_rechecked_inside_write(review_env,monkeypatch):
    _,db,_,_,_,_=review_env
    original=db.session
    @contextmanager
    def racing_session(write=False):
        if write:
            with original(write=True) as conn:conn.execute("UPDATE learner_access SET role='student' WHERE account_id='acct-a'")
        with original(write=write) as conn:yield conn
    monkeypatch.setattr(db,'session',racing_session)
    assert decide(review_env).status_code==404
    with original() as conn:
        assert conn.execute('SELECT COUNT(*) FROM variant_reviews').fetchone()[0]==0


def test_regeneration_uses_new_idempotent_job_and_preserves_rejected_history(review_env):
    s,db,c,h,job,_=review_env
    assert decide(review_env,decision='reject').status_code==200
    path='/api/v1/variant-jobs'
    body={'objective_id':'obj-1','source_question_version_id':'source-v1'}
    new=c.post(path,headers={**h,'Idempotency-Key':'regenerate'},json=body)
    assert new.status_code==202 and new.json()['job_id']!=job
    assert c.post(path,headers={**h,'Idempotency-Key':'regenerate'},json=body).json()==new.json()
    changed=c.post(path,headers={**h,'Idempotency-Key':'regenerate'},json={'objective_id':'obj-1'})
    assert changed.status_code==409
    assert run_worker_once(db,s)['status']=='succeeded'
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM variant_reviews').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0]==1


def test_schema10_upgrade_preserves_sources_and_context_then_adds_review_tables(tmp_path):
    migrations=tmp_path/'old-migrations';migrations.mkdir()
    for path in (Path(__file__).parents[1]/'learning_service/migrations').glob('*.sql'):
        if int(path.name[:3])<=10:shutil.copy2(path,migrations/path.name)
    old=Database(tmp_path/'old.db',migrations)
    with old.session(write=True) as conn:
        now=utc_now()
        conn.execute("INSERT INTO accounts VALUES ('a',?)",(now,))
        conn.execute("INSERT INTO learners(id,display_name,curriculum_id,created_at) VALUES ('l','synthetic','math-g7-v1',?)",(now,))
        conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES ('kp','math-g7-v1','signed','signed',?)",(now,))
        conn.execute("INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES ('obj-1','kp','subtract','subtract',?)",(now,))
        conn.execute("INSERT INTO account_contexts VALUES ('a','l',4,?)",(now,))
    seed_source(old)
    upgraded=Database(old.path)
    with upgraded.session() as conn:
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]==11
        assert tuple(conn.execute('SELECT learner_id,revision FROM account_contexts').fetchone())==('l',4)
        assert json.loads(conn.execute("SELECT answer_key_json FROM question_versions WHERE id='source-v1'").fetchone()[0])=={'accepted':['2']}
        assert conn.execute('SELECT COUNT(*) FROM variant_reviews').fetchone()[0]==0
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
