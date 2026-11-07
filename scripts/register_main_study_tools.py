"""Register only the new private read-only Tool requested by the family owner.

No credentials or broad WebUI reads. The exact bound owner is resolved inside
family storage; stdout records only hashes. Use native-validated source/specs.
Plain SQLite avoids importing production configuration or secret loaders.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'learning_data/verification/main-chat-study-20261107'
SOURCE = ROOT / 'deploy/open-webui-reuse/readonly_study_tools.py'
TOOL_ID = 'dd_family_study_readonly_v1'

PROGRAM = r'''
import hashlib,json,sqlite3,sys,time,uuid
payload=json.load(sys.stdin)
mode=payload['mode']; assert mode in {'prepare','apply'}
assert payload['id']=='dd_family_study_readonly_v1'
source=payload['source']; sha=hashlib.sha256(source.encode()).hexdigest()
assert sha==payload['source_sha256']
conn=sqlite3.connect('file:'+sys.argv[1]+('?mode=ro' if mode=='prepare' else '?mode=rw'),uri=True,timeout=10)
conn.row_factory=sqlite3.Row
if mode=='apply': conn.execute('BEGIN IMMEDIATE')
role=conn.execute('SELECT role FROM user WHERE id=?',(payload['owner'],)).fetchone()
assert role and role[0] in {'admin','user'}, 'Bound owner is unavailable'
for table,names in [('tool',{'id','version_id','user_id','name','content','specs','meta','valves','created_at','updated_at'}),
                    ('tool_history',{'id','tool_id','parent_id','snapshot','user_id','commit_message','created_at'})]:
    assert names.issubset({r['name'] for r in conn.execute('PRAGMA table_info('+table+')')}), 'Unexpected Tool schema'
row=conn.execute('SELECT id,user_id,content,specs,meta,version_id FROM tool WHERE id=?',(payload['id'],)).fetchone()
if row:
    assert row['user_id']==payload['owner'] and row['content']==source and json.loads(row['specs'])==payload['specs'], 'Existing Tool differs; preserve it'
    state='already_matching'
else:
    state='absent'
if mode=='apply' and not row:
    now=int(time.time()); version=str(uuid.uuid4())
    meta={'description':'按当前家庭档案查教材、概念和关联练习，原页核对；不修改学习记录。',
          'manifest':payload['metadata'],'has_user_valves':False}
    snapshot={'name':'课本伴学（只读）','content':source,'meta':{'description':meta['description']}}
    conn.execute('INSERT INTO tool (id,version_id,user_id,name,content,specs,meta,valves,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
       (payload['id'],version,payload['owner'],snapshot['name'],source,json.dumps(payload['specs'],ensure_ascii=False),json.dumps(meta,ensure_ascii=False),None,now,now))
    conn.execute('INSERT INTO tool_history (id,tool_id,parent_id,snapshot,user_id,commit_message,created_at) VALUES (?,?,?,?,?,?,?)',
       (version,payload['id'],None,json.dumps(snapshot,ensure_ascii=False),payload['owner'],'新增家庭只读教材与学科伴学工具',now))
    assert conn.total_changes==2
    state='created_private'
if mode=='apply': conn.commit()
print(json.dumps({'tool_id':payload['id'],'state':state,'source_sha256':sha,
 'owner_sha256':hashlib.sha256(payload['owner'].encode()).hexdigest(),'row_changes':conn.total_changes,
 'methods':[s['name'] for s in payload['specs']],'secrets_read':False,'other_tools_modified':False}))
conn.close()
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    native=json.loads((OUT/'native-tools.json').read_text())
    source=SOURCE.read_text(); digest=hashlib.sha256(source.encode()).hexdigest()
    assert native['passed'] and native['source_sha256']==digest and len(native['specs'])==6
    # Resolve only the existing owner binding, never browser sessions or tokens.
    code="import sqlite3,json; c=sqlite3.connect('file:/var/lib/dd-learning/learning.db?mode=ro',uri=True); rows=c.execute(\"SELECT subject FROM identity_bindings WHERE provider='open-webui' AND issuer='family-pilot-webui'\").fetchall(); assert len(rows)==1; print(json.dumps(rows[0][0]))"
    owner=json.loads(subprocess.check_output(['docker','exec','dd-family-math-learning-api-1','python','-c',code],text=True))
    payload={'mode':'apply' if args.apply else 'prepare','id':TOOL_ID,'owner':owner,'source':source,
             'source_sha256':digest,'specs':native['specs'],'metadata':native['metadata']}
    if args.apply:
        prepared=json.loads((OUT/'registration-prepared.json').read_text())
        assert prepared['source_sha256']==digest and prepared['owner_sha256']==hashlib.sha256(owner.encode()).hexdigest()
    result=subprocess.run(['docker','exec','-i','open-webui','python','-c',PROGRAM,'/app/backend/data/webui.db'],
        input=json.dumps(payload),text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError('Target Tool registration validation failed; no existing Tool was overwritten.')
    report=json.loads(result.stdout)
    (OUT/('registration-applied.json' if args.apply else 'registration-prepared.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
