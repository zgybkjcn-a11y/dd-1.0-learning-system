"""Chapter coverage, immutable installation and actual challenge/grade integration."""
from collections import Counter
from fractions import Fraction
import json

import pytest

from learning_service import chapter_practice as chapter
from learning_service.app import run_worker_once
from learning_service.practice import bank, install, grade_numeric
from learning_service.textbooks import practice_scope
from practice_catalogue import PRACTICE_BOOKS
from test_family_math import family


def test_practice_catalogue_chapters_have_real_questions_and_all_levels():
    questions = list(bank().values()) + list(chapter.bank().values())
    coverage = Counter((q['book_id'], q['chapter_id'], q['difficulty']) for q in questions)
    for book in PRACTICE_BOOKS:
        for ch in book['chapters']:
            for level in ('easy', 'normal', 'hard'):
                assert coverage[book['id'], ch['id'], level] >= (4 if book['subject'] == 'math' else 1)
    assert sum(len(chapter.bank(b)) for b in ('math', 'upper', 'remaining')) == 414
    assert len(set(chapter.bank())-set(chapter.bank('math_gaps'))-set(chapter.bank('subject_gaps'))) == 1050
    assert len(set(chapter.bank())-set(chapter.bank('math_gaps'))) == 1064
    assert len(chapter.bank()) == 1074
    assert len({q['prompt'] for q in chapter.bank().values()}) == 1074
    for q in chapter.bank().values():
        assert practice_scope(q['id']) == {'book_id': q['book_id'], 'chapter_id': q['chapter_id']}
        key = json.loads(chapter.stored(q)['answer_key_json'])
        if 'responses' in q:
            from learning_service.practice_response import grade_fields, grade_short_fields
            if q.get('response_protocol') in ('short-fields-v2','structured-fields-v3'):grade_fields=grade_short_fields
            assert grade_fields(q['answer'], key)[0] == 'correct'
            assert grade_fields('999999', key)[0] == 'incorrect'
        else:
            assert grade_numeric(q['answer'], key) == 'correct'
            assert grade_numeric('999999', key) == 'incorrect'
        assert q['hint'] and q['explanation'] and not q['source']['textbook_original_question']


def test_math_answers_against_separate_constraints():
    groups = {}
    for q in chapter.bank('math').values():
        groups.setdefault((q['book_id'], q['chapter_id']), []).append(q)
    for (book, cid), rows in groups.items():
        for i in range(4):
            a, d = i + 3, i + 2
            values = [Fraction(q['answer']) for q in rows[i*3:i*3+3]]
            if book == 'math-g2-upper':
                if cid == 'activity1':
                    directions = ['北', '东', '南', '西']
                    for q, offset in zip(rows[i*3:i*3+3], (2, 1, 2)):
                        assert f"{q['answer']}. {directions[(i+offset)%4]}" in q['prompt']
                    continue
                expected = {'1': (a, 4, 5), '4': (7, 80-10*i, 100-10*a-5*d),
                            'activity2': ((10+i)*d, (10+i)*d+3, (12+2*i)*d),
                            '6': (a*d, a+3, a*d+3)}[cid]
            elif book == 'math-g7-upper':
                expected = {'1': (i+4, 2*i+8, -(i+5)), '3': (3*d+2, a*d+5, 4*d+11),
                            '4': (a+d, 7, -a+4*d-6), '6': (a, 25+5*i, Fraction(1,2))}[cid]
            else:
                expected = {'7': (35+10*i, 120-10*i, 130-10*i), '8': (a,-a,a),
                            '9': (-a,4,3*a), '10': (d,a,a), '11': (a+1,1-a,4),
                            '12': (a+d+4,36+18*i,200+40*i)}[cid]
                if cid == '8':
                    assert values[0]**2 == a*a and values[1]**3 == -a**3
                    assert values[2]**2 < a*a+2 < (values[2]+1)**2
                if cid == '10':
                    assert values[1] + d == a+d and values[1] - d == a-d
            assert values == list(expected), (book, cid, i)


def test_install_preserves_old_questions_and_is_idempotent(family):
    _, db, api, headers = family
    install(db)
    with db.session() as conn:
        old = {tuple(r) for r in conn.execute('SELECT * FROM question_versions')}
    for batch in chapter.BATCHES:
        assert chapter.install(db, batch)['added'] == len(chapter.bank(batch))
        assert chapter.install(db, batch)['added'] == 0
    with db.session() as conn:
        assert old <= {tuple(r) for r in conn.execute('SELECT * FROM question_versions')}
        assert conn.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 0
    for grade in (2, 7):
        result = api.get('/api/v1/question-choices', headers={**headers, 'X-Learner-Id': f'family-g{grade}'})
        assert result.status_code == 200
        assert 'numeric_answer' not in result.text and 'explanation' not in result.text
        rows = result.json()['items']
        for q in chapter.bank().values():
            assert (q['id'] in {r['question_version_id'] for r in rows}) == (q['grade'] == grade)


