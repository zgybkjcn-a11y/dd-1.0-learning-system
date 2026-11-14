"""Derive chapter-four action mappings from the preserved v12/v11 plans."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from learning_service.chapter_practice import bank as chapter_bank
from learning_service.practice import bank as initial_bank
from learning_service.reserve_practice import bank as reserve_bank
from scripts.build_math_coverage_plan_v7 import add_mapping, set_role


SOURCES = (
    ('learning_service/data/family_math_coverage_plan_v12.json',
     'f2af8ae9e1cac592876bdccc30c368b00fa70dd72e8afa144dcb7f5ddb8f1396',
     'learning_service/data/family_math_coverage_plan_v13.json',
     '2026-11-12-v13-g7-chapter4-action-review'),
    ('learning_service/data/family_subject_coverage_plan_v11.json',
     '4d1d54c0f60291a765504b3821da50f885dcb6ef712969a455d33d6565b6c9f9',
     'learning_service/data/family_subject_coverage_plan_v12.json',
     'subject-coverage-v12-g7-chapter4-action-review-2026-11-12'),
)

CANDIDATE_BATCH = ROOT / 'learning_service/data/family_chapter_math_g7_chapter4_action_candidates_v1.json'
CANDIDATE_BATCH_SHA256 = '9d0479b06dea7a68eb627016f41210cafad1be508f62c428d9ec720c524945d6'


def main():
    questions = initial_bank() | reserve_bank() | chapter_bank()
    candidate_raw = CANDIDATE_BATCH.read_bytes()
    if hashlib.sha256(candidate_raw).hexdigest() != CANDIDATE_BATCH_SHA256:
        raise ValueError('unexpected chapter-four candidate batch')
    candidate = json.loads(candidate_raw)
    questions.update({q['id']: q for q in candidate['questions']})

    for source, expected_sha, destination, version in SOURCES:
        source_path = ROOT / source
        raw = source_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            raise ValueError(f'unexpected source plan: {source}')
        target_path = ROOT / destination
        if target_path.exists():
            raise FileExistsError(destination)

        data = json.loads(raw)
        rows = {row['id']: row for row in data['rows']}

        application = 'math-g7-upper:4:application'
        subtract_question = 'family-chapter-math-g7-upper-4-depth-application-03-v1'
        set_role(rows, application, 'distinguish', subtract_question, 'supporting',
                 '题目只要求算出整式差，没有检查某人的错误步骤；改列为应用计算的直接题。')
        add_mapping(rows, questions, application, subtract_question, 'apply', 'direct',
                    '直接计算两个整式的差，检验减去整个括号时逐项变号；与已映射的整式求和是不同操作。')
        rows[application]['mappings'][-1]['family'] = 'g7:polynomial:subtract-whole-expression'

        # The structured task expands and combines two products before substitution.
        bracket = 'math-g7-upper:4:bracket'
        coefficient_task = 'family-chapter-math-g7-upper-4-math_g7_multistep-coefficients-v1'
        add_mapping(rows, questions, bracket, coefficient_task, 'apply', 'direct',
                    '分别展开正、负系数乘括号，再合并同类项；与单个正系数展开属于不同解题动作。')
        rows[bracket]['mappings'][-1]['family'] = 'g7:bracket:multiple-distribution-and-combine'

        candidate_id = 'family-chapter-math-g7-upper-4-action-subtract-expression-v1'
        add_mapping(rows, questions, application, candidate_id, 'distinguish', 'direct',
                    '定位减去括号时常数项漏变号的错误，并核验完整结果。')

        data['version'] = version
        output = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        target_path.write_bytes(output)
        print(destination, hashlib.sha256(output).hexdigest())


if __name__ == '__main__':
    main()
