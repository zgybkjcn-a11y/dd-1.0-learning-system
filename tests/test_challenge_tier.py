"""Challenge coverage, selection contracts, real grading and populated migrations."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import hashlib,json,shutil,sqlite3
import pytest
from learning_service import chapter_practice as chapter,subject_coverage
from learning_service.app import run_worker_once
from learning_service.db import Database
from learning_service.practice import guidance
from learning_service.practice_response import grade_short_fields,selection_values,validate_short_key
from practice_catalogue import PRACTICE_BOOKS
from test_family_math import family


def pick(book,ch):return next(q for q in chapter.bank('challenge_variety').values() if (q['book_id'],q['chapter_id'])==(book,str(ch)))
def values(q):
 return [([f['options'][int(n)-1] for n in f['answer'].split(',')] if f['options'] else Fraction(f['answer']) if f['kind']=='number' else f['answer']) for f in q['responses']]

def test_inventory_prior_bytes_and_coverage_mappings():
 qs=chapter.bank('challenge_variety');assert len(qs)==98
 assert Counter((q['book_id'],q['chapter_id']) for q in qs.values())==Counter((b['id'],c['id']) for b in PRACTICE_BOOKS for c in b['chapters'])
 assert all(q['difficulty']=='challenge' and q['extension'] and len(q['responses'])>=2 for q in qs.values())
 assert {'multi','order','number','choice','text'}=={f['kind'] for q in qs.values() for f in q['responses']}
 for b in PRACTICE_BOOKS:assert any(f['kind'] in ('multi','order') for q in qs.values() if q['book_id']==b['id'] for f in q['responses']) or b['id']=='math-g7-upper'
 old=json.loads(Path('learning_service/data/family_subject_coverage_plan_v1.json').read_bytes());new=json.loads(Path('learning_service/data/family_subject_coverage_plan_v2.json').read_bytes())
 for a,b in zip(old['rows'],new['rows'],strict=True):
  assert {k:v for k,v in a.items() if k!='mappings'}=={k:v for k,v in b.items() if k!='mappings'}
  assert b['mappings'][:len(a['mappings'])]==a['mappings']
  assert all(m['role']=='supporting' for m in b['mappings'][len(a['mappings']):])
 # Pinned old banks still load with their original digests; baseline plan is immutable.
 assert hashlib.sha256(Path('learning_service/data/family_subject_coverage_plan_v1.json').read_bytes()).hexdigest()=='2d55b184245224650c329e6d199a342adaad6780062b25c2be68d63b4066d43b'
 assert len(set(chapter.bank())-set(chapter.bank('math_gaps')))==1145
 assert len(chapter.bank())==1155
 from learning_service.reserve_practice import bank as reserve
 assert len(reserve())==12 and {q['difficulty'] for q in reserve().values()}=={'easy','normal','hard'}
 for grade in (2,7):subject_coverage.report(f'math-g{grade}-v1',set(chapter.bank()))

@pytest.mark.parametrize('raw',['','0','7','1,1','1,7','1,2,','1;2','1 2','[1,2]','true','-1','1.0',None,[],{},'1'*81])
def test_reject_malformed_selections(raw):
 assert selection_values(raw,4,'multi') is None
 assert selection_values(raw,4,'order') is None

def test_order_requires_permutation_and_multi_is_unordered():
 assert selection_values(' ２, １ ',4,'multi')==(1,2)
 assert selection_values('4,3,2,1',4,'order')==(4,3,2,1)
 assert selection_values('1,2,3',4,'order') is None
 for q in chapter.bank('challenge_variety').values():
  key=json.loads(chapter.stored(q)['answer_key_json']);assert grade_short_fields(q['answer'],key)[0]=='correct'
  for f in q['responses']:
   raw=json.loads(q['answer'])
   if f['kind']=='multi':
    raw[f['id']]=','.join(reversed(f['answer'].split(',')));assert grade_short_fields(json.dumps(raw),key)[0]=='correct'
    expected=set(f['answer'].split(','));raw[f['id']]=','.join(sorted(expected^{str(next(i for i in range(1,len(f['options'])+1) if str(i) not in expected))}))
   elif f['kind']=='order':raw[f['id']]=','.join(reversed(f['answer'].split(',')))
   else:raw[f['id']]='wrong'
   result,feedback=grade_short_fields(json.dumps(raw),key);assert result=='incorrect' and f['label'] in feedback
  for raw in ('{}','[]','null',q['answer'][:-1]+',"x":"1"}', '{"a":"1","a":"2"}'):
   assert grade_short_fields(raw,key)[0]=='incorrect'

@pytest.mark.parametrize('mutation',['selection','options','kind','units','missing','duplicate'])
def test_tampered_keys_fail_closed(mutation):
 key=json.loads(chapter.stored(pick('chinese-g2-upper',1))['answer_key_json']);f=key['field_answers'][0]
 if mutation=='selection':f['selection']='1,1'
 elif mutation=='options':f['options']=list(reversed(f['options']))
 elif mutation=='kind':f['kind']='number'
 elif mutation=='units':f['units']=['元']
 elif mutation=='missing':f.pop('selection')
 else:key['response_fields'][0]['options'][1]=key['response_fields'][0]['options'][0]
 assert grade_short_fields('{}',key)[0]=='undetermined'
 with pytest.raises(ValueError):validate_short_key(key['response_fields'],key['field_answers'])

def test_mathematical_answers_against_enumerated_constraints():
 v=lambda b,ch:values(pick(b,ch))
 x=v('math-g2-upper',2);schemes=[(3,1),(2,2),(1,3),(0,4)]
 feasible=[(8*l+6*s,6*l+4*s-19,l,s) for l,s in schemes if 6*l+4*s>=19]
 assert x[1:]==list(min(feasible)[:2])
 x=v('math-g2-upper',3);assert x[0]*5==30 and x[0]-x[1]==30/6
 x=v('math-g2-upper',4);lengths={'甲':9-2,'乙':11-5,'丙':9-1};assert x[0]==sorted(lengths,key=lengths.get) and x[1]==max(lengths.values())-min(lengths.values())
 x=v('math-g2-upper',5);assert x[:2]==[3,6];assert set(x[2])=={f'{l}大{s}小' for l,s in [(4,1),(2,5),(3,2),(1,6)] if 8*l+4*s==36}
 x=v('math-g7-upper',1);ps=[p for p in range(-10,11) if abs(p+3)==2];assert set(x[0])=={str(p).replace('-','−') for p in ps};assert x[1]==(-3+5)/2 and x[2]==min(abs(p-x[1]) for p in ps)
 assert v('math-g7-upper',2)[:2]==[['A','C','B'],20]
 x=v('math-g7-upper',4);k,coeff,result=x;assert 2-k==0 and coeff==-3-4*k and result==coeff*(-1)+1+2*k
 x=v('math-g7-upper',5);assert x[0]==5 and set(x[1])=={'4小时10分','5小时'} and x[2]==9
 assert v('math-g7-upper',6)[:2]==[80,60]
 assert v('math-g7-lower',7)[:2]==[20,105]
 assert v('math-g7-lower',9)==[-2,2,8]
 x=v('math-g7-lower',10);assert x[0]+x[1]==10 and 20*x[0]+12*x[1]==152
 x=v('math-g7-lower',11);solutions=[n for n in range(1,30) if 20+10*n<8+12*n and 20+10*n<=100];assert x[:2]==[min(solutions),max(solutions)] and set(x[2])==set(map(str,solutions))
 data=[12,15,18,20,20,22,25,28];x=v('math-g7-lower',12);assert x[:3]==[sum(n<20 for n in data),sum(n<21 for n in data),100*Fraction(sum(20<=n<21 for n in data),len(data))]
 assert v('history-g7-upper',5)[:2]==[['甲','丙','丁','乙'],4]
 assert v('geography-g7-upper',3)[:2]==[4,2]
 assert v('geography-g7-upper',6)[:2]==[200,400]
 assert v('biology-g7-upper',3)[:2]==[16,'分化']
 assert v('english-g7-upper',9)[:3]==['takes','visit',15]
 assert v('english-g7-upper',12)[:2]==['library',25]


def test_fourth_tier_progression_and_top_bound():
 def r(i,level='hard',outcome='correct',assistance='none'):return dict(question_version_id=str(i),difficulty=level,outcome=outcome,assistance=assistance,assessment_eligibility=assistance=='none')
 assert guidance([r(1)]*10)['difficulty']=='easy'
 assert guidance([r(i) for i in range(3)])['difficulty']=='easy'
 history=[r(i) for i in range(4)];assert guidance(history)['difficulty']=='challenge'
 assert guidance(history+[r(i+4,'challenge') for i in range(10)])['difficulty']=='challenge'
 for changes in ({'outcome':'incorrect'},{'assistance':'hint'}):assert guidance(history+[r(10,'challenge',**changes)])['difficulty']=='hard'


def test_every_new_question_api_grade_restore_privacy_collection(family):
 _,db,api,headers=family
 assert chapter.install(db,'challenge_variety')['added']==98
 assert chapter.install(db,'challenge_variety')['added']==0
 wrong=None
 for q in [*chapter.bank('challenge_variety').values(),pick('biology-g7-upper',7)]:
  h={**headers,'X-Learner-Id':f"family-g{q['grade']}"}
  response=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'textbook_book_id':q['book_id'],'textbook_chapter_id':q['chapter_id']});assert response.status_code==201,response.text
  session=response.json();item=session['items'][0]
  restored=api.get('/api/v1/test-sessions/'+session['session_id'],headers=h);assert restored.json()['items'][0]['response_fields']==item['response_fields']
  assert session['answer_key'] is None and not any(term in response.text+restored.text for term in ('field_answers','selection','accepted','case_sensitive'))
  foreign={**headers,'X-Learner-Id':'family-g7' if q['grade']==2 else 'family-g2'}
  assert api.get('/api/v1/test-sessions/'+session['session_id'],headers=foreign).status_code in (403,404)
  raw=q['answer'] if wrong is None else json.dumps({**json.loads(q['answer']),'a':'wrong'})
  token=api.post(f"/api/v1/test-items/{item['test_item_id']}/submission-challenges",headers=h).json()
  body={k:token[k] for k in ('challenge_id','nonce')}|{'raw_answer':raw};url=f"/api/v1/test-items/{item['test_item_id']}/answers";hh=h|{'Idempotency-Key':item['test_item_id']}
  answer=api.post(url,headers=hh,json=body);assert answer.status_code==202,answer.text
  assert api.post(url,headers=hh,json=body).json()==answer.json()
  run_worker_once(db,api.app.state.settings);aid=answer.json()['attempt_id'];assert api.get('/api/v1/attempts/'+aid,headers=h).json()['outcome']==('correct' if wrong is None else 'incorrect')
  if q==list(chapter.bank('challenge_variety').values())[-1]:wrong=True
 preview=api.get(f'/api/v1/attempts/{aid}/collection-preview',headers=h);assert preview.status_code==200
 result=api.post(f'/api/v1/attempts/{aid}/collection',headers=h|{'Idempotency-Key':'new-collect'},json={'confirmed':True,'preview_sha256':preview.json()['preview_sha256']});assert result.status_code==201,result.text
 with db.session() as c:
  snap=json.loads(c.execute('SELECT content_json FROM mistake_entries WHERE id=?',(result.json()['mistake_id'],)).fetchone()[0]);assert snap['response_fields']==item['response_fields'];assert snap['student_answer']==raw
  assert c.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0

@pytest.mark.parametrize('failure',['none','sql','reference','admin'])
def test_populated_schema13_migration_is_atomic_and_idempotent(tmp_path,monkeypatch,failure):
 import prepare_family_math as setup
 from fastapi.testclient import TestClient
 from learning_service.app import create_app
 from learning_service.config import Settings
 migrations=tmp_path/'learning_service/migrations';migrations.mkdir(parents=True)
 import learning_service.identity_admin as identity
 monkeypatch.setattr(identity,'ROOT',tmp_path)
 for p in Path('learning_service/migrations').glob('*.sql'):
  if int(p.name.split('_')[0])<=13:shutil.copyfile(p,migrations/p.name)
 monkeypatch.setattr(setup,'Database',lambda p:Database(p,migrations))
 directory=tmp_path/'family';setup.prepare(directory,'synthetic-parent');db=Database(directory/'learning.db',migrations)
 chapter.install(db,'math')
 settings=Settings(directory,db.path,directory/'attachments','synthetic-admin','synthetic-adapter',False)
 api=TestClient(create_app(settings,db));h={'X-Adapter-Secret':'synthetic-adapter','X-Trusted-Provider':'open-webui','X-Trusted-Issuer':'family-pilot-webui','X-Trusted-Subject':'synthetic-parent','X-Learner-Id':'family-g7'}
 cfg=api.put('/api/v1/practice-workspace',headers=h,json={'expected_revision':0,'book_id':'math-g7-upper','chapter_id':'1','difficulty':'hard','pool':'initial'});assert cfg.status_code==200,cfg.text
 q=next(q for q in chapter.bank('math').values() if q['book_id']=='math-g7-upper' and q['chapter_id']=='1' and q['difficulty']=='hard')
 s=api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'workspace_revision':cfg.json()['revision'],'textbook_book_id':q['book_id'],'textbook_chapter_id':'1'});assert s.status_code==201,s.text
 with db.session() as c:
  tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
  before={t:{tuple(r) for r in c.execute('SELECT * FROM "'+t+'"')} for t in tables}
  assert any(r['practice_round_id'] for r in c.execute('SELECT * FROM test_items'))
 script=Path('learning_service/migrations/014_challenge_difficulty.sql').read_text()
 if failure=='sql':script+='\nINSERT INTO missing_table VALUES (1);'
 if failure=='reference':script+="\nUPDATE test_items SET practice_round_id='missing';"
 target=migrations/'014_challenge_difficulty.sql';target.write_text(script)
 if failure in ('sql','reference'):
  with pytest.raises((ValueError,sqlite3.OperationalError)):Database(db.path,migrations)
  with db.session() as c:
   for t,rows in before.items():assert rows=={tuple(r) for r in c.execute('SELECT * FROM "'+t+'"')}
   assert c.execute('PRAGMA foreign_keys').fetchone()[0]==1
  target.write_text(Path('learning_service/migrations/014_challenge_difficulty.sql').read_text())
 if failure=='admin':
  manifest={'format':'dd-learning-identities-v1','initialize_math':False,**{k:[] for k in identity.ROWS}}
  plan=identity.plan_identity(manifest,db.path,'test-upgrade')
  identity.apply_identity(manifest,db.path,'test-upgrade',plan['plan_sha256'])
  with db.session(write=True) as c:c.execute("DELETE FROM audit_events WHERE operation='identity_manifest_apply' AND account_id='test-upgrade'")
 with ThreadPoolExecutor(2) as pool:list(pool.map(lambda _:Database(db.path,migrations),range(2)))
 new=Database(db.path,migrations)
 with new.session() as c:
  for t,rows in before.items():
   current={tuple(r) for r in c.execute('SELECT * FROM "'+t+'"')}
   assert rows<=current if t=='schema_migrations' else rows==current
  assert c.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==14
  assert not c.execute('PRAGMA foreign_key_check').fetchall()
 with new.session(write=True) as c:
  c.execute("UPDATE practice_workspaces SET difficulty='challenge'")
  c.execute("UPDATE practice_rounds SET difficulty='challenge'")
  with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE practice_workspaces SET difficulty='invented'")
  with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE test_items SET practice_round_id='invented'")
