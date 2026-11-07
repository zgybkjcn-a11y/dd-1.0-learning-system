"""Version-bound reference reads with synthetic accounts and public local PDFs."""
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from learning_service import app as app_module, math_references as references, tools as tool_module
from learning_service.app import create_app
from learning_service.learner_context import select_context
from learning_service.practice import bank, install
from learning_service.tools import Tools
from test_family_math import family
from test_login_gateway import gateway_env, gateway_login
from test_browser_auth import auth_env
from test_learning_service import env
from open_webui_harness import call_tool, load_tool_module, visible_parameters

ROOT = Path(__file__).parents[1]
PUBLIC_BOOKS = ROOT / 'learning_data/textbooks/pep-current-20261105'


@pytest.fixture
def reference_family(family):
    directory, db, client, headers = family
    install(db)
    client.app.state.settings = replace(client.app.state.settings, textbook_dir=PUBLIC_BOOKS)
    return directory, db, client, headers


def query(fixture, grade=2, **params):
    _, _, client, headers = fixture
    return client.get('/api/v1/math-references', headers={**headers, 'X-Learner-Id': f'family-g{grade}'}, params=params)


@pytest.mark.parametrize('grade,chapter,count', [(2,'',12),(2,'2',4),(2,'3',4),(2,'5',4),(7,'',8),(7,'2',4),(7,'5',4)])
def test_scope_optional_chapter_and_original_page_boundaries(reference_family, grade, chapter, count):
    response = query(reference_family, grade, chapter_id=chapter)
    assert response.status_code == 200, response.text
    assert response.headers['Cache-Control'] == 'no-store'
    result = response.json()
    assert result['scope']['book_id'] == f'math-g{grade}-upper'
    assert result['scope']['chapter_id'] == chapter
    assert result['mapped_question_count'] == count and result['mapping_status'] == 'mapped'
    assert result['reference_only'] and not result['eligible_as_grading_basis'] and not result['teacher_reviewed']
    assert result['mastery_claim'] is None
    assert result['provenance']['commit'] == '508748a2c8dddc1253100b2d10d91c9526903f67'
    for node in result['concepts'] + result['prerequisites']:
        assert node['reference_only'] and not node['eligible_as_grading_basis']
        for page in node['pages']:
            assert page['book_id'] == f'math-g{grade}-upper'
            assert page['pdf_page'] == page['printed_page'] + (5 if grade == 2 else 7)
            assert not chapter or int(page['chapter_id']) <= int(chapter)
            assert page['page_image_path'].endswith(f"/pages/{page['printed_page']}/image")
    for forbidden in ('answer_key', 'prompt', 'raw_answer', 'learner_id', 'account_id', 'accepted'):
        assert forbidden not in response.text


def test_precise_question_reference_same_chapter_and_no_future_pages(reference_family):
    qid = 'family-word-g2-share-1-v1'
    result = query(reference_family, question_version_id=qid).json()
    assert result['scope']['chapter_id'] == '3'
    assert {'g2-share','g2-small-table'} == {c['id'] for c in result['concepts']}
    assert 0 < len(result['questions']) <= 3
    assert all(q['chapter_id'] == '3' and q['question_version_id'] != qid for q in result['questions'])
    assert all(int(p['chapter_id']) <= 3 for c in result['concepts']+result['prerequisites'] for p in c['pages'])
    unmapped = next(q['id'] for q in bank().values() if q['grade'] == 2 and q['id'] not in references.load_reference()['question_mappings'])
    assert query(reference_family, question_version_id=unmapped).json()['mapping_status'] == 'unmapped'


@pytest.mark.parametrize('grade,params,status', [
    (2,{'book_id':'math-g7-upper'},422), (7,{'book_id':'math-g2-upper'},422),
    (2,{'book_id':'chinese-g2-upper'},422), (2,{'chapter_id':'99'},422),
    (2,{'chapter_id':'2','question_version_id':'family-word-g2-share-1-v1'},422),
    (2,{'question_version_id':'family-word-g7-sea-rise-v1'},404),
    (2,{'question_version_id':'unknown-v1'},404), (2,{'concept_id':'g7-solve'},404),
    (2,{'concept_id':'g2-share','chapter_id':'2'},404),
    (2,{'concept_id':'g2-share','question_version_id':'family-word-g2-share-1-v1'},422),
    (2,{'book_id':'../../outside'},422), (2,{'learner_id':'family-g7'},422),
    (2,{'chapter_id':['2','3']},422), (2,{'context_version':'9'},422),
])
def test_invalid_cross_grade_scope_and_model_identity_arguments_rejected(reference_family, grade, params, status):
    response = query(reference_family, grade, **params)
    assert response.status_code == status, response.text
    assert 'concepts' not in response.text


