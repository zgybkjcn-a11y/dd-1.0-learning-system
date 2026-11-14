"""Derive a reviewed math coverage candidate without replacing earlier plans."""
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
    ('learning_service/data/family_math_coverage_plan_v8.json',
     '4e855d9ffa30e9cfca7ce40732a630423d28a1217b22fb79884275c3469c240c',
     'learning_service/data/family_math_coverage_plan_v10.json',
     '2026-11-12-v10-g2-single-action-review'),
    ('learning_service/data/family_subject_coverage_plan_v7.json',
     '7a9c93d4641763575613302263530e143862ec0d944bf476405dddf0527dd6de',
     'learning_service/data/family_subject_coverage_plan_v9.json',
     'subject-coverage-v9-g2-single-action-review-2026-11-12'),
)

WORD_GROUP_ID = 'family-chapter-math-g2-upper-2-depth-word-understand-2-v1'
WORD_TOTAL_ID = 'family-chapter-math-g2-upper-5-depth-word-understand-2-v1'
ARRAY_PRODUCT_ID = 'family-chapter-math-g2-upper-2-multistep-array-count-v1'
SHARE_SIZE_ID = 'family-word-g2-share-1-v1'


def main():
    questions = initial_bank() | reserve_bank() | chapter_bank()
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
        set_role(rows, 'math-g2-upper:2:word', 'understand', WORD_GROUP_ID, 'direct',
                 '选项明确对应每车4个轮子、3辆车即3组；直接核对每份量和份数，与单纯读乘积不同。此有界识别不代表能独立口述。')
        set_role(rows, 'math-g2-upper:5:word', 'understand', WORD_TOTAL_ID, 'direct',
                 '改为每袋4颗后，选择仍不变的珠子总数；直接识别总量与份数变化的关系，与按每份量求总数不同。此有界识别不代表能独立解释。')
        q = questions[ARRAY_PRODUCT_ID]
        if (q['book_id'], q['chapter_id']) != ('math-g2-upper', '2'):
            raise ValueError('array question scope changed')
        add_mapping(rows, questions, 'math-g2-upper:2:tables', ARRAY_PRODUCT_ID, 'apply', 'direct',
                    '先以4行、每行6个的位置模型求总数24，再扣除空位；这是数组模型求积，区别于直接回忆口诀。不能将分步字段数量另算题型。')
        quotient_row = rows['math-g2-upper:3:quotient']
        if any(m['question_version_id'] == SHARE_SIZE_ID and m['task'] == 'apply'
               for m in quotient_row['mappings']):
            raise ValueError('duplicate quotient application mapping')
        share_question = questions[SHARE_SIZE_ID]
        quotient_row['mappings'].append({
            'question_version_id': SHARE_SIZE_ID,
            'question_sha256': hashlib.sha256(json.dumps(
                share_question, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'task': 'apply',
            'family': 'g2:division:find-share-size',
            'role': 'direct',
            'rationale': '已知总量与3份求每份量，和已知每份量求份数是两种不同除法模型；本题已在同章安装，直接对应口诀求商，无需重编。',
        })
        data['version'] = version
        output = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        target_path.write_bytes(output)
        print(destination, hashlib.sha256(output).hexdigest())


if __name__ == '__main__':
    main()
