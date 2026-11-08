#!/usr/bin/env python3
"""Prepare a new B02 review/freeze packet. No database, learner, provider or OCR access."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import html
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from learning_service import reserve_practice as reserve

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / 'learning_service/data/family_chapter_coverage_v1.json'


def windows(started_at):
    if started_at is None:
        return [{'offset_days': d, 'due_at': None, 'observed_at': None, 'outcome': None} for d in (1, 3, 7)]
    start = datetime.fromisoformat(started_at)
    if start.tzinfo is None:
        raise ValueError('actual observation start requires timezone')
    start = start.astimezone(ZoneInfo('Asia/Shanghai'))
    return [{'offset_days': d, 'due_at': (start + timedelta(days=d)).isoformat(),
             'observed_at': None, 'outcome': None} for d in (1, 3, 7)]


def prepare(destination):
    destination = Path(destination)
    if destination.exists() or any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError('new independent output directory required')
    paths = (reserve.PATH, reserve.BANK_PATH, COVERAGE, Path(reserve.__file__))
    if any(p.is_symlink() for path in paths for p in (path, *path.parents)):
        raise ValueError('symlink input')
    inputs = {path: path.read_bytes() for path in paths}
    questions = list(reserve.bank().values())
    payload = json.loads(inputs[reserve.PATH])
    if hashlib.sha256(inputs[COVERAGE]).hexdigest() != payload['coverage_sha256']:
        raise ValueError('coverage source changed')
    row_ids = {r['id'] for r in json.loads(inputs[COVERAGE])['rows']}
    if any(not q['coverage_row_ids'] or not set(q['coverage_row_ids']) <= row_ids for q in questions):
        raise ValueError('unsupported coverage relationship')
    review = {'scope': 'assistant_checked_question_trial_not_teacher_signoff', 'teacher_reviewed': False,
              'bank_sha256': reserve.SHA256, 'questions': [{
                  'question_version_id': q['id'], 'question_sha256': hashlib.sha256(reserve.canonical(q)).hexdigest(),
                  'stored_version_sha256': hashlib.sha256(reserve.canonical(reserve.stored(q))).hexdigest(),
                  'difficulty': q['difficulty'], 'conditions_complete': q['review']['conditions_complete'],
                  'units_checked': q['review']['units_checked'], 'mathematical_check': q['mathematical_check'],
                  'independent_check': q['independent_check'], 'answer': q['answer'],
                  'template_relation': q['template_relation'], 'status': 'assistant_checked',
                  'unresolved_issues': []} for q in questions]}
    plan = {'status': 'pending_actual_use', 'baseline_started_at': None, 'baseline_attempt_id': None,
            'bank_sha256': reserve.SHA256, 'question_version_hashes': {q['question_version_id']: q['question_sha256'] for q in review['questions']},
            'windows': windows(None), 'conditions': ['真实日期与同一题版', '无提示记录另列', '同母题改数不算新情境',
                                                  '结果不能单独证明掌握', '未发生的观察保持null']}
    esc = lambda x: html.escape(str(x), quote=True)
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
             '<title>B02备用题审核包</title><style>body{max-width:900px;margin:24px auto;padding:0 18px;font:18px/1.7 system-ui}article{border:1px solid #ccc;border-radius:12px;padding:16px;margin:20px 0}small{overflow-wrap:anywhere}pre{white-space:pre-wrap}a{color:#006b70}</style>',
             '<h1>七上第二章备用题审核包</h1><p>12题，每档4题。助手编写与核对，非教师签署或学生难度校准。此页供审阅题面与解析，家庭候选界面另有未见备用题选择。</p>',
             '<p>真实1/3/7天观察尚未开始；结果保持留空。<a href="review.json">题版与审核记录</a> · <a href="observation-plan.json">延迟观察计划</a></p>']
    for q in questions:
        relation = q['template_relation']
        label = '同母题改数：' + relation['parent_title'] if relation['kind'] == 'numeric_variant' else ('新编情境' if relation['kind'] == 'new_authored_situation' else '新编计算任务')
        parts.append(f'<article><h2>{esc(q["title"])} · {esc(q["difficulty"])}</h2><small>{esc(q["id"])} · {esc(label)}</small><pre>{esc(q["prompt"])}</pre><details><summary>审核答案与解析</summary><p>{esc(q["answer"])}</p><p>{esc(q["explanation"])}</p></details></article>')
    parts.append('</html>')
    outputs = {'questions.json': payload, 'review.json': review, 'observation-plan.json': plan}
    files = {name: (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode() for name, data in outputs.items()}
    files['preview.html'] = ('\n'.join(parts) + '\n').encode()
    if any(path.read_bytes() != raw for path, raw in inputs.items()):
        raise ValueError('input changed during preparation')
    manifest = {'format': 'dd-reserve-practice-packet-v1', 'created_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
                'inputs': {str(path.relative_to(ROOT)): hashlib.sha256(raw).hexdigest() for path, raw in inputs.items()},
                'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'deployment': False, 'actual_observations': 0}
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        (destination / name).write_bytes(raw)
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output_dir), ensure_ascii=False))


if __name__ == '__main__':
    main()
