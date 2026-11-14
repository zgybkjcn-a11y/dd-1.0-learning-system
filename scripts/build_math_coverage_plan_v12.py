"""Derive chapter-six action mappings from the preserved v13/v12 plans."""
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
    ('learning_service/data/family_math_coverage_plan_v13.json',
     '8aa7c576425c17a9e73924139c144fef1f833bd54b9f40128952b741a6dabd3c',
     'learning_service/data/family_math_coverage_plan_v14.json',
     '2026-11-12-v14-g7-chapter6-action-review'),
    ('learning_service/data/family_subject_coverage_plan_v12.json',
     '33ee29e6ac5e711456170d3859061b692deb379d54d51806cae37a1d9b37c154',
     'learning_service/data/family_subject_coverage_plan_v13.json',
     'subject-coverage-v13-g7-chapter6-action-review-2026-11-12'),
)


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

        # Single-option recognition does not establish independent notation or measurement.
        set_role(rows, 'math-g7-upper:6:angle', 'apply',
                 'family-chapter-math-g7-upper-6-depth-angle-02-v1', 'supporting',
                 '只从选项中读出一个角的度分秒记法，不能证明能独立读写或用量角器测量。')
        set_role(rows, 'math-g7-upper:6:lines', 'apply',
                 'family-chapter-math-g7-upper-6-depth-lines-02-v1', 'supporting',
                 '只识别一条射线的表示，不能证明能独立画并表示线段、射线和直线。')

        shape_question = 'family-chapter-math-g7-upper-6-depth-shapes-01-v1'
        add_mapping(rows, questions, 'math-g7-upper:6:shapes', shape_question,
                    'distinguish', 'direct',
                    '要求从平面图形与立体图形选项中辨认平面图形，直接检验本项辨析。')

        data['version'] = version
        output = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        target_path.write_bytes(output)
        print(destination, hashlib.sha256(output).hexdigest())


if __name__ == '__main__':
    main()
