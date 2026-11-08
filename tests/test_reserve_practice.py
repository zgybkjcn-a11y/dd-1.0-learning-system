"""B02 trial content, immutable versions, unseen eligibility and learner isolation."""
from copy import deepcopy
from collections import Counter
from fractions import Fraction
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from learning_service import reserve_practice as reserve
from learning_service.practice import bank, install, grade_numeric
from test_family_math import family
from scripts.prepare_reserve_practice import prepare, windows
from learning_service.app import _ensure_review_card, run_worker_once


def setup(family):
    _, db, api, headers = family
    install(db)
    assert reserve.install(db)['added'] == 12
    return db, api, {**headers, 'X-Learner-Id': 'family-g7'}


def test_exact_content_and_trial_relationships():
    questions = reserve.bank()
    assert len(questions) == 12
    assert Counter(q['difficulty'] for q in questions.values()) == {'easy': 4, 'normal': 4, 'hard': 4}
    assert not set(questions) & bank().keys()
    for q in questions.values():
        reserve.mathematical_check(q)
        assert q['review']['teacher_reviewed'] is False
    variant = next(q for q in questions.values() if q['template_relation']['kind'] == 'numeric_variant')
    assert variant['template_relation']['parent_question_version_id'] == 'family-word-g7-storage-compare-v1'
    assert sum(q['template_relation']['kind'] == 'numeric_variant' for q in questions.values()) == 1
    assert reserve.stored(variant)['variant_kind'] == 'variant'


@pytest.mark.parametrize('name', ['reciprocal', 'rounding', 'scientific-exponent', 'mixed', 'fraction-distribute'])
def test_wrong_answers_fail_the_independent_condition(name):
    q = deepcopy(reserve.bank()['family-reserve-g7-' + name + '-v1'])
    q['answer'] = '999'
    q['independent_check'] = '999'  # A matching literal alone cannot make an answer valid.
    with pytest.raises(ValueError): reserve.mathematical_check(q)


def test_additive_installation_keeps_existing_questions_and_identities(family):
    _, db, _, _ = family
    install(db)
    with db.session() as conn:
        old = {t: [tuple(row) for row in conn.execute('SELECT * FROM ' + t)] for t in
               ('questions', 'question_versions', 'accounts', 'learners', 'identity_bindings')}
    assert reserve.install(db)['added'] == 12
    assert reserve.install(db)['added'] == 0
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 86
        for t, rows in old.items():
            assert set(rows) <= {tuple(row) for row in conn.execute('SELECT * FROM ' + t)}


def test_unseen_selection_survives_cancel_refresh_and_keeps_answers_hidden(family):
    db, api, h = setup(family)
    qs = reserve.bank()
    choices = api.get('/api/v1/question-choices', headers=h).json()['items']
    reserves = [c for c in choices if c['practice'] and c['practice'].get('reserve')]
    assert len(reserves) == 12 and all(c['practice']['reserve_unseen'] for c in reserves)
    assert all('answer_key' not in c and 'content_json' not in c and 'answer_key_json' not in c for c in choices)
    assert 'numeric_answer' not in json.dumps(choices)
    qid = next(iter(qs))
    body = {'question_version_id': qid, 'textbook_book_id': 'math-g7-upper', 'textbook_chapter_id': '2'}
    started = api.post('/api/v1/test-sessions', headers=h, json=body)
    assert started.status_code == 201
    assert started.json()['items'][0]['prompt'] == qs[qid]['prompt']
    assert started.json()['answer_key'] is None
    assert api.post('/api/v1/test-sessions/' + started.json()['session_id'] + '/cancel', headers=h).status_code == 200
    assert api.post('/api/v1/test-sessions', headers=h, json=body).status_code == 409
    again = api.get('/api/v1/question-choices', headers=h).json()['items']
    assert next(c for c in again if c['question_version_id'] == qid)['practice']['reserve_unseen'] is False
    assert sum(bool(c['practice'] and c['practice'].get('reserve_unseen')) for c in again) == 11
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0


