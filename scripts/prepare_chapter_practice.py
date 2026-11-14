#!/usr/bin/env python3
"""Export a self-contained review packet and catalogue coverage; no DB access."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.chapter_practice import bank, BATCHES, metadata
from learning_service.practice import bank as base_bank
from learning_service.textbooks import BOOKS
from learning_service.practice_coverage import report as knowledge_report
from learning_service.reserve_practice import bank as reserve_bank
from learning_service.practice_design import validate_visual


def visual_html(spec):
    if not spec:
        return ''
    spec = validate_visual(spec)
    esc = lambda s: html.escape(str(s), quote=True)
    if spec['kind'] == 'ruler':
        height = 100 + 48*len(spec['segments'])
        parts = [f'<svg role="img" aria-label="{esc(spec["caption"])}" viewBox="0 0 560 {height}" style="width:100%;max-width:650px">']
        x = lambda n: 40+n*480/spec['maximum']
        parts.append('<line x1="40" y1="40" x2="520" y2="40" stroke="#344d41"/>')
        for i in range(spec['maximum']+1):
            parts.append(f'<line x1="{x(i)}" y1="32" x2="{x(i)}" y2="48" stroke="#344d41"/><text x="{x(i)}" y="24" text-anchor="middle">{i}</text>')
        parts.append('<text x="535" y="24">cm</text>')
        for i,s in enumerate(spec['segments']):
            y=85+i*48
            parts.append(f'<line x1="{x(s["start"])}" y1="{y}" x2="{x(s["end"])}" y2="{y}" stroke="#3f7561" stroke-width="7"/><text x="{(x(s["start"])+x(s["end"]))/2}" y="{y+28}" text-anchor="middle">{esc(s["label"])}</text>')
        parts.append('</svg>')
        body=''.join(parts)
    else:
        body='<table>'+''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in spec['rows'])+'</table>'
    return '<figure><figcaption>'+esc(spec['caption'])+'</figcaption>'+body+'</figure>'


def response_html(q, answers=False):
    parts = []
    for f in q.get('responses', []):
        value = ((' → ' if f.get('kind')=='order' else '、').join(f['options'][int(n)-1] for n in f['answer'].split(',')) if f['options'] else f['answer']) if answers else '________'
        options = ('（' + ' / '.join(f['options']) + '）') if f['options'] and not answers else ''
        parts.append(html.escape(f['label'] + options + '：' + value))
    return '<p>' + '<br>'.join(parts) + '</p>' if parts else (html.escape(q['answer']) if answers else '')


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    questions = list(bank().values())
    old = Counter((q['book_id'], q['chapter_id']) for q in base_bank().values())
    new = Counter((q['book_id'], q['chapter_id']) for q in questions)
    rows = [{'book_id': b['id'], 'grade': b['grade'], 'subject': b['subject_title'], 'book': b['title'],
             'chapter_id': c['id'], 'chapter': c['title'], 'before': old[b['id'], c['id']],
             'added': new[b['id'], c['id']], 'after': old[b['id'], c['id']] + new[b['id'], c['id']]}
            for b in BOOKS for c in b['chapters']]
    summary = {'books': len(BOOKS), 'chapters': len(rows), 'added': len(questions), 'batches': BATCHES,
               'empty_before': sum(r['before'] == 0 for r in rows), 'empty_after': sum(r['after'] == 0 for r in rows),
               'teacher_reviewed': False, 'coverage_basis': 'initial_word_bank_plus_new_batches_excludes_starters_and_reserve',
               'rows': rows}
    esc = lambda value: html.escape(str(value), quote=True)
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>家庭学习章节练习审核包</title><style>body{max-width:1000px;margin:24px auto;padding:0 16px;font:18px/1.7 system-ui;color:#24363b}article,details{border:1px solid #bdcecf;border-radius:10px;padding:14px;margin:12px 0}pre{white-space:pre-wrap;font:inherit}table{border-collapse:collapse}td,th{padding:6px;border:1px solid #bdcecf}small{overflow-wrap:anywhere}</style>',
             f'<h1>家庭学习 · 章节练习</h1><p>{len(questions)}道自编章节题，{len(BATCHES)}个批次；{len(BOOKS)}册{len(rows)}个目录范围。已有起步题不表示整章知识点已覆盖。助手核对，无教师签署；数学含数值/方向变式，英语附录不含实际听力测验。</p>',
             '<details><summary>全部章节覆盖清单</summary><table><tr><th>课本</th><th>章节</th><th>原应用题</th><th>新增</th></tr>']
    for r in rows:
        parts.append(f'<tr><td>{r["grade"]}年级 {esc(r["book"])}</td><td>{esc(r["chapter"])}</td><td>{r["before"]}</td><td>{r["added"]}</td></tr>')
    parts.append('</table></details>')
    for book in BOOKS:
        selected = [q for q in questions if q['book_id'] == book['id']]
        if not selected:
            continue
        parts.append(f'<details><summary>{book["grade"]}年级 {esc(book["title"])} · 新增{len(selected)}题</summary>')
        for q in selected:
            info=metadata(q)
            parts.append(f'<article><h2>{esc(q["source"]["chapter_title"])} · {esc(q["title"])}</h2><small>{esc(q["id"])} · 当前档位{esc(info["difficulty"])} · {esc(info.get("task_form", "练习"))} · {esc(q["source"].get("template_relation") or "自编题")}</small><pre>{esc(q["prompt"])}</pre>{visual_html(q.get("visual"))}{response_html(q)}<details><summary>答案、提示与解析</summary><p>答案：{response_html(q, answers=True)}</p><p>提示：{esc(q["hint"])}</p><p>{esc(q["explanation"])}</p></details></article>')
        parts.append('</details>')
    parts.append('</html>')
    files = {'coverage.json': json.dumps(summary, ensure_ascii=False, indent=2),
             'questions.json': json.dumps(questions, ensure_ascii=False, indent=2), 'preview.html': '\n'.join(parts)}
    ids = set(bank()) | set(base_bank()) | set(reserve_bank())
    plans = [knowledge_report('math-g2-v1', ids), knowledge_report('math-g7-v1', ids)]
    files['math-knowledge-gaps.json'] = json.dumps(plans, ensure_ascii=False, indent=2)
    gap_html = parts[:2] + ['<h1>二上、七上数学知识点配题缺口</h1><p>此审阅表包含全部本地候选（含未安装的备用题），不是线上可用题统计。助手清单草案，课程标准与教师复核待完成。两种独立题型为每项能力的初步目标，数值变式合并计数。辨认解释的选择题只计辅助练习，不替代独立口述或实测。该表不证明整章穷尽或学生掌握。</p><table><tr><th>范围</th><th>知识点</th><th>能力要求</th><th>题数/题型数</th></tr>']
    for plan in plans:
        for row in plan['items']:
            for task in row['tasks']:
                support = task['supporting_question_count']
                gap_html.append(f'<tr><td>{esc(row["book_id"])} / {esc(row["chapter_id"])}</td><td>{esc(row["title"])}</td><td>{esc(task["label"])}：{esc(task["requirement"])}</td><td>{task["question_count"]-support}道对应练习/{task["family_count"]}种题型；{support}道辅助练习 · {esc(task["status"])}</td></tr>')
    files['math-knowledge-gaps.html'] = '\n'.join(gap_html + ['</table></html>'])
    for name, data in files.items():
        (output / name).write_text(data + '\n')
    manifest = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in files}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return {k: summary[k] for k in ('books', 'chapters', 'added', 'empty_before', 'empty_after')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output)))
