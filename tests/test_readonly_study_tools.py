"""Chat read-only tools against the real family gateway with synthetic cookies."""
import asyncio
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.browser_auth import CSRF_COOKIE
from learning_service.gateway_http import GatewayResult
from learning_service.login_gateway import GatewaySettings, create_gateway
from learning_service.textbooks import catalogue
from test_family_math import family
from test_math_references import reference_family
from test_login_gateway import SyntheticBridge, gateway_login

SOURCE = Path(__file__).parents[1] / 'deploy/open-webui-reuse/readonly_study_tools.py'
spec = importlib.util.spec_from_file_location('dd_readonly_tools', SOURCE)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


@pytest.fixture
def chat_tools(reference_family):
    _, db, original, _ = reference_family
    origin = 'https://172.19.116.53'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
        browser_auth_secret='synthetic-gateway-key-0123456789abcdef', browser_auth_issuer='synthetic-gateway',
        browser_identity_issuer='family-pilot-webui', browser_origin=origin, public_base_path='/learning',
        shared_learner_context_enabled=True)
    api = TestClient(create_app(settings, db), base_url=origin)
    class Bridge(SyntheticBridge):
        retrieval_result = None
        def send(self, upstream, method, path, headers, body=b'', **kwargs):
            if path == '/api/v1/retrieval/query/doc':
                assert upstream == 'http://webui.invalid:8080' and method == 'POST'
                self.calls.append((upstream, method, path, dict(headers), body))
                book = next(b for b in catalogue('math-g7-v1') if b['id'] == 'math-g7-upper')
                return GatewayResult(200, json.dumps(self.retrieval_result or {'documents': [['UNREVIEWED_ANSWER=999', 'PRIVATE_WRONG_BOOK']],
                    'metadatas': [[{'file_id':book['file_id'],'page_number':37,'edition':'pep-2022-standard-current'},
                                   {'file_id':'wrong-book','page_number':37,'edition':'pep-2022-standard-current'}]]}).encode())
            return super().send(upstream, method, path, headers, body, **kwargs)
    bridge = Bridge(api); bridge.identities['synthetic-token-a'] = 'synthetic-parent'
    gateway = TestClient(create_gateway(GatewaySettings(enabled=True, public_origin=origin,
        openwebui_url='http://webui.invalid:8080', learning_url='http://learning.invalid:8000',
        assertion_secret=settings.browser_auth_secret, assertion_issuer='synthetic-gateway', identity_issuer='family-pilot-webui'), bridge), base_url=origin)
    gateway.cookies.set('token','synthetic-token-a')
    assert gateway_login(settings, gateway)[0].status_code == 303
    response = gateway.post('/learning/api/v1/learner-context', json={'learner_id':'family-g7','expected_revision':0},
        headers={'Origin':origin,'X-CSRF-Token':gateway.cookies[CSRF_COOKIE]})
    assert response.status_code == 200, response.text
    cookie = '; '.join(k+'='+v for k,v in gateway.cookies.items())
    request = Request({'type':'http','headers':[(b'cookie',cookie.encode())]})
    tool = module.Tools(); calls = []; race = [False]
    def fetch(host, port, path, cookies, revision=None, payload=None):
        calls.append((host, path, payload))
        if host == 'open-webui': return {'id':'synthetic-parent','role':'user'}
        headers = {'Cookie':cookies}
        if revision is not None: headers['X-Learner-Context-Version']=str(revision)
        if payload is not None:
            headers.update({'Origin':origin,'X-CSRF-Token':gateway.cookies[CSRF_COOKIE]})
        result = gateway.request('POST' if payload is not None else 'GET', path, headers=headers, json=payload, follow_redirects=False)
        data = tool._response(host, result.status_code, result.content, result.headers.get('X-DD-Request-ID'))
        if race[0] and ('/math-references?' in path or path.endswith('/textbooks/search')):
            race[0] = False
            with db.session(write=True) as conn:
                conn.execute('UPDATE account_contexts SET revision=revision+1')
        return data
    tool._fetch = fetch
    return tool, {'id':'synthetic-parent'}, request, calls, race, db, bridge


def invoke(fixture, method, **kwargs):
    tool,user,request,*_=fixture; events=[]
    async def emit(event): events.append(event)
    args={'__user__':user,'__request__':request,**kwargs}
    if method != 'get_study_catalogue': args['__event_emitter__']=emit
    return json.loads(asyncio.run(getattr(tool,method)(**args))),events


