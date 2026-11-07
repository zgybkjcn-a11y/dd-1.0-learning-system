"""Run only in a fresh --network=none Open WebUI image, with synthetic data.

Mount learning_service and this script read-only, plus the two public upper
math PDFs. DATA_DIR must be disposable. Never run in the live WebUI container.
"""
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.error import HTTPError

assert os.environ['DATA_DIR'].startswith('/tmp/dd-reference-')
assert os.environ['ENABLE_OPENAI_API']=='false' and os.environ['ENABLE_OLLAMA_API']=='false'
assert os.environ['OFFLINE_MODE']=='true'
Path(os.environ['DATA_DIR']).mkdir(parents=True,exist_ok=True)
os.environ.update(LEARNING_DATA_DIR='/tmp/dd-reference-default-service',
                  LEARNING_DB_PATH='/tmp/dd-reference-default-service/learning.db',
                  LEARNING_ATTACHMENT_DIR='/tmp/dd-reference-default-service/attachments',
                  LEARNING_EXPORT_DIR='/tmp/dd-reference-default-service/exports')
os.environ['WEBUI_SECRET_KEY']='synthetic-native-loader-secret-0123456789abcdef'
sys.path.insert(0,'/candidate')
sys.path.insert(0,'/candidate/scripts')

from fastapi import Request
from fastapi.testclient import TestClient
from learning_service.app import create_app
from learning_service.config import Settings
from learning_service.db import Database
from learning_service.learner_context import select_context
from learning_service.practice import install
from prepare_family_math import prepare
from open_webui.utils import tools as native
from open_webui.utils.plugin import load_tool_module_by_id


class Response:
    def __init__(self, data): self.body=json.dumps(data).encode()
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self,*_): return False


async def main():
    directory=Path('/tmp/dd-reference-family')
    prepare(directory,'synthetic-parent')
    db=Database(directory/'learning.db');install(db)
    settings=Settings(directory,db.path,directory/'attachments','synthetic-admin','synthetic-adapter',False,
                      textbook_dir=Path('/candidate/books'),shared_learner_context_enabled=True)
    api=TestClient(create_app(settings,db))
    with db.session() as conn:
        account=conn.execute("SELECT account_id FROM identity_bindings WHERE subject='synthetic-parent'").fetchone()[0]
    with db.session(write=True) as conn:select_context(conn,account,'family-g2',0)
    source=Path('/candidate/learning_service/tools.py').read_text()
    tool,metadata,source_module=await load_tool_module_by_id('dd_reference_synthetic',content=source)
    assert metadata['version']=='1.2.0'
    calls=[]
    def send(request,timeout):
        path=request.full_url.split(':31010')[-1]
        headers=dict(request.header_items())
        calls.append((request.get_method(),path,headers))
        response=api.request(request.get_method(),path,headers=headers,content=request.data)
        if response.status_code>=400:
            raise HTTPError(request.full_url,response.status_code,'synthetic',{},io.BytesIO(response.content))
        return Response(response.json())
    source_module.urlopen=send
    tool_id='dd_reference_synthetic'
    record=SimpleNamespace(id=tool_id,user_id='synthetic-parent',content=source,specs=native.get_tool_specs(tool))
    async def groups(*args,**kwargs): return []
    async def models(ids): return {tool_id:record}
    async def valves(*args):
        return {'DD_LEARNING_BASE_URL':'http://learning-api:31010','DD_LEARNING_ADAPTER_SECRET':'synthetic-adapter',
                'DD_TRUSTED_ISSUER':'family-pilot-webui','DD_TRUSTED_SUBJECT':'','DD_SHARED_LEARNER_CONTEXT':True}
    async def user_valves(*args):return {'DD_LEARNER_ID':''}
    async def load(*args,**kwargs):return tool,metadata,source_module
    native.Groups.get_groups_by_member_id=groups
    native.Tools.get_tools_by_ids=models
    native.Tools.get_tool_valves_by_id=valves
    native.Tools.get_user_valves_by_id_and_user_id=user_valves
    native.load_tool_module_by_id=load
    req=Request({'type':'http','app':SimpleNamespace(state=SimpleNamespace()),'headers':[]})
    user=SimpleNamespace(id='synthetic-parent',role='user')
    loaded=await native.get_tools(req,[tool_id],user,{'__user__':{'id':user.id}})
    assert len(loaded)==15 and all(not any(k.startswith('__') for k in t['spec']['parameters']['properties']) for t in loaded.values())
    for name in ('get_math_scope','get_math_question_reference','get_math_concept_reference','get_study_support'):
        assert not {'learner_id','context_version','account_id'} & loaded[name]['spec']['parameters']['properties'].keys()
    result=json.loads(await loaded['get_math_scope']['callable'](chapter_id='3'))
    assert result['scope']['grade']==2 and result['mapped_question_count']==4
    result=json.loads(await loaded['get_math_question_reference']['callable'](question_version_id='family-word-g2-share-1-v1'))
    assert result['mapping_status']=='mapped' and len(result['questions'])<=3
    result=json.loads(await loaded['get_math_concept_reference']['callable'](concept_id='g2-share',chapter_id='3'))
    assert result['concepts'][0]['id']=='g2-share' and not result['prerequisites']
    with db.session(write=True) as conn:select_context(conn,account,'family-g7',1)
    result=json.loads(await loaded['get_math_concept_reference']['callable'](concept_id='g7-solve',chapter_id='5'))
    assert [p['id'] for p in result['prerequisites']]==['g7-equality']
    for subject in ('math','chinese','english','ethics','history','geography','biology'):
        result=json.loads(await loaded['get_study_support']['callable'](subject=subject,chapter_id='2'))
        assert result['scope']['grade']==7 and result['scope']['subject']==subject
        assert result['reference_only'] and result['mastery_claim'] is None
    assert all(h['X-trusted-subject']=='synthetic-parent' for _,_,h in calls)
    assert all(method=='GET' for method,_,_ in calls)
    with db.session() as conn:assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0]==0
    print('DD_NATIVE_RESULT='+json.dumps({'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'native_loader':'Open WebUI 0.12.5 get_tools','public_methods':len(loaded),'passed':True,
        'synthetic_accounts_only':True,'model_calls':0,'network':'none','formal_data_mounted':False,
        'math_mappings':20,'study_subjects':7,'context_switch':'passed','provider_calls':0}))


asyncio.run(main())
