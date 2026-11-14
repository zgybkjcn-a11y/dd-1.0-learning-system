"""Append grade-seven mappings and audit legacy families without rewriting banks."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.chapter_practice import bank
from learning_service.practice import bank as word_bank
from learning_service.reserve_practice import bank as reserve_bank
from build_math_g7_depth import PAGES

ROOT = Path(__file__).resolve().parents[1]


def build():
    data = json.loads((ROOT/'learning_service/data/family_math_coverage_plan_v2.json').read_bytes())
    data['version'] = '2026-11-09-v3-g7-depth'
    by_id = {r['id']: r for r in data['rows']}
    questions = bank() | word_bank() | reserve_bank()
    # The same single operation in different stories is one family. A final
    # number alone cannot demonstrate the required explanation or equation.
    for row in data['rows']:
        if row['book_id'] != 'math-g7-upper':
            continue
        chapter, key = row['id'].split(':')[1:]
        row['printed_page'] = PAGES[chapter, key]
        if key == 'binary':
            row['title'] = row['title'].replace('（选学）', '').replace('(选学)', '')
        for mapping in row['mappings']:
            title = questions[mapping['question_version_id']]['title']
            if key == 'add' and mapping['task'] == 'apply':
                mapping['family'] = 'g7:add:signed-sum'
            if key == 'subtract' and title in ('记录一天温差', '两地温差'):
                mapping['family'] = 'g7:subtract:difference'
            if key == 'subtract' and title in ('两天的温度变化', '比较两天升温'):
                mapping['family'] = 'g7:subtract:compare-differences'
            if key == 'multiply' and title in ('确定两数乘积', '多个因子与小数'):
                mapping['family'] = 'g7:multiply:product'
            if (key == 'model' or (key == 'add' and mapping['task'] == 'transfer')):
                mapping['role'] = 'supporting'
                mapping['rationale'] = '原题只要求最终数值，未要求独立列方程或解释过程；仅计辅助练习。'
            if key == 'add' and title in ('水库三天的变化', '仓库出入货'):
                mapping['family'] = 'g7:add:successive-changes'
    # A signed route-distance problem has no continuous multiplication; fix
    # its point mapping, while retaining the original immutable question.
    multiply = by_id['math-g7-upper:2:multiply']['mappings']
    for mapping in list(multiply):
        if questions[mapping['question_version_id']]['title'] == '往返运输路程':
            multiply.remove(mapping)
            mapping.update(role='supporting', rationale='路线分段求和辅助理解多次变化，原题未要求乘法倍率或独立解释。')
            by_id['math-g7-upper:2:add']['mappings'].append(mapping)
    for q in bank('math_g7_depth').values():
        m = q['coverage']
        row = by_id[m['point_id']]
        assert (q['book_id'], q['chapter_id']) == (row['book_id'], row['chapter_id'])
        row['mappings'].append({
            'question_version_id': q['id'],
            'question_sha256': hashlib.sha256(json.dumps(q, ensure_ascii=False, sort_keys=True,
                                                       separators=(',', ':')).encode()).hexdigest(),
            **{k: m[k] for k in ('task', 'family', 'role', 'rationale')},
        })
    raw = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
    (ROOT/'learning_service/data/family_math_coverage_plan_v3.json').write_bytes(raw)
    print(len(data['rows']), hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    build()
