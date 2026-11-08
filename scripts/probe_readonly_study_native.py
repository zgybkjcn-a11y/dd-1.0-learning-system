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
    passage_mode = [False]
    passage_fixture = json.loads(Path('/candidate/passages.json').read_text()) if Path('/candidate/passages.json').exists() else None
    # Public catalogue location only; the response and local explanation are
    # synthetic. No PDF, production database or retrieval provider is mounted.
    evidence = {'schema': 'dd-textbook-page-evidence-v1', 'kind': 'page_location',
        'evidence_id': 'dd-page-f20ec0531973131c0ce247cbe987f6b3dd102ce449c576e648e17740fae439b2',
        'source_ref': 'dd-textbook-772d77e0fcfd206330a120643f7820b07e24dd44aaeb15cb9430591601d668f3',
        'book_id': 'math-g7-upper', 'book_title': '人教社数学 · 上册', 'grade': 7, 'subject': 'math',
        'semester': '上册', 'edition': '依据2022年课标修订的现行新版', 'edition_id': 'pep-2022-standard-current',
        'pdf_sha256': 'd995a2072c2b00418eacf1fdfc7a00234953592f5fba61a4b227731c8a19fdd8',
        'source_binding': 'catalogue_sha256', 'chapter_id': '2', 'chapter_title': '第二章 有理数的运算',
        'printed_page': 30, 'pdf_page': 37, 'locator_precision': 'page', 'review_status': 'location_only',
        'quote_status': 'unavailable', 'supports_textbook_answer': False, 'eligible_as_grading_basis': False}
    def fetch(host,port,path,cookies,revision=None,payload=None):
        calls.append((host,path,payload))
        if host=='open-webui': return {'id':'synthetic-parent','role':'user'}
        if path.endswith('/auth/session'): return {'account_id':'synthetic-account','learner_id':'synthetic-learner','server_context_mode':True,'context_version':3}
        if passage_mode[0]:
            if path.endswith('/textbooks/search'):
                assert payload['query'] == passage_fixture['query']
                return passage_fixture['search']
            if '/passages/' in path:
                return passage_fixture['details'][path.split('/passages/')[1].split('?')[0]]
        if '/math-references?' in path:
            return {'scope':{'book_id':'math-g7-upper','chapter_id':'2','grade':7},'reference_only':True,'eligible_as_grading_basis':False,
                    'reference_sha256':'a'*64,
                    'concepts':[{'id':'g7-subtract','title':'有理数减法','explanation':'减去一个数可转成加上它的相反数。','checks':[],
                                 'pages':[{'book_id':'math-g7-upper','chapter_id':'2','printed_page':30,'pdf_page':37,'evidence':evidence}]}], 'questions':[]}
        if path.endswith('/textbooks/search'):
            assert payload['query']=='有理数减法'
            return {'book_id':'math-g7-upper','chapter_id':'2','items':[{'book_title':'人教数学上册','content_title':'有理数减法','printed_page':30,'pdf_page':37,'evidence':evidence,'text':'UNREVIEWED'}]}
        raise AssertionError(path)
    tool._fetch=fetch
    loaded=await native.get_tools(request,[tool_id],user,{'__user__':{'id':user.id},'__request__':request,'__event_emitter__':emit})
    assert set(loaded)==expected
    for t in loaded.values():
        assert not any(k.startswith('__') for k in t['spec']['parameters']['properties'])
        assert not {'learner_id','account_id','url','cookies','token','as_of','today','path','bundle','manifest_sha256'} & t['spec']['parameters']['properties'].keys()
    data=json.loads(await loaded['get_math_concept_reference']['callable'](concept_id='g7-subtract',chapter_id='2'))
    assert data['concepts'][0]['id']=='g7-subtract' and events[0]['type']=='citation'
    data=json.loads(await loaded['search_textbook']['callable'](query='有理数减法',book_id='math-g7-upper',chapter_id='2'))
    assert 'studyPage=30' in data['pages'][0]['url'] and 'UNREVIEWED' not in json.dumps(data)
    assert data['grounding']['status']=='incomplete' and not data['grounding']['can_answer_from_textbook']
    assert data['retrieval']['coverage_complete'] is False
    assert events[0]['data']['metadata'][0]['kind']=='local_explanation'
    assert events[1]['data']['metadata'][0]['evidence_id']==data['pages'][0]['evidence']['evidence_id']
    assert events[1]['data']['source']['id']==evidence['evidence_id']
    assert all(e['data']['metadata'][0]['page_evidence_id']==evidence['evidence_id'] for e in events)
    if passage_fixture:
        passage_mode[0] = True
        data = json.loads(await loaded['search_textbook']['callable'](query=passage_fixture['query'], book_id='math-g7-upper', chapter_id='2'))
        assert len(data['passages']) == len(data['answer']['claims']) == 2
        for passage, event in zip(data['passages'], events[2:]):
            assert event['data']['document'] == [passage['text']]
            assert event['data']['source']['id'] == passage['evidence']['evidence_id']
            assert event['data']['metadata'][0]['page_evidence_id'] == passage['evidence']['page_evidence_id']
            assert 'studyEvidence=' in event['data']['source']['url']
        assert len(events) == 4 and not data['grounding']['can_answer_from_textbook']
    print('DD_CHAT_NATIVE_RESULT='+json.dumps({'passed':True,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'metadata':metadata,'specs':[t['spec'] for t in loaded.values()],'methods':sorted(loaded),'citation_events':len(events),
        'passage_fixture_checked':bool(passage_fixture),'model_calls':0,'network':'none','formal_data_mounted':False},ensure_ascii=False))
    faulthandler.cancel_dump_traceback_later()

asyncio.run(main())
