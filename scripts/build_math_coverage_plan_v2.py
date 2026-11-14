"""Append reviewed point mappings without modifying the published v1 inventory."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.chapter_practice import bank

ROOT = Path(__file__).resolve().parents[1]


def build():
    data = json.loads((ROOT/'learning_service/data/family_math_coverage_plan_v1.json').read_bytes())
    data['version'] = '2026-11-09-v2-g2-depth'
    data['mapping_policy'] = 'direct_tasks_count_toward_target; explanation_recognition_is_supporting_only'
    by_id = {r['id']: r for r in data['rows']}
    # Narrow or clarify requirements using the local textbook topics. These are
    # still an assistant's inventory, not a curriculum-standard or teacher signoff.
    refinements = {
        '1:classify': {'distinguish': '检查分类标准是否混用及有无遗漏'},
        '1:compare': {'apply': '从分类记录求总数或比较数量'},
        '3:word': {'distinguish': '辨析先后顺序及给一人与给每人的区别'},
        'activity1:route': {'distinguish': '检查路线起点和分段参照位置'},
        '4:ruler': {'distinguish': '辨析起点刻度和尺子摆放错误'},
        '6:relations': {'distinguish': '辨析所求量和相同份数是否与算式匹配'},
    }
    pages = {'2:word': 24, '4:units': 58, '4:ruler': 56, '4:estimate': 60,
             'activity1:route': 52, '5:word': 83, '6:organize': 93}
    for short_id, tasks in refinements.items():
        row = by_id['math-g2-upper:' + short_id]
        row['requirements'].update(tasks)
    for short_id, page in pages.items():
        by_id['math-g2-upper:' + short_id]['printed_page'] = page
    for q in bank('math_g2_depth').values():
        m = q['coverage']
        row = by_id[m['point_id']]
        assert (q['book_id'], q['chapter_id']) == (row['book_id'], row['chapter_id'])
        row['mappings'].append({
            'question_version_id': q['id'],
            'question_sha256': hashlib.sha256(json.dumps(q, ensure_ascii=False, sort_keys=True,
                                                       separators=(',', ':')).encode()).hexdigest(),
            'task': m['task'], 'family': m['family'], 'role': m['role'], 'rationale': m['rationale']})
    raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
    (ROOT/'learning_service/data/family_math_coverage_plan_v2.json').write_bytes(raw)
    print(len(data['rows']), hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    build()
