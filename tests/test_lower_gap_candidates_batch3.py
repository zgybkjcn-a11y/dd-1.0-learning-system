"""Offline checks for the third lower batch: 7.1.2 split plus 二下数学 units 2—5."""
from collections import Counter
from fractions import Fraction
import hashlib
import json

import pytest

from learning_service import chapter_practice as chapter, practice
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields
from scripts import review_lower_gap_candidates_batch3 as review
from scripts.build_lower_gap_candidates_batch3 import (
    BATCH, DESTINATION, PERPENDICULAR_POINTS, build)
from scripts.build_lower_gap_candidates import DESTINATION as BATCH1_DESTINATION
from scripts.build_lower_gap_candidates_batch2 import DESTINATION as BATCH2_DESTINATION
from test_family_math import family


@pytest.fixture
def candidates():
    return chapter._parse(DESTINATION.read_bytes())[2]


def by_point(qs, point):
    return next(q for q in qs.values() if q['knowledge']['point_id'] == point)


def values(q):
    return [f['options'][int(f['answer']) - 1] if f['kind'] == 'choice'
            else Fraction(f['answer']) for f in q['responses']]


def test_nine_reviewed_points_are_registered_and_reproducible(candidates):
    qs, points, before, after = review.proposal()
    assert json.loads(DESTINATION.read_bytes()) == build()
    assert len(qs) == len(points) == 9
    assert set(points) == {q['knowledge']['point_id'] for q in qs.values()}
    assert Counter(q['knowledge']['role'] for q in qs.values()) == {'direct': 9}
    assert Counter(q['book_id'] for q in qs.values()) == {
        'math-g7-lower': 3, 'math-g2-lower': 6}
    assert Counter(p['point_kind'] for p in points.values()) == {
        'inventory_new_initial_point': 6, 'reviewed_page_split': 3}
    assert set(candidates) <= set(chapter.bank()) and BATCH in chapter.BATCHES
    # Earlier lower batches stay separate registered batches.
    first = chapter._parse(BATCH1_DESTINATION.read_bytes())[2]
    second = chapter._parse(BATCH2_DESTINATION.read_bytes())[2]
    assert len(first) == 7 and len(second) == 9
    assert not (set(first) | set(second)) & set(candidates)
    assert len(chapter.bank()) == 1155
    old = {r['id']: r for r in json.loads(review.SUBJECT.read_bytes())['rows']}
    new = {r['id']: r for r in before['rows']}
    assert set(new) - set(old) == set(points)
    for row_id, row in old.items():
        assert {k: v for k, v in row.items() if k != 'mappings'} == \
               {k: v for k, v in new[row_id].items() if k != 'mappings'}
    for point_id in points:
        assert new[point_id]['candidate_only'] is True and new[point_id]['mappings'] == []
        assert new[point_id]['manual_task']['automatically_graded'] is False


def test_legacy_perpendicular_row_is_kept_and_only_refined(candidates):
    plan = {r['id']: r for r in json.loads(review.SUBJECT.read_bytes())['rows']}
    _, points, before, _ = review.proposal()
    new = {r['id']: r for r in before['rows']}
    legacy = 'math-g7-lower:7:perpendicular'
    assert legacy in plan and plan[legacy]['printed_page'] == 3
    assert {k: v for k, v in plan[legacy].items() if k != 'mappings'} == \
           {k: v for k, v in new[legacy].items() if k != 'mappings'}
    refined = [p for p in PERPENDICULAR_POINTS]
    for point_id in refined:
        assert points[point_id]['refines_point_id'] == legacy
        assert new[point_id]['refines_point_id'] == legacy
        assert new[point_id]['printed_page'] in (4, 5, 6)
        assert '保留不改' in new[point_id]['refines_location_note']
    assert {new[p]['printed_page'] for p in refined} == {4, 5, 6}


def test_every_item_carries_an_unobserved_manual_task(candidates):
    for q in candidates.values():
        m = q['manual_followup']
        assert m['automatically_graded'] is False
        assert m['completion'] == 'not_observed'
        assert m['learner_record_created'] is False
        assert m['reviewer'] is None
        assert len(m['criteria']) >= 3
        assert q['review']['teacher_reviewed'] is False
        assert q['review']['deployment_status'] == 'registered_family_bank'


