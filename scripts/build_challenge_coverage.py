"""Append conservative mappings without changing any earlier inventory row."""
import hashlib,json,re
from pathlib import Path
from learning_service.chapter_practice import bank
p=json.loads(Path('learning_service/data/family_subject_coverage_plan_v1.json').read_bytes())
rows={r['id']:r for r in p['rows']};p['version']='subject-coverage-v2-challenge'
for q in bank('challenge_variety').values():
 k=q['knowledge'];r=rows[k['point_id']];assert k['task'] in r['requirements']
 assert k['role']=='supporting'
 raw=json.dumps(q,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 r['mappings'].append(dict(question_version_id=q['id'],question_sha256=hashlib.sha256(raw).hexdigest(),**{x:k[x] for x in ('task','family','role','rationale')}))
raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();Path('learning_service/data/family_subject_coverage_plan_v2.json').write_bytes(raw)
path=Path('learning_service/subject_coverage.py');s=path.read_text().replace('family_subject_coverage_plan_v1.json','family_subject_coverage_plan_v2.json');s=re.sub(r"SHA256='[a-f0-9]+'","SHA256='"+hashlib.sha256(raw).hexdigest()+"'",s);path.write_text(s)
print('challenge mappings:',98)