def test_scope_and_profile_cannot_be_bypassed(family):
    _, api, h = setup(family)
    qid = next(iter(reserve.bank()))
    for chapter in ('1', '5'):
        assert api.post('/api/v1/test-sessions', headers=h, json={
            'question_version_id': qid, 'textbook_book_id': 'math-g7-upper', 'textbook_chapter_id': chapter}).status_code == 422
    other = {**h, 'X-Learner-Id': 'family-g2'}
    assert not any(c['practice'] and c['practice'].get('reserve') for c in api.get('/api/v1/question-choices', headers=other).json()['items'])
    assert api.post('/api/v1/test-sessions', headers=other, json={'question_version_id': qid}).status_code == 403


def test_unseen_reservation_is_atomic_under_two_requests(family):
    db, api, h = setup(family)
    qid = next(iter(reserve.bank()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: api.post('/api/v1/test-sessions', headers=h, json={'question_version_id': qid}).status_code, range(2)))
    assert sorted(statuses) == [201, 409]
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM test_items WHERE question_version_id=?', (qid,)).fetchone()[0] == 1


@pytest.mark.parametrize('field', ['content_json', 'answer_key_json', 'version', 'variant_kind'])
def test_runtime_changed_versions_are_rejected_without_new_session(family, field):
    db, api, h = setup(family)
    qid = next(iter(reserve.bank()))
    with db.session(write=True) as conn:
        conn.execute('UPDATE question_versions SET ' + field + '=? WHERE id=?', (2 if field == 'version' else 'changed', qid))
    result = api.get('/api/v1/question-choices', headers=h)
    assert result.status_code == 503
    assert api.post('/api/v1/test-sessions', headers=h, json={'question_version_id': qid}).status_code == 503
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM test_sessions').fetchone()[0] == 0
    with pytest.raises(ValueError): reserve.install(db)


def test_bank_changed_bytes_cannot_hide_behind_a_cache(tmp_path, monkeypatch):
    reserve.bank()
    p = tmp_path / 'bank.json'
    p.write_bytes(reserve.PATH.read_bytes() + b' ')
    monkeypatch.setattr(reserve, 'PATH', p)
    with pytest.raises(ValueError, match='changed'): reserve.bank()


def test_frozen_packet_preserves_future_observation_nulls(tmp_path):
    packet = tmp_path / 'packet'
    result = prepare(packet)
    plan = json.loads((packet / 'observation-plan.json').read_text())
    assert result['actual_observations'] == 0
    assert plan['baseline_started_at'] is None and plan['baseline_attempt_id'] is None
    assert [w['offset_days'] for w in plan['windows']] == [1, 3, 7]
    assert all(w['due_at'] is None and w['observed_at'] is None and w['outcome'] is None for w in plan['windows'])
    assert len(plan['question_version_hashes']) == 12
    with pytest.raises(ValueError, match='independent'): prepare(packet)
    assert windows('2026-11-08T10:00:00+08:00')[0]['due_at'] == '2026-11-09T10:00:00+08:00'
    with pytest.raises(ValueError, match='timezone'): windows('2026-11-08T10:00:00')


def test_numeric_answers_do_not_accept_equations_or_wrong_units():
    for raw in ('-0.25', '−1/4', '-2/8'):
        assert grade_numeric(raw, {'numeric_answer': '-1/4', 'units': []}) == 'correct'
    assert grade_numeric('2.75米', {'numeric_answer': '2.75', 'units': ['米']}) == 'correct'
    assert grade_numeric('2.75升', {'numeric_answer': '2.75', 'units': ['米']}) == 'incorrect'
    assert grade_numeric('6.4*10^6', {'numeric_answer': '6', 'units': []}) == 'incorrect'


def submit(api, h, item, answer, key):
    challenge = api.post('/api/v1/test-items/' + item + '/submission-challenges', headers=h).json()
    return api.post('/api/v1/test-items/' + item + '/answers', headers={**h, 'Idempotency-Key': key},
                    json={'raw_answer': answer, 'challenge_id': challenge['challenge_id'], 'nonce': challenge['nonce']})


