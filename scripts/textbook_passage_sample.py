#!/usr/bin/env python3
"""Offline, explicitly pinned excerpt pilot; no provider, API or production writes.

Review records are authored attestations, not cryptographic proof of correctness.
This script checks their bindings and returns quote-only candidates. It does not
decide entailment, approve a page, generate answers, or grant grading authority.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata

from learning_service.textbooks import learning_scope, page_evidence, PDF_SHA256

# Compatibility exports for historical offline evaluation entrypoints.
from learning_service.passage_evidence import (FORMAT, SHA, digest, canonical, text_digest,
                                                asset, load_bundle, quote_answer, verify_quote_answer)

def normalize(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text)).casefold()


def retrieve(passages: list[dict], curriculum_id: str, book_id: str, chapter_id: str, query: str) -> dict:
    """Transparent lexical candidate retrieval, not intent or truth classification."""
    book, chapter = learning_scope(curriculum_id, book_id, chapter_id)
    if type(query) is not str or not query.strip() or len(query) > 120 or any(ord(c) < 32 for c in query):
        raise ValueError('invalid query')
    found = []
    for passage in passages:
        evidence = passage['evidence']
        if evidence['book_id'] != book['id'] or chapter['id'] and evidence['chapter_id'] != chapter['id']:
            continue
        matched = [term for term in passage['retrieval_terms'] if normalize(term) in normalize(query)]
        if matched:
            found.append((sum(len(normalize(t)) for t in matched), passage))
    found.sort(key=lambda row: (-row[0], row[1]['evidence']['evidence_id']))
    items = [{k: v for k, v in p.items() if k != 'retrieval_terms'} for _, p in found[:4]]
    return {'scope': {'book_id': book['id'], 'chapter_id': chapter['id'], 'grade': book['grade']},
            'items': items, 'grounding': {'status': 'reviewed_excerpts_only' if items else 'no_evidence',
            'can_quote_textbook': bool(items), 'can_answer_from_textbook': False,
            'eligible_as_grading_basis': False,
            'message': '以下为助手核对过的教材片段，请打开原页；关键词命中不代表已回答问题。' if items
                       else '当前样本与书章范围没有可用片段；不补写引文、答案或页码。'}}


def render_report(cases: list[dict], destination: Path):
    """Local report: each body quote links by identity to its original page card."""
    esc = lambda value: html.escape(str(value), quote=True)
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>教材片段溯源小样本</title><style>body{max-width:960px;margin:32px auto;padding:0 18px;font:18px/1.7 system-ui;color:#172c35;background:#f6f8fa}article{padding:18px;margin:24px 0;background:white;border:1px solid #cdd9de;border-radius:12px}blockquote{margin:12px 0;padding:8px 16px;border-left:4px solid #167a79;white-space:pre-wrap}a{color:#006b70}small{color:#52616b}</style>',
             '<h1>教材片段溯源小样本</h1><p>七上数学第二章 · 5 页限定片段。助手逐字对照并独立核算，非教师审核，非整页通过。这里只展示引文，不生成答案。</p>']
    for i, case in enumerate(cases, 1):
        result, answer = case['retrieval'], case['answer']
        if not verify_quote_answer(result, answer):
            raise ValueError('unbound quote in report')
        parts.append(f'<article><h2>{i}. {esc(case["query"])}</h2><p>{esc(result["grounding"]["message"])}</p>')
        sources = {p['evidence']['evidence_id']: p for p in result['items']}
        for claim in answer['claims']:
            source = sources[claim['evidence_id']]; e = source['evidence']
            anchor = f'case-{i}-{e["evidence_id"]}'
            parts.append(f'<blockquote>{esc(claim["text"])} <a href="#{anchor}">[教材 p.{e["printed_page"]}]</a></blockquote>')
            parts.append(f'<p id="{anchor}"><a href="{esc(source["image_path"])}">打开教材 p.{e["printed_page"]} 原页（PDF 第 {e["pdf_page"]} 页）</a><br><small>{esc(source["context"])}</small></p>')
        parts.append('</article>')
    parts.append('</html>')
    destination.write_text('\n'.join(parts), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--textbook-dir', type=Path, required=True)
    parser.add_argument('--as-of', type=date.fromisoformat, required=True)
    args = parser.parse_args()
    passages = load_bundle(args.bundle, args.manifest_sha256, args.textbook_dir, as_of=args.as_of)
    cases = json.loads((args.bundle / 'cases.json').read_text())
    evaluated = []
    for case in cases:
        result = retrieve(passages, case['curriculum_id'], case['book_id'], case['chapter_id'], case['query'])
        found = {p['id'] for p in result['items']}
        answer = quote_answer(result)
        passed = found == set(case['expected_ids']) and verify_quote_answer(result, answer)
        evaluated.append({**case, 'passed': passed, 'retrieval': result, 'answer': answer})
    report = {'passed': all(c['passed'] for c in evaluated), 'case_count': len(cases), 'usable_excerpts': len(passages),
              'manifest_sha256': args.manifest_sha256, 'as_of': args.as_of.isoformat(),
              'model_calls': 0, 'fully_reviewed_pages': 0, 'teacher_reviewed': False,
              'eligible_as_grading_basis': False, 'cases': evaluated}
    (args.bundle / 'evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    render_report(evaluated, args.bundle / 'preview.html')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}, ensure_ascii=False))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
