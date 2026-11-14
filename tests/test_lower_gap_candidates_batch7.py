"""Offline checks for the seventh lower batch: six scopes, seven items."""
from collections import Counter
from fractions import Fraction
import hashlib
import json

import pytest

from learning_service import chapter_practice as chapter, practice
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields
from scripts import review_lower_gap_candidates_batch7 as review
from scripts.build_lower_gap_candidates_batch7 import BATCH, DESTINATION, build
from scripts.build_lower_gap_candidates import DESTINATION as BATCH1_DESTINATION
from scripts.build_lower_gap_candidates_batch2 import DESTINATION as BATCH2_DESTINATION
from scripts.build_lower_gap_candidates_batch3 import DESTINATION as BATCH3_DESTINATION
from scripts.build_lower_gap_candidates_batch4 import DESTINATION as BATCH4_DESTINATION
from scripts.build_lower_gap_candidates_batch5 import DESTINATION as BATCH5_DESTINATION
from scripts.build_lower_gap_candidates_batch6 import DESTINATION as BATCH6_DESTINATION
from test_family_math import family


@pytest.fixture
def candidates():
    return chapter._parse(DESTINATION.read_bytes())[2]


def by_point(qs, point):
    return next(q for q in qs.values() if q['knowledge']['point_id'] == point)


def values(q):
    return [f['options'][int(f['answer']) - 1] if f['kind'] == 'choice'
            else Fraction(f['answer']) for f in q['responses']]


def test_seven_scopes_are_unregistered_and_reproducible(candidates):
    qs, points, before, after = review.proposal()
    assert json.loads(DESTINATION.read_bytes()) == build()
    assert len(qs) == len(points) == 7
    assert set(points) == {q['knowledge']['point_id'] for q in qs.values()}
    assert Counter(q['knowledge']['role'] for q in qs.values()) == {'direct': 7}
    assert Counter(q['book_id'] for q in qs.values()) == {
        'ethics-g2-lower': 4, 'ethics-g7-lower': 3}
    assert not (set(candidates) & set(chapter.bank())) and BATCH not in chapter.BATCHES
    earlier = [chapter._parse(p.read_bytes())[2]
               for p in (BATCH1_DESTINATION, BATCH2_DESTINATION, BATCH3_DESTINATION,
                         BATCH4_DESTINATION, BATCH5_DESTINATION, BATCH6_DESTINATION)]
    assert [len(qs) for qs in earlier] == [7, 9, 9, 9, 9, 7]
    assert not (set().union(*earlier) & set(candidates))
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


def test_grade_two_ethics_answers_match_the_pages(candidates):
    nature = values(by_point(candidates, 'ethics-g2-lower:2:inventory-1'))
    assert nature[0] == '晴天'
    assert nature[1] == '雨水可能到身边'
    assert '只用眼睛看' in nature[2]
    assert '都有生命' in nature[3]

    water = values(by_point(candidates, 'ethics-g2-lower:2:inventory-2'))
    assert '秧苗' in water[0]
    assert '作业本' in water[1]
    assert '非常重要' in water[2]
    assert '倒掉' in water[3] and '垃圾' in water[3]

    virtues = values(by_point(candidates, 'ethics-g2-lower:3:inventory-1'))
    assert '勤劳' in virtues[0]
    assert virtues[1] == '诚信'
    assert '自强' in virtues[2]
    assert '看齐' in virtues[3]

    dreams = values(by_point(candidates, 'ethics-g2-lower:4:inventory-1'))
    assert dreams[0] == '我们共同的梦想'
    assert '有大有小' in dreams[1]
    assert '从现在' in dreams[2] or '珍惜时光' in dreams[2]
    assert '多做几次' in dreams[3]


def test_grade_seven_ethics_answers_match_the_pages(candidates):
    respect = values(by_point(candidates, 'ethics-g7-lower:2:inventory-1'))
    assert respect[0] == '自我尊重和赢得他人的尊重'
    assert '知廉耻' in respect[1]
    assert '伤害了他人' in respect[2]
    assert '恰当' in respect[3] and '过高' in respect[3]
    q = by_point(candidates, 'ethics-g7-lower:2:inventory-1')
    assert '不涉及任何同学的真实个人评价' in q['prompt']

    ideas = values(by_point(candidates, 'ethics-g7-lower:3:inventory-1'))
    assert '非物质文化遗产' in ideas[0]
    assert '和谐共生' in ideas[1]
    assert '多样性' in ideas[2] and '失去生机' in ideas[2]
    assert '求同' in ideas[3] or '不同' in ideas[3]

    law = values(by_point(candidates, 'ethics-g7-lower:4:inventory-1'))
    assert '社会公共利益' in law[0] and '法律责任' in law[0]
    assert '界限' in law[1] and '义务' in law[1]
    assert '知识产权' in law[2] and '许可' in law[2]
    assert law[3] == '保护知识产权就是尊重劳动、保护创新'


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
    assert summary['installed_evidence'] == {'configured': 112, 'partial': 288, 'gap': 265}
    assert summary['candidate_inclusive'] == {'configured': 112, 'partial': 295, 'gap': 258}
    assert summary['new_configured_requirements'] == 0
    assert not summary['local_bank_registered'] and BATCH not in chapter.BATCHES
    diffs = json.loads((tmp_path / 'review/coverage-diff.json').read_bytes())
    assert len(diffs) == 7
    assert sum(d['candidate_inclusive_after']['family_count'] for d in diffs) == 7
    assert all(d['installed_before']['status'] == 'gap' for d in diffs)
    evidence = json.loads((tmp_path / 'review/source-evidence.json').read_bytes())
    assert {e['book_id'] for e in evidence} == {'ethics-g2-lower', 'ethics-g7-lower'}
    for row in evidence:
        if row['book_id'] == 'ethics-g2-lower':
            assert row['text_layer'] is False
            assert row['source_review_method'] == 'local_page_image_view_no_OCR'
            assert row['figure_review'] == 'local_page_image_view_no_OCR'
        else:
            assert row['text_layer'] is True
            assert row['source_review_method'] == 'local_original_PDF_native_text_no_OCR'
            assert row['figure_review'] == 'unverified'
    assert summary['figure_verified_items'].keys() == review.FIGURE_VERIFIED.keys()


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
    assert chapter.install(db, BATCH)['added'] == 7
    assert chapter.install(db, BATCH)['added'] == 0
    with db.session() as c:
        for table, old in before.items():
            assert old <= set(map(tuple, c.execute('SELECT * FROM "' + table + '"')))
        assert c.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1152
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
