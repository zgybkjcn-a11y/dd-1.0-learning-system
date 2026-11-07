import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from prepare_family_math import prepare, STARTER_QUESTIONS
from learning_service.app import create_app
from learning_service.config import Settings
from learning_service.db import Database
from test_browser_auth import assertion


@pytest.fixture
def family(tmp_path):
    directory = tmp_path / 'family'
    prepare(directory, 'synthetic-parent')
    db = Database(directory / 'learning.db')
    settings = Settings(directory, db.path, directory / 'attachments', 'synthetic-admin', 'synthetic-adapter', False)
    client = TestClient(create_app(settings, db))
    headers = {'X-Adapter-Secret': 'synthetic-adapter', 'X-Trusted-Provider': 'open-webui',
               'X-Trusted-Issuer': 'family-pilot-webui', 'X-Trusted-Subject': 'synthetic-parent'}
    return directory, db, client, headers


def test_parent_sees_two_grades_with_separate_choices_and_no_answer_keys(family):
    _, db, c, headers = family
    learners = c.get('/api/v1/learners', headers=headers).json()['items']
    assert {x['curriculum_id'] for x in learners} == {'math-g2-v1', 'math-g7-v1'}
    choices = {}
    for grade, count in ((2, 8), (7, 6)):
        h = {**headers, 'X-Learner-Id': f'family-g{grade}'}
        result = c.get('/api/v1/question-choices', headers=h).json()
        assert len(result['items']) == count
        assert all(f'math-g{grade}' in x['id'] for x in result['objectives'])
        assert 'accepted' not in json.dumps(result) and 'answer_key' not in json.dumps(result)
        choices[grade] = result['items'][0]['question_version_id']
    h = {**headers, 'X-Learner-Id': 'family-g2'}
    assert c.post('/api/v1/test-sessions', headers=h, json={'question_version_id': choices[7]}).status_code == 403
    session = c.post('/api/v1/test-sessions', headers=h, json={'question_version_id': choices[2]}).json()
    assert session['items'][0]['prompt'] == STARTER_QUESTIONS['objective-math-g2-add-subtract-100'][0][0]
    assert c.get('/api/v1/test-sessions/' + session['session_id'], headers={**headers, 'X-Learner-Id': 'family-g7'}).status_code == 404


def test_two_grade_manual_notebooks_keep_their_own_content(family):
    _, _, c, headers = family
    for grade in (2, 7):
        h = {**headers, 'X-Learner-Id': f'family-g{grade}', 'Idempotency-Key': f'manual-{grade}'}
        objective = c.get('/api/v1/question-choices', headers=h).json()['objectives'][0]['id']
        assert c.post('/api/v1/mistakes/manual', headers=h,
                      json={'question_text': f'合成{grade}年级错题', 'objective_id': objective}).status_code == 201
        mistakes = c.get('/api/v1/mistakes', headers=h).json()['items']
        assert [x['content']['question_text'] for x in mistakes] == [f'合成{grade}年级错题']


def test_setup_preserves_existing_data_and_starter_answers_are_correct(family):
    directory, db, _, _ = family
    with pytest.raises(ValueError, match='existing data'):
        prepare(directory, 'another-parent')
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 14
    for questions in STARTER_QUESTIONS.values():
        for prompt, answer in questions:
            # Only the fixed arithmetic literals authored above are evaluated.
            assert str(eval(prompt.removesuffix(' = ?').replace('×', '*'), {'__builtins__': {}}, {})) == answer


def test_first_parent_claim_needs_signed_login_and_code_and_cannot_be_reused(tmp_path):
    directory = tmp_path / 'new-family'
    prepare(directory)
    db = Database(directory / 'learning.db')
    settings = Settings(directory, db.path, directory / 'attachments', 'admin', 'adapter', False,
                        browser_auth_enabled=True, browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                        browser_auth_issuer='synthetic-gateway', browser_identity_issuer='family-pilot-webui',
                        browser_origin='https://learning.example.invalid', family_setup_code='synthetic-family-code-0123456789abcdef')
    client = TestClient(create_app(settings, db), base_url=settings.browser_origin)
    def claim(subject, code, jti):
        return client.post('/api/v1/auth/session', headers={'Origin':settings.browser_origin,
            'Authorization':'Bearer ' + assertion(settings, changes={'sub':subject,'jti':jti}), 'X-Family-Setup-Code':code})
    assert claim('parent-a','wrong','attempt-a').status_code == 401
    assert claim('parent-a',settings.family_setup_code,'attempt-b').status_code == 201
    assert claim('parent-a','','attempt-c').status_code == 201
    assert claim('parent-b',settings.family_setup_code,'attempt-d').status_code == 401
    with db.session(write=True) as conn:
        assert conn.execute('SELECT COUNT(*) FROM identity_bindings').fetchone()[0] == 1
        assert settings.family_setup_code not in json.dumps([dict(r) for r in conn.execute('SELECT * FROM audit_events')])
        conn.execute('DELETE FROM identity_bindings')
    assert claim('parent-b',settings.family_setup_code,'attempt-e').status_code == 401
