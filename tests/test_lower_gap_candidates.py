"""Offline lower-candidate checks: bounded actions, grade boundaries and rehearsal."""
from collections import Counter
from fractions import Fraction
import hashlib
import json

import pytest

from learning_service import chapter_practice as chapter, practice
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields
from scripts import review_lower_gap_candidates as review
from scripts.build_lower_gap_candidates import build, DESTINATION, BATCH
from test_family_math import family


@pytest.fixture
def candidates():
    return chapter._parse(DESTINATION.read_bytes())[2]


def by_point(qs, point):
    return next(q for q in qs.values() if q['knowledge']['point_id'] == point)


def values(q):
    return [f['options'][int(f['answer']) - 1] if f['kind'] == 'choice'
            else Fraction(f['answer']) if f['kind'] == 'number' else f['answer']
            for f in q['responses']]


def test_seven_first_scope_points_are_registered_and_reproducible(candidates):
    qs, points, before, after = review.proposal()
    assert json.loads(DESTINATION.read_bytes()) == build()
    assert len(qs) == len(points) == 7
    assert set(points) == {q['knowledge']['point_id'] for q in qs.values()}
    assert Counter(q['knowledge']['role'] for q in qs.values()) == {'direct': 6, 'supporting': 1}
    assert {q['book_id'] for q in qs.values()} == {'math-g2-lower', 'english-g7-lower', 'biology-g7-lower'}
    assert set(candidates) <= set(chapter.bank()) and BATCH in chapter.BATCHES
    assert len(chapter.bank()) == 1155
    # Only appended candidate-only rows; no existing requirement may be rewritten.
    old = {r['id']: r for r in json.loads(review.SUBJECT.read_bytes())['rows']}
    new = {r['id']: r for r in before['rows']}
    assert set(new) - set(old) == set(points)
    for row_id, row in old.items():
        assert {k: v for k, v in row.items() if k != 'mappings'} == \
               {k: v for k, v in new[row_id].items() if k != 'mappings'}
        assert new[row_id]['mappings'] == row['mappings']
    for point_id, row in new.items():
        if point_id in points:
            assert row['candidate_only'] is True and row['mappings'] == []
            assert row['manual_task']['automatically_graded'] is False


def test_bounded_actions_are_answered_correctly_from_independent_arithmetic(candidates):
    v = lambda p: values(by_point(candidates, p))
    quotient, remainder, _, identity = v('math-g2-lower:1:inventory-1')
    assert 5 * quotient + remainder == 23 and remainder < 5
    assert identity == '成立，因为4×6+2=26' and 4 * 6 + 2 == 26
    bundles, left, boxes, multi = v('math-g2-lower:1:inventory-2')
    assert 5 * bundles + left == 22 and left < 5
    assert 6 * (boxes - 1) < 40 <= 6 * boxes  # the leftover forces one more box
    assert '至少要几个盒子' in multi
    assert v('english-g7-lower:1:inventory-2')[:2] == ['mice', 'sheep']
    germ = by_point(candidates, 'biology-g7-lower:1:inventory-1')
    rows = germ['visual']['rows']
    assert sum(int(c) for c in rows[1][1:]) == int(next(
        f['answer'] for f in germ['responses'] if f['kind'] == 'number')) == 27
    assert all(c == '0' for c in rows[2][1:])
    root = v('biology-g7-lower:1:inventory-2')
    assert '分生区' in root[0] and '伸长区' in root[0]
    assert '成熟区' in root[1]
    assert '落到雌蕊柱头上' in root[2] and '形成受精卵' in root[3]
    assert root[2] != root[3]


