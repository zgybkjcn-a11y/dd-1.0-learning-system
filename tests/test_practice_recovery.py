"""Persistent rounds and answer concurrency using isolated synthetic learners."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app, run_worker_once, _learner_export
from learning_service.db import Database, json_dumps, write_context
from learning_service.practice import bank, install, question_snapshot, learner_guidance
from test_family_math import family
from test_practice_collection import practice, collect, answer


def state(env):
    _, api, headers, _ = env
    result = api.get('/api/v1/practice-workspace', headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def configure(env, **changes):
    _, api, headers, _ = env
    current = state(env)
    body = {k: current[k] for k in ('book_id', 'chapter_id', 'difficulty', 'pool')}
    body['book_id'] = body['book_id'] or 'math-g7-upper'
    if not current['revision']: body['chapter_id'] = '2'
    body.update({'expected_revision': current['revision'], **changes})
    return api.put('/api/v1/practice-workspace', headers=headers, json=body)


def start(env, question=None, **changes):
    _, api, headers, default = env
    current = state(env)
    return api.post('/api/v1/test-sessions', headers=headers, json={
        'question_version_id': (question or default)['id'], 'workspace_revision': current['revision'],
        'textbook_book_id': current['book_id'], 'textbook_chapter_id': current['chapter_id'], **changes})


def submit(env, session, raw='99999', *, grade=True):
    db, api, headers, _ = env
    assert session.status_code == 201, session.text
    item = session.json()['items'][0]['test_item_id']
    challenge = api.post(f'/api/v1/test-items/{item}/submission-challenges', headers=headers)
    assert challenge.status_code == 200, challenge.text
    payload = {k: challenge.json()[k] for k in ('challenge_id', 'nonce')} | {'raw_answer': raw}
    result = api.post(f'/api/v1/test-items/{item}/answers', headers={**headers, 'Idempotency-Key': item}, json=payload)
    assert result.status_code == 202, result.text
    if grade: run_worker_once(db, api.app.state.settings)
    return item, payload, result.json()


def test_read_only_empty_state_validation_and_profile_isolation(practice):
    db, api, headers, _ = practice
    assert state(practice)['revision'] == 0
    with db.session() as conn:
        assert conn.execute('SELECT count(*) FROM practice_workspaces').fetchone()[0] == 0
    assert configure(practice, book_id='math-g2-upper').status_code == 422
    assert configure(practice, completed_ids=['invented']).status_code == 422
    assert configure(practice, expected_revision=True).status_code == 422
    assert configure(practice).status_code == 200
    other = {**headers, 'X-Learner-Id': 'family-g2'}
    assert api.get('/api/v1/practice-workspace', headers=other).json()['revision'] == 0
    assert api.get('/api/v1/practice-workspace').status_code in (401, 403)


def test_concurrent_workspace_updates_and_starts_are_fenced(practice):
    db, api, headers, question = practice
    assert configure(practice).status_code == 200
    current = state(practice)
    payload = {k: current[k] for k in ('book_id', 'chapter_id', 'difficulty', 'pool')} | {'expected_revision': current['revision']}
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: api.put('/api/v1/practice-workspace', headers=headers, json=payload), range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    current = state(practice)
    body = {'question_version_id': question['id'], 'workspace_revision': current['revision'],
            'textbook_book_id': current['book_id'], 'textbook_chapter_id': current['chapter_id']}
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: api.post('/api/v1/test-sessions', headers=headers, json=body), range(2)))
    assert sorted(r.status_code for r in results) == [201, 409]
    with db.session() as conn:
        assert conn.execute('SELECT count(*) FROM test_sessions').fetchone()[0] == 1


def test_new_client_restores_active_pending_and_graded_answer_after_reopen(practice):
    db, api, headers, question = practice
    assert configure(practice, difficulty='hard').status_code == 200
    session = start(practice)
    current = state(practice)
    assert current['current_session_id'] == session.json()['session_id']
    item = session.json()['items'][0]['test_item_id']
    assert api.post(f'/api/v1/test-items/{item}/hints', headers=headers).status_code == 200
    item, _, attempt = submit(practice, session, '<script>raw text</script>', grade=False)
    reopened = Database(db.path)
    other = TestClient(create_app(api.app.state.settings, reopened))
    assert other.get('/api/v1/practice-workspace', headers=headers).json() == current
    restored = other.get('/api/v1/test-sessions/' + current['current_session_id'], headers=headers).json()['items'][0]
    assert restored['status'] == 'grading_pending' and restored['submitted_answer'] == '<script>raw text</script>'
    assert restored['assistance'] == 'hint' and restored['attempt_id'] == attempt['attempt_id']
    assert 'answer_key' not in restored and 'question_snapshot_json' not in restored
    assert configure(practice, chapter_id='5').status_code == 409
    assert start(practice, replace_current=True).status_code == 409
    run_worker_once(reopened, api.app.state.settings)
    assert state(practice)['completed_ids'] == [question['id']]
    with reopened.session() as conn:
        assert learner_guidance(conn, 'family-g7')['math-g7-upper|2']['difficulty'] == 'easy'


def test_explicit_skip_atomic_invalid_replacement_and_scope_restore(practice):
    db, api, headers, question = practice
    configure(practice)
    session = start(practice)
    first = session.json()['items'][0]['test_item_id']
    assert start(practice).status_code == 409
    assert configure(practice, chapter_id='5').status_code == 409
    foreign = next(q for q in bank().values() if q['grade'] == 2)
    assert start(practice, foreign, replace_current=True).status_code in (403, 422)
    with db.session() as conn:
        assert conn.execute('SELECT status FROM test_items WHERE id=?', (first,)).fetchone()[0] == 'presented'
    assert configure(practice, chapter_id='5', discard_current=True).status_code == 200
    with db.session() as conn:
        assert conn.execute('SELECT status FROM test_items WHERE id=?', (first,)).fetchone()[0] == 'cancelled'
    assert state(practice)['current_session_id'] is None


@pytest.mark.parametrize('same', [True, False])
def test_parallel_answers_keep_one_attempt_and_report_different_content(practice, same):
    db, api, headers, _ = practice
    configure(practice); session = start(practice)
    item = session.json()['items'][0]['test_item_id']
    challenges = [api.post(f'/api/v1/test-items/{item}/submission-challenges', headers=headers).json() for _ in range(2)]
    bodies = [{k: c[k] for k in ('challenge_id', 'nonce')} | {'raw_answer': '21' if same or i == 0 else '22'} for i, c in enumerate(challenges)]
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda i: api.post(f'/api/v1/test-items/{item}/answers',
            headers={**headers, 'Idempotency-Key': f'concurrent-{i}'}, json=bodies[i]), range(2)))
    assert sorted(r.status_code for r in results) == ([202, 202] if same else [202, 409])
    if not same: assert next(r for r in results if r.status_code == 409).json()['error']['code'] == 'PRACTICE_ANSWER_CONFLICT'
    run_worker_once(db, api.app.state.settings); run_worker_once(db, api.app.state.settings)
    with db.session() as conn:
        assert conn.execute('SELECT count(*) FROM attempts').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM grade_versions').fetchone()[0] == 1
        stored = conn.execute('SELECT raw_answer FROM attempts').fetchone()[0]
    winner = next(i for i, r in enumerate(results) if r.status_code == 202)
    assert stored == bodies[winner]['raw_answer']
    wrong = {**headers, 'X-Learner-Id': 'family-g2', 'Idempotency-Key': 'other-profile'}
    assert api.post(f'/api/v1/test-items/{item}/answers', headers=wrong, json=bodies[winner]).status_code == 404


def test_response_lost_retry_uses_original_key_without_rescoring(practice):
    db, api, headers, _ = practice
    configure(practice); session = start(practice)
    item, payload, result = submit(practice, session)
    retried = api.post(f'/api/v1/test-items/{item}/answers', headers={**headers, 'Idempotency-Key': item}, json=payload)
    assert retried.status_code == 202 and retried.json() == result
    assert api.post(f'/api/v1/test-items/{item}/answers', headers={**headers, 'Idempotency-Key': 'new-key'}, json=payload).json()['attempt_id'] == result['attempt_id']
    run_worker_once(db, api.app.state.settings)
    with db.session() as conn: assert conn.execute('SELECT count(*) FROM grade_versions').fetchone()[0] == 1


def test_round_restart_keeps_history_guidance_and_other_levels(practice):
    db, api, headers, _ = practice
    configure(practice)
    easy = [q for q in bank().values() if q['grade'] == 7 and q['chapter_id'] == '2' and q['difficulty'] == 'easy']
    for q in easy: submit(practice, start(practice, q), q['answer'])
    assert len(state(practice)['completed_ids']) == 4
    assert start(practice, easy[0]).status_code == 409
    with db.session() as conn: assert learner_guidance(conn, 'family-g7')['math-g7-upper|2']['difficulty'] == 'normal'
    hard = next(q for q in bank().values() if q['grade'] == 7 and q['chapter_id'] == '2' and q['difficulty'] == 'hard')
    configure(practice, difficulty='hard'); submit(practice, start(practice, hard), hard['answer'])
    assert configure(practice, difficulty='easy', restart_round=True).status_code == 200
    assert state(practice)['completed_ids'] == [hard['id']]
    with db.session() as conn:
        assert conn.execute('SELECT count(*) FROM attempts').fetchone()[0] == 5
        assert learner_guidance(conn, 'family-g7')['math-g7-upper|2']['difficulty'] == 'normal'
    configure(practice, chapter_id='5'); assert state(practice)['completed_ids'] == []
    configure(practice, chapter_id='2'); assert state(practice)['completed_ids'] == [hard['id']]
    assert start(practice, easy[0]).status_code == 201


def test_reserve_unseen_and_collected_review_are_not_reset_or_counted(practice):
    from learning_service.reserve_practice import install as install_reserves, bank as reserves
    db, api, headers, _ = practice
    install_reserves(db)
    configure(practice, pool='reserve')
    q = next(iter(reserves().values()))
    session = start(practice, q); submit(practice, session)
    assert configure(practice, restart_round=True).status_code == 409
    configure(practice, pool='initial')
    attempt, _ = answer(practice)
    saved = collect(practice, attempt).json()
    with db.session(write=True) as conn:
        conn.execute("UPDATE review_cards SET due_at='2020-01-01T00:00:00+00:00' WHERE id=?", (saved['review_card_id'],))
    review = start(practice, card_id=saved['review_card_id'], mistake_id=saved['mistake_id'])
    submit(practice, review)
    assert state(practice)['completed_ids'] == []
    configure(practice, pool='reserve')
    assert state(practice)['completed_ids'] == [q['id']]
    assert start(practice, q).status_code == 409


def test_legacy_client_does_not_invent_round_membership_and_export_includes_state(practice):
    db, api, headers, _ = practice
    attempt, item = answer(practice)
    assert state(practice)['revision'] == 0
    configure(practice); assert state(practice)['completed_ids'] == []
    with db.session() as conn:
        assert conn.execute('SELECT practice_round_id FROM test_items WHERE id=?', (item,)).fetchone()[0] is None
        account = conn.execute('SELECT id FROM accounts').fetchone()[0]
        exported = _learner_export(conn, 'family-g7', account, 'synthetic-export')
    assert exported['practice_workspaces'][0]['learner_id'] == 'family-g7'
    assert exported['attempts'][0]['id'] == attempt


def test_schema12_upgrade_preserves_old_frozen_item_and_answer(tmp_path):
    migrations = Path(__file__).parents[1] / 'learning_service/migrations'
    old_migrations = tmp_path / 'old-migrations'; old_migrations.mkdir()
    for path in migrations.glob('*.sql'):
        if int(path.name.split('_')[0]) <= 12: shutil.copy2(path, old_migrations / path.name)
    old = Database(tmp_path / 'old.db', old_migrations); install(old)
    q = next(iter(bank().values()))
    with old.session(write=True) as conn:
        conn.execute("INSERT INTO learners(id,display_name,created_at) VALUES ('old','synthetic','2026-01-01')")
        conn.execute("INSERT INTO test_sessions(id,learner_id,mode,status,created_at) VALUES ('session','old','independent','active','2026-01-01')")
        conn.execute("INSERT INTO test_items(id,session_id,learner_id,question_version_id,status,question_snapshot_json) VALUES ('item','session','old',?,'grading_pending',?)", (q['id'], json_dumps(question_snapshot(conn, q['id']))))
        conn.execute("INSERT INTO attempts(id,test_item_id,learner_id,raw_answer,submitted_at,idempotency_key) VALUES ('attempt','item','old','original answer','2026-01-01','original-key')")
        original = dict(conn.execute("SELECT * FROM test_items WHERE id='item'").fetchone())
    upgraded = Database(old.path)
    with upgraded.session() as conn:
        row = dict(conn.execute("SELECT * FROM test_items WHERE id='item'").fetchone())
        assert {k: row[k] for k in original} == original
        assert row['practice_round_id'] is None and row['practice_round_generation'] is None
        assert conn.execute('SELECT count(*) FROM practice_workspaces').fetchone()[0] == 0
        assert conn.execute('SELECT raw_answer,idempotency_key FROM attempts').fetchone()[:] == ('original answer', 'original-key')
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == 13
    Database(old.path)  # Repeated migration is safe.


def test_profile_change_between_authorization_and_workspace_write_is_fenced(practice, monkeypatch):
    from learning_service.learner_context import select_context
    from test_browser_auth import assertion, csrf
    db, api, _, _ = practice
    settings = replace(api.app.state.settings, browser_auth_enabled=True, shared_learner_context_enabled=True,
        browser_auth_secret='synthetic-gateway-key-0123456789abcdef', browser_auth_issuer='synthetic-gateway',
        browser_identity_issuer='family-pilot-webui', browser_origin='https://recovery.example.invalid')
    client = TestClient(create_app(settings, db), base_url=settings.browser_origin)
    assert client.post('/api/v1/auth/session', headers={'Origin': settings.browser_origin,
        'Authorization': 'Bearer ' + assertion(settings, changes={'sub': 'synthetic-parent'})}).status_code == 201
    client.post('/api/v1/learner-context', headers=csrf(settings, client), json={'learner_id': 'family-g7', 'expected_revision': 0})
    original = db.session
    with original() as conn: account = conn.execute('SELECT account_id FROM account_contexts').fetchone()[0]
    @contextmanager
    def racing_session(write=False):
        if write and write_context.get():
            token = write_context.set(None)
            try:
                with original(write=True) as conn: select_context(conn, account, 'family-g2', 1)
            finally: write_context.reset(token)
        with original(write=write) as conn: yield conn
    monkeypatch.setattr(db, 'session', racing_session)
    response = client.put('/api/v1/practice-workspace', headers={**csrf(settings, client), 'X-Learner-Context-Version': '1'},
                          json={'expected_revision': 0, 'book_id': 'math-g7-upper', 'chapter_id': '2'})
    assert response.status_code == 409, response.text
    with original() as conn: assert conn.execute('SELECT count(*) FROM practice_workspaces').fetchone()[0] == 0
