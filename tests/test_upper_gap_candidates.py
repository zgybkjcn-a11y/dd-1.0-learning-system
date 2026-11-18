"""Offline candidate checks: complete actions, grade boundaries and additive rehearsal."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import hashlib
import json

import pytest

from learning_service import chapter_practice as chapter, practice
from learning_service.app import run_worker_once
from learning_service.practice_response import grade_short_fields
from scripts import review_upper_gap_candidates as review
from scripts.build_upper_gap_candidates import build, DESTINATION, BATCH
from test_family_math import family


@pytest.fixture
def candidates():
    return chapter._parse(DESTINATION.read_bytes())[2]


def by_point(qs, point):
    return next(q for q in qs.values() if q['knowledge']['point_id'] == point)


def values(q):
    return [f['options'][int(f['answer']) - 1] if f['kind'] == 'choice'
            else Fraction(f['answer']) for f in q['responses']]


def test_exact_twenty_gaps_are_registered_and_reproducible(candidates):
    qs, gaps, before, after = review.proposal()
    assert json.loads(DESTINATION.read_bytes()) == build()
    assert len(qs) == len(gaps) == 20
    assert Counter(q['knowledge']['role'] for q in qs.values()) == {'direct': 16, 'supporting': 4}
    assert set(candidates) <= set(chapter.bank()) and BATCH in chapter.BATCHES
    assert len(chapter.bank()) == 1155
    for old, new in zip(before['rows'], after['rows'], strict=True):
        assert {k: v for k, v in old.items() if k != 'mappings'} == {k: v for k, v in new.items() if k != 'mappings'}
        assert new['mappings'][:len(old['mappings'])] == old['mappings']
        assert len(new['mappings']) - len(old['mappings']) == int(old['id'] in gaps)


def test_quantities_and_full_composite_requirements_independently(candidates):
    v = lambda p: values(by_point(candidates, p))
    day, year, hemi, season = v('geography-g7-upper:5:temperature')
    monthly = [-2, 0, 6, 14, 20, 24, 26, 25, 20, 12, 5, 0]
    assert day == 24 - 14 and year == max(monthly) - min(monthly) == 28
    assert monthly.index(max(monthly)) + 1 == 7 and hemi == '北半球' and season == '夏季'
    spring, summer, difference, unit = v('geography-g7-upper:5:rain')
    assert spring == sum([30, 40, 50]) and summer == sum([80, 120, 100])
    assert difference == summer - spring and unit == '毫米'
    density, ga, gb, comparison = v('geography-g7-upper:6:population')
    assert density == 20 * 10000 / 1000 < 12 * 10000 / 300
    assert ga == Fraction(14 - 6, 10) and gb == Fraction(20 - 16, 10)
    assert comparison == '甲总量大；乙密度大'
    burden_a, burden_b, _, _ = v('ethics-g7-upper:2:group')
    assert burden_a == 4 and burden_b == 1 and burden_a == burden_b * 4
    assert v('biology-g7-upper:1:observation')[2] == sum([3, 4, 3])
    # Facts, not merely copying stored option indexes.
    assert v('history-g7-upper:3:unification') == ['政治', '经济', '文化']
    events = {'官渡之战': 200, '赤壁之战': 208, '魏': 220, '蜀汉': 221, '吴': 229}
    assert events['赤壁之战'] < min(events[x] for x in ('魏', '蜀汉', '吴'))
    assert v('history-g7-upper:4:three') == ['官渡之战', '战争', '魏220—蜀汉221—吴229', '赤壁之战早于三国建国']
    assert v('geography-g7-upper:2:space')[:3] == ['恒星', '行星', '天然卫星']
    assert v('biology-g7-upper:2:celllife') == ['细胞膜', '细胞核', '叶绿体', '线粒体']
    assert v('biology-g7-upper:3:single')[:3] == ['运动', '摄食和消化', '气体交换']
    assert v('biology-g7-upper:6:fungi')[0] == '酵母菌有，乳酸菌没有'


def test_maps_and_tables_have_complete_readable_data(candidates):
    q = by_point(candidates, 'history-g7-upper:5:map')
    rows = q['visual']['rows']
    before, after = rows[1:3], rows[3:5]
    changes = [(y, x) for y in range(2) for x in (1, 2) if before[y][x] != after[y][x]]
    assert changes == [(0, 2)]
    assert before[0][2] == '○' and after[0][2] == '●'
    assert before[1][2] == after[1][2] == '？'
    assert values(q)[1:] == ['东北地区', '由乙政权变为甲政权', '两期均无资料，不能判断归属变化']
    assert '虚构' in q['prompt'] and '不表示面积大小' in q['prompt']
    t = by_point(candidates, 'geography-g7-upper:5:temperature')['visual']['rows']
    assert [int(x) for x in t[0][1:] + t[2][1:]] == list(range(1, 13))
    assert [int(x) for x in t[1][1:] + t[3][1:]] == [-2, 0, 6, 14, 20, 24, 26, 25, 20, 12, 5, 0]
    assert Fraction(1, 5000) > Fraction(1, 1000000)
    assert values(by_point(candidates, 'geography-g7-upper:3:selection'))[::3] == ['甲', '乙']


def test_each_field_wrong_missing_extra_and_feedback_boundaries(candidates):
    for q in candidates.values():
        key = json.loads(chapter.stored(q)['answer_key_json'])
        right = json.loads(q['answer'])
        assert grade_short_fields(q['answer'], key)[0] == 'correct'
        for field in q['responses']:
            wrongs = ([str(i + 1) for i in range(len(field['options'])) if str(i + 1) != field['answer']]
                      if field['kind'] == 'choice' else [str(Fraction(field['answer']) + 1)])
            for wrong in wrongs:
                raw = {**right, field['id']: wrong}
                assert grade_short_fields(json.dumps(raw), key)[0] == 'incorrect', (q['id'], raw)
            missing = {k: v for k, v in right.items() if k != field['id']}
            assert grade_short_fields(json.dumps(missing), key)[0] == 'incorrect'
            for invalid in (True, '', '1 or 2'):
                assert grade_short_fields(json.dumps({**right, field['id']: invalid}), key)[0] == 'incorrect'
            for e in field.get('errors', []):
                outcome, feedback = grade_short_fields(json.dumps({**right, field['id']: e['answer']}), key)
                assert outcome == 'incorrect' and e['message'] in feedback and e['action'] in feedback
            if field['kind'] == 'number':
                # Whitespace, full width digits and equivalent numeric forms remain accepted.
                raw = {**right, field['id']: f" {float(Fraction(field['answer']))} "}
                assert grade_short_fields(json.dumps(raw), key)[0] == 'correct'
        assert grade_short_fields(json.dumps({**right, 'extra': '1'}), key)[0] == 'incorrect'
        duplicate = '{"a":"1",' + q['answer'][1:]
        assert grade_short_fields(duplicate, key)[0] == 'incorrect'


def test_open_performance_is_not_automatically_completed(candidates):
    supporting = {q['knowledge']['point_id'] for q in candidates.values() if q['knowledge']['role'] == 'supporting'}
    assert supporting == {'ethics-g2-upper:4:participate', 'ethics-g7-upper:2:family',
                          'ethics-g7-upper:2:teacher', 'biology-g7-upper:1:observation'}
    for q in candidates.values():
        assert q['review']['teacher_reviewed'] is False
        assert q['review']['curriculum_standard_crosscheck'] == 'assistant_crosscheck_passed_2026-11-18_against_local_plan_or_inventory'
        assert len(q['review']['field_coverage']) == len(q['responses'])
        if q['knowledge']['role'] == 'supporting':
            assert q['manual_followup']['automatically_graded'] is False
            assert q['manual_followup']['completion'] == 'not_observed'
            assert q['manual_followup']['learner_record_created'] is False


def test_installed_and_candidate_evidence_remain_separate(candidates, tmp_path):
    summary = review.export(tmp_path / 'review')
    assert summary['formal_coverage_unchanged'] == {'configured': 112, 'partial': 288, 'gap': 258}
    assert summary['candidate_inclusive'] == {'configured': 112, 'partial': 293, 'gap': 253}
    assert summary['new_configured_requirements'] == 0
    assert summary['local_bank_registered'] and BATCH in chapter.BATCHES
    diffs = json.loads((tmp_path / 'review/coverage-diff.json').read_bytes())
    assert len(diffs) == 20 and sum(d['candidate_inclusive_after']['family_count'] for d in diffs) == 16
    assert all(d['formal_after']['family_count'] == 0 for d in diffs)


def test_synthetic_install_preserves_all_existing_rows_and_is_idempotent(family, candidates, monkeypatch):
    _, db, api, headers = family
    practice.install(db)
    for batch in chapter.BATCHES:
        if batch not in ('math_g7_action_candidates', 'math_g7_chapter4_action_candidates'):
            chapter.install(db, batch)
    with db.session() as c:
        assert c.execute('SELECT COUNT(*) FROM question_versions').fetchone()[0] == 1226
        before = {r[0]: set(map(tuple, c.execute('SELECT * FROM "' + r[0] + '"')))
                  for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
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
                           json={'question_version_id': q['id'], 'textbook_book_id': q['book_id'], 'textbook_chapter_id': q['chapter_id']})
        assert response.status_code == 201, response.text
        data = response.json()
        assert data['answer_key'] is None and 'field_answers' not in response.text
        assert 'common_error_feedback' not in response.text and 'content_check' not in response.text
        item = data['items'][0]
        foreign = {**headers, 'X-Learner-Id': 'family-g7' if q['grade'] == 2 else 'family-g2'}
        assert api.get('/api/v1/test-sessions/' + data['session_id'], headers=foreign).status_code in (403, 404)
        token = api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges", headers=h).json()
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
            # Mutable projections change under synthetic answering; originals stay intact.
            if table in ('questions', 'question_versions'):
                assert old <= set(map(tuple, c.execute('SELECT * FROM "' + table + '"')))


def test_readable_catalogue_does_not_expand_the_formal_practice_catalogue():
    from learning_service.textbooks import BOOKS
    from learning_service import subject_coverage
    from practice_catalogue import PRACTICE_BOOKS, PRACTICE_BOOK_IDS, READING_ONLY_BOOK_IDS
    assert len(BOOKS) == 20 and sum(len(b['chapters']) for b in BOOKS) == 152
    assert len(PRACTICE_BOOKS) == 13 and sum(len(b['chapters']) for b in PRACTICE_BOOKS) == 98
    assert not (PRACTICE_BOOK_IDS & READING_ONLY_BOOK_IDS)
    assert {b['id'] for b in BOOKS} == PRACTICE_BOOK_IDS | READING_ONLY_BOOK_IDS
    assert sum(len(b['chapters']) for b in BOOKS if b['id'] in READING_ONLY_BOOK_IDS) == 54
    # The 2026-11-18 authored candidates add the seven new lower books to the
    # chapter question bank, but not to the formal practice catalogue, and the
    # coverage plan still has no rows for them.
    assert {q['book_id'] for q in chapter.bank().values()} == PRACTICE_BOOK_IDS | READING_ONLY_BOOK_IDS
    plan = json.loads(subject_coverage.PATH.read_bytes())
    assert not ({r['book_id'] for r in plan['rows']} & READING_ONLY_BOOK_IDS)
