import asyncio
import io
import json
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from learning_service import tools as tool_module
from learning_service.tools import Tools
from test_learner_context import shared_env, choose
from test_browser_auth import auth_env
from test_learning_service import env
from open_webui_harness import call_tool, call_tool_async, load_tool_module, discover_functions, visible_parameters


class Response:
    def __init__(self, data):self.body=json.dumps(data).encode()
    def read(self):return self.body
    def __enter__(self):return self
    def __exit__(self,*_):return False


@pytest.fixture
def adapter(shared_env,monkeypatch):
    s,db,browser=shared_env
    choose(s,browser,'learner-a',0)
    internal=TestClient(browser.app)
    tool=Tools();tool.valves.DD_SHARED_LEARNER_CONTEXT=True;tool.valves.DD_LEARNING_ADAPTER_SECRET=s.adapter_secret
    tool.valves.DD_TRUSTED_ISSUER='open-webui';tool.valves.DD_TRUSTED_SUBJECT='';tool.learner_id='';tool.account_id=''
    calls=[]
    def send(request,timeout):
        path=request.full_url.split(':31010')[-1]
        calls.append((request.get_method(),path,dict(request.header_items())))
        r=internal.request(request.get_method(),path,content=request.data,headers=dict(request.header_items()))
        if r.status_code>=400:raise HTTPError(request.full_url,r.status_code,'synthetic error',{},io.BytesIO(r.content))
        return Response(r.json())
    monkeypatch.setattr(tool_module,'urlopen',send)
    return tool,s,db,browser,calls


def test_shared_adapter_follows_workbench_and_refuses_old_uservalves(adapter):
    tool,s,db,browser,calls=adapter
    user={'id':'subject-a'}
    r=json.loads(tool.request_variant('obj-1',__user__=user));assert r['status']=='queued'
    post=next(h for method,path,h in calls if method=='POST')
    assert post['X-learner-context-version']=='1' and post['X-learner-id']=='learner-a'
    choose(s,browser,'learner-b',1)
    before=len(calls)
    r=json.loads(tool.get_progress(__user__={'id':'subject-a','valves':{'DD_LEARNER_ID':'learner-a'}}))
    assert r['error']['code']=='LEARNER_CONTEXT_CHANGED'
    assert len(calls)==before+1 and calls[-1][1]=='/api/v1/learner-context'
    r=json.loads(tool.get_progress(__user__=user));assert 'error' not in r and 'learner_id' not in r
    assert calls[-2][2]['X-learner-id']=='learner-b'
    choose(s,browser,None,2)
    assert json.loads(tool.get_mistakes(__user__=user))['error']['code']=='LEARNER_CONTEXT_REQUIRED'


def test_switch_during_native_callback_never_creates_or_submits_challenge(adapter):
    tool,s,db,browser,calls=adapter
    h={'Origin':s.browser_origin,'X-CSRF-Token':browser.cookies.get('__Host-dd_learning_csrf'),'X-Learner-Context-Version':'1'}
    draft=browser.post('/api/v1/learning-drafts',headers=h,json={'objective_id':'obj-1','content':{'note':'private learning content'}}).json()['draft_id']
    async def callback(event):
        assert event['type']=='confirmation'
        choose(s,browser,'learner-b',1)
        choose(s,browser,'learner-a',2)
        return True
    r=json.loads(asyncio.run(tool.start_trusted_interaction('confirm_learning',draft,__user__={'id':'subject-a'},__event_call__=callback)))
    assert r['error']['code']=='LEARNER_CONTEXT_CHANGED'
    assert not any(path.endswith('/confirmations') for _,path,_ in calls)
    with db.session() as conn:assert conn.execute('SELECT COUNT(*) FROM interaction_challenges').fetchone()[0]==0


@pytest.mark.parametrize('method,args,kind', [
 ('list_learners',[], 'learners'),('get_review_tasks',[],'review'),('get_mistakes',[],'mistakes'),('get_progress',[],'progress'),
 ('get_attempt',['attempt-1'],'attempt'),('request_document_analysis',['batch-1'],'request'),('request_diagnosis',['mistake-1'],'request'),
 ('request_variant',['obj-1'],'request'),('request_hint',['item-1'],'request'),('request_visual',[1,-2],'request')])
def test_every_public_read_and_request_projects_sensitive_and_unknown_fields(monkeypatch,method,args,kind):
    tool=Tools();tool.valves.DD_SHARED_LEARNER_CONTEXT=True;tool.learner_id='';tool.account_id=''
    secret={'raw_answer':'PRIVATE_RAW_ANSWER','content':{'document_text':'PRIVATE_DOCUMENT'},'answer_key':{'accepted':['PRIVATE_KEY']},
            'email':'PRIVATE_EMAIL','identity':{'subject':'PRIVATE_SUBJECT'},'provider_payload':'PRIVATE_PROVIDER','metadata_json':'PRIVATE_METADATA','unknown':'PRIVATE_UNKNOWN'}
    def send(request,timeout):
        if request.full_url.endswith('/learner-context'):return Response({'learner_id':'learner-a','context_version':7})
        return Response({**secret,'items':[{**secret,'id':'safe-id','status':'active','objective_id':'obj-1','state':'review','stage':1,'due_at':'2026-11-04'}],
                         'cards':[{**secret,'state':'review','stage':1,'count':1}], 'attempts':{**secret,'total':1,'graded':1,'independent':1},
                         'job_id':'job-1','id':'attempt-1','status':'queued','outcome':'correct','assessment_eligibility':True})
    monkeypatch.setattr(tool_module,'urlopen',send)
    result=getattr(tool,method)(*args,__user__={'id':'subject-a'})
    assert 'PRIVATE_' not in result
    assert json.loads(result)['workbench_url']=='https://172.19.116.53/learning/ui'
    assert 'learner_id' not in result and 'account_id' not in result


def test_changed_context_after_read_drops_old_result(monkeypatch):
    tool=Tools();tool.valves.DD_SHARED_LEARNER_CONTEXT=True;tool.learner_id=''
    contexts=iter([{'learner_id':'a','context_version':1},{'learner_id':'b','context_version':2}])
    def send(request,timeout):
        if request.full_url.endswith('/learner-context'):return Response(next(contexts))
        return Response({'items':[{'id':'old-private-id','status':'active'}]})
    monkeypatch.setattr(tool_module,'urlopen',send)
    result=tool.get_mistakes(__user__={'id':'host'})
    assert 'old-private-id' not in result and json.loads(result)['error']['code']=='LEARNER_CONTEXT_CHANGED'


def test_loader_shared_profile_reserves_user_and_context_and_keeps_15_methods(adapter,monkeypatch):
    original,s,db,browser,calls=adapter
    module,tool=load_tool_module(__import__('pathlib').Path(tool_module.__file__))
    tool.valves=tool.Valves(**original.valves.model_dump());tool.learner_id='';tool.account_id=''
    monkeypatch.setattr(module,'urlopen',tool_module.urlopen)
    result=json.loads(call_tool(tool,'get_progress',{'__user__':{'id':'attacker'}},{'id':'subject-a'}))
    assert 'error' not in result
    assert all(headers['X-trusted-subject']=='subject-a' for _,_,headers in calls)
    assert len(discover_functions(tool))==15
    assert all('learner_id' not in visible_parameters(f) and 'context_version' not in visible_parameters(f) for f in discover_functions(tool).values())
