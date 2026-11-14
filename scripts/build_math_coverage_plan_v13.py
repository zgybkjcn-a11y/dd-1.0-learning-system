"""Reconcile reviewed math action roles with bounded and human requirements."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_math_coverage_plan_v7 import set_role


SOURCES = (
    ('learning_service/data/family_math_coverage_plan_v14.json',
     'c99e9b16c549c8a8088117c2f11c91e7bdaff9e83fa040edd9c9293709fbcad1',
     'learning_service/data/family_math_coverage_plan_v15.json',
     '2026-11-12-v15-cross-plan-action-review'),
    ('learning_service/data/family_subject_coverage_plan_v13.json',
     '94bdbad224f66032709df359890c5825c712645ff5b2801444dc3eda06b144ae',
     'learning_service/data/family_subject_coverage_plan_v14.json',
     'subject-coverage-v14-cross-plan-action-review-2026-11-12'),
)


PROMOTE_MATH = (
    ('math-g2-upper:1:compare', 'understand',
     'family-chapter-math-g2-upper-1-depth-compare-understand-1-v1',
     '直接读取分类记录中某类数量的含义，对应有界的记录辨认；不表示能自主提出问题。'),
    ('math-g2-upper:2:word', 'understand',
     'family-chapter-math-g2-upper-2-depth-word-understand-1-v1',
     '直接辨认每份量和份数的已知值，对应有界识别；不替代口头解释乘法意义。'),
    ('math-g2-upper:3:word', 'understand',
     'family-chapter-math-g2-upper-3-depth-word-understand-1-v1',
     '直接辨认求组数所需的总量与每份量，对应有界关系识别。'),
    ('math-g2-upper:5:word', 'understand',
     'family-chapter-math-g2-upper-5-depth-word-understand-1-v1',
     '直接从情境辨认每盒数量、盒数和总量关系，对应有界关系识别。'),
    ('math-g2-upper:activity1:direction', 'understand',
     'family-chapter-math-g2-upper-activity1-depth-direction-understand-1-v1',
     '直接识别一组相对方向，对应有界方向知识辨认。'),
    ('math-g7-upper:6:shapes', 'understand',
     'family-chapter-math-g7-upper-6-depth-shapes-01-v1',
     '直接从常见图形选项中辨认平面图形，对应本项有界识别。'),
)

DEMOTE_MATH = (
    ('math-g2-upper:activity2:body', 'apply',
     tuple('family-chapter-math-g2-upper-activity2-' + suffix + '-v1'
           for suffix in ('01', '02', '04', '05', '07', '08', '10', '11')),
     '题目给定身体尺单位长度与使用次数后只要求计算，没有观察实际校准和测量过程；保留为辅助。'),
    ('math-g2-upper:activity2:body', 'distinguish',
     tuple('family-chapter-math-g2-upper-activity2-' + suffix + '-v1'
           for suffix in ('03', '06', '09', '12')),
     '题目只用已给的同一人的拃长求物体长度，另一人的拃长没有参与判断；不能直接证明会辨析不同身体尺。'),
    ('math-g7-upper:1:line', 'apply',
     ('family-chapter-math-g7-upper-1-depth-line-02-v1',),
     '题目给出现成数轴并要求读出点的数值，没有要求独立标示或说明数轴表示；保留为辅助。'),
)


def main():
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
        if source.endswith('family_math_coverage_plan_v14.json'):
            for row_id, task, question_id, rationale in PROMOTE_MATH:
                set_role(rows, row_id, task, question_id, 'direct', rationale)
            for row_id, task, question_ids, rationale in DEMOTE_MATH:
                for question_id in question_ids:
                    set_role(rows, row_id, task, question_id, 'supporting', rationale)

        data['version'] = version
        output = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        target_path.write_bytes(output)
        print(destination, hashlib.sha256(output).hexdigest())


if __name__ == '__main__':
    main()