def test_public_concepts_citations_and_no_learning_writes(chat_tools):
    data,_=invoke(chat_tools,'get_study_catalogue')
    assert len(data['books']) >= 7 and all(b['grade']==7 for b in data['books'])
    data,events=invoke(chat_tools,'get_math_concept_reference',concept_id='g7-subtract',book_id='math-g7-upper',chapter_id='2')
    assert data['concepts'][0]['id']=='g7-subtract' and data['prerequisites']
    assert events and all(e['type']=='citation' for e in events)
    assert 'studyPage=30' in json.dumps(data) and 'studyRevision=1' in json.dumps(events)
    assert data['questions'][0]['source']['repository']=='xiaoyang111222/cn-math-taxonomy'
    raw=json.dumps(data)+json.dumps(events)
    for forbidden in ('synthetic-parent','family-g7','token','account_id','answer_key'):
        assert forbidden not in raw
    for subject in ('math','chinese','english','ethics','history','geography','biology'):
        data,_=invoke(chat_tools,'get_study_support',subject=subject,chapter_id='2')
        assert data['scope']['subject']==subject and data['study_steps']
    _,_,_,calls,_,db,_=chat_tools
    assert all(payload is None for _,_,payload in calls)
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM test_sessions').fetchone()[0]==0


def test_search_returns_locations_not_unreviewed_text(chat_tools):
    data,events=invoke(chat_tools,'search_textbook',query='有理数减法',book_id='math-g7-upper',chapter_id='2')
    assert len(data['pages'])==1, data
    assert data['pages'][0]['printed_page']==30 and 'studyPage=30' in data['pages'][0]['url']
    raw=json.dumps(data)+json.dumps(events)
    assert 'UNREVIEWED' not in raw and 'PRIVATE_WRONG_BOOK' not in raw
    assert any(payload is not None for _,_,payload in chat_tools[3])
    assert all(path=='/learning/api/v1/textbooks/search' for _,path,payload in chat_tools[3] if payload is not None)


def test_citations_resolve_evidence_ids_and_distinguish_local_explanations(chat_tools):
    search, events = invoke(chat_tools, 'search_textbook', query='有理数减法', book_id='math-g7-upper', chapter_id='2')
    page = search['pages'][0]
    evidence = page['evidence']
    citation = events[0]['data']
    assert citation['source']['id'] == citation['metadata'][0]['evidence_id'] == evidence['evidence_id']
    assert citation['metadata'][0]['source_ref'] == evidence['source_ref']
    assert citation['metadata'][0]['pdf_page'] == 37 and citation['metadata'][0]['printed_page'] == 30
    assert citation['metadata'][0]['pdf_sha256'] == evidence['pdf_sha256']
    assert citation['source']['url'] == page['url'] == evidence['url']
    assert search['grounding']['status'] == 'incomplete'
    assert search['retrieval']['coverage_complete'] is False
    assert search['grounding']['can_quote_textbook'] is search['grounding']['can_answer_from_textbook'] is False
    concept, events = invoke(chat_tools, 'get_math_concept_reference', concept_id='g7-subtract', book_id='math-g7-upper', chapter_id='2')
    node = concept['concepts'][0]
    assert node['pages'][0]['evidence'] == evidence
    assert evidence['evidence_id'] in node['evidence']['page_evidence_ids']
    local = events[0]['data']['metadata'][0]
    assert local['kind'] == 'local_explanation' and local['quote_status'] == 'not_a_textbook_quote'
    assert local['evidence_id'] == node['evidence']['evidence_id'] != evidence['evidence_id']
    assert local['page_evidence_id'] == evidence['evidence_id']
    support, _ = invoke(chat_tools, 'get_study_support', subject='math', book_id='math-g7-upper', chapter_id='2')
    same_node = next(n for n in support['concepts'] if n['id'] == node['id'])
    assert same_node['evidence']['evidence_id'] == node['evidence']['evidence_id']


def test_empty_truncated_retrieval_is_incomplete_and_has_no_citation(chat_tools):
    chat_tools[-1].retrieval_result = {'documents': [[]], 'metadatas': [[]]}
    data, events = invoke(chat_tools, 'search_textbook', query='不存在的内容', book_id='math-g7-upper', chapter_id='2')
    assert data['pages'] == [] and events == []
    assert data['grounding']['status'] == 'incomplete'
    assert not data['grounding']['can_quote_textbook'] and not data['grounding']['can_answer_from_textbook']


@pytest.mark.parametrize('field,value', [
    ('evidence_id', 'forged'), ('source_ref', 'forged'), ('pdf_sha256', '0' * 64),
    ('printed_page', 29), ('pdf_page', 38), ('book_id', 'math-g2-upper'), ('chapter_id', '5'),
    ('kind', 'reviewed_passage'), ('quote_status', 'verified'), ('review_status', 'approved'),
    ('supports_textbook_answer', True), ('supports_textbook_answer', 0), ('eligible_as_grading_basis', True)])
