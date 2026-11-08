#!/usr/bin/env python3
"""Score pinned local excerpt evaluations; never call a model or overwrite a run.

Run as ``python -m scripts.evaluate_textbook_retrieval --help``. Real cases and
outputs belong in an ignored local directory. The scoring core accepts an adapter
for future candidates; the CLI deliberately runs only the pinned offline baseline.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import unicodedata


SCHEMA = 'dd-retrieval-evaluation-v1'
DISTRIBUTION = {'answerable': 20, 'unsupported': 10, 'scope': 10}
THRESHOLDS = {'recall_hits_min': 18, 'unsupported_empty_min': 9,
              'scope_leaks_max': 0, 'source_accuracy': 1.0, 'quote_accuracy': 1.0}
SOURCE_FIELDS = ('evidence_id', 'source_ref', 'pdf_sha256', 'book_id',
                 'chapter_id', 'printed_page', 'pdf_page', 'review_sha256', 'review_revision')
IMPLEMENTATIONS = ('scripts/textbook_passage_sample.py', 'learning_service/textbooks.py')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_pinned(path: Path, expected: str):
    if not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise ValueError('invalid hash pin')
    raw = path.read_bytes()
    if path.is_symlink() or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('pinned input changed')
    return json.loads(raw)


def normalized(query):
    return ''.join(unicodedata.normalize('NFKC', query).casefold().split())


def validate_cases(cases, gold, *, namespace, historical=False):
    if not isinstance(cases, list) or not cases:
        raise ValueError('missing cases')
    ids, groups = set(), set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError('invalid case')
        key, group = case.get('id'), case.get('expression_group')
        if (not isinstance(key, str) or not key or key in ids
                or not isinstance(group, str) or not group.startswith(namespace + '/')
                or group in groups):
            raise ValueError('duplicate or invalid case/group')
        ids.add(key); groups.add(group)
        scope = case.get('scope')
        if (not isinstance(scope, dict) or set(scope) != {'curriculum_id', 'book_id', 'chapter_id'}
                or any(not isinstance(v, str) for v in scope.values())
                or not scope['curriculum_id'] or not scope['book_id']):
            raise ValueError('invalid case scope')
        query = case.get('query')
        if (not isinstance(query, str) or not query.strip() or len(query) > 120
                or any(ord(c) < 32 for c in query) or not case.get('reason')):
            raise ValueError('invalid query/reason')
        for field in ('expected_ids', 'required_ids'):
            values = case.get(field)
            if (not isinstance(values, list) or any(not isinstance(v, str) or v not in gold for v in values)
                    or len(values) != len(set(values))):
                raise ValueError('invalid expected evidence')
        expected, required = set(case['expected_ids']), set(case['required_ids'])
        if not required <= expected:
            raise ValueError('required evidence must be expected')
        kind, outcome = case.get('kind'), case.get('expected_outcome')
        if kind == 'answerable':
            if not expected or not required or outcome != 'returned':
                raise ValueError('answerable case needs evidence')
            for key in expected:
                evidence = gold[key]['evidence']
                if (evidence['book_id'] != scope['book_id']
                        or scope['chapter_id'] and evidence['chapter_id'] != scope['chapter_id']):
                    raise ValueError('expected evidence outside scope')
        elif kind in ('unsupported', 'scope'):
            if expected or required or outcome not in (('empty',) if kind == 'unsupported' else ('empty', 'scope_rejected')):
                raise ValueError('invalid negative expectation')
        else:
            raise ValueError('invalid case kind')
        review = case.get('review', {})
        if (review.get('reviewer_type') not in ('assistant', 'human', 'teacher')
                or review.get('status') != ('historical' if historical else 'checked')
                or not review.get('method') or type(review.get('teacher_reviewed')) is not bool):
            raise ValueError('missing case review')


def validate_suite(suite):
    if (suite.get('schema') != SCHEMA or suite.get('top_k') != 4
            or type(suite.get('top_k')) is not int or not suite.get('version')
            or suite.get('distribution') != DISTRIBUTION or suite.get('thresholds') != THRESHOLDS):
        raise ValueError('invalid pilot specification')
    if datetime.fromisoformat(suite['frozen_at']).tzinfo is None:
        raise ValueError('freeze timestamp needs timezone')
    gold = suite.get('gold')
    if not isinstance(gold, dict) or not gold:
        raise ValueError('missing gold')
    evidence_ids = set()
    for key, entry in gold.items():
        evidence = entry.get('evidence', {})
        if (not key or not isinstance(entry.get('text'), str) or not entry['text']
                or set(evidence) != set(SOURCE_FIELDS)):
            raise ValueError('invalid gold evidence')
        for field, value in evidence.items():
            if field in ('printed_page', 'pdf_page', 'review_revision'):
                valid = type(value) is int and value > 0
            else:
                valid = isinstance(value, str) and bool(value)
            if not valid:
                raise ValueError('invalid gold field')
        if evidence['evidence_id'] in evidence_ids:
            raise ValueError('duplicate gold identity')
        evidence_ids.add(evidence['evidence_id'])
        if date.fromisoformat(entry['reviewed_on']) > date.fromisoformat(entry['valid_until']):
            raise ValueError('invalid gold dates')
    validate_cases(suite['cases'], gold, namespace='pilot')
    if dict(Counter(c['kind'] for c in suite['cases'])) != DISTRIBUTION:
        raise ValueError('pilot distribution changed')
    if not suite.get('review') or not suite.get('independence'):
        raise ValueError('missing review/exposure declaration')


def load_inputs(directory: Path, freeze_sha256: str, root: Path):
    freeze = read_pinned(directory / 'freeze.json', freeze_sha256)
    suite = read_pinned(directory / 'pilot-v1.json', freeze['suite_sha256'])
    validate_suite(suite)
    if (suite['frozen_at'] != freeze['frozen_at']
            or suite['material_manifest_sha256'] != freeze['material_manifest_sha256']):
        raise ValueError('freeze metadata mismatch')
    if set(freeze['implementation']) != set(IMPLEMENTATIONS):
        raise ValueError('invalid implementation pins')
    for name, pin in freeze['implementation'].items():
        if sha256(root / name) != pin:
            raise ValueError('baseline implementation changed')
    partitions = {'pilot': suite['cases']}
    for name in ('development', 'regression'):
        part = read_pinned(directory / (name + '-v1.json'), freeze[name + '_sha256'])
        if part.get('schema') != 'dd-evaluation-partition-v1' or not part.get('version'):
            raise ValueError('invalid partition')
        validate_cases(part['cases'], suite['gold'], namespace=name, historical=name == 'development')
        if len(part['cases']) != (20 if name == 'development' else 4):
            raise ValueError('partition size changed')
        partitions[name] = part['cases']
    read_pinned(directory / 'development-original.json', freeze['original_development_sha256'])
    old_queries = {normalized(c['query']) for name in ('development', 'regression') for c in partitions[name]}
    if any(normalized(c['query']) in old_queries for c in partitions['pilot']):
        raise ValueError('pilot expression overlaps historical queries')
    return freeze, suite, partitions


def ratio(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'rate': numerator / denominator if denominator else None}


def source_matches(item, gold, today):
    if not isinstance(item, dict) or not isinstance(item.get('id'), str):
        return False
    entry = gold.get(item['id'])
    evidence = item.get('evidence')
    return bool(entry and isinstance(evidence, dict)
                and date.fromisoformat(entry['reviewed_on']) <= today <= date.fromisoformat(entry['valid_until'])
                and all(type(evidence.get(k)) is type(v) and evidence.get(k) == v
                        for k, v in entry['evidence'].items()))


def score_case(case, observation, gold, today, top_k=4):
    """Untrusted results cannot change denominators, gold or the allowed scope."""
    issues = []
    if not isinstance(observation, dict):
        observation = {}
    status = observation.get('status')
    if status not in ('ok', 'scope_rejected', 'error'):
        issues.append('invalid_status')
    if status == 'error':
        issues.append('adapter_error')
    result = observation.get('retrieval', {})
    if not isinstance(result, dict):
        result = {}
    items = result.get('items')
    if not isinstance(items, list):
        issues.append('invalid_items'); items = []
    answer = observation.get('answer', {})
    claims = answer.get('claims') if isinstance(answer, dict) else None
    if (not isinstance(answer, dict) or set(answer) != {'claims', 'generated_answer'}
            or answer.get('generated_answer') is not None or not isinstance(claims, list)):
        issues.append('invalid_answer')
    if not isinstance(claims, list):
        claims = []
    if len(items) > top_k:
        issues.append('excess_results')
    if status == 'scope_rejected' and (items or claims):
        issues.append('rejection_with_output')
    scope = case['scope']
    if status == 'ok':
        reported_scope = result.get('scope', {})
        if (not isinstance(reported_scope, dict)
                or any(reported_scope.get(k) != scope[k] for k in ('book_id', 'chapter_id'))):
            issues.append('scope_mismatch')
    valid_ids, retrieved, seen_ids, seen_evidence = set(), {}, set(), set()
    source_correct = 0
    outside_scope = False
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get('evidence'), dict):
            issues.append('malformed_item'); continue
        key, evidence = item.get('id'), item['evidence']
        eid = evidence.get('evidence_id')
        if not isinstance(key, str) or not isinstance(eid, str):
            issues.append('malformed_identity'); continue
        duplicate = key in seen_ids or eid in seen_evidence
        if duplicate:
            issues.append('duplicate_item')
        seen_ids.add(key); seen_evidence.add(eid)
        valid_source = source_matches(item, gold, today)
        source_correct += int(valid_source)
        in_scope = (evidence.get('book_id') == scope['book_id']
                    and (not scope['chapter_id'] or evidence.get('chapter_id') == scope['chapter_id']))
        outside_scope |= not in_scope
        valid_text = valid_source and item.get('text') == gold[key]['text']
        if not valid_source:
            issues.append('invalid_source')
        if not valid_text:
            issues.append('invalid_item_text')
        if valid_text and in_scope and not duplicate and index < top_k and status == 'ok':
            valid_ids.add(key)
            retrieved[eid] = item
    quote_correct, quoted = 0, set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {'kind', 'text', 'evidence_id'}:
            issues.append('malformed_claim'); continue
        eid = claim['evidence_id']
        if not isinstance(eid, str):
            issues.append('invalid_claim_identity'); continue
        item = retrieved.get(eid)
        if (item and eid not in quoted and claim['kind'] == 'direct_quote'
                and claim['text'] == item['text'] == gold[item['id']]['text']):
            quote_correct += 1
        else:
            issues.append('invalid_quote')
        quoted.add(eid)
    if len(claims) != len(items) or quoted != seen_evidence:
        issues.append('quote_coverage_mismatch')
    expected, required = set(case['expected_ids']), set(case['required_ids'])
    # A retrieval hit is independent of answer formatting; overall acceptance also
    # requires quote integrity. Extra irrelevant passages never increase recall.
    hits = valid_ids & expected
    rejected = status == 'scope_rejected' and not items and not claims
    empty = status == 'ok' and not items and not claims and not issues
    outcome_ok = (bool(hits) if case['expected_outcome'] == 'returned' else
                  rejected if case['expected_outcome'] == 'scope_rejected' else empty)
    return {'id': case['id'], 'kind': case['kind'], 'status': status,
            'recall_hit': bool(hits), 'required_found': sorted(valid_ids & required),
            'required_total': len(required), 'all_required': bool(required) and required <= valid_ids,
            'unsupported_empty': case['kind'] == 'unsupported' and empty,
            'scope_handled': case['kind'] == 'scope' and outcome_ok and not issues,
            'scope_leak': outside_scope or case['kind'] == 'scope' and bool(items or claims),
            'source_correct': source_correct, 'returned_count': len(items),
            'quote_correct': quote_correct, 'claim_count': len(claims),
            'quote_slots': max(len(items), len(claims)),
            'relevant_count': len(hits), 'issues': sorted(set(issues)),
            'passed': outcome_ok and not issues and not outside_scope
                      and (case['kind'] != 'answerable' or valid_ids == expected and required <= valid_ids)}


def evaluate(cases, gold, adapter, *, today):
    rows, observations = [], []
    for case in cases:
        try:
            observation = adapter(deepcopy(case))
        except Exception:
            # No exception messages: they may contain queries, paths or credentials.
            observation = {'status': 'error', 'error_code': 'adapter_exception',
                           'retrieval': {'items': []}, 'answer': {'claims': [], 'generated_answer': None}}
        rows.append(score_case(case, observation, gold, today))
        observations.append({'id': case['id'], 'output': observation})
    answerable = [r for r in rows if r['kind'] == 'answerable']
    unsupported = [r for r in rows if r['kind'] == 'unsupported']
    scope = [r for r in rows if r['kind'] == 'scope']
    multi = [r for r in answerable if r['required_total'] > 1]
    metrics = {
        'recall_at_4': ratio(sum(r['recall_hit'] for r in answerable), len(answerable)),
        'all_required_cases': ratio(sum(r['all_required'] for r in answerable), len(answerable)),
        'required_associations': ratio(sum(len(r['required_found']) for r in answerable), sum(r['required_total'] for r in answerable)),
        'multi_required_cases': ratio(sum(r['all_required'] for r in multi), len(multi)),
        'multi_required_associations': ratio(sum(len(r['required_found']) for r in multi), sum(r['required_total'] for r in multi)),
        'unsupported_rejection': ratio(sum(r['unsupported_empty'] for r in unsupported), len(unsupported)),
        'scope_leaks': ratio(sum(r['scope_leak'] for r in scope), len(scope)),
        'scope_handled': ratio(sum(r['scope_handled'] for r in scope), len(scope)),
        'source_accuracy': ratio(sum(r['source_correct'] for r in rows), sum(r['returned_count'] for r in rows)),
        'exact_quotes': ratio(sum(r['quote_correct'] for r in rows), sum(r['claim_count'] for r in rows)),
        'quote_completeness': ratio(sum(r['quote_correct'] for r in rows), sum(r['quote_slots'] for r in rows)),
        'relevance_precision': ratio(sum(r['relevant_count'] for r in rows), sum(r['returned_count'] for r in rows)),
        'exact_cases': ratio(sum(r['passed'] for r in rows), len(rows)),
        'error_cases': sum(r['status'] == 'error' for r in rows),
        'integrity_issue_cases': sum(bool(r['issues']) for r in rows),
        'any_scope_leak_cases': sum(r['scope_leak'] for r in rows),
        'per_evidence': {key: ratio(sum(key in r['required_found'] for r in answerable),
                                    sum(key in c['required_ids'] for c in cases)) for key in sorted(gold)},
    }
    return {'case_count': len(rows), 'metrics': metrics, 'cases': rows, 'observations': observations}


def pilot_criteria(metrics):
    return {
        'recall': metrics['recall_at_4']['denominator'] == 20 and metrics['recall_at_4']['numerator'] >= 18,
        'unsupported_rejection': metrics['unsupported_rejection']['denominator'] == 10 and metrics['unsupported_rejection']['numerator'] >= 9,
        'scope': metrics['scope_handled']['numerator'] == metrics['scope_handled']['denominator'] == 10
                 and metrics['any_scope_leak_cases'] == 0,
        'source_accuracy': metrics['source_accuracy']['rate'] == 1.0,
        'exact_quotes': metrics['exact_quotes']['rate'] == metrics['quote_completeness']['rate'] == 1.0,
        'no_errors': metrics['error_cases'] == metrics['integrity_issue_cases'] == 0,
    }


def baseline_adapter(passages):
    from scripts import textbook_passage_sample as sample

    def call(case):
        try:
            sample.learning_scope(**case['scope'])
        except ValueError as exc:
            if str(exc) not in ('book outside current grade', 'chapter unavailable'):
                raise
            return {'status': 'scope_rejected', 'error_code': 'scope_denied',
                    'retrieval': {'items': []}, 'answer': {'claims': [], 'generated_answer': None}}
        result = sample.retrieve(passages, **case['scope'], query=case['query'])
        return {'status': 'ok', 'retrieval': result, 'answer': sample.quote_answer(result)}
    return call


def write_run(destination: Path, report):
    # Exclusive directory creation is intentional, including for empty directories.
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / 'results.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    (destination / 'results.sha256').write_text(sha256(destination / 'results.json') + '\n')


def run_baseline(directory: Path, freeze_pin: str, bundle: Path, textbooks: Path, destination: Path):
    from scripts import textbook_passage_sample as sample

    if destination.exists():
        raise FileExistsError('run destination already exists')
    root = Path(__file__).resolve().parents[1]
    freeze, suite, partitions = load_inputs(directory, freeze_pin, root)
    now = datetime.now().astimezone()
    today = now.date()  # No historical --as-of escape hatch.
    if datetime.fromisoformat(suite['frozen_at']) > now:
        raise ValueError('freeze timestamp is in the future')
    passages = sample.load_bundle(bundle, freeze['material_manifest_sha256'], textbooks, as_of=today)
    if ({p['id'] for p in passages} != set(suite['gold'])
            or any(not source_matches(p, suite['gold'], today) or p['text'] != suite['gold'][p['id']]['text'] for p in passages)):
        raise ValueError('frozen gold unavailable or changed; renew review with a new evaluation version')
    results = {name: evaluate(cases, suite['gold'], baseline_adapter(passages), today=today)
               for name, cases in partitions.items()}
    criteria = pilot_criteria(results['pilot']['metrics'])
    report = {'schema': 'dd-retrieval-results-v1', 'evaluated_at': now.isoformat(), 'as_of': today.isoformat(),
              'suite_version': suite['version'], 'freeze_sha256': freeze_pin,
              'inputs': freeze, 'runner_sha256': sha256(Path(__file__)), 'usable_excerpts': len(passages),
              'review': suite['review'], 'independence': suite['independence'],
              'model_calls': 0, 'criteria': criteria, 'quality_targets_passed': all(criteria.values()),
              'partitions': results}
    write_run(destination, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation-dir', type=Path, required=True)
    parser.add_argument('--freeze-sha256', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--textbook-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_baseline(args.evaluation_dir, args.freeze_sha256, args.bundle, args.textbook_dir, args.output)
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({'completed': False, 'error_code': 'invalid_or_unavailable_inputs'}))
        return 1
    print(json.dumps({'completed': True, 'quality_targets_passed': report['quality_targets_passed'],
                      'criteria': report['criteria'], 'metrics': report['partitions']['pilot']['metrics']}, ensure_ascii=False))
    return 0 if report['quality_targets_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
