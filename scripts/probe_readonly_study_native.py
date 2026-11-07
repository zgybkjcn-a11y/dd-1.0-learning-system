"""Fresh offline WebUI image only; no production volume or network."""
import asyncio
import hashlib
import json
import os
import faulthandler
from pathlib import Path
from types import SimpleNamespace

assert os.environ['DATA_DIR']=='/tmp/dd-chat-native'
assert os.environ['OFFLINE_MODE']=='true'
Path(os.environ['DATA_DIR']).mkdir(parents=True, exist_ok=True)
faulthandler.dump_traceback_later(45)
from fastapi import Request
from open_webui.utils import tools as native
from open_webui.utils.plugin import load_tool_module_by_id

async def main():
    source=Path('/candidate/readonly_study_tools.py').read_text()
    tool_id='dd_family_study_readonly_v1'
    tool,metadata,source_module=await load_tool_module_by_id(tool_id,content=source)
    specs=native.get_tool_specs(tool)
    expected={'get_study_catalogue','get_math_scope','get_math_concept_reference','get_math_question_reference','get_study_support','search_textbook'}
    assert {s['name'] for s in specs}==expected
    record=SimpleNamespace(id=tool_id,user_id='synthetic-parent',content=source,specs=specs)
    async def groups(*args,**kwargs): return []
    async def models(ids): return {tool_id:record}
    async def load(*args,**kwargs): return tool,metadata,source_module
    native.Groups.get_groups_by_member_id=groups
    native.Tools.get_tools_by_ids=models
    native.load_tool_module_by_id=load
    events=[]
    async def emit(event): events.append(event)
    request=Request({'type':'http','app':SimpleNamespace(state=SimpleNamespace()),'headers':[
        (b'cookie',b'token=synthetic-token; __Host-dd_learning_session=synthetic-session; __Host-dd_learning_csrf=synthetic-csrf')]})
    user=SimpleNamespace(id='synthetic-parent',role='user')
    calls=[]
    def fetch(host,port,path,cookies,revision=None,payload=None):
        calls.append((host,path,payload))
        if host=='open-webui': return {'id':'synthetic-parent','role':'user'}
        if path.endswith('/auth/session'): return {'account_id':'synthetic-account','learner_id':'synthetic-learner','server_context_mode':True,'context_version':3}
        if '/math-references?' in path:
            return {'scope':{'book_id':'math-g7-upper','chapter_id':'2','grade':7},'reference_only':True,'eligible_as_grading_basis':False,
                    'concepts':[{'id':'g7-subtract','title':'有理数减法','explanation':'减去一个数可转成加上它的相反数。','checks':[],
                                 'pages':[{'book_id':'math-g7-upper','chapter_id':'2','printed_page':30}]}], 'questions':[]}
        if path.endswith('/textbooks/search'):
            assert payload['query']=='有理数减法'
            return {'book_id':'math-g7-upper','chapter_id':'2','items':[{'book_title':'人教数学上册','content_title':'有理数减法','printed_page':30,'text':'UNREVIEWED'}]}
        raise AssertionError(path)
    tool._fetch=fetch
    loaded=await native.get_tools(request,[tool_id],user,{'__user__':{'id':user.id},'__request__':request,'__event_emitter__':emit})
    assert set(loaded)==expected
    for t in loaded.values():
        assert not any(k.startswith('__') for k in t['spec']['parameters']['properties'])
        assert not {'learner_id','account_id','url','cookies','token'} & t['spec']['parameters']['properties'].keys()
    data=json.loads(await loaded['get_math_concept_reference']['callable'](concept_id='g7-subtract',chapter_id='2'))
    assert data['concepts'][0]['id']=='g7-subtract' and events[0]['type']=='citation'
    data=json.loads(await loaded['search_textbook']['callable'](query='有理数减法',book_id='math-g7-upper',chapter_id='2'))
    assert 'studyPage=30' in data['pages'][0]['url'] and 'UNREVIEWED' not in json.dumps(data)
    print('DD_CHAT_NATIVE_RESULT='+json.dumps({'passed':True,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'metadata':metadata,'specs':[t['spec'] for t in loaded.values()],'methods':sorted(loaded),'citation_events':len(events),
        'model_calls':0,'network':'none','formal_data_mounted':False},ensure_ascii=False))
    faulthandler.cancel_dump_traceback_later()

asyncio.run(main())
