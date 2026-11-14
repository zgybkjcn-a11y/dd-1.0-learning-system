"""Review direct-action mappings without changing frozen question versions."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_service.chapter_practice import bank

MATH_SOURCE = ROOT / 'learning_service/data/family_math_coverage_plan_v6.json'
SUBJECT_SOURCE = ROOT / 'learning_service/data/family_subject_coverage_plan_v5.json'


def question_mapping(q, task, role, rationale):
    return {
        'question_version_id': q['id'],
        'question_sha256': hashlib.sha256(json.dumps(
            q, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'task': task,
        'family': (q.get('knowledge') or q.get('coverage'))['family'],
        'role': role,
        'rationale': rationale,
    }


def add_mapping(rows, questions, row_id, question_id, task, role, rationale):
    row = rows[row_id]
    if task not in row['requirements']:
        raise ValueError(f'{row_id} has no {task} requirement')
    if any(m['question_version_id'] == question_id and m['task'] == task for m in row['mappings']):
        raise ValueError(f'duplicate mapping: {row_id} {task} {question_id}')
    row['mappings'].append(question_mapping(questions[question_id], task, role, rationale))


def set_role(rows, row_id, task, question_id, role, rationale):
    row = rows[row_id]
    matches = [m for m in row['mappings']
               if m['question_version_id'] == question_id and m['task'] == task]
    if len(matches) != 1:
        raise ValueError(f'expected one mapping: {row_id} {task} {question_id}')
    matches[0]['role'] = role
    matches[0]['rationale'] = rationale


def build_math(questions):
    data = json.loads(MATH_SOURCE.read_bytes())
    data['version'] = '2026-11-12-v8-math-single-action-review'
    rows = {row['id']: row for row in data['rows']}

    # Bring the installed math-gap batch into the older math-specific inventory.
    gap_questions = bank('math_gaps')
    for q in gap_questions.values():
        mapping = q['knowledge']
        if mapping['point_id'] not in rows:
            raise ValueError(f'missing math coverage row: {mapping["point_id"]}')
        add_mapping(rows, questions, mapping['point_id'], q['id'], mapping['task'],
                    mapping['role'], mapping['rationale'])

    unknown_factor = 'family-chapter-math-g2-upper-2-challenge-unknown-factor-v1'
    set_role(rows, 'math-g2-upper:2:tables', 'transfer', unknown_factor, 'direct',
             '从已知积减去一个等组，再确定相邻乘积；与直接回忆乘积采用不同求解动作。')
    add_mapping(rows, questions, 'math-g2-upper:3:quotient',
                'family-chapter-math-g2-upper-3-depth-equal-distinguish-2-v1', 'distinguish', 'direct',
                '核对除法中已知份数、每份量与求得商的角色，直接对应除数和商的含义。')

    # These installed tasks fully require unit conversion or table multiplication.
    add_mapping(rows, questions, 'math-g2-upper:4:units',
                'family-chapter-math-g2-upper-4-multistep-ribbon-plan-v1', 'apply', 'direct',
                '必须先将1米换成100厘米，再逐项核对已用、剩余和缺少的长度。')
    add_mapping(rows, questions, 'math-g2-upper:5:tables',
                'family-chapter-math-g2-upper-5-multistep-array-removal-v1', 'apply', 'direct',
                '用7～9乘法口诀计算方阵总数和整列数量，再核对移除后的乘积。')
    for question_id in (
        'family-chapter-math-g2-upper-5-math_gaps-regroup-total-v1',
        'family-chapter-math-g2-upper-5-math_gaps-recover-total-v1',
    ):
        add_mapping(rows, questions, 'math-g2-upper:5:quotient', question_id, 'apply', 'direct',
                    '直接用7～9乘法口诀求商，题目分别检验求份数与反推总量两种分组情境。')
        add_mapping(rows, questions, 'math-g2-upper:5:quotient', question_id, 'distinguish', 'direct',
                    '明确区分给定每份量与给定份数，两题分别检验固定总量改分及反推总量。')

    add_mapping(rows, questions, 'math-g7-upper:1:signed',
                'family-chapter-math-g7-upper-1-depth-signed-04-v1', 'distinguish', 'direct',
                '从实测值与标准值区分绝对长度和带符号的偏差量，并核对允许范围。')
    add_mapping(rows, questions, 'math-g7-upper:1:rational',
                'family-chapter-math-g7-upper-1-depth-rational-04-v1', 'apply', 'direct',
                '按整数/非整数后再按正负的两级标准给有理数分类，直接对应分类要求。')

    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    (ROOT / 'learning_service/data/family_math_coverage_plan_v8.json').write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def build_subject(questions):
    data = json.loads(SUBJECT_SOURCE.read_bytes())
    data['version'] = 'subject-coverage-v7-math-single-action-review-2026-11-12'
    rows = {row['id']: row for row in data['rows']}

    unknown_factor = 'family-chapter-math-g2-upper-2-challenge-unknown-factor-v1'
    row_id = 'math-g2-upper:2:tables'
    set_role(rows, row_id, 'transfer', unknown_factor, 'direct',
             '从已知积减去一个等组，再确定相邻乘积；与直接回忆乘积采用不同求解动作。')
    add_mapping(rows, questions, 'math-g2-upper:3:quotient',
                'family-chapter-math-g2-upper-3-depth-equal-distinguish-2-v1', 'distinguish', 'direct',
                '核对除法中已知份数、每份量与求得商的角色，直接对应除数和商的含义。')
    add_mapping(rows, questions, 'math-g2-upper:4:units',
                'family-chapter-math-g2-upper-4-multistep-ribbon-plan-v1', 'apply', 'direct',
                '必须先将1米换成100厘米，再逐项核对已用、剩余和缺少的长度。')
    add_mapping(rows, questions, 'math-g2-upper:5:tables',
                'family-chapter-math-g2-upper-5-multistep-array-removal-v1', 'apply', 'direct',
                '用7～9乘法口诀计算方阵总数和整列数量，再核对移除后的乘积。')
    for question_id in (
        'family-chapter-math-g2-upper-5-math_gaps-regroup-total-v1',
        'family-chapter-math-g2-upper-5-math_gaps-recover-total-v1',
    ):
        add_mapping(rows, questions, 'math-g2-upper:5:quotient', question_id, 'apply', 'direct',
                    '直接用7～9乘法口诀求商，题目分别检验求份数与反推总量两种分组情境。')
        add_mapping(rows, questions, 'math-g2-upper:5:quotient', question_id, 'distinguish', 'direct',
                    '明确区分给定每份量与给定份数，两题分别检验固定总量改分及反推总量。')

    add_mapping(rows, questions, 'math-g7-upper:1:signed',
                'family-chapter-math-g7-upper-1-depth-signed-04-v1', 'distinguish', 'direct',
                '从实测值与标准值区分绝对长度和带符号的偏差量，并核对允许范围。')
    add_mapping(rows, questions, 'math-g7-upper:1:rational',
                'family-chapter-math-g7-upper-1-depth-rational-04-v1', 'apply', 'direct',
                '按整数/非整数后再按正负的两级标准给有理数分类，直接对应分类要求。')

    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    (ROOT / 'learning_service/data/family_subject_coverage_plan_v7.json').write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main():
    questions = bank()
    print('math-v7', build_math(questions))
    print('subject-v6', build_subject(questions))


if __name__ == '__main__':
    main()
