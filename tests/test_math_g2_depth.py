"""The new batch reuses scopes, preserves attempts, and grades through the API."""
import json

from learning_service import chapter_practice as chapter
from learning_service.app import run_worker_once
from test_family_math import family


def test_depth_batch_reuses_scopes_and_existing_attempts(family):
    _, db, api, headers = family
    chapter.install(db, 'math')
    with db.session() as conn:
        before = {table: {tuple(r) for r in conn.execute('SELECT * FROM '+table)} for table in
                  ('question_versions', 'questions', 'knowledge_points', 'review_objectives', 'attempts')}
    assert chapter.install(db, 'math_g2_depth')['added'] == 88
    assert chapter.install(db, 'math_g2_depth')['added'] == 0
    with db.session() as conn:
        for table, old in before.items():
            assert old <= {tuple(r) for r in conn.execute('SELECT * FROM '+table)}
        # Three formerly base-bank-only chapter scopes (2,3,5) are now needed.
        assert conn.execute('SELECT count(*) FROM knowledge_points').fetchone()[0] == len(before['knowledge_points']) + 3
    h = {**headers, 'X-Learner-Id': 'family-g2'}
    result = api.get('/api/v1/question-choices', headers=h)
    assert result.status_code == 200
    assert 'numeric_answer' not in result.text and 'explanation' not in result.text
    rows = result.json()['coverage_plan']['items']
    assert all(any(t['question_count'] for t in row['tasks']) for row in rows)
    assert '口述' in result.json()['coverage_plan']['notice']
    seen = set()
    for q in chapter.bank('math_g2_depth').values():
        if q['chapter_id'] in seen:
            continue
        seen.add(q['chapter_id'])
        r = api.post('/api/v1/test-sessions', headers=h, json={
            'question_version_id': q['id'], 'textbook_book_id': q['book_id'], 'textbook_chapter_id': q['chapter_id']})
        assert r.status_code == 201, r.text
        item = r.json()['items'][0]
        assert item['prompt'] == q['prompt'] and r.json()['answer_key'] is None
        token = api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges", headers=h).json()
        submit = api.post(f"/api/v1/test-items/{item['test_item_id']}/answers",
                          headers={**h, 'Idempotency-Key': q['id']}, json={
                              'challenge_id': token['challenge_id'], 'nonce': token['nonce'], 'raw_answer': q['answer']})
        assert submit.status_code == 202, submit.text
        run_worker_once(db, api.app.state.settings)
        outcome = api.get('/api/v1/attempts/' + submit.json()['attempt_id'], headers=h).json()
        assert outcome['outcome'] == 'correct' and outcome['feedback'] == q['explanation']
    assert len(seen) == 8
    with db.session() as conn:
        attempts = {tuple(r) for r in conn.execute('SELECT * FROM attempts')}
    assert chapter.install(db, 'math_g2_depth')['added'] == 0
    with db.session() as conn:
        assert attempts == {tuple(r) for r in conn.execute('SELECT * FROM attempts')}


def test_new_ids_and_original_frozen_banks_coexist():
    original = {qid for b in ('math', 'upper', 'remaining') for qid in chapter.bank(b)}
    new = chapter.bank('math_g2_depth')
    assert not original.intersection(new)
    assert len(new) == 88
    for q in new.values():
        assert q['grade'] == 2 and q['book_id'] == 'math-g2-upper'
        assert q['source']['topic_printed_pages']
        assert not q['review']['teacher_reviewed']
        if q['coverage']['role'] == 'supporting':
            assert q['coverage']['task'] == 'understand'
        key = json.loads(chapter.stored(q)['answer_key_json'])
        assert key['numeric_answer'] == q['answer']
