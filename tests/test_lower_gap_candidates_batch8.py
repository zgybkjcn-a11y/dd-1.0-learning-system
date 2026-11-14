"""Offline checks for the eighth lower batch: three history scopes, four items."""
from collections import Counter
from fractions import Fraction
import hashlib
import json

import pytest

from learning_service import chapter_practice as chapter, practice
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields
from scripts import review_lower_gap_candidates_batch8 as review
from scripts.build_lower_gap_candidates_batch8 import BATCH, DESTINATION, build
from scripts.build_lower_gap_candidates import DESTINATION as BATCH1_DESTINATION
from scripts.build_lower_gap_candidates_batch2 import DESTINATION as BATCH2_DESTINATION
from scripts.build_lower_gap_candidates_batch3 import DESTINATION as BATCH3_DESTINATION
from scripts.build_lower_gap_candidates_batch4 import DESTINATION as BATCH4_DESTINATION
from scripts.build_lower_gap_candidates_batch5 import DESTINATION as BATCH5_DESTINATION
from scripts.build_lower_gap_candidates_batch6 import DESTINATION as BATCH6_DESTINATION
from scripts.build_lower_gap_candidates_batch7 import DESTINATION as BATCH7_DESTINATION
from test_family_math import family


@pytest.fixture
def candidates():
    return chapter._parse(DESTINATION.read_bytes())[2]


def by_point(qs, point):
    return next(q for q in qs.values() if q['knowledge']['point_id'] == point)


def values(q):
    return [f['options'][int(f['answer']) - 1] if f['kind'] == 'choice'
            else Fraction(f['answer']) for f in q['responses']]


def test_four_scopes_are_unregistered_and_reproducible(candidates):
    qs, points, before, after = review.proposal()
    assert json.loads(DESTINATION.read_bytes()) == build()
    assert len(qs) == len(points) == 4
    assert set(points) == {q['knowledge']['point_id'] for q in qs.values()}
    assert Counter(q['knowledge']['role'] for q in qs.values()) == {'direct': 4}
    assert Counter(q['book_id'] for q in qs.values()) == {'history-g7-lower': 4}
    assert not (set(candidates) & set(chapter.bank())) and BATCH not in chapter.BATCHES
    earlier = [chapter._parse(p.read_bytes())[2]
               for p in (BATCH1_DESTINATION, BATCH2_DESTINATION, BATCH3_DESTINATION,
                         BATCH4_DESTINATION, BATCH5_DESTINATION, BATCH6_DESTINATION,
                         BATCH7_DESTINATION)]
    assert [len(qs) for qs in earlier] == [7, 9, 9, 9, 9, 7, 7]
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


def test_song_and_ming_answers_match_the_pages(candidates):
    song = values(by_point(candidates, 'history-g7-lower:2:inventory-1'))
    assert song[0] == 960
    assert song[1] == '979 年'
    assert song[2] == '通判'
    assert '战斗力减弱' in song[3] and '文臣' in song[3]

    ming = values(by_point(candidates, 'history-g7-lower:3:inventory-1'))
    assert ming[0] == 1368
    assert ming[1] == '1421 年'
    assert '废除丞相' in ming[2] and '六部' in ming[2]
    assert ming[3] == '科举考试的文体规定'


def test_source_and_festival_answers_match_the_pages(candidates):
    sources = values(by_point(candidates, 'history-g7-lower:4:inventory-1'))
    assert sources[0] == '《旧唐书·魏征传》'
    assert sources[1] == '虚心接受别人的意见'
    assert sources[2] == '1127 年，北宋都城东京'
    assert sources[3] == '魏征已经去世'
    q = by_point(candidates, 'history-g7-lower:4:inventory-1')
    assert '今魏征殂逝' in q['responses'][3]['label']

    festival = values(by_point(candidates, 'history-g7-lower:4:inventory-2'))
    assert '延续与传承' in festival[0]
    assert festival[1] == '各具特色的民族节日'
    assert '习俗还会发展变化' in festival[2]
    assert festival[3] == '中华文明的连续性'
    qf = by_point(candidates, 'history-g7-lower:4:inventory-2')
    assert '一幅' in qf['responses'][2]['label']


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
    assert summary['installed_evidence'] == {'configured': 112, 'partial': 288, 'gap': 262}
    assert summary['candidate_inclusive'] == {'configured': 112, 'partial': 292, 'gap': 258}
    assert summary['new_configured_requirements'] == 0
    assert not summary['local_bank_registered'] and BATCH not in chapter.BATCHES
    diffs = json.loads((tmp_path / 'review/coverage-diff.json').read_bytes())
    assert len(diffs) == 4
    assert sum(d['candidate_inclusive_after']['family_count'] for d in diffs) == 4
    assert all(d['installed_before']['status'] == 'gap' for d in diffs)
    evidence = json.loads((tmp_path / 'review/source-evidence.json').read_bytes())
    assert {e['book_id'] for e in evidence} == {'history-g7-lower'}
    assert all(e['text_layer'] is True for e in evidence)
    assert all(e['source_review_method'] == 'local_original_PDF_native_text_no_OCR'
               for e in evidence)
    assert all(e['figure_review'] == 'unverified' for e in evidence)
    assert summary['figure_verified_items'] == {}


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
    assert chapter.install(db, BATCH)['added'] == 4
    assert chapter.install(db, BATCH)['added'] == 0
    with db.session() as c:
        for table, old in before.items():
            assert old <= set(map(tuple, c.execute('SELECT * FROM "' + table + '"')))
        assert c.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1149
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