def test_inconsistent_evidence_fails_closed_without_citations(chat_tools, field, value):
    tool = chat_tools[0]; fetch = tool._fetch
    def tamper(*args, **kwargs):
        data = fetch(*args, **kwargs)
        if args[2].endswith('/textbooks/search'):
            data['items'][0]['evidence'][field] = value
        return data
    tool._fetch = tamper
    data, events = invoke(chat_tools, 'search_textbook', query='有理数减法', book_id='math-g7-upper', chapter_id='2')
    assert 'error' in data and events == [] and 'pages' not in data


def test_evidence_projection_discards_extra_text_and_external_links(chat_tools):
    tool = chat_tools[0]; fetch = tool._fetch
    def inject(*args, **kwargs):
        data = fetch(*args, **kwargs)
        if args[2].endswith('/textbooks/search'):
            data['items'][0]['evidence'].update(quote='UNREVIEWED_SECRET', url='https://foreign.invalid/')
        return data
    tool._fetch = inject
    data, events = invoke(chat_tools, 'search_textbook', query='有理数减法', book_id='math-g7-upper', chapter_id='2')
    assert data['pages'] and events
    assert 'UNREVIEWED_SECRET' not in json.dumps([data, events]) and 'foreign.invalid' not in json.dumps([data, events])


def test_search_revision_change_discards_evidence(chat_tools):
    chat_tools[4][0] = True
    data, events = invoke(chat_tools, 'search_textbook', query='有理数减法', book_id='math-g7-upper', chapter_id='2')
    assert 'error' in data and events == [] and 'pages' not in data


@pytest.mark.parametrize('kwargs', [dict(concept_id='g2-groups',book_id='math-g2-upper'),
    dict(concept_id='g7-solve',book_id='math-g7-upper',chapter_id='2'),
    dict(concept_id='../mistakes'), dict(concept_id='unknown'), dict(concept_id='')])
def test_cross_scope_or_invalid_query_has_no_citation(chat_tools,kwargs):
    data,events=invoke(chat_tools,'get_math_concept_reference',**kwargs)
    assert 'error' in data and not events


def test_mid_query_identity_change_discards_response(chat_tools):
    chat_tools[4][0]=True
    data,events=invoke(chat_tools,'get_math_concept_reference',concept_id='g7-subtract',chapter_id='2')
    assert 'error' in data and not events and 'concepts' not in data


@pytest.mark.parametrize('cookie', ['', 'token=a', 'token=a; token=b; __Host-dd_learning_session=x'])
def test_missing_or_duplicate_cookies_rejected_before_network(chat_tools,cookie):
    tool,user,_,calls,*_=chat_tools
    request=Request({'type':'http','headers':[(b'cookie',cookie.encode())]})
    data=json.loads(asyncio.run(tool.get_study_catalogue(__user__=user,__request__=request)))
    assert 'error' in data and not calls


def test_native_user_must_match_webui_cookie(chat_tools):
    tool,_,request,calls,*_=chat_tools
    data=json.loads(asyncio.run(tool.get_study_catalogue(__user__={'id':'other-user'},__request__=request)))
    assert 'error' in data and len(calls)==1


def test_real_transport_is_fixed_and_search_forwards_csrf(monkeypatch):
    requests=[]
    class Response:
        status=200
        def read(self,limit):return b'{"items":[]}'
    class Connection:
        def __init__(self,host,port,timeout):self.host,self.port=host,port
        def request(self,method,path,body,headers):requests.append((self.host,self.port,method,path,body,headers))
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(module.http.client,'HTTPConnection',Connection)
    cookies='token=synthetic; __Host-dd_learning_session=session; __Host-dd_learning_csrf=csrf'
    module.Tools._fetch('learning-gateway',8000,'/learning/api/v1/textbooks/search',cookies,3,{'query':'相反数','book_id':'math-g7-upper','chapter_id':'2'})
    _,_,method,path,body,headers=requests[0]
    assert method=='POST' and headers['X-CSRF-Token']=='csrf' and headers['X-Learner-Context-Version']=='3'
    assert headers['Origin']=='https://172.19.116.53' and json.loads(body)['query']=='相反数'
    for host,port,path,payload in [('foreign.invalid',8000,'/learning/api/v1/textbooks',None),
        ('learning-gateway',8000,'/learning/api/v1/mistakes',None),
        ('learning-gateway',8000,'/learning/api/v1/study-support',{'write':'forbidden'})]:
        with pytest.raises(module.StudyError):module.Tools._fetch(host,port,path,cookies,payload=payload)
    assert len(requests)==1
    Response.status=302
    with pytest.raises(module.StudyError):module.Tools._fetch('learning-gateway',8000,'/learning/api/v1/textbooks',cookies)
    assert len(requests)==2
