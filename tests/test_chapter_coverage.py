"""B01 counting and refusal contracts; public metadata and synthetic evidence only."""
from copy import deepcopy
from datetime import date
import json
import subprocess
import sys

import pytest

from scripts import prepare_chapter_coverage as coverage
from learning_service.textbooks import learning_scope, page_evidence


@pytest.fixture
def inputs():
    spec = json.loads(coverage.SPEC.read_bytes())
    reference = json.loads((coverage.ROOT / coverage.SOURCE_PATHS['concepts']).read_bytes())
    questions = json.loads((coverage.ROOT / coverage.SOURCE_PATHS['questions']).read_bytes())['questions']
    book, _ = learning_scope(**coverage.SCOPE)
    passages = []
    for row in spec['rows']:
        for link in row['passage_links']:
            e = page_evidence(book, link['printed_page'] + 7)
            e.update(evidence_id=link['evidence_id'], review_revision=1,
                     review_sha256='a' * 64, reviewed_on='2026-11-07', valid_until='2026-12-07',
                     teacher_reviewed=False, fully_reviewed_page=False)
            passages.append({'id': link['id'], 'evidence': e,
                             'text': 'SYNTHETIC quote must not appear in output',
                             'context': 'SYNTHETIC context must not appear in output'})
    return spec, reference, questions, passages


def build(inputs, day=date(2026, 11, 8)):
    return coverage.build_report(*inputs, checked_on=day)


def test_counts_reconcile_distinct_questions_and_overlapping_concepts(inputs):
    r = build(inputs)
    assert r['summary']['rows'] == 19
    assert r['summary']['rows_by_role'] == {'core': 13, 'foundation': 3, 'local_check': 1, 'supplementary': 2}
    assert r['summary']['chapter_questions'] == r['summary']['mapped_questions'] == 12
    assert r['summary']['questions_by_level'] == {'easy': 4, 'normal': 4, 'hard': 4}
    assert r['summary']['existing_mapped_questions'] == 4
    assert r['summary']['new_candidate_mapped_questions'] == 8
    assert r['summary']['question_row_memberships'] == 42
    assert r['summary']['effective_passages'] == 5
    assert r['summary']['unmapped_question_ids'] == []
    assert all(row['review_card_count'] is None and row['delayed_observation'] is None for row in r['rows'])
    assert r['actual_review_records_read'] is False


def test_gaps_and_prior_foundations_do_not_gain_invented_sources(inputs):
    rows = {r['id']: r for r in build(inputs)['rows']}
    assert rows['g7-sign']['textbook_locations'][0]['chapter_id'] == '1'
    assert all(p['scope_relation'] == 'prior_foundation' for p in rows['g7-sign']['textbook_locations'])
    assert rows['g7-opposite']['questions'] == []
    assert rows['g7-target']['textbook_locations'] == []
    for key in ('g7-ch2-divide', 'g7-ch2-power', 'g7-ch2-scientific', 'g7-ch2-approximate'):
        assert rows[key]['concept_id'] is None
        assert rows[key]['effective_passages'] == []
        assert rows[key]['local_explanation'] is None
        assert rows[key]['questions'] == []
        assert '无本地讲解映射' in rows[key]['gaps']
    assert rows['g7-ch2-multiply-laws']['effective_passages'] == []
    assert len(rows['g7-ch2-distributive']['effective_passages']) == 1
    assert rows['g7-ch2-base-conversion']['review_resources'] == []


def test_unmapped_question_is_preserved_in_denominator(inputs):
    inputs[0]['question_mappings'].pop()
    r = build(inputs)
    assert r['summary']['chapter_questions'] == 12
    assert r['summary']['mapped_questions'] == 11
    assert r['summary']['unmapped_question_ids'] == ['family-word-g7-return-trip-v1']


