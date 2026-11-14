"""Offline checks for the second lower batch: four first-scope units, nine items."""
from collections import Counter
from fractions import Fraction
import hashlib
import json

import pytest

from learning_service import chapter_practice as chapter, practice
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields
from scripts import review_lower_gap_candidates_batch2 as review
from scripts.build_lower_gap_candidates_batch2 import build, DESTINATION, BATCH
from scripts.build_lower_gap_candidates import DESTINATION as BATCH1_DESTINATION
from test_family_math import family


@pytest.fixture
def candidates():
    return chapter._parse(DESTINATION.read_bytes())[2]


def by_point(qs, point):
    return next(q for q in qs.values() if q['knowledge']['point_id'] == point)


def values(q):
    return [f['options'][int(f['answer']) - 1] if f['kind'] == 'choice'
            else Fraction(f['answer']) for f in q['responses']]


def test_nine_points_across_four_units_are_unregistered_and_reproducible(candidates):
    qs, points, before, after = review.proposal()
    assert json.loads(DESTINATION.read_bytes()) == build()
    assert len(qs) == len(points) == 9
    assert set(points) == {q['knowledge']['point_id'] for q in qs.values()}
    assert Counter(q['knowledge']['role'] for q in qs.values()) == {'direct': 9}
    assert Counter(q['book_id'] for q in qs.values()) == {
        'ethics-g2-lower': 2, 'ethics-g7-lower': 3, 'history-g7-lower': 2,
        'geography-g7-lower': 2}
    assert not (set(candidates) & set(chapter.bank())) and BATCH not in chapter.BATCHES
    # Batch 1 stays a separate, byte-identical, still-unregistered candidate set.
    first = chapter._parse(BATCH1_DESTINATION.read_bytes())[2]
    assert len(first) == 7 and not (set(first) & set(candidates))
    assert len(chapter.bank()) == 1074
    old = {r['id']: r for r in json.loads(review.SUBJECT.read_bytes())['rows']}
    new = {r['id']: r for r in before['rows']}
    assert set(new) - set(old) == set(points)
    for row_id, row in old.items():
        assert {k: v for k, v in row.items() if k != 'mappings'} == \
               {k: v for k, v in new[row_id].items() if k != 'mappings'}
    for point_id in points:
        assert new[point_id]['candidate_only'] is True and new[point_id]['mappings'] == []
        assert new[point_id]['manual_task']['automatically_graded'] is False


def test_every_item_carries_an_unobserved_manual_task(candidates):
    for q in candidates.values():
        m = q['manual_followup']
        assert m['automatically_graded'] is False
        assert m['completion'] == 'not_observed'
        assert m['learner_record_created'] is False
        assert m['reviewer'] is None
        assert len(m['criteria']) >= 3
        assert q['review']['teacher_reviewed'] is False
        assert q['review']['deployment_status'] == 'local_candidate_not_registered'


def test_history_and_geography_numbers_are_independently_recomputed(candidates):
    years = values(by_point(candidates, 'history-g7-lower:1:inventory-1'))[:3]
    assert years == [581, 589, 618] and 581 < 589 < 618
    # Sui lasted well under a century; the prompt's claim of "速亡" is consistent.
    assert 618 - 581 < 40
    dense, per_capita, density_compare, combined = values(
        by_point(candidates, 'geography-g7-lower:7:inventory-2'))
    population_a, area_a, gdp_a = 20000 * 10000, 400 * 10000, 80000 * 10 ** 8
    population_b, area_b, gdp_b = 5000 * 10000, 50 * 10000, 60000 * 10 ** 8
    assert dense == population_a / area_a == 50
    assert per_capita == gdp_a / population_a == 40000
    assert population_b / area_b == 100 > dense
    assert density_compare == '乙地区更大'
    assert gdp_a > gdp_b and gdp_a / population_a < gdp_b / population_b
    assert combined == '甲地区经济总量更大，但人均国内生产总值低于乙地区'


