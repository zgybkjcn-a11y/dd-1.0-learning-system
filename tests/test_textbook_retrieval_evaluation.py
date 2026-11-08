"""Evaluation integrity tests using original synthetic text, never local教材."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys

import pytest

from scripts import evaluate_textbook_retrieval as ev


TODAY = date(2026, 11, 7)


@pytest.fixture
def gold():
    return {key: {'text': f'SYNTHETIC excerpt {key}: a token for evaluation only.',
                 'evidence': {'evidence_id': f'evidence-{key}', 'source_ref': 'synthetic-source',
                              'pdf_sha256': 'a' * 64, 'book_id': 'math-g7-upper', 'chapter_id': '2',
                              'printed_page': index, 'pdf_page': index + 7,
                              'review_sha256': 'b' * 64, 'review_revision': 1},
                 'reviewed_on': '2020-01-01', 'valid_until': '2099-01-01'}
            for index, key in enumerate(('one', 'two'), 1)}


def case(key='a', kind='answerable', expected=('one',), chapter='2', namespace='pilot'):
    return {'id': key, 'kind': kind, 'expression_group': f'{namespace}/{key}',
            'scope': {'curriculum_id': 'math-g7-v1', 'book_id': 'math-g7-upper', 'chapter_id': chapter},
            'query': f'SYNTHETIC query {namespace} {key}',
            'expected_ids': list(expected), 'required_ids': list(expected),
            'expected_outcome': 'returned' if kind == 'answerable' else 'empty',
            'reason': 'Original synthetic evaluation fixture.',
            'review': {'reviewer_type': 'assistant', 'method': 'synthetic_contract',
                       'status': 'historical' if namespace == 'development' else 'checked', 'teacher_reviewed': False}}


def output(c, gold, keys=()):
    items = [{'id': key, 'text': gold[key]['text'], 'evidence': deepcopy(gold[key]['evidence'])} for key in keys]
    return {'status': 'ok', 'retrieval': {'scope': deepcopy(c['scope']), 'items': items},
            'answer': {'claims': [{'kind': 'direct_quote', 'text': p['text'],
                                   'evidence_id': p['evidence']['evidence_id']} for p in items], 'generated_answer': None}}


def pilot(gold):
    cases = [case(f'a{i}') for i in range(20)]
    cases += [case(f'u{i}', 'unsupported', ()) for i in range(10)]
    cases += [case(f's{i}', 'scope', (), '5') for i in range(10)]
    return {'schema': ev.SCHEMA, 'version': 'synthetic-v1', 'frozen_at': '2026-01-01T00:00:00+08:00',
            'top_k': 4, 'distribution': deepcopy(ev.DISTRIBUTION), 'thresholds': deepcopy(ev.THRESHOLDS),
            'material_manifest_sha256': 'c' * 64, 'gold': gold, 'cases': cases,
            'review': {'reviewer_type': 'assistant'}, 'independence': {'blind_or_external_holdout': False}}


def test_perfect_synthetic_pilot_has_explicit_denominators(gold):
    suite = pilot(gold); ev.validate_suite(suite)
    result = ev.evaluate(suite['cases'], gold, lambda c: output(c, gold, c['expected_ids']), today=TODAY)
    metrics = result['metrics']
    assert all(ev.pilot_criteria(metrics).values())
    assert metrics['recall_at_4'] == ev.ratio(20, 20)
    assert metrics['unsupported_rejection'] == ev.ratio(10, 10)
    assert metrics['scope_leaks'] == ev.ratio(0, 10)
    assert metrics['source_accuracy'] == metrics['exact_quotes'] == ev.ratio(20, 20)
    assert metrics['multi_required_cases']['rate'] is None


def test_empty_outputs_never_pass_source_or_quote_accuracy(gold):
    result = ev.evaluate(pilot(gold)['cases'], gold, lambda c: output(c, gold), today=TODAY)
    assert result['metrics']['recall_at_4'] == ev.ratio(0, 20)
    criteria = ev.pilot_criteria(result['metrics'])
    assert not criteria['recall'] and not criteria['source_accuracy'] and not criteria['exact_quotes']
    assert criteria['unsupported_rejection'] and criteria['scope']


def test_exceptions_preserve_denominators_and_do_not_count_as_rejection(gold):
    def broken(c):
        raise TimeoutError('private query, credential and traceback must not escape')
    result = ev.evaluate(pilot(gold)['cases'], gold, broken, today=TODAY)
    assert result['metrics']['error_cases'] == 40
    assert result['metrics']['unsupported_rejection'] == ev.ratio(0, 10)
    assert result['metrics']['scope_handled'] == ev.ratio(0, 10)
    assert not ev.pilot_criteria(result['metrics'])['scope']
    assert 'private query' not in json.dumps(result)


def test_partial_multi_evidence_and_irrelevant_hits_are_separate(gold):
    cases = [case('multi', expected=('one', 'two')), case('wrong'), case('unsupported', 'unsupported', ())]
    result = ev.evaluate(cases, gold, lambda c: output(c, gold, ('one',) if c['id'] == 'multi' else ('two',)), today=TODAY)
    m = result['metrics']
    assert m['recall_at_4'] == ev.ratio(1, 2)
    assert m['multi_required_cases'] == ev.ratio(0, 1)
    assert m['multi_required_associations'] == ev.ratio(1, 2)
    assert m['required_associations'] == ev.ratio(1, 3)
    assert m['per_evidence']['one'] == ev.ratio(1, 2)
    assert m['per_evidence']['two'] == ev.ratio(0, 1)
    assert m['source_accuracy'] == ev.ratio(3, 3)
    assert m['relevance_precision'] == ev.ratio(1, 3)
    assert m['unsupported_rejection'] == ev.ratio(0, 1)


@pytest.mark.parametrize('field,value', [
    ('evidence_id', 'forged'), ('source_ref', 'other'), ('pdf_sha256', '0' * 64),
    ('book_id', 'math-g7-lower'), ('chapter_id', '5'), ('printed_page', 9),
    ('printed_page', True), ('pdf_page', 1), ('review_sha256', '0' * 64), ('review_revision', 2)])
def test_each_source_binding_is_checked_against_gold(gold, field, value):
    c = case(); result = output(c, gold, ('one',))
    result['retrieval']['items'][0]['evidence'][field] = value
    row = ev.score_case(c, result, gold, TODAY)
    assert row['source_correct'] == row['quote_correct'] == 0
    assert not row['recall_hit'] and not row['passed']


@pytest.mark.parametrize('mutation', ['item_text', 'claim_text', 'claim_id', 'missing_claim', 'duplicate_claim', 'free_answer'])
def test_fabricated_or_incomplete_answers_fail_even_if_retrieval_is_valid(gold, mutation):
    c = case(); result = output(c, gold, ('one',))
    answer = result['answer']
    if mutation == 'item_text':
        result['retrieval']['items'][0]['text'] = 'tampered'
        answer['claims'][0]['text'] = 'tampered'  # A self-consistent forgery still fails.
    elif mutation == 'claim_text': answer['claims'][0]['text'] += ' extra'
    elif mutation == 'claim_id': answer['claims'][0]['evidence_id'] = 'evidence-two'
    elif mutation == 'missing_claim': answer['claims'] = []
    elif mutation == 'duplicate_claim': answer['claims'] *= 2
    else: answer['generated_answer'] = 'invented answer'
    row = ev.score_case(c, result, gold, TODAY)
    assert not row['passed'] and row['issues']
    assert row['quote_slots'] >= 1
    if mutation == 'missing_claim': assert row['quote_correct'] == 0


def test_scope_leak_cannot_pass_by_reporting_requested_scope(gold):
    c = case('scope', 'scope', (), '5')
    row = ev.score_case(c, output(c, gold, ('one',)), gold, TODAY)
    assert row['source_correct'] == 1 and row['scope_leak']
    assert not row['scope_handled'] and not row['passed']


def test_only_expected_authorization_failure_is_successful_scope_handling(gold):
    c = case('scope', 'scope', ()); c['expected_outcome'] = 'scope_rejected'
    rejected = output(c, gold); rejected['status'] = 'scope_rejected'
    assert ev.score_case(c, rejected, gold, TODAY)['scope_handled']
    assert not ev.score_case(c, output(c, gold), gold, TODAY)['scope_handled']
    rejected['retrieval']['items'] = output(c, gold, ('one',))['retrieval']['items']
    assert not ev.score_case(c, rejected, gold, TODAY)['passed']


def test_duplicates_and_top_k_overflow_cannot_inflate_recall(gold):
    c = case(expected=('two',))
    result = output(c, gold, ('one', 'one', 'one', 'one', 'two'))
    row = ev.score_case(c, result, gold, TODAY)
    assert not row['recall_hit'] and not row['passed']
    assert {'duplicate_item', 'excess_results'} <= set(row['issues'])
    assert row['returned_count'] == 5


@pytest.mark.parametrize('result', [None, {}, {'status': 'ok'}, {'status': 'ok', 'retrieval': []},
                                  {'status': 'ok', 'retrieval': {'items': [None, {'id': []}]}, 'answer': {}}])
def test_malformed_outputs_are_counted_without_crashing(gold, result):
    row = ev.score_case(case(), result, gold, TODAY)
    assert row['issues'] and not row['passed']


def test_expired_gold_is_not_valid_evidence(gold):
    c = case(); result = output(c, gold, ('one',))
    gold['one']['valid_until'] = '2026-11-06'
    row = ev.score_case(c, result, gold, TODAY)
    assert not row['recall_hit'] and row['source_correct'] == 0


@pytest.mark.parametrize('change', ['counts', 'threshold', 'group', 'review', 'expected', 'scope', 'duplicates'])
def test_invalid_frozen_specifications_fail(gold, change):
    suite = pilot(gold)
    if change == 'counts': suite['cases'].pop()
    elif change == 'threshold': suite['thresholds']['recall_hits_min'] = 1
    elif change == 'group': suite['cases'][0]['expression_group'] = 'development/reused'
    elif change == 'review': suite['cases'][0]['review']['status'] = 'pending'
    elif change == 'expected': suite['cases'][0]['expected_ids'] = ['forged']
    elif change == 'scope': suite['cases'][0]['scope']['chapter_id'] = '5'
    else: suite['cases'][1] = deepcopy(suite['cases'][0])
    with pytest.raises(ValueError): ev.validate_suite(suite)


def frozen_inputs(tmp_path, gold):
    directory = tmp_path / 'evaluation'; directory.mkdir()
    root = Path(ev.__file__).resolve().parents[1]
    def save(name, data):
        path = directory / name; path.write_text(json.dumps(data))
        return ev.sha256(path)
    suite = pilot(gold)
    freeze = {'suite_sha256': save('pilot-v1.json', suite), 'frozen_at': suite['frozen_at'],
              'material_manifest_sha256': suite['material_manifest_sha256'],
              'implementation': {name: ev.sha256(root / name) for name in ev.IMPLEMENTATIONS}}
    for name, size in [('development', 20), ('regression', 4)]:
        freeze[name + '_sha256'] = save(name + '-v1.json', {'schema': 'dd-evaluation-partition-v1',
            'version': name + '-v1', 'cases': [case(str(i), namespace=name) for i in range(size)]})
    freeze['original_development_sha256'] = save('development-original.json', [])
    pin = save('freeze.json', freeze)
    return directory, pin, root


def test_mutated_suite_and_envelope_rejected(tmp_path, gold):
    directory, pin, root = frozen_inputs(tmp_path, gold)
    ev.load_inputs(directory, pin, root)
    path = directory / 'pilot-v1.json'
    path.write_text(path.read_text() + '\n')
    with pytest.raises(ValueError, match='pinned input changed'): ev.load_inputs(directory, pin, root)
    freeze = directory / 'freeze.json'; freeze.write_text(freeze.read_text() + '\n')
    with pytest.raises(ValueError, match='pinned input changed'): ev.load_inputs(directory, pin, root)


def test_baseline_run_current_date_is_enforced_and_results_repeat(tmp_path, gold, monkeypatch):
    from scripts import textbook_passage_sample as sample
    directory, pin, _ = frozen_inputs(tmp_path, gold)
    passages = output(case(), gold, ('one', 'two'))['retrieval']['items']
    dates = []
    def load(*args, as_of):
        dates.append(as_of); return passages
    monkeypatch.setattr(sample, 'load_bundle', load)
    monkeypatch.setattr(ev, 'baseline_adapter', lambda p: lambda c: output(c, gold, c['expected_ids']))
    first = ev.run_baseline(directory, pin, tmp_path, tmp_path, tmp_path / 'run1')
    second = ev.run_baseline(directory, pin, tmp_path, tmp_path, tmp_path / 'run2')
    assert first['partitions'] == second['partitions'] and first['quality_targets_passed']
    assert dates == [date.today(), date.today()]
    path = tmp_path / 'run1/results.json'; original = path.read_bytes()
    with pytest.raises(FileExistsError): ev.run_baseline(directory, pin, tmp_path, tmp_path, tmp_path / 'run1')
    assert path.read_bytes() == original
    assert (tmp_path / 'run1/results.sha256').read_text().strip() == ev.sha256(path)


def test_baseline_refuses_missing_current_material(tmp_path, gold, monkeypatch):
    from scripts import textbook_passage_sample as sample
    directory, pin, _ = frozen_inputs(tmp_path, gold)
    monkeypatch.setattr(sample, 'load_bundle', lambda *a, **kw: [])
    with pytest.raises(ValueError, match='unavailable or changed'):
        ev.run_baseline(directory, pin, tmp_path, tmp_path, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


def test_adapter_classifies_only_catalogue_denials(gold, monkeypatch):
    from scripts import textbook_passage_sample as sample
    c = case(); c['scope']['book_id'] = 'not-authorized'
    assert ev.baseline_adapter([])(c)['status'] == 'scope_rejected'
    def fail(*args, **kwargs): raise ValueError('book outside current grade')
    monkeypatch.setattr(sample, 'retrieve', fail)
    # An identically worded downstream error must not become authorization success.
    result = ev.evaluate([case()], gold, ev.baseline_adapter([]), today=TODAY)
    assert result['metrics']['error_cases'] == 1


def test_write_run_refuses_even_an_empty_existing_directory(tmp_path):
    with pytest.raises(FileExistsError): ev.write_run(tmp_path, {})


@pytest.mark.parametrize('outcome,exit_code', [('passed', 0), ('below_target', 2), ('invalid', 1)])
def test_cli_distinguishes_quality_failure_from_invalid_run(monkeypatch, capsys, outcome, exit_code):
    monkeypatch.setattr(sys, 'argv', ['evaluate', '--evaluation-dir', '/synthetic', '--freeze-sha256', 'a' * 64,
        '--bundle', '/synthetic', '--textbook-dir', '/synthetic', '--output', '/synthetic/output'])
    def run(*args):
        if outcome == 'invalid': raise ValueError('private input detail')
        return {'quality_targets_passed': outcome == 'passed', 'criteria': {}, 'partitions': {'pilot': {'metrics': {}}}}
    monkeypatch.setattr(ev, 'run_baseline', run)
    assert ev.main() == exit_code
    result = json.loads(capsys.readouterr().out)
    assert result['completed'] is (outcome != 'invalid')
    assert 'private input detail' not in str(result)
