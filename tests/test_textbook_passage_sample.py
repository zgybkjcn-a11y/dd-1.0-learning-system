"""Synthetic excerpt bindings, availability and quote-only grounding; no models."""
from copy import deepcopy
from datetime import date
import json

import pytest

from learning_service.textbooks import catalogue, page_evidence, PDF_SHA256
from scripts import textbook_passage_sample as sample

TODAY = date(2026, 11, 7)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    directory = tmp_path / 'bundle'; directory.mkdir()
    (directory / 'source').mkdir()
    pdfs = tmp_path / 'pdfs'; pdfs.mkdir()
    pdf_bytes = b'synthetic PDF bytes; not a publisher document'
    (pdfs / 'math-g7-upper.pdf').write_bytes(pdf_bytes)
    monkeypatch.setitem(PDF_SHA256, 'math-g7-upper', sample.digest(pdf_bytes))
    book = next(b for b in catalogue('math-g7-v1') if b['id'] == 'math-g7-upper')
    page = page_evidence(book, 38)
    image = b'\x89PNG\r\n\x1a\nsynthetic reviewed image'
    (directory / 'source/page.png').write_bytes(image)
    text, context = '合成测试片段：零与任何整数相加不改变该整数。', '本地测试文字，不来自教材。'
    binding = {k: page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')}
    binding.update(text_sha256=sample.text_digest(text), context_sha256=sample.text_digest(context), image_sha256=sample.digest(image))
    checks = json.dumps({'checks': {'synthetic-zero': {'passed': True, 'case_count': 3, 'method': 'exact_rational_checks'}}}).encode()
    (directory / 'semantic-checks.json').write_bytes(checks)
    verifier = b'# synthetic verifier evidence; never executed by the loader\n'
    (directory / 'verify_semantics.py').write_bytes(verifier)
    entry = {'id': 'synthetic-zero', 'curriculum_id': 'math-g7-v1', 'book_id': book['id'],
        **{k: page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')},
        'text': text, 'context': context, 'text_policy': 'layout_normalized_transcription',
        'image_path': 'source/page.png', 'retrieval_terms': ['零加整数'], 'enabled': True, 'binding': binding,
        'review': {'revision': 1, 'scope': 'selected_excerpt', 'binding': deepcopy(binding),
            'teacher_reviewed': False, 'reviewed_on': '2026-11-07', 'valid_until': '2026-12-07', 'unresolved_issues': [],
            'transcription': {'status': 'checked', 'reviewer_type': 'assistant', 'method': 'visual_original_comparison',
                              'layout_checked': True, 'notes': 'synthetic comparison'},
            'semantic': {'status': 'checked', 'reviewer_type': 'assistant',
                'method': 'independent_mathematical_reasoning_and_exact_checks', 'conditions_complete': True,
                'derivation': 'synthetic additive identity review', 'diagram_dependency': 'none_for_selected_excerpt',
                'checks_sha256': sample.digest(checks), 'verifier_sha256': sample.digest(verifier)}}}
    manifest = {'format': sample.FORMAT, 'passages': [entry]}
    return directory, pdfs, manifest


def seal(bundle):
    directory, _, manifest = bundle
    raw = json.dumps(manifest, ensure_ascii=False).encode()
    (directory / 'passages.json').write_bytes(raw)
    return sample.digest(raw)


def load(bundle, as_of=TODAY):
    return sample.load_bundle(bundle[0], seal(bundle), bundle[1], as_of=as_of)


def search(passages, query='零加整数怎么计算？', **kwargs):
    return sample.retrieve(passages, 'math-g7-v1', kwargs.get('book_id', 'math-g7-upper'), kwargs.get('chapter_id', '2'), query)


def test_quotes_bind_to_current_retrieval_and_review_version(bundle):
    first = load(bundle)
    scoped = search(first); whole = search(first, chapter_id='')
    assert scoped['items'] == whole['items']
    evidence = scoped['items'][0]['evidence']
    assert evidence['kind'] == 'assistant_reviewed_excerpt'
    assert evidence['printed_page'] == 31 and evidence['pdf_page'] == 38
    assert evidence['teacher_reviewed'] is evidence['fully_reviewed_page'] is False
    assert evidence['supports_textbook_answer'] is evidence['eligible_as_grading_basis'] is False
    assert scoped['grounding']['can_quote_textbook'] is True
    assert scoped['grounding']['can_answer_from_textbook'] is False
    answer = sample.quote_answer(scoped)
    assert sample.verify_quote_answer(scoped, answer)
    bundle[2]['passages'][0]['review']['revision'] = 2
    revised = search(load(bundle))
    assert revised['items'][0]['evidence']['evidence_id'] != evidence['evidence_id']
    assert not sample.verify_quote_answer(revised, answer)


@pytest.mark.parametrize('field,value', [
    ('text', 'changed words'), ('context', 'removed conditions'), ('printed_page', 32),
    ('pdf_page', 39), ('source_ref', 'forged'), ('chapter_id', '5'), ('pdf_sha256', '0'*64)])
def test_changed_excerpt_cannot_reuse_review_even_with_new_manifest_pin(bundle, field, value):
    bundle[2]['passages'][0][field] = value
    with pytest.raises(ValueError): load(bundle)


def test_text_and_binding_changed_without_new_review_rejected(bundle):
    entry = bundle[2]['passages'][0]
    entry['text'] = 'new text'
    entry['binding']['text_sha256'] = sample.text_digest(entry['text'])
    with pytest.raises(ValueError, match='review binding'): load(bundle)


def test_manifest_requires_out_of_band_pin(bundle):
    pin = seal(bundle)
    bundle[2]['passages'][0]['text'] = 'edited'
    seal(bundle)
    with pytest.raises(ValueError, match='manifest changed'):
        sample.load_bundle(bundle[0], pin, bundle[1], as_of=TODAY)


@pytest.mark.parametrize('target', ['pdf', 'image', 'checks', 'verifier'])
def test_changed_original_or_semantic_artifact_invalidates_bundle(bundle, target):
    path = {'pdf': bundle[1]/'math-g7-upper.pdf', 'image': bundle[0]/'source/page.png',
            'checks': bundle[0]/'semantic-checks.json', 'verifier': bundle[0]/'verify_semantics.py'}[target]
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError): load(bundle)


@pytest.mark.parametrize('state', ['disabled', 'pending_transcription', 'pending_semantic', 'unresolved', 'expired', 'future'])
def test_unavailable_review_does_not_become_retrieval_evidence(bundle, state):
    entry = bundle[2]['passages'][0]; when = TODAY
    if state == 'disabled': entry['enabled'] = False
    if state == 'pending_transcription': entry['review']['transcription']['status'] = 'pending'
    if state == 'pending_semantic': entry['review']['semantic']['status'] = 'pending'
    if state == 'unresolved': entry['review']['unresolved_issues'] = ['missing condition']
    if state == 'expired': when = date(2026,12,8)
    if state == 'future': when = date(2026,11,6)
    result = search(load(bundle, when))
    assert result['items'] == [] and result['grounding']['status'] == 'no_evidence'
    assert not result['grounding']['can_quote_textbook']
    assert sample.quote_answer(result)['claims'] == []


@pytest.mark.parametrize('mutation', ['teacher', 'whole_page', 'no_visual', 'no_derivation', 'no_conditions'])
def test_missing_review_steps_cannot_grant_quote_eligibility(bundle, mutation):
    review = bundle[2]['passages'][0]['review']
    if mutation == 'teacher': review['teacher_reviewed'] = True
    if mutation == 'whole_page': review['scope'] = 'whole_page'
    if mutation == 'no_visual': review['transcription']['method'] = 'extracted_text_only'
    if mutation == 'no_derivation': review['semantic']['derivation'] = ''
    if mutation == 'no_conditions': review['semantic']['conditions_complete'] = False
    with pytest.raises(ValueError): load(bundle)


def test_wrong_chapter_book_grade_or_query_does_not_leak_excerpt(bundle):
    passages = load(bundle)
    assert search(passages, chapter_id='5')['items'] == []
    assert search(passages, book_id='math-g7-lower', chapter_id='7')['items'] == []
    assert search(passages, '光合作用')['items'] == []
    with pytest.raises(ValueError): sample.retrieve(passages, 'math-g2-v1', 'math-g7-upper', '2', '零加整数')
    for query in ('', 'a'*121, 'zero\n', ['零加整数']):
        with pytest.raises(ValueError): search(passages, query)


def test_free_claims_fake_ids_inexact_quotes_and_duplicates_rejected(bundle):
    result = search(load(bundle)); answer = sample.quote_answer(result)
    bad = deepcopy(answer); bad['claims'][0]['text'] += '所以所有问题都已回答。'
    assert not sample.verify_quote_answer(result, bad)
    bad = deepcopy(answer); bad['claims'][0]['evidence_id'] = 'display-index-1'
    assert not sample.verify_quote_answer(result, bad)
    bad = deepcopy(answer); bad['claims'].append(deepcopy(bad['claims'][0]))
    assert not sample.verify_quote_answer(result, bad)
    bad = deepcopy(answer); bad['generated_answer'] = 'model memory answer'
    assert not sample.verify_quote_answer(result, bad)
    bad = deepcopy(answer); bad['extra_conclusion'] = 'unsupported assertion'
    assert not sample.verify_quote_answer(result, bad)
    assert not sample.verify_quote_answer(search(load(bundle), '未命中'), answer)


def test_local_report_links_quote_to_exact_source_and_escapes_query(bundle, tmp_path):
    result = search(load(bundle))
    report = tmp_path/'preview.html'
    sample.render_report([{'query': '<script>alert(1)</script>', 'retrieval': result,
                           'answer': sample.quote_answer(result)}], report)
    text = report.read_text()
    evidence_id = result['items'][0]['evidence']['evidence_id']
    assert f'href="#case-1-{evidence_id}"' in text
    assert 'href="source/page.png"' in text and '[教材 p.31]' in text and 'PDF 第 38 页' in text
    assert '<script>' not in text and '&lt;script&gt;' in text
    assert 'http://' not in text and 'https://' not in text


def test_duplicate_ids_and_image_path_escape_are_rejected(bundle):
    original = deepcopy(bundle[2])
    bundle[2]['passages'].append(deepcopy(bundle[2]['passages'][0]))
    with pytest.raises(ValueError): load(bundle)
    bundle[2].update(original)
    bundle[2]['passages'][0]['image_path'] = '../private.png'
    with pytest.raises(ValueError): load(bundle)
