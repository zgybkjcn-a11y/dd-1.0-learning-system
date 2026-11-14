"""Public, draft coverage inventory; never a learner mastery measurement."""
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from .textbooks import catalogue, PDF_SHA256

PATH = Path(__file__).parent / 'data/family_math_coverage_plan_v15.json'
SHA256 = 'e2b8c200c371439466699b9104536d5a76f0a0361b4ee31f831f8f5409b365a1'
MIN_FAMILIES = 2


@lru_cache(maxsize=2)
def _parse(raw):
    data = json.loads(raw)
    if (data['format'] != 'dd-math-coverage-plan-v1' or data['inventory_complete'] is not False
            or data['teacher_reviewed'] is not False or data['curriculum_standard_crosscheck'] != 'pending'):
        raise ValueError('coverage boundary changed')
    return data


def report(curriculum, available_ids):
    raw = PATH.read_bytes()
    if PATH.is_symlink() or hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('coverage plan changed')
    data = _parse(raw)
    return render_report(data,curriculum,available_ids)


def render_report(data,curriculum,available_ids):
    from .practice import bank
    from .reserve_practice import bank as reserves
    from .chapter_practice import bank as chapters
    questions = bank() | reserves() | chapters()
    books = {b['id']: b for b in catalogue(curriculum)}
    result = []
    for row in data['rows']:
        book = books.get(row['book_id'])
        if book is None:
            continue
        if data['pdf_sha256'][book['id']] != PDF_SHA256[book['id']]:
            raise ValueError('coverage edition changed')
        chapter = next(c for c in book['chapters'] if c['id'] == row['chapter_id'])
        if not chapter['printed_page'] <= row['printed_page'] <= chapter['printed_page']+chapter['page_end']-chapter['page_start']:
            raise ValueError('coverage location changed')
        grouped = defaultdict(list)
        seen = set()
        for mapping in row['mappings']:
            qid = mapping['question_version_id']
            q = questions.get(qid)
            canonical = json.dumps(q, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            if (q is None or hashlib.sha256(canonical).hexdigest() != mapping['question_sha256']
                    or (q['book_id'], q['chapter_id']) != (book['id'], chapter['id'])
                    or mapping['task'] not in row['requirements']
                    or mapping.get('role', 'direct') not in ('direct', 'supporting')
                    or (qid, mapping['task']) in seen):
                raise ValueError('coverage question mapping changed')
            if row.get('assessment_modes',{}).get(mapping['task'])=='human' and mapping.get('role','direct')=='direct':
                raise ValueError('manual performance cannot be counted from automatic answers')
            seen.add((qid, mapping['task']))
            if qid in available_ids:
                grouped[mapping['task']].append(mapping)
        tasks = []
        for task, requirement in row['requirements'].items():
            mappings = grouped[task]
            families = len({m['family'] for m in mappings if m.get('role', 'direct') == 'direct'})
            supporting = sum(m.get('role') == 'supporting' for m in mappings)
            tasks.append({'id': task, 'label': data['task_labels'][task], 'requirement': requirement,
                          'question_ids': sorted({m['question_version_id'] for m in mappings}),
                          'question_count': len(mappings), 'family_count': families,
                          'supporting_question_count': supporting,
                          'status': 'gap' if not mappings else 'partial' if families < MIN_FAMILIES else 'configured'})
            mode=row.get('assessment_modes',{}).get(task)
            if mode in ('human','bounded'):
                tasks[-1]['assessment_mode']=mode
        result.append({'id': row['id'], 'book_id': book['id'], 'chapter_id': chapter['id'],
                       'title': row['title'], 'printed_page': row['printed_page'], 'tasks': tasks})
        if row.get('manual_task'):
            result[-1]['manual_task']=row['manual_task']
    return {'version': data['version'], 'status': 'draft', 'inventory_complete': False,
            'teacher_reviewed': False, 'curriculum_standard_crosscheck': 'pending',
            'min_distinct_families_per_task': MIN_FAMILIES, 'items': result,
            'notice': '当前为助手整理的知识点清单，待课程标准与教师复核；每项能力以两种不同题型为配题目标。辨认解释的选择题只计辅助练习，口述、画图、实测任务仍保留缺口。配题比例不代表整章覆盖或学习掌握。'}
