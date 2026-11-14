"""Derive chapter-two action mappings from the preserved v11/v10 plans."""
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
    ('learning_service/data/family_math_coverage_plan_v11.json',
     'e3313252d47d29732b8ec80240d6352c7fdd908fcb64a3cc38972ad851fb5590',
     'learning_service/data/family_math_coverage_plan_v12.json',
     '2026-11-12-v12-g7-chapter2-action-review'),
    ('learning_service/data/family_subject_coverage_plan_v10.json',
     '5f5f3faf8ea728840aee5d16d560e2d8f8717cbf412029437925140935b6dca5',
     'learning_service/data/family_subject_coverage_plan_v11.json',
     'subject-coverage-v11-g7-chapter2-action-review-2026-11-12'),
)

QUESTION_BATCH = ROOT / 'learning_service/data/family_chapter_math_g7_action_candidates_v1.json'
QUESTION_BATCH_SHA256 = '61026253b37bde71555d7780833da6b231a77c746b4308a3fce4bdc2f207e713'


def main():
    questions = initial_bank() | reserve_bank() | chapter_bank()
    batch_raw = QUESTION_BATCH.read_bytes()
    if hashlib.sha256(batch_raw).hexdigest() != QUESTION_BATCH_SHA256:
        raise ValueError('unexpected chapter-two candidate batch')
    batch = json.loads(batch_raw)
    questions.update({q['id']: q for q in batch['questions']})

    source_decisions = (
        ('math-g7-upper:2:subtract',
         'family-chapter-math-g7-upper-2-depth-subtract-03-v1',
         'family-chapter-math-g7-upper-2-01-v1',
         'g7:subtract:negative-subtrahend',
         '只要求计算5−(−3)=8，没有要求辨认他人错误或说明原因，不能作为“辨析”直接题。',
         '减数明确为负数，直接检验减去负数转化为加相反数；与一般有理数差计算属于不同解题动作。'),
        ('math-g7-upper:2:multiply',
         'family-chapter-math-g7-upper-2-depth-multiply-03-v1',
         'family-chapter-math-g7-upper-2-02-v1',
         'g7:multiply:negative-factor-parity',
         '题目只计算三个非零负因数的积，未涉及零因子，也没有辨认错误过程，不能据此覆盖完整辨析要求。',
         '须先判断负因数个数的奇偶再求积；与两负因数相乘的直接计算不同。'),
    )
    candidate_rationales = {
        'family-chapter-math-g7-upper-2-01-v1': '判断并修正“减去负数等于减去正数”的错误，要求给出等价转化和结果。',
        'family-chapter-math-g7-upper-2-02-v1': '同时检查奇数个负因数的积与含零因子的积，直接覆盖两类符号错误。',
    }

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
        for row_id, old_id, new_id, family, distinguish_note, apply_note in source_decisions:
            set_role(rows, row_id, 'distinguish', old_id, 'supporting', distinguish_note)
            add_mapping(rows, questions, row_id, old_id, 'apply', 'direct', apply_note)
            rows[row_id]['mappings'][-1]['family'] = family
            add_mapping(rows, questions, row_id, new_id, 'distinguish', 'direct',
                        candidate_rationales[new_id])

        data['version'] = version
        output = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        target_path.write_bytes(output)
        print(destination, hashlib.sha256(output).hexdigest())


if __name__ == '__main__':
    main()
