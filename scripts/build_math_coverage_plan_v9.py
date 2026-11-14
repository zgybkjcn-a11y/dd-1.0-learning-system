"""Extend reviewed math mappings from the preserved v10/v9 candidate pair."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from learning_service.chapter_practice import bank as chapter_bank
from learning_service.practice import bank as initial_bank
from learning_service.reserve_practice import bank as reserve_bank
from scripts.build_math_coverage_plan_v7 import add_mapping


SOURCES = (
    ('learning_service/data/family_math_coverage_plan_v10.json',
     '5a5e0ba4cfb8fddb8d43a2ba13de1bd3101fa1176810e25a1d1d533c01982b96',
     'learning_service/data/family_math_coverage_plan_v11.json',
     '2026-11-12-v11-g7-chapter1-action-review'),
    ('learning_service/data/family_subject_coverage_plan_v9.json',
     '965ac5088141fca0a4ef7a42bf52338bd50e6a2646eecde972d4a5a1e20c0a86',
     'learning_service/data/family_subject_coverage_plan_v10.json',
     'subject-coverage-v10-g7-chapter1-action-review-2026-11-12'),
)


def main():
    questions = initial_bank() | reserve_bank() | chapter_bank()
    decisions = (
        ('math-g7-upper:1:signed', 'apply', 'family-chapter-math-g7-upper-1-depth-signed-04-v1',
         '实测值减标准值，再按正负判断偏差方向与范围；不同于依据“取出/低于”直接把变化记为负数。'),
        ('math-g7-upper:1:absolute', 'apply', 'family-chapter-math-g7-upper-1-depth-absolute-01-v1',
         '从数轴上的点到原点距离求绝对值，直接应用定义；不同于对给定负数表达式取绝对值。'),
    )
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
        for point_id, task, question_id, rationale in decisions:
            add_mapping(rows, questions, point_id, question_id, task, 'direct', rationale)
        data['version'] = version
        output = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        target_path.write_bytes(output)
        print(destination, hashlib.sha256(output).hexdigest())


if __name__ == '__main__':
    main()
