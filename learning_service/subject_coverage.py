"""All-subject editorial knowledge inventory, not learner proficiency."""
from functools import lru_cache
from pathlib import Path
import hashlib
import json

from .practice_coverage import render_report

PATH=Path(__file__).parent/'data/family_subject_coverage_plan_v16.json'
SHA256='f3861070f1081833a47bf5a2cca5dedb714de44f0fc8878eea85ec2d9490189a'


@lru_cache(maxsize=2)
def _parse(raw):
    data=json.loads(raw)
    if (data['format']!='dd-subject-coverage-plan-v1' or data['inventory_complete'] is not False
            or data['teacher_reviewed'] is not False or data['curriculum_standard_crosscheck']!='pending'
            or len({r['id'] for r in data['rows']})!=len(data['rows'])):
        raise ValueError('subject coverage boundary changed')
    for row in data['rows']:
        modes=row.get('assessment_modes',{})
        if (set(modes)!=set(row['requirements'])
                or any(mode not in ('human','bounded') for mode in modes.values())):
            raise ValueError('subject assessment mode changed')
        task=row.get('manual_task')
        if 'human' in modes.values() and not task:
            raise ValueError('human requirements need an observable manual task')
        if task and (task['automatically_graded'] is not False or not task['criteria']
                     or not task['prompt'] or not task['title']):
            raise ValueError('manual task boundary changed')
    return data


def report(curriculum,available_ids):
    from .chapter_practice import bank
    from .textbooks import catalogue
    raw=PATH.read_bytes()
    if PATH.is_symlink() or hashlib.sha256(raw).hexdigest()!=SHA256:
        raise ValueError('subject coverage plan changed')
    data=_parse(raw)
    result=render_report(data,curriculum,available_ids)
    books={b['id']:b for b in catalogue(curriculum)}
    questions=bank()
    sections=[]
    for scope in data['section_inventory']:
        if scope['book_id'] not in books:continue
        mapped={m['question_version_id'] for row in data['rows']
                if (row['book_id'],row['chapter_id'])==(scope['book_id'],scope['chapter_id']) for m in row['mappings']}
        unmapped=[qid for qid,q in questions.items() if qid in available_ids and qid not in mapped
                  and (q['book_id'],q['chapter_id'])==(scope['book_id'],scope['chapter_id'])]
        sections.append({**scope,'unmapped_available_questions':len(unmapped)})
    result['section_inventory']=sections
    result['notice']='助手按固定教材整理的知识点草案，尚待课程标准和教师复核。无映射表示缺少已核对的对应题，不等于本章完全没有练习；待映射题另列。口述、听说、写作和实操按任务单人工核对，不能由选择题代替。配题数量不代表掌握程度。'
    return result
