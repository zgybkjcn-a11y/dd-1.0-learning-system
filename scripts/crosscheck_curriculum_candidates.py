"""Assistant cross-check of the authored gap candidates before formal registration.

The check is against the local reviewed artefacts only: the subject/math coverage
plans for upper books and the lower knowledge inventory for lower books. The
national curriculum standard text is not present in this repository, so this
record never claims a standard-text comparison or a teacher signature.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from learning_service import chapter_practice as chapter
from learning_service.practice import LEVELS
from learning_service.textbooks import PDF_SHA256, learning_scope

DATA = ROOT / 'learning_service/data'
SUBJECT = DATA / 'family_subject_coverage_plan_v16.json'
MATH = DATA / 'family_math_coverage_plan_v15.json'
INVENTORY = ROOT / 'docs/quality/lower-knowledge-inventory-2026-11-13.json'
OUT = ROOT / 'learning_data/verification/curriculum-crosscheck-20261118'

BATCHES = ['upper_gap_candidates', 'lower_gap_candidates'] + [
    'lower_gap_candidates_batch%d' % index for index in range(2, 9)]
# batch3 splits the inherited perpendicular point into page-correct refine rows.
REFINE_PARENT = {
    'math-g7-lower:7:perpendicular-definition': 'math-g7-lower:7:perpendicular',
    'math-g7-lower:7:perpendicular-unique': 'math-g7-lower:7:perpendicular',
    'math-g7-lower:7:perpendicular-distance': 'math-g7-lower:7:perpendicular',
}
CROSSCHECK = 'assistant_crosscheck_passed_2026-11-18_against_local_plan_or_inventory'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def sources():
    subject = json.loads(SUBJECT.read_text())
    math = json.loads(MATH.read_text())
    rows = {row['id']: ('subject-v16', row) for row in subject['rows']}
    rows |= {row['id']: ('math-v15', row) for row in math['rows']}
    inventory = json.loads(INVENTORY.read_text())
    points = {}
    for scope in inventory['scopes']:
        for point in scope.get('new_initial_points', []):
            points[point['id']] = ('lower-inventory-new', point)
        for point in scope.get('inherited_points', []):
            points[point['id']] = ('lower-inventory-inherited', point)
    return rows, points


def requirement(source, row, task):
    if source.startswith('lower-inventory'):
        return row.get('bounded_candidate_action') or (row.get('requirements') or {}).get(task)
    return row['requirements'].get(task)


def check_question(q, seen, rows, points, batch):
    problems = []
    if q['batch'] != batch:
        problems.append('batch mismatch')
    if q['id'] in seen:
        problems.append('duplicate id')
    seen.add(q['id'])
    if q['id'] in chapter.bank():
        registered = True
    else:
        registered = False
    if not q['id'].startswith(chapter.PREFIX) or not q['id'].endswith('-v1'):
        problems.append('id form')
    curriculum = 'math-g%d-v1' % q['grade']
    try:
        book, scope = learning_scope(curriculum, q['book_id'], q['chapter_id'])
    except (KeyError, ValueError):
        problems.append('unknown scope')
        book = scope = None
    else:
        if book['subject'] != q['subject']:
            problems.append('subject/scope mismatch')
        if scope['id'] != q['chapter_id']:
            problems.append('chapter mismatch')
    if q['difficulty'] not in LEVELS:
        problems.append('difficulty')
    if not q['prompt'] or not q['hint'] or not q['explanation']:
        problems.append('empty text')
    if q['source']['kind'] != 'authored' or q['source'].get('textbook_original_question'):
        problems.append('source boundary')
    if q['source']['textbook_sha256'] != PDF_SHA256.get(q['book_id']):
        problems.append('textbook identity')
    if q['review']['status'] != 'assistant_checked' or q['review']['teacher_reviewed'] is not False:
        problems.append('review status')
    knowledge = q.get('knowledge') or {}
    point_id = knowledge.get('point_id')
    parent = REFINE_PARENT.get(point_id)
    lookup = parent or point_id
    source = row = None
    if lookup in rows:
        source, row = rows[lookup]
    elif lookup in points:
        source, row = points[lookup]
    if row is None:
        problems.append('point missing from local plan/inventory')
        text = None
    else:
        text = requirement(source, row, knowledge.get('task'))
        if not text:
            problems.append('requirement text missing')
        if source.startswith('lower-inventory') and knowledge.get('task') != 'check':
            problems.append('inventory task must be check')
        mode = (row.get('assessment_modes') or {}).get(knowledge.get('task'))
        if mode == 'human' and knowledge.get('role') == 'direct':
            problems.append('direct automatic claim for a human requirement')
    if knowledge.get('role') not in ('direct', 'supporting'):
        problems.append('role')
    if not knowledge.get('family') or not knowledge.get('rationale'):
        problems.append('mapping rationale')
    if not q.get('design', {}).get('core_actions'):
        problems.append('core actions missing')
    if set(q['review'].get('field_coverage') or {}) != {r['id'] for r in q['responses']}:
        problems.append('field coverage mismatch')
    if book and len(q.get('responses') or []) != len(q.get('design', {}).get('core_actions') or []):
        problems.append('response/action count mismatch')
    return problems, {'point_id': point_id, 'requirement_source': source,
                      'requirement': text, 'role': knowledge.get('role'),
                      'parent_point_id': parent, 'assessment_mode': mode if row else None,
                      'registered_in_bank': registered}


def main():
    rows, points = sources()
    seen, items, problems = set(), [], []
    for batch in BATCHES:
        path = DATA / ('family_chapter_%s_v1.json' % batch)
        raw = path.read_bytes()
        payload = json.loads(raw)
        if payload['batch'] != batch or payload['teacher_reviewed'] is not False:
            problems.append({'batch': batch, 'problem': 'file header'})
        chapter._parse(raw)  # full authored-content validation, including grading
        for q in payload['questions']:
            found, item = check_question(q, seen, rows, points, batch)
            record = {'batch': batch, 'question_version_id': q['id'],
                      'question_sha256': hashlib.sha256(canonical(q)).hexdigest(),
                      'grade': q['grade'], 'subject': q['subject'], 'book_id': q['book_id'],
                      'chapter_id': q['chapter_id'], 'difficulty': q['difficulty'],
                      'decision': 'accepted' if not found else 'rejected',
                      'checks': found or 'all structural, scope, evidence and mapping checks passed',
                      **item}
            items.append(record)
            if found:
                problems.append(record)
    summary = {
        'batches': len(BATCHES), 'questions': len(items),
        'accepted': sum(item['decision'] == 'accepted' for item in items),
        'rejected': sum(item['decision'] == 'rejected' for item in items),
        'by_subject': {subject: sum(item['subject'] == subject for item in items)
                       for subject in sorted({item['subject'] for item in items})},
        'by_grade': {str(grade): sum(item['grade'] == grade for item in items) for grade in (2, 7)},
        'direct': sum(item['role'] == 'direct' for item in items),
        'supporting': sum(item['role'] == 'supporting' for item in items),
        'manual_followups': sum('manual_followup' in q
                                for batch in BATCHES
                                for q in json.loads((DATA / ('family_chapter_%s_v1.json' % batch)).read_bytes())['questions']),
        'files_sha256': {batch: hashlib.sha256((DATA / ('family_chapter_%s_v1.json' % batch)).read_bytes()).hexdigest()
                         for batch in BATCHES},
    }
    record = {
        'format': 'dd-curriculum-crosscheck-v1',
        'recorded_at': '2026-11-18',
        'method': 'assistant structural, scope, evidence and mapping cross-check against the local reviewed '
                  'subject-v16/math-v15 plans and the lower knowledge inventory; textbook pages were already '
                  'checked page-by-page during authoring without OCR',
        'crosscheck_status': CROSSCHECK,
        'teacher_reviewed': False,
        'national_standard_text_available': False,
        'limitations': [
            '国家课标文本不在本仓库，本次核对的是本地已审计划/清单中的要求表述与教材页位证据，不是课标原文比对。',
            '教师签署仍为 false；本记录不能替代教师复核或真实难度校准。',
            '人工任务（口述、作图、实测）仍未被观察，选择题只证明指定的自动判分部分。',
        ],
        'summary': summary,
        'items': items,
    }
    if problems:
        raise SystemExit(json.dumps(problems, ensure_ascii=False, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'crosscheck.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
