#!/usr/bin/env python3
"""Build an offline, source-bound B01 audit. Never import/publish questions or read a DB."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
import hashlib
import html
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from learning_service.passage_evidence import asset, canonical, digest, load_bundle
from learning_service.textbooks import learning_scope, page_evidence

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'learning_service/data/family_chapter_coverage_v1.json'
SOURCE_PATHS = {
    'concepts': 'learning_service/data/family_concepts_v1.json',
    'questions': 'learning_service/data/family_word_problems_v1.json',
    'catalogue': 'learning_service/textbooks.py',
    'starter': 'scripts/prepare_family_math.py',
}
SCOPE = {'curriculum_id': 'math-g7-v1', 'book_id': 'math-g7-upper', 'chapter_id': '2'}
LEVELS = ('easy', 'normal', 'hard')


def current_date():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date()


def read_file(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink input/output')
    return path.read_bytes()


def build_report(spec, reference, questions, passages, *, checked_on):
    """Join explicit mappings only. Page adjacency and keywords never create links."""
    if (spec['format'] != 'dd-family-chapter-coverage-v1' or spec['scope'] != SCOPE
            or spec['review']['reviewer_type'] != 'assistant'
            or spec['review']['teacher_reviewed'] is not False):
        raise ValueError('invalid coverage scope/review')
    book, chapter = learning_scope(**SCOPE)
    rows = deepcopy(spec['rows'])
    by_row = {row['id']: row for row in rows}
    if len(by_row) != len(rows):
        raise ValueError('duplicate coverage row')
    scoped = {q['id']: q for q in questions if q['book_id'] == book['id'] and q['chapter_id'] == chapter['id']}
    if len({q['id'] for q in questions}) != len(questions):
        raise ValueError('duplicate question')
    mappings = spec['question_mappings']
    if len({m['question_version_id'] for m in mappings}) != len(mappings):
        raise ValueError('duplicate question mapping')
    for mapping in mappings:
        q = scoped.get(mapping['question_version_id'])
        if q is None or digest(canonical(q)) != mapping['question_sha256']:
            raise ValueError('question scope/version changed')
        if (q['difficulty'] not in LEVELS or mapping['reviewer_type'] != 'assistant'
                or mapping['teacher_reviewed'] is not False or not mapping['source_ref']):
            raise ValueError('invalid question mapping review')
        if (not mapping['row_ids'] or len(set(mapping['row_ids'])) != len(mapping['row_ids'])
                or not set(mapping['row_ids']) <= by_row.keys() or not mapping['rationale']):
            raise ValueError('unsupported question mapping')
        if mapping['origin'] == 'existing_reference':
            old = reference['question_mappings'][q['id']]
            if (mapping['row_ids'] != old['concept_ids'] or old['question_sha256'] != mapping['question_sha256']
                    or mapping['source_ref'] != f'concepts#/question_mappings/{q["id"]}'):
                raise ValueError('existing mapping changed')
        elif mapping['origin'] != 'b01_assistant_checked':
            raise ValueError('invalid mapping origin')
        elif mapping['source_ref'] != f'questions#/questions/{questions.index(q)}':
            raise ValueError('question source pointer changed')
    by_passage = {p['id']: p for p in passages}
    if len(by_passage) != len(passages):
        raise ValueError('duplicate passage')
    seen_passages = set()
    for row in rows:
        cid = row['concept_id']
        if cid is not None:
            concept = reference['concepts'][cid]
            if concept['book_id'] != book['id'] or chapter['id'] not in concept['chapters']:
                raise ValueError('concept scope changed')
            if row['local_explanation_ref'] != f'concepts#/concepts/{cid}/explanation':
                raise ValueError('explanation source changed')
            row['local_explanation'] = concept['explanation']
        else:
            if row['local_explanation_ref'] is not None:
                raise ValueError('unbound explanation')
            row['local_explanation'] = None
        for loc in row['textbook_locations'] + row['review_resources']:
            evidence = page_evidence(book, loc['pdf_page'])
            if (loc['printed_page'] != evidence['printed_page'] or loc['chapter_id'] != evidence['chapter_id']
                    or loc['pdf_sha256'] != evidence['pdf_sha256']):
                raise ValueError('textbook location changed')
            if loc in row['review_resources'] and loc['chapter_id'] != chapter['id']:
                raise ValueError('review outside chapter')
            if loc['origin'] == 'existing_reference':
                if cid is None or not any(all(loc[k] == p[k] for k in ('printed_page', 'pdf_page', 'chapter_id', 'pdf_sha256'))
                                          for p in reference['concepts'][cid]['textbook_pages']):
                    raise ValueError('unbound original location')
            elif loc['origin'] != 'native_pdf_location':
                raise ValueError('invalid location origin')
            loc['page_evidence_id'] = evidence['evidence_id']
            loc['scope_relation'] = 'current_chapter' if loc['chapter_id'] == chapter['id'] else 'prior_foundation'
        row['effective_passages'] = []
        for link in row['passage_links']:
            if link['id'] in seen_passages:
                raise ValueError('duplicate passage mapping')
            seen_passages.add(link['id'])
            p = by_passage.get(link['id'])
            if p is None:
                continue
            e = p['evidence']
            if (e['book_id'] != book['id'] or e['chapter_id'] != chapter['id']
                    or e['evidence_id'] != link['evidence_id'] or e['printed_page'] != link['printed_page']
                    or not date.fromisoformat(e['reviewed_on']) <= checked_on <= date.fromisoformat(e['valid_until'])
                    or e['teacher_reviewed'] is not False or e['fully_reviewed_page'] is not False):
                raise ValueError('passage scope/review changed')
            # Metadata only: no textbook quotations, contexts or images in this audit.
            row['effective_passages'].append({k: e[k] for k in (
                'evidence_id', 'source_ref', 'printed_page', 'pdf_page', 'review_revision',
                'review_sha256', 'reviewed_on', 'valid_until') } | {'id': p['id']})
        related = [m for m in mappings if row['id'] in m['row_ids']]
        row['questions'] = [{'question_version_id': m['question_version_id'],
                             'title': scoped[m['question_version_id']]['title'],
                             'difficulty': scoped[m['question_version_id']]['difficulty'],
                             'origin': m['origin'], 'question_sha256': m['question_sha256'],
                             'source': scoped[m['question_version_id']]['source'],
                             'rationale': m['rationale']} for m in related]
        row['question_counts'] = {level: sum(q['difficulty'] == level for q in row['questions']) for level in LEVELS}
        row['review_card_count'] = None
        row['delayed_observation'] = None
        row['gaps'] = []
        for missing, label in (
            (not row['textbook_locations'], '无已核对教材定位'),
            (cid is None, '现有概念库无此知识点条目'),
            (not row['effective_passages'], '无当前有效片段映射'),
            (row['local_explanation'] is None, '无本地讲解映射'),
            (not row['questions'], '无现有练习映射'),
            (not row['review_resources'], '无已核对复习资源映射'),
        ):
            if missing:
                row['gaps'].append(label)
        row['gaps'].append('实际复习卡与延迟观察未核验')
    mapped = {m['question_version_id'] for m in mappings}
    summary = {
        'rows': len(rows), 'rows_by_role': dict(Counter(r['role'] for r in rows)),
        'chapter_questions': len(scoped), 'mapped_questions': len(mapped),
        'unmapped_question_ids': sorted(scoped.keys() - mapped),
        'existing_mapped_questions': sum(m['origin'] == 'existing_reference' for m in mappings),
        'new_candidate_mapped_questions': sum(m['origin'] == 'b01_assistant_checked' for m in mappings),
        'questions_by_level': {level: sum(q['difficulty'] == level for q in scoped.values()) for level in LEVELS},
        'question_row_memberships': sum(len(r['questions']) for r in rows),
        'effective_passages': sum(len(r['effective_passages']) for r in rows),
        'unmapped_effective_passage_ids': sorted(by_passage.keys() - seen_passages),
        'rows_with_local_explanation': sum(r['local_explanation'] is not None for r in rows),
        'rows_with_questions': sum(bool(r['questions']) for r in rows),
        'rows_with_review_resources': sum(bool(r['review_resources']) for r in rows),
    }
    return {'format': 'dd-family-chapter-coverage-report-v1', 'version': spec['version'],
            'checked_on': checked_on.isoformat(), 'scope': SCOPE, 'edition': book['edition'],
            'chapter_title': chapter['title'], 'pdf_sha256': spec['pdf_sha256'],
            'sources': spec['sources'], 'inventory_basis': spec['inventory_basis'],
            'review': spec['review'], 'summary': summary, 'rows': rows,
            'reference_only': True, 'teacher_reviewed': False, 'fully_reviewed_pages': 0,
            'eligible_as_grading_basis': False, 'can_answer_from_textbook': False,
            'delivery': 'independent_offline_candidate', 'actual_review_records_read': False}


def render_html(report):
    esc = lambda x: html.escape(str(x), quote=True)
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
             '<title>七上第二章内容覆盖表</title><style>body{font:16px/1.6 system-ui;margin:24px;color:#172c35}table{border-collapse:collapse;width:100%;min-width:1100px}th,td{border:1px solid #cad3d9;padding:12px;text-align:left;vertical-align:top}th{background:#eaf1f4;min-width:120px}td{min-width:150px}small{overflow-wrap:anywhere}details{margin:8px 0}.scroll{overflow:auto}a{color:#006b70}li{margin:4px 0}</style>',
             '<h1>七上第二章内容覆盖表</h1>',
             f'<p>{esc(report["chapter_title"])} · {esc(report["edition"])} · 核对日期 {esc(report["checked_on"])}</p>',
             '<p>独立离线候选。教材定位和有效片段分开记录，缺少来源的关系留空。助手核对不代表教师签署、整页审核或判分依据。</p>',
             '<p>片段数量只在上述核对日期有效；再次使用须重新生成并核验当前日期。实际复习卡与延迟观察未读取、未验收。</p>',
             f'<p>{report["summary"]["rows"]} 行；本章 {report["summary"]["chapter_questions"]} 道应用题，已映射 {report["summary"]["mapped_questions"]} 道（旧 {report["summary"]["existing_mapped_questions"]} / 新候选 {report["summary"]["new_candidate_mapped_questions"]}）；当前有效片段 {report["summary"]["effective_passages"]} 个。各行题数含重叠，不能相加当独立题量。</p>',
             '<p><a href="coverage.json">可审计数据</a> · <a href="manifest.json">文件清单</a></p>',
             '<p>手机可横向滚动表格查看各列；键盘可聚焦表格后用方向键滚动。</p>',
             '<div class="scroll" tabindex="0" role="region" aria-label="章节内容覆盖表，可横向滚动"><table><thead><tr><th>知识点</th><th>教材定位</th><th>有效片段</th><th>本地讲解</th><th>练习</th><th>复习与缺项</th></tr></thead><tbody>']
    roles = {'core': '本章', 'foundation': '先修回顾', 'local_check': '本地核对', 'supplementary': '综合实践'}
    for r in report['rows']:
        def locations(items):
            return '<br>'.join(f'书内 p.{p["printed_page"]} / PDF {p["pdf_page"]} · {esc(p.get("label", ""))}<br><small>{esc(p["source_ref"])}</small>' for p in items) or '留空'
        excerpt = '<br>'.join(f'p.{p["printed_page"]} · revision {p["review_revision"]} · 有效至 {esc(p["valid_until"])}<br><small>{esc(p["id"])}<br>{esc(p["evidence_id"])}</small>' for p in r['effective_passages']) or '留空'
        questions = '<br>'.join(f'{esc(q["title"])}（{esc(q["difficulty"])}）<br><small>{esc(q["question_version_id"])} · {esc(q["origin"])}</small>' for q in r['questions']) or '留空'
        parts.append(f'<tr data-row-id="{esc(r["id"])}"><th scope="row">{esc(r["title"])}<br><small>{esc(roles[r["role"]])}<br>{esc(r["id"])}</small></th><td>{locations(r["textbook_locations"])}</td><td>{excerpt}</td><td>{esc(r["local_explanation"]) if r["local_explanation"] is not None else "留空"}<br><small>{esc(r["local_explanation_ref"] or "")}</small></td><td>简单 {r["question_counts"]["easy"]} / 正常 {r["question_counts"]["normal"]} / 困难 {r["question_counts"]["hard"]}<details><summary>题目 ID 与版本来源</summary>{questions}</details></td><td>{locations(r["review_resources"])}<ul>{"".join("<li>"+esc(g)+"</li>" for g in r["gaps"])}</ul></td></tr>')
    parts.append('</tbody></table></div><details><summary>输入来源与版本</summary><ul>')
    parts.extend(f'<li>{esc(key)} · {esc(value["path"])}<br><small>SHA256 {esc(value["sha256"])}</small></li>' for key, value in report['sources'].items())
    parts.append('</ul></details></html>')
    return '\n'.join(parts) + '\n'


def prepare(output_dir, *, bundle, textbook_dir, spec_path=SPEC):
    destination = Path(output_dir)
    if destination.exists() or any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError('output must be a new independent directory')
    spec_raw = read_file(spec_path)
    spec = json.loads(spec_raw)
    if set(spec['sources']) != set(SOURCE_PATHS):
        raise ValueError('unexpected source set')
    inputs = {Path(spec_path): digest(spec_raw)}
    payloads = {}
    for key, relative in SOURCE_PATHS.items():
        pin = spec['sources'][key]
        if pin['path'] != relative:
            raise ValueError('unexpected input path')
        raw = read_file(ROOT / relative)
        if digest(raw) != pin['sha256']:
            raise ValueError('source version changed: ' + key)
        inputs[ROOT / relative] = digest(raw)
        if key in ('concepts', 'questions'):
            payloads[key] = json.loads(raw)
    pdf = Path(textbook_dir) / (SCOPE['book_id'] + '.pdf')
    if digest(read_file(pdf)) != spec['pdf_sha256']:
        raise ValueError('PDF version changed')
    inputs[pdf] = spec['pdf_sha256']
    # Native text is used only to verify location pointers, never as approved prose.
    import fitz
    with fitz.open(pdf) as document:
        inventory = spec['inventory_basis']
        if digest(document[inventory['toc_pdf_page']-1].get_text().encode()) != inventory['toc_text_sha256']:
            raise ValueError('native contents location changed')
        for row in spec['rows']:
            for loc in row['textbook_locations'] + row['review_resources']:
                if loc['origin'] == 'native_pdf_location' and digest(document[loc['pdf_page']-1].get_text().encode()) != loc['source_text_sha256']:
                    raise ValueError('native page location changed')
    checked_on = current_date()
    # Bind all files checked by the existing bundle validator, without executing its verifier.
    manifest_raw = read_file(Path(bundle) / 'passages.json')
    if digest(manifest_raw) != spec['passage_manifest_sha256']:
        raise ValueError('passage manifest changed')
    for name in ('passages.json', 'semantic-checks.json', 'verify_semantics.py'):
        p = Path(bundle) / name
        inputs[p] = digest(read_file(p))
    for p in json.loads(manifest_raw)['passages']:
        path = Path(bundle) / p['image_path']
        inputs[path] = digest(asset(Path(bundle), p['image_path']))
    passages = load_bundle(bundle, spec['passage_manifest_sha256'], textbook_dir, as_of=checked_on)
    report = build_report(spec, payloads['concepts'], payloads['questions']['questions'], passages, checked_on=checked_on)
    if current_date() != checked_on or any(digest(read_file(path)) != pin for path, pin in inputs.items()):
        raise ValueError('input/date changed during preparation')
    files = {'coverage.json': (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode(),
             'coverage.html': render_html(report).encode()}
    manifest = {'format': 'dd-chapter-coverage-packet-v1', 'checked_on': checked_on.isoformat(),
                'inputs': {str(k): v for k, v in inputs.items()},
                'generator_sha256': digest(read_file(Path(__file__))),
                'files': {name: digest(raw) for name, raw in files.items()}}
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        (destination / name).write_bytes(raw)
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--textbook-dir', type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.output_dir, bundle=args.bundle, textbook_dir=args.textbook_dir)
    print(json.dumps(report['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