@pytest.mark.parametrize('mutation, error', [
    ('question_hash', 'question scope/version'),
    ('question_chapter', 'question scope/version'),
    ('mapping_row', 'unsupported question mapping'),
    ('existing_mapping', 'existing mapping changed'),
    ('duplicate_row', 'duplicate coverage row'),
    ('duplicate_question', 'duplicate question mapping'),
    ('chapter', 'invalid coverage scope'),
    ('page', 'textbook location changed'),
    ('explanation', 'unbound explanation'),
    ('teacher', 'invalid question mapping review'),
    ('evidence', 'passage scope/review changed'),
    ('expiry', 'passage scope/review changed'),
    ('source_pointer', 'question source pointer changed'),
])
def test_changed_or_unbound_inputs_are_rejected(inputs, mutation, error):
    spec, ref, qs, passages = inputs
    first = spec['question_mappings'][0]
    if mutation == 'question_hash': first['question_sha256'] = '0' * 64
    elif mutation == 'question_chapter': next(q for q in qs if q['id'] == first['question_version_id'])['chapter_id'] = '5'
    elif mutation == 'mapping_row': first['row_ids'].append('guessed-concept')
    elif mutation == 'existing_mapping': first['row_ids'] = ['g7-add']
    elif mutation == 'duplicate_row': spec['rows'].append(deepcopy(spec['rows'][0]))
    elif mutation == 'duplicate_question': spec['question_mappings'].append(deepcopy(first))
    elif mutation == 'chapter': spec['scope']['chapter_id'] = ''
    elif mutation == 'page': spec['rows'][0]['textbook_locations'][0]['pdf_page'] += 1
    elif mutation == 'explanation': spec['rows'][6]['local_explanation_ref'] = 'guessed'
    elif mutation == 'teacher': first['teacher_reviewed'] = True
    elif mutation == 'evidence': passages[0]['evidence']['evidence_id'] = 'guessed'
    elif mutation == 'expiry': passages[0]['evidence']['valid_until'] = '2026-11-07'
    elif mutation == 'source_pointer': spec['question_mappings'][1]['source_ref'] = 'questions#/questions/999'
    with pytest.raises(ValueError, match=error): build(inputs)


def test_unavailable_passages_remain_empty_without_replacement(inputs):
    inputs[3].clear()  # Validator filters disabled/expired entries before the join.
    r = build(inputs, day=date(2026, 12, 8))
    assert r['summary']['effective_passages'] == 0
    assert all(row['effective_passages'] == [] for row in r['rows'])
    assert all('无当前有效片段映射' in row['gaps'] for row in r['rows'])


def test_html_escapes_content_and_does_not_disclose_material_text(inputs):
    r = build(inputs)
    r['rows'][0]['title'] = '<script>unsafe</script>'
    output = coverage.render_html(r)
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in output
    assert '<script>' not in output
    assert 'SYNTHETIC quote' not in output and 'SYNTHETIC context' not in output
    assert output.count('data-row-id=') == 19
    assert '留空' in output and '实际复习卡与延迟观察未读取、未验收' in output
    assert 'default-src' in output and '上述核对日期有效' in output


@pytest.mark.parametrize('kind', ['existing', 'symlink'])
def test_output_never_overwrites_old_evidence(tmp_path, kind):
    target = tmp_path / 'old'
    target.mkdir()
    marker = target / 'old.json'
    marker.write_text('historical evidence')
    destination = target
    if kind == 'symlink':
        destination = tmp_path / 'linked'
        destination.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='new independent directory'):
        coverage.prepare(destination, bundle=tmp_path / 'absent', textbook_dir=tmp_path / 'absent')
    assert marker.read_text() == 'historical evidence'


def test_source_drift_creates_no_packet(tmp_path, inputs):
    spec = inputs[0]
    spec['sources']['concepts']['sha256'] = '0' * 64
    spec_path = tmp_path / 'spec.json'
    spec_path.write_text(json.dumps(spec))
    output = tmp_path / 'packet'
    with pytest.raises(ValueError, match='source version changed'):
        coverage.prepare(output, bundle=tmp_path / 'absent', textbook_dir=tmp_path / 'absent', spec_path=spec_path)
    assert not output.exists()


def test_import_has_no_database_or_directory_side_effects(tmp_path):
    completed = subprocess.run([sys.executable, '-c',
        'import sys; sys.path.insert(0, sys.argv[1]); import scripts.prepare_chapter_coverage', str(coverage.ROOT)],
        cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert list(tmp_path.iterdir()) == []