def test_geography_profile_and_latitude_answers_match_the_given_data(candidates):
    q = by_point(candidates, 'geography-g7-lower:7:inventory-1')
    rows = q['visual']['rows']
    heights = [int(v.replace('约', '').replace(' ', '')) for v in rows[1][1:]]
    assert heights[1] == max(heights) and heights[0] > heights[2]
    assert values(q)[1] == '北半球和南半球'
    assert values(q)[2] == '中部高、东西两侧低'
    assert '面积' in values(q)[3] or '高原' in values(q)[3]
    assert '自编示意值' in q['visual']['caption']
    assert '81' not in q['responses'][1]['label'], 'the latitude answer must not be leaked'


def test_ethics_items_use_fictional_scenarios_and_avoid_privacy(candidates):
    for point in ('ethics-g7-lower:1:inventory-1', 'ethics-g7-lower:1:inventory-2',
                  'ethics-g7-lower:1:inventory-3'):
        q = by_point(candidates, point)
        assert '虚构' in q['prompt'], point
        assert '不涉及任何真实的人和事' in q['prompt'] or '虚构记录' in q['prompt']
        assert '教材' in q['source']['evidence_limit'] and (
            '自编' in q['source']['evidence_limit'])
        m = q['manual_followup']['prompt']
        # Every manual prompt must say that a fictional stand-in is acceptable and
        # that personal disclosure is not required.
        assert ('虚构' in m or '假设' in m) and (
            '不追问' in m or '不必' in m or '不愿' in m or '不讲述真实' in m), m
    boundary = by_point(candidates, 'ethics-g7-lower:1:inventory-2')
    assert any('没有错' in v for v in values(boundary))


def test_each_field_wrong_missing_extra_and_feedback_boundaries(candidates):
    for q in candidates.values():
        key = json.loads(chapter.stored(q)['answer_key_json'])
        right = json.loads(q['answer'])
        assert grade_short_fields(q['answer'], key)[0] == 'correct'
        for field in q['responses']:
            wrongs = ([str(i + 1) for i in range(len(field['options'])) if str(i + 1) != field['answer']]
                      if field['kind'] == 'choice' else [str(Fraction(field['answer']) + 1)])
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


def test_installed_and_candidate_evidence_remain_separate(candidates, tmp_path):
    summary = review.export(tmp_path / 'review')
    assert summary['installed_evidence'] == {'configured': 112, 'partial': 288, 'gap': 267}
    assert summary['candidate_inclusive'] == {'configured': 112, 'partial': 297, 'gap': 258}
    assert summary['new_configured_requirements'] == 0
    assert not summary['local_bank_registered'] and BATCH not in chapter.BATCHES
    diffs = json.loads((tmp_path / 'review/coverage-diff.json').read_bytes())
    assert len(diffs) == 9
    assert sum(d['candidate_inclusive_after']['family_count'] for d in diffs) == 9
    assert all(d['installed_before']['status'] == 'gap' for d in diffs)
    evidence = json.loads((tmp_path / 'review/source-evidence.json').read_bytes())
    assert {e['book_id'] for e in evidence} == {
        'ethics-g2-lower', 'ethics-g7-lower', 'history-g7-lower', 'geography-g7-lower'}
    assert all(e['text_layer'] is False for e in evidence if e['book_id'] == 'ethics-g2-lower')
    assert all(e['figure_review'] == 'unverified' for e in evidence)


def test_synthetic_install_preserves_all_existing_rows_and_is_idempotent(family, candidates, monkeypatch):
    _, db, api, headers = family
    practice.install(db)
    for batch in chapter.BATCHES:
        if batch not in ('math_g7_action_candidates', 'math_g7_chapter4_action_candidates'):
            chapter.install(db, batch)
    with db.session() as c:
        assert c.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1145
        before = {r[0]: set(map(tuple, c.execute('SELECT * FROM "' + r[0] + '"')))
                  for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                     "AND name NOT LIKE 'sqlite_%'")}
    monkeypatch.setitem(chapter.BATCHES, BATCH, hashlib.sha256(DESTINATION.read_bytes()).hexdigest())
    assert chapter.install(db, BATCH)['added'] == 9
    assert chapter.install(db, BATCH)['added'] == 0
    with db.session() as c:
        for table, old in before.items():
            assert old <= set(map(tuple, c.execute('SELECT * FROM "' + table + '"')))
        assert c.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1154
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
