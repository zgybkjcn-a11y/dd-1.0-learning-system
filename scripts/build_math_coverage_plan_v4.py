"""Append challenge mappings; preserve explicit expression/practical limits."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.chapter_practice import bank

ROOT = Path(__file__).resolve().parents[1]


def build():
    data = json.loads((ROOT/'learning_service/data/family_math_coverage_plan_v3.json').read_bytes())
    data['version'] = '2026-11-09-v4-g2-challenge'
    rows = {r['id']: r for r in data['rows']}
    for q in bank('math_g2_challenge').values():
        m = q['coverage']
        rows[m['point_id']]['mappings'].append({
            'question_version_id': q['id'],
            'question_sha256': hashlib.sha256(json.dumps(q,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            **{k:m[k] for k in ('task','family','role','rationale')},
        })
    raw = (json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
    (ROOT/'learning_service/data/family_math_coverage_plan_v4.json').write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    build()