def test_perpendicular_answers_match_the_reviewed_pages(candidates):
    definition = values(by_point(candidates, 'math-g7-lower:7:perpendicular-definition'))
    assert definition[0] == '互相垂直'
    assert definition[1] == 90 and definition[3] == 90
    assert definition[2] == '两条互相垂直的直线的交点叫作垂足'
    unique = values(by_point(candidates, 'math-g7-lower:7:perpendicular-unique'))
    assert unique[0] == '有且只有一条'
    assert '不能去掉' in unique[1]
    assert unique[2] == '线段 AB 所在的直线'
    assert '直角边' in unique[3]
    distance = values(by_point(candidates, 'math-g7-lower:7:perpendicular-distance'))
    assert distance[0] == 'PO < PA'
    assert distance[1] == '从这点到直线的垂线段'
    assert distance[2] == 8
    # BC is perpendicular to AC, so the distance from B to line AC is BC.
    assert 6 ** 2 + 8 ** 2 == 10 ** 2
    assert distance[3] == '与直角相对的那条边'
    # The distance answer equals a leg, and both legs are shorter than the hypotenuse.
    assert distance[2] == 8 < 10


def test_math_g2_answers_are_independently_recomputed(candidates):
    times = values(by_point(candidates, 'math-g2-lower:2:inventory-1'))
    assert times[:3] == [2, 8, 2]
    assert times[0] == 6 / 3 and times[1] == 2 * 4 and times[2] == 8 / 4
    assert times[3] == '大树的高度是小树的 3 倍'
    assert (3 + 6) / 3 == 3 and (3 + 6) - 3 == 6

    place = values(by_point(candidates, 'math-g2-lower:3:inventory-1'))
    assert place[0] == 1000 == 10 * 100
    assert place[1] == '3005'
    assert place[2] == 4320 == 4 * 1000 + 3 * 100 + 2 * 10
    assert place[3] == '25' and int(place[3]) == 2500 / 100

    tens = values(by_point(candidates, 'math-g2-lower:3:inventory-2'))
    assert tens[:3] == [130, 1500, 800]
    assert tens[0] == 80 + 50 and tens[1] == 900 + 600 and tens[2] == 1700 - 900
    assert tens[3].startswith('2 个千减 1 个千是 1 个千')

    written = values(by_point(candidates, 'math-g2-lower:4:inventory-1'))
    assert written[:3] == [302, 743, 68]
    assert written[0] == 271 + 31 and written[1] == 445 + 298 and written[2] == 213 - 145
    assert written[3].endswith('得 180') and 278 - 98 == 180

    parts = values(by_point(candidates, 'math-g2-lower:4:inventory-2'))
    assert parts[:3] == [249, 358, 289]
    assert parts[0] == 709 - 460 and parts[1] == 836 - 478 and parts[2] == 664 - 375
    assert parts[3] == '加数=和-另一个加数'

    links = values(by_point(candidates, 'math-g2-lower:5:inventory-1'))
    assert links[0] == 4 == 32 / 8
    assert links[1] == 6 and 6 * 7 + 3 == 45
    assert links[2] == '相同数位对齐，从个位算起'
    assert links[3] == '加、减法各部分间的关系'


def test_answers_are_not_leaked_into_prompts_or_other_fields(candidates):
    for q in candidates.values():
        labels = [f['label'] for f in q['responses']]
        assert len(labels) == len(set(labels)), q['id']
        texts = [q['prompt'], *labels]
        for field in q['responses']:
            if field['kind'] != 'choice':
                continue
            correct = field['options'][int(field['answer']) - 1]
            for text in texts:
                if text != field['label']:
                    assert correct not in text, (q['id'], field['id'], correct)


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
    assert summary['local_bank_registered'] and BATCH in chapter.BATCHES
    diffs = json.loads((tmp_path / 'review/coverage-diff.json').read_bytes())
    assert len(diffs) == 9
    assert sum(d['candidate_inclusive_after']['family_count'] for d in diffs) == 9
    assert all(d['installed_before']['status'] == 'gap' for d in diffs)
    evidence = json.loads((tmp_path / 'review/source-evidence.json').read_bytes())
    assert {e['book_id'] for e in evidence} == {'math-g2-lower', 'math-g7-lower'}
    assert all(e['figure_review'] == 'unverified' for e in evidence)
    for row in evidence:
        if row['book_id'] == 'math-g2-lower':
            assert row['text_layer'] is False
            assert row['source_review_method'] == 'local_page_image_view_no_OCR'
        else:
            assert row['text_layer'] is True
            assert row['source_review_method'] == 'local_original_PDF_native_text_no_OCR'


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
