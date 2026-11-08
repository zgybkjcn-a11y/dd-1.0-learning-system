"""Pinned excerpt validation and literal quotes. No providers or database side effects."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re

from .textbooks import learning_scope, page_evidence, PDF_SHA256

FORMAT = 'dd-textbook-excerpt-pilot-v1'
SHA = re.compile(r'[a-f0-9]{64}')


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def text_digest(text: str) -> str:
    return digest(text.encode())


def asset(directory: Path, relative: str) -> bytes:
    if not isinstance(relative, str) or not re.fullmatch(r'source/[A-Za-z0-9_-]+\.png', relative):
        raise ValueError('invalid source image path')
    path = directory / relative
    if directory.is_symlink() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError('source image symlink')
    raw = path.read_bytes()
    if len(raw) > 8_000_000 or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('invalid source image')
    return raw


def load_bundle(directory: Path, expected_sha256: str, textbook_dir: Path, *, as_of: date) -> list[dict]:
    """The caller pins an independently reviewed manifest, never an adjacent checksum.

    Inactive, pending, expired or unresolved entries are unavailable. Broken
    source/review bindings fail the entire candidate closed.
    """
    directory, textbook_dir = Path(directory), Path(textbook_dir)
    if any(p.is_symlink() for root in (directory, textbook_dir) for p in (root, *root.parents)):
        raise ValueError('material directory symlink')
    path = directory / 'passages.json'
    if directory.is_symlink() or path.is_symlink() or not SHA.fullmatch(expected_sha256):
        raise ValueError('invalid manifest pin')
    raw = path.read_bytes()
    if len(raw) > 1_000_000 or digest(raw) != expected_sha256:
        raise ValueError('manifest changed')
    manifest = json.loads(raw)
    if manifest.get('format') != FORMAT or not isinstance(manifest.get('passages'), list) or len(manifest['passages']) > 40:
        raise ValueError('invalid excerpt manifest')
    result, seen, checked_books = [], set(), set()
    for entry in manifest['passages']:
        if entry['id'] in seen or not re.fullmatch(r'[a-z0-9-]{1,80}', entry['id']):
            raise ValueError('duplicate or invalid excerpt id')
        seen.add(entry['id'])
        book, chapter = learning_scope(entry['curriculum_id'], entry['book_id'], entry['chapter_id'])
        if not chapter['id']:
            raise ValueError('excerpt requires actual chapter')
        page = page_evidence(book, entry['pdf_page'])
        for key in ('source_ref', 'pdf_sha256', 'printed_page', 'chapter_id'):
            if type(entry[key]) is not type(page[key]) or entry[key] != page[key]:
                raise ValueError('source location mismatch')
        if book['id'] not in checked_books:
            pdf = textbook_dir / (book['id'] + '.pdf')
            if textbook_dir.is_symlink() or pdf.is_symlink() or digest(pdf.read_bytes()) != PDF_SHA256[book['id']]:
                raise ValueError('source PDF changed')
            checked_books.add(book['id'])
        if (not isinstance(entry['text'], str) or not 1 <= len(entry['text']) <= 1400
                or not isinstance(entry['context'], str) or not 1 <= len(entry['context']) <= 4000
                or entry['text_policy'] != 'layout_normalized_transcription'):
            raise ValueError('invalid excerpt text')
        binding = {key: entry[key] for key in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')}
        binding.update(text_sha256=text_digest(entry['text']), context_sha256=text_digest(entry['context']),
                       image_sha256=digest(asset(directory, entry['image_path'])))
        if entry['binding'] != binding:
            raise ValueError('excerpt content changed')
        review = entry['review']
        if review['binding'] != binding or type(review['revision']) is not int or review['revision'] < 1:
            raise ValueError('review binding changed')
        if review.get('teacher_reviewed') is not False or review.get('scope') != 'selected_excerpt':
            raise ValueError('invalid review scope')
        if type(entry['enabled']) is not bool or not isinstance(review['unresolved_issues'], list):
            raise ValueError('invalid availability record')
        reviewed_on, valid_until = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
        if valid_until < reviewed_on:
            raise ValueError('invalid review dates')
        if (not entry['enabled'] or not reviewed_on <= as_of <= valid_until or review['unresolved_issues']):
            continue
        transcription, semantic = review['transcription'], review['semantic']
        if any(r.get('status') != 'checked' for r in (transcription, semantic)):
            continue
        if (transcription.get('reviewer_type') != 'assistant' or semantic.get('reviewer_type') != 'assistant'
                or transcription.get('method') != 'visual_original_comparison'
                or transcription.get('layout_checked') is not True or not transcription.get('notes')
                or semantic.get('method') != 'independent_mathematical_reasoning_and_exact_checks'
                or semantic.get('conditions_complete') is not True or not semantic.get('derivation')
                or semantic.get('diagram_dependency') != 'none_for_selected_excerpt'):
            raise ValueError('incomplete review')
        check_path = directory / 'semantic-checks.json'
        if check_path.is_symlink():
            raise ValueError('invalid semantic evidence')
        check_raw = check_path.read_bytes()
        if digest(check_raw) != semantic['checks_sha256']:
            raise ValueError('semantic check evidence changed')
        checks = json.loads(check_raw).get('checks', {})
        check = checks.get(entry['id'], {})
        if (check.get('passed') is not True or type(check.get('case_count')) is not int
                or check['case_count'] < 1 or check.get('method') != 'exact_rational_checks'):
            raise ValueError('semantic checks missing or failed')
        # Pin the exact script used to produce the review evidence as well.
        verifier = directory / 'verify_semantics.py'
        if verifier.is_symlink() or digest(verifier.read_bytes()) != semantic['verifier_sha256']:
            raise ValueError('semantic verifier changed')
        terms = entry['retrieval_terms']
        if not isinstance(terms, list) or not terms or any(type(t) is not str or not 2 <= len(t) <= 30 for t in terms):
            raise ValueError('invalid retrieval terms')
        review_sha = digest(canonical(review))
        evidence_id = 'dd-excerpt-' + digest(canonical({'binding': binding, 'review_sha256': review_sha}))
        result.append({'id': entry['id'], 'text': entry['text'], 'context': entry['context'],
                       'retrieval_terms': terms, 'image_path': entry['image_path'],
                       'evidence': {**page, 'schema': 'dd-textbook-excerpt-evidence-v1',
                           'kind': 'assistant_reviewed_excerpt', 'evidence_id': evidence_id,
                           'page_evidence_id': page['evidence_id'], 'review_sha256': review_sha,
                           **binding, 'review_status': 'assistant_checked_excerpt',
                           'quote_status': 'layout_normalized_transcription', 'teacher_reviewed': False,
                           'fully_reviewed_page': False, 'review_revision': review['revision'],
                           'reviewed_on': reviewed_on.isoformat(), 'valid_until': valid_until.isoformat()}})
    return result


def quote_answer(retrieved: dict) -> dict:
    """Only literal excerpt claims; no free-form answer generation."""
    return {'claims': [{'kind': 'direct_quote', 'text': p['text'],
                        'evidence_id': p['evidence']['evidence_id']} for p in retrieved['items']],
            'generated_answer': None}


def verify_quote_answer(retrieved: dict, answer: dict) -> bool:
    """Check exact quote bindings against THIS retrieval, not arbitrary corpus IDs."""
    if (not isinstance(answer, dict) or set(answer) != {'claims', 'generated_answer'}
            or answer.get('generated_answer') is not None or not isinstance(answer.get('claims'), list)):
        return False
    evidence = {p['evidence']['evidence_id']: p for p in retrieved['items']}
    seen = set()
    for claim in answer['claims']:
        if not isinstance(claim, dict) or set(claim) != {'kind', 'text', 'evidence_id'}:
            return False
        key = claim['evidence_id']
        if type(key) is not str or key not in evidence or key in seen:
            return False
        if claim['kind'] != 'direct_quote' or claim['text'] != evidence[key]['text']:
            return False
        seen.add(key)
    return True