def test_empty_chapter_and_unmapped_edition_do_not_fallback(reference_family):
    for grade, params in [(2,{'chapter_id':'1'}),(7,{'book_id':'math-g7-lower'})]:
        response = query(reference_family, grade, **params)
        assert response.status_code == 200
        result = response.json()
        assert result['mapping_status'] == 'unmapped' and result['mapped_question_count'] == 0
        assert not result['concepts'] and not result['questions']
    assert query(reference_family, 7, book_id='math-g7-lower', concept_id='g7-solve').status_code == 404


def test_concept_uses_its_own_prerequisites_and_mathematical_direction(reference_family):
    result = query(reference_family, 7, chapter_id='5', concept_id='g7-solve').json()
    assert [c['id'] for c in result['concepts']] == ['g7-solve']
    assert [p['id'] for p in result['prerequisites']] == ['g7-equality']
    edge = result['prerequisites'][0]
    assert edge['from_concept'] == 'g7-solve' and edge['strength'] == 'hard'
    assert '零' in edge['rationale'] and '零' in edge['explanation']
    for concept in ('g2-pack','g2-share'):
        result = query(reference_family, concept_id=concept, chapter_id='3').json()
        assert [c['id'] for c in result['concepts']] == [concept]
        assert not result['prerequisites']  # Division interpretations are peers.
    result = query(reference_family, 7, chapter_id='5', concept_id='g7-percent').json()
    assert result['questions'] and all(q['mapping_role'] == 'supporting' for q in result['questions'])


@pytest.mark.parametrize('column,value', [
    ('content_json',{'prompt':'Changed prompt'}), ('answer_key_json',{'numeric_answer':'999'}),
    ('answer_key_json',{'numeric_answer':'12','units':['wrong unit']}), ('validator_version','changed-validator'),
    ('version',2),
])
def test_stored_question_changes_invalidate_reference(reference_family, column, value):
    _, db, _, _ = reference_family
    with db.session(write=True) as conn:
        conn.execute(f'UPDATE question_versions SET {column}=? WHERE id=?',
                     (json.dumps(value) if isinstance(value,dict) else value,'family-word-g2-share-1-v1'))
    response = query(reference_family, chapter_id='3')
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'MATH_REFERENCE_VERSION_MISMATCH'
    assert 'Changed prompt' not in response.text


def test_changed_reference_bank_and_original_pdf_are_rejected(reference_family, tmp_path, monkeypatch):
    bad = tmp_path/'changed-reference.json'
    bad.write_bytes(references.REFERENCE_PATH.read_bytes()+b' ')
    with monkeypatch.context() as m:
        m.setattr(references,'REFERENCE_PATH',bad)
        assert query(reference_family).json()['error']['code'] == 'MATH_REFERENCE_UNAVAILABLE'
    with monkeypatch.context() as m:
        m.setattr(references,'BANK_PATH',bad)
        assert query(reference_family).status_code == 503
    with monkeypatch.context() as m:
        m.setattr(references,'bank',lambda: (_ for _ in ()).throw(ValueError('sensitive exception')))
        response = query(reference_family)
        assert response.status_code == 503 and 'sensitive' not in response.text
    _, _, client, _ = reference_family
    client.app.state.settings = replace(client.app.state.settings,textbook_dir=tmp_path)
    response = query(reference_family)
    assert response.json()['error']['code'] == 'MATH_REFERENCE_TEXTBOOK_UNAVAILABLE'
    (tmp_path/'math-g2-upper.pdf').write_bytes(b'Wrong original')
    assert query(reference_family).status_code == 503
    (tmp_path/'math-g2-upper.pdf').unlink()
    (tmp_path/'math-g2-upper.pdf').symlink_to(PUBLIC_BOOKS/'math-g2-upper.pdf')
    assert query(reference_family).status_code == 503


