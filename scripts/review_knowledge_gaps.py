"""Export an editorial review using an explicit read-only installed-ID snapshot.

Never installs content, opens a learner database, or infers mappings from titles.
The historical math plan and current subject plan remain separate reports.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_service import practice_coverage, subject_coverage
from learning_service.chapter_practice import bank as chapters
from learning_service.practice import bank as initial
from learning_service.practice_design import presentation
from learning_service.reserve_practice import bank as reserves
from learning_service.textbooks import practice_scope
from scripts.prepare_family_math import STARTER_QUESTIONS


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def export(available_path: Path, destination: Path):
    snapshot = json.loads(available_path.read_bytes())
    available = {grade: set(snapshot['available_ids'][str(grade)]) for grade in (2, 7)}
    chapter_questions = chapters()
    questions = initial() | reserves() | chapter_questions
    for objective, exercises in STARTER_QUESTIONS.items():
        for index, (prompt, answer) in enumerate(exercises, 1):
            qid = f'family-starter-{objective}-{index}-v1'
            questions[qid] = {'id': qid, 'title': '起步运算', 'prompt': prompt, 'answer': answer,
                              'source': 'authored_family_starter_math_v1', **(practice_scope(qid) or {})}
    ids = set.union(*available.values())
    if not ids or any(ids - questions.keys()) or available[2] & available[7]:
        raise ValueError('installed IDs must be known, nonempty and grade-isolated')
    destination.mkdir(parents=True, exist_ok=False)
    reports, summary, review_rows = {}, {}, []
    for name, module in (('math', practice_coverage), ('subject', subject_coverage)):
        plans = [module.report(f'math-g{grade}-v1', available[grade]) for grade in (2, 7)]
        reports[name] = plans
        write_json(destination / (name + '-coverage.json'), plans)
        summary[name] = {'version': plans[0]['version'], 'books': {}}
        for plan in plans:
            for row in plan['items']:
                book = row['book_id']
                counts = summary[name]['books'].setdefault(book, Counter())
                counts['points'] += 1
                for task in row['tasks']:
                    counts['requirements'] += 1
                    counts[task['status']] += 1
                    mode = task.get('assessment_mode', 'unspecified')
                    counts[mode] += 1
                    if not task['family_count']:
                        counts['without_direct_family'] += 1
                    if mode == 'human':
                        category = 'human'
                    elif not task['question_count']:
                        category = 'no_mapping'
                    elif not task['family_count']:
                        category = 'supporting_only'
                    elif task['family_count'] == 1:
                        category = 'one_direct_family'
                    else:
                        category = 'configured_editorial_target'
                    candidates = [qid for qid, q in questions.items() if qid in ids
                                  and (q.get('book_id'), q.get('chapter_id')) == (book, row['chapter_id'])
                                  and qid not in task['question_ids']]
                    review_rows.append({'plan': name, 'point_id': row['id'], 'title': row['title'],
                                        'book_id': book, 'chapter_id': row['chapter_id'],
                                        'printed_page': row['printed_page'], **task,
                                        'review_category': category,
                                        'candidate_ids_same_scope_unreviewed': sorted(candidates)})
    write_json(destination / 'requirements.json', review_rows)
    write_json(destination / 'summary.json', summary)
    write_json(destination / 'installed-questions.json', [
        {'id': qid, **questions[qid], 'presentation': presentation(questions[qid]) if 'difficulty' in questions[qid] else {'difficulty': 'starter'}}
        for qid in sorted(ids)
    ])
    write_json(destination / 'provenance.json', {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'available_snapshot': str(available_path),
        'available_snapshot_sha256': hashlib.sha256(available_path.read_bytes()).hexdigest(),
        'installed_counts': {g: len(v) for g, v in available.items()},
        'reserve_candidates_excluded': sorted(set(reserves()) - ids),
        'plans': {name: {'path': str(module.PATH), 'sha256': module.SHA256}
                  for name, module in (('math', practice_coverage), ('subject', subject_coverage))},
        'candidate_policy': 'Same-scope IDs are unreviewed suggestions, never automatic mappings.',
        'boundary': 'Editorial target only. Human and unspecified modes are not automatic mastery evidence.',
    })
    style = '<meta charset="utf-8"><style>body{font:16px sans-serif;max-width:1100px;margin:2em auto;padding:1em}pre{white-space:pre-wrap}article,details{border-top:1px solid #bbb;padding:1em 0}a{color:#1459a3}</style>'
    def text(value):
        return escape(json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value)
    html = [style, '<h1>正式题库知识点缺口审阅</h1><p>两个清单口径分别保留。配题目标不表示整章完整率、教学签署或掌握；候选题须逐项审阅。人工要求不由自动答题替代。</p>',
            '<a href="questions.html">题干、答案与解析</a> · <a href="requirements.json">逐项缺口 JSON</a>']
    for row in review_rows:
        if row['review_category'] == 'configured_editorial_target':
            continue
        html.append('<details><summary>' + text(f"{row['plan']} | {row['point_id']} | {row['requirement']} | {row['review_category']}") + '</summary><pre>' + text(row) + '</pre></details>')
    (destination / 'index.html').write_text(''.join(html))
    html = [style, '<h1>正式已安装题库审阅</h1><p>仅含快照中的已安装题；答案私有，仅用于本地编辑审阅。教师签署仍待完成。</p>']
    for qid in sorted(ids):
        q = questions[qid]
        html.append('<article id="' + escape(qid) + '"><h2>' + text(qid + ' · ' + q['title']) + '</h2><pre>' + text(q) + '</pre></article>')
    (destination / 'questions.html').write_text(''.join(html))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--available-ids', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.available_ids, args.output), ensure_ascii=False))