def test_text_answers_accept_only_the_documented_variants(candidates):
    q = by_point(candidates, 'english-g7-lower:1:inventory-1')
    field = next(f for f in q['responses'] if f['kind'] == 'text')
    key = json.loads(chapter.stored(q)['answer_key_json'])
    right = json.loads(q['answer'])
    for accepted in ('Because it is quiet and strong.', 'Because it is quiet and strong',
                     "Because it's quiet and strong.", 'BECAUSE IT IS QUIET AND STRONG'):
        assert grade_short_fields(json.dumps({**right, field['id']: accepted}), key)[0] == 'correct'
    # A different reason, a bare adjective phrase or an unstated cause must not pass.
    for wrong in ('Because it is big and fast.', 'Because people like it.',
                  'quiet and strong', 'Because it can jump far.'):
        assert grade_short_fields(json.dumps({**right, field['id']: wrong}), key)[0] == 'incorrect'


def test_each_field_wrong_missing_extra_and_feedback_boundaries(candidates):
    for q in candidates.values():
        key = json.loads(chapter.stored(q)['answer_key_json'])
        right = json.loads(q['answer'])
        assert grade_short_fields(q['answer'], key)[0] == 'correct'
        for field in q['responses']:
            if field['kind'] == 'choice':
                wrongs = [str(i + 1) for i in range(len(field['options'])) if str(i + 1) != field['answer']]
            elif field['kind'] == 'number':
                wrongs = [str(Fraction(field['answer']) + 1)]
            else:
                wrongs = ['not a plural']
            for wrong in wrongs:
                assert grade_short_fields(json.dumps({**right, field['id']: wrong}), key)[0] == 'incorrect'
            missing = {k: v for k, v in right.items() if k != field['id']}
            assert grade_short_fields(json.dumps(missing), key)[0] == 'incorrect'
            for invalid in (True, '', '1 or 2'):
                assert grade_short_fields(json.dumps({**right, field['id']: invalid}), key)[0] == 'incorrect'
            for e in field['errors']:
                outcome, feedback = grade_short_fields(json.dumps({**right, field['id']: e['answer']}), key)
                assert outcome == 'incorrect' and e['message'] in feedback and e['action'] in feedback
        assert grade_short_fields(json.dumps({**right, 'extra': '1'}), key)[0] == 'incorrect'
        assert grade_short_fields('{"a":"1",' + q['answer'][1:], key)[0] == 'incorrect'


def test_manual_observation_and_language_evidence_stay_open(candidates):
    supporting = {q['knowledge']['point_id'] for q in candidates.values()
                  if q['knowledge']['role'] == 'supporting'}
    assert supporting == {'biology-g7-lower:1:inventory-1'}
    for q in candidates.values():
        assert q['review']['teacher_reviewed'] is False
        assert q['review']['curriculum_standard_crosscheck'] == 'assistant_crosscheck_passed_2026-11-18_against_local_plan_or_inventory'
        assert q['review']['deployment_status'] == 'registered_family_bank'
        assert len(q['review']['field_coverage']) == len(q['responses'])
        if q['knowledge']['role'] == 'supporting':
            assert q['manual_followup']['automatically_graded'] is False
            assert q['manual_followup']['completion'] == 'not_observed'
            assert q['manual_followup']['learner_record_created'] is False
    # Reading and listening are never claimed by a text-only item.
    for point in ('english-g7-lower:1:inventory-1', 'english-g7-lower:1:inventory-2',
                  'english-g7-lower:1:inventory-3'):
        q = by_point(candidates, point)
        assert '不代替自由写作、口述、听说或实际操作' in q['design']['assessment_limit']
        assert '听力' in q['source']['evidence_limit'] or '朗读' in q['source']['evidence_limit']
        assert q['design']['skills'] and q['review']['teacher_reviewed'] is False


def test_installed_and_candidate_evidence_remain_separate(candidates, tmp_path):
    summary = review.export(tmp_path / 'review')
    assert summary['installed_evidence'] == {'configured': 112, 'partial': 288, 'gap': 265}
    assert summary['candidate_inclusive'] == {'configured': 112, 'partial': 295, 'gap': 258}
    assert summary['new_configured_requirements'] == 0
    assert summary['local_bank_registered'] and BATCH in chapter.BATCHES
    diffs = json.loads((tmp_path / 'review/coverage-diff.json').read_bytes())
    assert len(diffs) == 7
    assert sum(d['candidate_inclusive_after']['family_count'] for d in diffs) == 6
    assert all(d['installed_before']['status'] == 'gap' for d in diffs)
    evidence = json.loads((tmp_path / 'review/source-evidence.json').read_bytes())
    assert {e['book_id'] for e in evidence} == {'math-g2-lower', 'english-g7-lower', 'biology-g7-lower'}
    assert all(e['text_layer'] is False for e in evidence if e['book_id'] == 'math-g2-lower')
    assert all(e['figure_review'] == 'unverified' for e in evidence)