def test_reference_query_is_read_only_and_avoids_student_material(reference_family):
    _, db, _, _ = reference_family
    with db.session() as conn:
        conn.execute('PRAGMA query_only=ON')
        statements=[]
        conn.set_trace_callback(statements.append)
        result=references.query_reference(conn,'family-g2','math-g2-v1',PUBLIC_BOOKS)
        assert result['mapping_status']=='mapped'
        for forbidden in ('attempts','mistake_entries','browser_sessions','accounts','provider_calls'):
            assert not any(forbidden in sql for sql in statements)
        assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0]==0


@pytest.fixture
def shared_reference_family(reference_family):
    directory, db, old, headers = reference_family
    settings=replace(old.app.state.settings,shared_learner_context_enabled=True)
    client=TestClient(create_app(settings,db))
    with db.session() as conn:
        account=conn.execute('SELECT account_id FROM identity_bindings WHERE subject=?',('synthetic-parent',)).fetchone()[0]
    with db.session(write=True) as conn:
        select_context(conn,account,'family-g2',0)
    return db,client,headers,account


def test_api_requires_revision_and_drops_switch_away_and_back(shared_reference_family, monkeypatch):
    db,client,headers,account=shared_reference_family
    assert client.get('/api/v1/math-references',headers=headers).status_code==409
    h={**headers,'X-Learner-Id':'family-g2','X-Learner-Context-Version':'1'}
    assert client.get('/api/v1/math-references',headers=h).status_code==200
    original=app_module.query_math_reference
    def switch(*args,**kwargs):
        result=original(*args,**kwargs)
        with db.session(write=True) as conn:
            select_context(conn,account,'family-g7',1)
            select_context(conn,account,'family-g2',2)
        return result
    monkeypatch.setattr(app_module,'query_math_reference',switch)
    response=client.get('/api/v1/math-references',headers=h)
    assert response.status_code==409 and response.json()['error']['code']=='LEARNER_CONTEXT_CHANGED'
    assert 'concepts' not in response.text


class ToolResponse:
    def __init__(self, data): self.body=json.dumps(data).encode()
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self,*_): return False


def test_tools_host_identity_native_schema_and_shared_service(shared_reference_family, monkeypatch):
    db,client,headers,account=shared_reference_family
    module,tool=load_tool_module(ROOT/'learning_service/tools.py')
    tool.account_id=tool.learner_id=''
    tool.valves.DD_LEARNING_ADAPTER_SECRET=headers['X-Adapter-Secret']
    tool.valves.DD_TRUSTED_ISSUER=headers['X-Trusted-Issuer']
    tool.valves.DD_SHARED_LEARNER_CONTEXT=True
    calls=[]
    def send(request,timeout):
        path=request.full_url.split(':31010')[-1]
        h=dict(request.header_items())
        calls.append((path,h))
        response=client.request(request.get_method(),path,headers=h,content=request.data)
        if response.status_code>=400:
            raise HTTPError(request.full_url,response.status_code,'synthetic',{},io.BytesIO(response.content))
        return ToolResponse(response.json())
    monkeypatch.setattr(module,'urlopen',send)
    user={'id':'synthetic-parent'}
    result=json.loads(call_tool(tool,'get_math_scope',{'chapter_id':'3','__user__':{'id':'attacker'}},user))
    assert result['scope']['grade']==2 and all(h['X-trusted-subject']=='synthetic-parent' for _,h in calls)
    result=json.loads(tool.get_math_question_reference('family-word-g2-share-1-v1',__user__=user))
    assert result['mapping_status']=='mapped'
    assert json.loads(tool.get_math_concept_reference('g2-share',chapter_id='3',__user__=user))['concepts'][0]['id']=='g2-share'
    assert 'learner_id' not in visible_parameters(tool.get_math_scope)
    assert 'context_version' not in visible_parameters(tool.get_math_scope)
    with db.session(write=True) as conn: select_context(conn,account,'family-g7',1)
    assert json.loads(tool.get_math_scope(__user__=user))['scope']['grade']==7
    assert json.loads(tool.get_math_scope(__user__={'id':'synthetic-parent','valves':{'DD_LEARNER_ID':'family-g2'}}))['error']['code']=='LEARNER_CONTEXT_CHANGED'
    assert json.loads(tool.get_math_scope(book_id='math-g2-upper',__user__=user))['error']['code']=='MATH_REFERENCE_SCOPE_INVALID'
    assert not any('question-choices' in path or 'test-sessions' in path for path,_ in calls)