def test_each_chapter_can_launch_and_representative_answers_grade(family):
    _, db, api, headers = family
    for batch in chapter.BATCHES:
        chapter.install(db, batch)
    seen = set()
    graded_subjects = set()
    for q in chapter.bank().values():
        scope = q['book_id'], q['chapter_id']
        if scope in seen:
            continue
        seen.add(scope)
        h = {**headers, 'X-Learner-Id': f"family-g{q['grade']}"}
        response = api.post('/api/v1/test-sessions', headers=h, json={
            'question_version_id': q['id'], 'textbook_book_id': q['book_id'], 'textbook_chapter_id': q['chapter_id']})
        assert response.status_code == 201, response.text
        item = response.json()['items'][0]
        assert item['prompt'] == q['prompt'] and response.json()['answer_key'] is None
        assert 'numeric_answer' not in response.text
        assert api.post('/api/v1/test-sessions', headers={**h, 'X-Learner-Id': 'family-g7' if q['grade'] == 2 else 'family-g2'},
                        json={'question_version_id': q['id']}).status_code == 403
        if q['subject'] in graded_subjects:
            continue
        graded_subjects.add(q['subject'])
        token = api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges", headers=h).json()
        answer = api.post(f"/api/v1/test-items/{item['test_item_id']}/answers", headers={**h, 'Idempotency-Key': q['id']},
                          json={'challenge_id': token['challenge_id'], 'nonce': token['nonce'], 'raw_answer': q['answer']})
        assert answer.status_code == 202, answer.text
        run_worker_once(db, api.app.state.settings)
        graded = api.get('/api/v1/attempts/' + answer.json()['attempt_id'], headers=h).json()
        assert graded['outcome'] == 'correct' and graded['feedback'] == q['explanation']
    assert len(seen) == 98 and len(graded_subjects) == 7


def test_bulk_placements_match_the_single_lookup():
    """One-bank-per-request lookup must agree with the per-version rule."""
    from learning_service.reserve_practice import bank as reserve_bank
    from learning_service.textbooks import practice_scopes

    ids = (list(chapter.bank())[:40] + list(bank())[:20] + list(reserve_bank())[:5]
           + ['family-starter-objective-math-g2-multiplication-1-v1',
              'family-starter-objective-math-g7-subtract-negative-v1-6-v1',
              'family-starter-objective-math-g2-multiplication-9-v1'])
    scopes = practice_scopes(ids)
    assert scopes == {question_id: practice_scope(question_id) for question_id in ids}


def test_bulk_question_lookup_and_metadata_match_per_version():
    """Bulk loading must return exactly what the per-version helpers return."""
    from learning_service.practice import metadata, metadata_for, question, questions
    from learning_service.reserve_practice import bank as reserve_bank

    ids = (list(chapter.bank())[:40] + list(bank())[:20] + list(reserve_bank())[:5]
           + ['family-starter-objective-math-g2-multiplication-1-v1', 'missing-version'])
    loaded = questions(ids)
    assert loaded == {version_id: question(version_id) for version_id in ids}
    assert ({version_id: metadata_for(version_id, item) for version_id, item in loaded.items()}
            == {version_id: metadata(version_id) for version_id in ids})


def test_question_choices_loads_the_bank_once_per_request(family, monkeypatch):
    """Candidates must not re-read the chapter bank or re-look each one up."""
    from learning_service import practice

    _, db, api, headers = family
    chapter.install(db, 'math')
    h = {**headers, 'X-Learner-Id': 'family-g2'}
    answered = next(q for q in chapter.bank('math').values() if q['grade'] == 2)
    session = api.post('/api/v1/test-sessions', headers=h, json={'question_version_id': answered['id']}).json()
    test_item = session['items'][0]
    token = api.post(f"/api/v1/test-items/{test_item['test_item_id']}/submission-challenges", headers=h).json()
    answer = api.post(f"/api/v1/test-items/{test_item['test_item_id']}/answers",
                      headers={**h, 'Idempotency-Key': answered['id']},
                      json={'challenge_id': token['challenge_id'], 'nonce': token['nonce'],
                            'raw_answer': answered['answer']})
    assert answer.status_code == 202, answer.text
    run_worker_once(db, api.app.state.settings)
    calls = []
    original = chapter.bank

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    def forbid(version_id):
        raise AssertionError('per-version lookup in question-choices: %s' % version_id)

    monkeypatch.setattr(chapter, 'bank', counting)
    monkeypatch.setattr(practice, 'question', forbid)
    response = api.get('/api/v1/question-choices', headers=h)
    assert response.status_code == 200, response.text
    chapter_items = [item for item in response.json()['items']
                     if item['question_version_id'].startswith('family-chapter-')]
    assert len(chapter_items) > 20
    assert len(calls) == 1, 'chapter bank loaded %d times for %d items' % (len(calls), len(chapter_items))


def test_tampered_bank_and_stored_version_fail_closed(family, tmp_path, monkeypatch):
    _, db, api, headers = family
    chapter.install(db, 'math')
    q = next(iter(chapter.bank('math').values()))
    with db.session(write=True) as conn:
        conn.execute('UPDATE question_versions SET answer_key_json=? WHERE id=?', ('{}', q['id']))
    h = {**headers, 'X-Learner-Id': 'family-g2'}
    assert api.get('/api/v1/question-choices', headers=h).status_code == 503
    assert api.post('/api/v1/test-sessions', headers=h, json={'question_version_id': q['id']}).status_code == 503
    with pytest.raises(ValueError):
        chapter.install(db, 'math')
    name = 'family_chapter_math_v1.json'
    (tmp_path / name).write_bytes((chapter.DATA / name).read_bytes() + b' ')
    monkeypatch.setattr(chapter, 'DATA', tmp_path)
    with pytest.raises(ValueError, match='bank changed'):
        chapter.bank('math')
