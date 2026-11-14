"""Grade seven batch: immutable import, real grading and conservative coverage."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import json

from learning_service import chapter_practice as chapter
from learning_service.app import run_worker_once
from learning_service.practice import bank as word_bank
from learning_service.practice_coverage import report
from test_family_math import family


def test_g7_install_preserves_records_and_all_six_chapters_grade(family):
    _, db, api, headers = family
    # Reproduce the historical pre-depth baseline: later batches already create
    # its two newly introduced objectives and cannot be installed first here.
    for batch in ('math', 'upper', 'remaining', 'math_g2_depth'):
        chapter.install(db, batch)
    with db.session() as conn:
        before = {r[0]: {tuple(v) for v in conn.execute('SELECT * FROM "'+r[0]+'"')}
                  for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    assert chapter.install(db, 'math_g7_depth')['added'] == 136
    assert chapter.install(db, 'math_g7_depth')['added'] == 0
    with db.session() as conn:
        additions = {}
        for table, old in before.items():
            current = {tuple(r) for r in conn.execute('SELECT * FROM "'+table+'"')}
            assert old <= current
            if current-old:
                additions[table] = len(current-old)
        assert additions == {'knowledge_points': 2, 'review_objectives': 2,
                             'questions': 136, 'question_versions': 136, 'audit_events': 1}
    h = {**headers, 'X-Learner-Id': 'family-g7'}
    result = api.get('/api/v1/question-choices', headers=h)
    assert result.status_code == 200
    assert 'numeric_answer' not in result.text and 'explanation' not in result.text
    assert len(result.json()['coverage_plan']['items']) == 34
    new = chapter.bank('math_g7_depth')
    g2 = api.get('/api/v1/question-choices', headers={**headers, 'X-Learner-Id': 'family-g2'}).json()
    assert not (set(new) & {r['question_version_id'] for r in g2['items']})
    seen = set()
    for q in new.values():
        if q['chapter_id'] in seen:
            continue
        seen.add(q['chapter_id'])
        response = api.post('/api/v1/test-sessions', headers=h, json={
            'question_version_id': q['id'], 'textbook_book_id': q['book_id'], 'textbook_chapter_id': q['chapter_id']})
        assert response.status_code == 201, response.text
        item = response.json()['items'][0]
        assert response.json()['answer_key'] is None and item['prompt'] == q['prompt']
        token = api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges", headers=h).json()
        submit = api.post(f"/api/v1/test-items/{item['test_item_id']}/answers",
                          headers={**h, 'Idempotency-Key': q['id']}, json={
                              'challenge_id': token['challenge_id'], 'nonce': token['nonce'], 'raw_answer': q['answer']})
        assert submit.status_code == 202
        run_worker_once(db, api.app.state.settings)
        outcome = api.get('/api/v1/attempts/'+submit.json()['attempt_id'], headers=h).json()
        assert outcome['outcome'] == 'correct' and outcome['feedback'] == q['explanation']
    assert seen == set('123456')
    with db.session() as conn:
        attempts = {tuple(r) for r in conn.execute('SELECT * FROM attempts')}
    assert chapter.install(db, 'math_g7_depth')['added'] == 0
    with db.session() as conn:
        assert attempts == {tuple(r) for r in conn.execute('SELECT * FROM attempts')}


def test_g7_numeric_answers_against_independent_constraints():
    qs = {q['id'].split('-depth-')[1].removesuffix('-v1'): q for q in chapter.bank('math_g7_depth').values()}
    expected = {
        'line-02': 6, 'line-04': 9, 'opposite-02': Fraction(5, 2), 'opposite-04': 4,
        'absolute-02': Fraction(3, 4), 'absolute-04': -2, 'add-02': -8,
        'subtract-02': -11, 'subtract-03': 8, 'multiply-02': 12,
        'multiply-03': -6, 'multiply-04': -6, 'laws-02': -686, 'divide-02': -4,
        'divide-04': 16, 'power-02': -27, 'power-04': -11,
        'approximate-02': Fraction(Decimal('3.146').quantize(Decimal('.01'), rounding=ROUND_HALF_UP)),
        'binary-02': int('101', 2), 'value-02': -7, 'value-04': 7,
        'like-04': 2, 'bracket-04': 5, 'solve-02': 11,
    }
    numeric = {key for key, q in qs.items() if '请填正确选项' not in q['prompt']}
    assert numeric == set(expected)
    for key, value in expected.items():
        assert Fraction(qs[key]['answer']) == value, key
    x = Fraction(qs['solve-02']['answer'])
    assert (x+3)/2 == 7
    assert abs(Fraction(qs['absolute-04']['answer'])) == 2
    assert Fraction(qs['absolute-04']['answer']) < 0


def test_g7_expression_recognition_and_old_variants_cannot_inflate_coverage():
    ids = (set(chapter.bank()) - set(chapter.bank('math_g7_multistep'))) | set(word_bank())
    rows = {r['id'].split(':', 1)[1]: {t['id']: t for t in r['tasks']}
            for r in report('math-g7-v1', ids)['items']}
    assert len(rows) == 34 and all(t['question_count'] for tasks in rows.values() for t in tasks.values())
    for point, task in [('3:expression', 'apply'), ('3:pattern', 'apply'), ('5:model', 'apply'),
                        ('6:design', 'transfer'), ('5:equality', 'transfer'), ('2:binary', 'transfer')]:
        t = rows[point][task]
        assert t['family_count'] == 0 and t['status'] == 'partial'
        assert t['question_count'] == t['supporting_question_count']
    for point, task in [('1:line', 'transfer'), ('1:opposite', 'apply'), ('3:value', 'transfer'),
                        ('4:like', 'apply'), ('6:bisect', 'apply')]:
        t = rows[point][task]
        assert t['question_count'] == 5 and t['family_count'] == 1 and t['status'] == 'partial'
    # Raw positive/negative addition in stories is one operation family.
    assert rows['2:add']['apply']['family_count'] == 1
    assert rows['2:add']['transfer']['family_count'] == 0
    assert rows['5:model']['transfer']['family_count'] == 0
    assert Counter(t['status'] for tasks in rows.values() for t in tasks.values()) == {'configured': 17, 'partial': 119}


def test_g2_inventory_is_preserved_byte_for_byte_as_rows():
    data = chapter.DATA
    old = json.loads((data/'family_math_coverage_plan_v2.json').read_bytes())
    new = json.loads((data/'family_math_coverage_plan_v3.json').read_bytes())
    assert [r for r in old['rows'] if r['book_id']=='math-g2-upper'] == [r for r in new['rows'] if r['book_id']=='math-g2-upper']