@pytest.mark.parametrize('method,args', [('get_math_scope',()),('get_math_question_reference',('q-v1',)),('get_math_concept_reference',('concept',))])
def test_reference_tools_project_nested_unknown_fields_and_bound_output(monkeypatch,method,args):
    tool=Tools(); tool.learner_id=tool.account_id=''; tool.valves.DD_SHARED_LEARNER_CONTEXT=True
    secret={'raw_answer':'PRIVATE_RAW','answer_key':{'accepted':['PRIVATE_KEY']},'email':'PRIVATE_EMAIL','unknown':'PRIVATE_UNKNOWN'}
    page={**secret,'book_id':'math-g2-upper','printed_page':12,'page_image_path':'https://evil.invalid/PRIVATE_URL'}
    node={**secret,'id':'g2-groups','title':'相同组','checks':['核对组数',secret,'X'*500], 'pages':[page]*100}
    body={**secret,'scope':{**secret,'book_id':'math-g2-upper','grade':2},'provenance':secret,
          'concepts':[node]*100,'prerequisites':[node]*100,'questions':[{**secret,'question_version_id':'safe','source':secret}]*100}
    def send(request,timeout):
        if request.full_url.endswith('/learner-context'): return ToolResponse({'learner_id':'a','context_version':1})
        return ToolResponse(body)
    monkeypatch.setattr(tool_module,'urlopen',send)
    raw=getattr(tool,method)(*args,__user__={'id':'host'})
    assert 'PRIVATE_' not in raw and 'evil.invalid' not in raw and 'X'*500 not in raw
    result=json.loads(raw)
    assert len(result['concepts'])==18 and len(result['prerequisites'])==6 and len(result['questions'])==20
    assert all(len(c['pages'])==8 for c in result['concepts'])
    assert result['mastery_claim'] is None and result['reference_only'] and not result['eligible_as_grading_basis']


def test_reference_tool_drops_stale_output_and_rejects_argument_injection(monkeypatch):
    tool=Tools(); tool.learner_id=tool.account_id=''; tool.valves.DD_SHARED_LEARNER_CONTEXT=True
    contexts=iter([{'learner_id':'a','context_version':1},{'learner_id':'b','context_version':2}])
    def send(request,timeout):
        if request.full_url.endswith('/learner-context'): return ToolResponse(next(contexts))
        return ToolResponse({'concepts':[{'title':'OLD_REFERENCE'}]})
    monkeypatch.setattr(tool_module,'urlopen',send)
    raw=tool.get_math_scope(__user__={'id':'host'})
    assert 'OLD_REFERENCE' not in raw and json.loads(raw)['error']['code']=='LEARNER_CONTEXT_CHANGED'
    monkeypatch.setattr(tool_module,'urlopen',lambda *_a,**_k: pytest.fail('invalid args must not make a request'))
    for call in (lambda:tool.get_math_scope(chapter_id='3&learner_id=other'),lambda:tool.get_math_question_reference(''),
                 lambda:tool.get_math_concept_reference(''),lambda:tool.get_math_scope(book_id=7)):
        assert json.loads(call())['error']['code']=='MATH_REFERENCE_SCOPE_INVALID'


def test_gateway_forwards_reference_queries_without_retrieval_or_model_call(gateway_env):
    s,db,settings,bridge,client=gateway_env
    assert gateway_login(s,client)[0].status_code==303
    assert client.post('/learning/api/v1/learner-context',json={'learner_id':'learner-a','expected_revision':0},
                       headers={'Origin':s.browser_origin,'X-CSRF-Token':client.cookies.get('__Host-dd_learning_csrf')}).status_code==200
    bridge.api.app.state.settings=replace(bridge.api.app.state.settings,textbook_dir=PUBLIC_BOOKS)
    # This account has the synthetic g2 curriculum but no practice import.
    response=client.get('/learning/api/v1/math-references?chapter_id=2',headers={'X-Learner-Context-Version':'1'})
    assert response.status_code==200 and response.json()['mapping_status']=='unmapped'
    assert bridge.calls[-1][2]=='/api/v1/math-references?chapter_id=2'
    assert not any('/retrieval/' in path for _,_,path,_,_ in bridge.calls)
