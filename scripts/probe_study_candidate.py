"""Smoke-test the sealed service image with a fresh synthetic family only."""
import json
from pathlib import Path
import sys
import threading
import time
from urllib.request import urlopen
import uvicorn

sys.path.insert(0,'/tmp/dd-probe-scripts')
from prepare_family_math import prepare
from learning_service.app import create_app
from learning_service.config import Settings
from learning_service.db import Database
from learning_service.learner_context import select_context
from learning_service.math_references import load_reference
from learning_service.practice import install
from learning_service import tools as module

directory=Path('/var/lib/dd-learning/synthetic-family')
prepare(directory,'synthetic-parent');db=Database(directory/'learning.db');install(db)
settings=Settings(directory,db.path,directory/'attachments','synthetic-admin','synthetic-adapter',False,
                  shared_learner_context_enabled=True,textbook_dir=Path('/tmp/dd-public-books'))
server=uvicorn.Server(uvicorn.Config(create_app(settings,db),host='127.0.0.1',port=31010,log_level='warning'))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
for _ in range(50):
    try:
        with urlopen('http://127.0.0.1:31010/health',timeout=1) as response:
            assert response.status==200
        break
    except OSError:
        time.sleep(.1)
else:
    raise AssertionError('synthetic service did not start')
with db.session() as conn:
    account=conn.execute("SELECT account_id FROM identity_bindings WHERE subject='synthetic-parent'").fetchone()[0]
with db.session(write=True) as conn:select_context(conn,account,'family-g2',0)
tool=module.Tools();tool.account_id=tool.learner_id=''
tool.valves.DD_LEARNING_BASE_URL='http://127.0.0.1:31010'
tool.valves.DD_LEARNING_ADAPTER_SECRET='synthetic-adapter'
tool.valves.DD_TRUSTED_ISSUER='family-pilot-webui';tool.valves.DD_TRUSTED_SUBJECT=''
tool.valves.DD_SHARED_LEARNER_CONTEXT=True
user={'id':'synthetic-parent'}
assert len(load_reference()['question_mappings'])==20
assert json.loads(tool.get_math_scope(chapter_id='3',__user__=user))['mapped_question_count']==4
assert json.loads(tool.get_math_question_reference('family-word-g2-share-1-v1',__user__=user))['mapping_status']=='mapped'
assert json.loads(tool.get_math_concept_reference('g2-share',chapter_id='3',__user__=user))['concepts'][0]['id']=='g2-share'
with db.session(write=True) as conn:select_context(conn,account,'family-g7',1)
for subject in ('math','chinese','english','ethics','history','geography','biology'):
    result=json.loads(tool.get_study_support(subject,chapter_id='2',__user__=user))
    assert result['scope']['grade']==7 and result['scope']['subject']==subject
assert json.loads(tool.get_math_concept_reference('g7-solve',chapter_id='5',__user__=user))['prerequisites'][0]['id']=='g7-equality'
with db.session() as conn:
    assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0]==0
with urlopen('http://127.0.0.1:31010/ui',timeout=5) as response:
    ui=response.read().decode()
assert all(text in ui for text in ('打开理解工坊','id="studySupport"','loadStudySupport','下载学习卡'))
assert 'STUDY_SUPPORT_SCRIPT' not in ui and 'STUDY_SUPPORT_PANEL' not in ui
for name in ('faststudy-LICENSE-DATA.txt','faststudy-NOTICE.txt'):
    assert (Path(module.__file__).parent/'data'/name).is_file()
server.should_exit=True;thread.join(timeout=5)
print(json.dumps({'sealed_image_runtime':'passed','fresh_synthetic_database':True,'reference_json_and_notice_in_image':True,
                  'math_queries':'passed','seven_subjects':'passed','provider_calls':0,'network':'none','formal_data_mounted':False}))