def test_seen_question_can_only_repeat_with_its_valid_scoped_review_card(family):
    db, api, h = setup(family)
    qid = next(iter(reserve.bank()))
    body = {'question_version_id': qid}
    started = api.post('/api/v1/test-sessions', headers=h, json=body).json()
    api.post('/api/v1/test-sessions/' + started['session_id'] + '/cancel', headers=h)
    with db.session(write=True) as conn:
        card = _ensure_review_card(conn, 'family-g7', reserve.OBJECTIVE, api.app.state.settings)
        other = _ensure_review_card(conn, 'family-g7', 'objective-math-g7-subtract-negative-v1', api.app.state.settings)
    assert api.post('/api/v1/test-sessions', headers=h, json={**body, 'card_id': card}).status_code == 409
    with db.session(write=True) as conn:
        conn.execute("UPDATE review_cards SET due_at='2026-01-01T00:00:00+00:00' WHERE id IN (?,?)", (card, other))
    assert api.post('/api/v1/test-sessions', headers=h, json={**body, 'card_id': other}).status_code == 422
    foreign = {**h, 'X-Learner-Id': 'family-g2'}
    assert api.post('/api/v1/test-sessions', headers=foreign, json={**body, 'card_id': card}).status_code == 403
    repeated = api.post('/api/v1/test-sessions', headers=h, json={**body, 'card_id': card})
    assert repeated.status_code == 201
    item = repeated.json()['items'][0]['test_item_id']
    assert submit(api, h, item, '-0.25', 'review-reserve').status_code == 202
    assert run_worker_once(db, api.app.state.settings)['status'] == 'succeeded'
    with db.session() as conn:
        assert conn.execute('SELECT stage FROM review_cards WHERE id=?', (card,)).fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM grade_versions').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0


@pytest.mark.parametrize('after_submission', [False, True])
def test_frozen_version_checked_again_for_restore_hint_submit_and_worker(family, after_submission):
    db, api, h = setup(family)
    qid = next(iter(reserve.bank()))
    session = api.post('/api/v1/test-sessions', headers=h, json={'question_version_id': qid}).json()
    item = session['items'][0]['test_item_id']
    if after_submission:
        assert submit(api, h, item, '-1/4', 'before-drift').status_code == 202
    with db.session(write=True) as conn:
        conn.execute("UPDATE question_versions SET answer_key_json='{}' WHERE id=?", (qid,))
    assert api.get('/api/v1/test-sessions/' + session['session_id'], headers=h).status_code == 503
    if after_submission:
        result = run_worker_once(db, api.app.state.settings)
        assert result['error'] == 'PRACTICE_RESERVE_UNAVAILABLE'
    else:
        for method, suffix in [('GET', ''), ('POST', '/hints'), ('POST', '/submission-challenges')]:
            assert api.request(method, '/api/v1/test-items/' + item + suffix, headers=h).status_code == 503
        assert api.post('/api/v1/test-items/' + item + '/answers', headers={**h, 'Idempotency-Key': 'after-drift'},
                        json={'raw_answer': '-1/4', 'challenge_id': 'unknown', 'nonce': 'unknown'}).status_code == 503
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM grade_versions').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM review_events').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM learning_events').fetchone()[0] == 0
    assert api.post('/api/v1/test-sessions/' + session['session_id'] + '/cancel', headers=h).status_code == 200


def test_reserve_relationship_does_not_publish_precise_concept_mappings(family, reference_textbooks):
    _, api, h = setup(family)
    api.app.state.settings = replace(api.app.state.settings, textbook_dir=reference_textbooks)
    qid = next(iter(reserve.bank()))
    response = api.get('/api/v1/math-references', headers=h, params={'question_version_id': qid})
    assert response.status_code == 200
    assert response.json()['mapping_status'] == 'unmapped'


def test_reserve_imports_are_pure_and_optional_for_existing_choices(family, monkeypatch):
    monkeypatch.setattr(reserve, 'PATH', reserve.PATH.with_name('not-installed-reserves.json'))
    _, _, api, h = family
    choices = api.get('/api/v1/question-choices', headers={**h, 'X-Learner-Id': 'family-g7'})
    assert choices.status_code == 200 and len(choices.json()['items']) == 6
    code = "import sqlite3; sqlite3.connect=lambda *a, **k: (_ for _ in ()).throw(AssertionError('import opened DB')); import learning_service.reserve_practice; import scripts.prepare_reserve_practice"
    subprocess.run([sys.executable, '-c', code], check=True, capture_output=True)