def test_synthetic_install_preserves_all_existing_rows_and_is_idempotent(family, candidates, monkeypatch):
    _, db, api, headers = family
    practice.install(db)
    for batch in chapter.BATCHES:
        if batch not in ('math_g7_action_candidates', 'math_g7_chapter4_action_candidates'):
            chapter.install(db, batch)
    with db.session() as c:
        assert c.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1226
        before = {r[0]: set(map(tuple, c.execute('SELECT * FROM "' + r[0] + '"')))
                  for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                     "AND name NOT LIKE 'sqlite_%'")}
    monkeypatch.setitem(chapter.BATCHES, BATCH, hashlib.sha256(DESTINATION.read_bytes()).hexdigest())
    assert chapter.install(db, BATCH)['added'] == 0
    assert chapter.install(db, BATCH)['added'] == 0
    with db.session() as c:
        for table, old in before.items():
            assert old <= set(map(tuple, c.execute('SELECT * FROM "' + table + '"')))
        assert c.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1226
    for q in candidates.values():
        h = {**headers, 'X-Learner-Id': f"family-g{q['grade']}"}
        response = api.post('/api/v1/test-sessions', headers=h,
                            json={'question_version_id': q['id'], 'textbook_book_id': q['book_id'],
                                  'textbook_chapter_id': q['chapter_id']})
        assert response.status_code == 201, response.text
        data = response.json()
        assert data['answer_key'] is None and 'field_answers' not in response.text
        item = data['items'][0]
        foreign = {**headers, 'X-Learner-Id': 'family-g7' if q['grade'] == 2 else 'family-g2'}
        assert api.get('/api/v1/test-sessions/' + data['session_id'],
                       headers=foreign).status_code in (403, 404)
        token = api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",
                         headers=h).json()
        body = {'challenge_id': token['challenge_id'], 'nonce': token['nonce'], 'raw_answer': q['answer']}
        url = f"/api/v1/test-items/{item['test_item_id']}/answers"
        hh = {**h, 'Idempotency-Key': q['id']}
        response = api.post(url, headers=hh, json=body)
        assert response.status_code == 202, response.text
        aid = response.json()['attempt_id']
        assert api.post(url, headers=hh, json=body).json()['attempt_id'] == aid
        run_worker_once(db, api.app.state.settings)
        assert api.get('/api/v1/attempts/' + aid, headers=h).json()['outcome'] == 'correct'
    with db.session() as c:
        assert c.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0
        for table, old in before.items():
            if table in ('questions', 'question_versions'):
                assert old <= set(map(tuple, c.execute('SELECT * FROM "' + table + '"')))


def test_candidates_cover_new_lower_books_but_the_starter_bank_does_not(candidates):
    from learning_service import practice
    from learning_service.textbooks import BOOKS
    from practice_catalogue import PRACTICE_BOOK_IDS, READING_ONLY_BOOK_IDS
    assert {q['book_id'] for q in candidates.values()} <= READING_ONLY_BOOK_IDS
    assert not ({q['book_id'] for q in candidates.values()} & PRACTICE_BOOK_IDS)
    assert {q['book_id'] for q in chapter.bank().values()} == PRACTICE_BOOK_IDS | READING_ONLY_BOOK_IDS
    assert {q['book_id'] for q in practice.bank().values()} == {'math-g2-upper', 'math-g7-upper'}
    assert len(BOOKS) == 20 and sum(len(b['chapters']) for b in BOOKS) == 152
