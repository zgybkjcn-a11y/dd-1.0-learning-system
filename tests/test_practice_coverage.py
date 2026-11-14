"""Coverage counts must reflect available, version-matched, distinct task families."""
from copy import deepcopy
import hashlib
import json
import pytest

from learning_service import practice_coverage as coverage
from learning_service.chapter_practice import bank as new_bank
from learning_service.practice import bank
from learning_service.reserve_practice import bank as reserve_bank


def test_coverage_requires_explicit_mapping_and_deduplicates_variants():
    ids = set(bank()) | {qid for qid, q in new_bank().items() if q['batch'] != 'math_g7_depth'} | set(reserve_bank())
    result = coverage.report('math-g7-v1', ids)
    assert len(result['items']) == 34 and result['inventory_complete'] is False
    row = next(r for r in result['items'] if r['id'] == 'math-g7-upper:3:value')
    application = next(t for t in row['tasks'] if t['id'] == 'apply')
    assert application['question_count'] == 8 and application['family_count'] == 2
    assert application['status'] == 'configured'
    assert next(t for t in row['tasks'] if t['id'] == 'understand')['status'] == 'gap'
    transfer = next(t for t in row['tasks'] if t['id'] == 'transfer')
    assert transfer['question_count'] == 4 and transfer['family_count'] == 1 and transfer['status'] == 'partial'
    assert all(r['book_id'] == 'math-g7-upper' for r in result['items'])
    empty = coverage.report('math-g2-v1', set())
    assert len(empty['items']) == 19 and all(t['question_count'] == 0 for r in empty['items'] for t in r['tasks'])


def test_unknown_or_changed_plan_is_not_counted(tmp_path, monkeypatch):
    original = json.loads(coverage.PATH.read_bytes())
    data = deepcopy(original)
    data['rows'][0]['mappings'][0]['question_sha256'] = '0'*64
    raw = json.dumps(data).encode()
    path = tmp_path/'plan.json'; path.write_bytes(raw)
    monkeypatch.setattr(coverage, 'PATH', path)
    monkeypatch.setattr(coverage, 'SHA256', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match='mapping changed'):
        coverage.report('math-g2-v1', set(new_bank()))
    path.write_bytes(raw + b' ')
    with pytest.raises(ValueError, match='plan changed'):
        coverage.report('math-g2-v1', set(new_bank()))


def test_recognition_does_not_complete_expression_and_variants_do_not_inflate():
    questions = new_bank()
    ids = set(questions) | set(bank())
    rows = {r['id']: r for r in coverage.report('math-g2-v1', ids)['items']}
    assert len(rows) == 19 and all(any(t['question_count'] for t in r['tasks']) for r in rows.values())
    understand = next(t for t in rows['math-g2-upper:2:meaning']['tasks'] if t['id'] == 'understand')
    assert understand['question_count'] == understand['supporting_question_count'] == 3
    assert understand['family_count'] == 0 and understand['status'] == 'partial'
    calculation = next(t for t in rows['math-g2-upper:2:tables']['tasks'] if t['id'] == 'apply')
    assert calculation['question_count'] == 5 and calculation['family_count'] == 2
    assert calculation['supporting_question_count'] == 2
    assert calculation['status'] == 'configured'
    practical = next(t for t in rows['math-g2-upper:4:ruler']['tasks'] if t['id'] == 'transfer')
    assert practical['status'] == 'gap'  # Drawing and physically verifying a line is not tested by choices.
    legacy_ids = {qid for qid in ids if questions.get(qid, {}).get('batch') not in ('math_g2_depth', 'math_g2_challenge', 'math_g2_multistep')}
    legacy = coverage.report('math-g2-v1', legacy_ids)
    assert sum(t['status'] == 'configured' for r in legacy['items'] for t in r['tasks']) == 12
    body = next(r for r in legacy['items'] if r['id'] == 'math-g2-upper:activity2:body')
    body_calculation = next(t for t in body['tasks'] if t['id'] == 'apply')
    assert body_calculation['status'] == 'partial'
    assert body_calculation['family_count'] == 0
    assert body_calculation['supporting_question_count'] == 8


@pytest.mark.parametrize('tamper', ['role', 'duplicate'])
def test_invalid_assessment_roles_and_duplicate_mappings_rejected(tmp_path, monkeypatch, tamper):
    data = json.loads(coverage.PATH.read_bytes())
    mappings = data['rows'][0]['mappings']
    if tamper == 'role':
        mappings[-1]['role'] = 'assume_complete'
    else:
        mappings.append(deepcopy(mappings[-1]))
    raw = json.dumps(data).encode()
    path = tmp_path/'plan.json'; path.write_bytes(raw)
    monkeypatch.setattr(coverage, 'PATH', path)
    monkeypatch.setattr(coverage, 'SHA256', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match='mapping changed'):
        coverage.report('math-g2-v1', set(new_bank()))
