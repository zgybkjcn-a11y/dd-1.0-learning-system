"""Subject scope, explicit reading-scaffold boundaries, safe exports and context."""
from dataclasses import replace
import json

import pytest

from learning_service import app as app_module, tools as tool_module
from learning_service.learner_context import select_context
from learning_service.study_support import query_support
from learning_service.tools import Tools
from test_math_references import reference_family, shared_reference_family, ToolResponse, PUBLIC_BOOKS
from test_family_math import family
from test_login_gateway import gateway_env, gateway_login
from test_browser_auth import auth_env
from test_learning_service import env


def support(fixture, grade=7, **parameters):
    _,_,client,h=fixture
    return client.get('/api/v1/study-support',headers={**h,'X-Learner-Id':f'family-g{grade}'},params=parameters)


@pytest.mark.parametrize('grade,subject', [(2,'math'),(2,'chinese'),(2,'ethics'),(7,'math'),(7,'chinese'),
                                         (7,'english'),(7,'ethics'),(7,'history'),(7,'geography'),(7,'biology')])
def test_available_subject_scaffolds_and_math_metadata(reference_family, grade, subject):
    response=support(reference_family,grade,subject=subject,chapter_id='2')
    assert response.status_code==200, response.text
    result=response.json()
    assert result['scope']['grade']==grade and result['scope']['subject']==subject
    assert result['scope']['chapter_id']=='2' and len(result['study_steps'])==3
    assert result['reference_only'] and not result['teacher_reviewed'] and not result['eligible_as_grading_basis']
    assert result['mastery_claim'] is None
    assert result['diagram_mermaid'].startswith('flowchart TD\n')
    assert result['lesson_markdown'].startswith('---\nmarp: true\n')
    if subject=='math':
        assert result['mapping_status']=='mapped' and '本册原页' in result['lesson_markdown']
        assert result['diagram_role']=='catalogue_and_local_concept_mapping'
    else:
        assert result['mapping_status']=='reading_scaffold_only'
        assert result['diagram_role']=='reading_process_not_knowledge_dependencies'
        assert '本册原页' not in result['lesson_markdown']
    for forbidden in ('raw_answer','numeric_answer','answer_key','learner_id','account_id'):
        assert forbidden not in response.text


@pytest.mark.parametrize('grade,params', [(2,{'subject':'english'}),(2,{'subject':'history'}),(7,{'subject':'physics'}),
    (7,{'subject':'chemistry'}),(7,{'book_id':'chinese-g2-upper'}),(7,{'subject':'biology','book_id':'history-g7-upper'}),
    (7,{'subject':'history','chapter_id':'99'}),(7,{'subject':'history','learner_id':'other'}),
    (7,{'subject':['history','math']}),(7,{'subject':'history&learner_id=other'})])
def test_unavailable_classes_and_injected_parameters_rejected(reference_family,grade,params):
    assert support(reference_family,grade,**params).status_code==422


def test_book_and_optional_chapter_support_without_unreviewed_lower_math(reference_family):
    result=support(reference_family,book_id='chinese-g7-lower').json()
    assert result['scope']['subject']=='chinese' and result['scope']['chapter_id']==''
    assert result['scope']['semester']=='下册'
    result=support(reference_family,book_id='math-g7-lower').json()
    assert result['mapping_status']=='unmapped' and result['mapped_question_count']==0
    assert '本册原页' not in result['lesson_markdown']


@pytest.mark.parametrize('grade,chapter,template', [(2,'2','multiplication_groups_v1'),(2,'3','equal_groups_v1'),
    (2,'5','equal_groups_v1'),(2,'1',None),(7,'2','signed_number_line_v1'),(7,'5',None)])
def test_demo_templates_follow_book_chapter_and_reference_scope(reference_family,grade,chapter,template):
    result=support(reference_family,grade,subject='math',chapter_id=chapter).json()
    assert result['interactive_template']==template
    for node in result['concepts']+result['prerequisites']:
        assert node['reference_only'] and not node['eligible_as_grading_basis']
        assert all(int(p['chapter_id'])<=int(chapter) for p in node['pages'])


def test_nonmath_support_reads_no_database_or_unreviewed_text(reference_family):
    _,db,_,_=reference_family
    with db.session() as conn:
        statements=[]
        conn.execute('PRAGMA query_only=ON');conn.set_trace_callback(statements.append)
        result=query_support(conn,'family-g7','math-g7-v1',None,subject='biology')
    assert result['mapping_status']=='reading_scaffold_only' and not statements


def test_study_support_rejects_selection_race(shared_reference_family,monkeypatch):
    db,client,h,account=shared_reference_family
    original=app_module.query_study_support
    def switch(*args,**kwargs):
        result=original(*args,**kwargs)
        with db.session(write=True) as conn:select_context(conn,account,'family-g7',1)
        return result
    monkeypatch.setattr(app_module,'query_study_support',switch)
    response=client.get('/api/v1/study-support?subject=chinese',headers={**h,'X-Learner-Context-Version':'1'})
    assert response.status_code==409 and 'study_steps' not in response.text


def test_study_tool_projects_fields_limits_text_and_follows_host(monkeypatch):
    tool=Tools();tool.account_id=tool.learner_id='';tool.valves.DD_SHARED_LEARNER_CONTEXT=True
    secret={'raw_answer':'PRIVATE_RAW','answer_key':{'accepted':['PRIVATE_KEY']},'email':'PRIVATE_EMAIL','unknown':'PRIVATE_UNKNOWN'}
    calls=[]
    def send(request,timeout):
        calls.append(request)
        if request.full_url.endswith('/learner-context'):return ToolResponse({'learner_id':'g7','context_version':2})
        return ToolResponse({**secret,'scope':{**secret,'grade':7,'subject':'history'},
                             'study_steps':[{**secret,'title':'时空','prompt':'回到教材核对'}]*100,
                             'provenance':secret,'diagram_mermaid':'X'*4001,'lesson_markdown':'X'*12001})
    monkeypatch.setattr(tool_module,'urlopen',send)
    raw=tool.get_study_support('history',__user__={'id':'host'})
    assert 'PRIVATE_' not in raw and 'X'*4001 not in raw
    result=json.loads(raw)
    assert len(result['study_steps'])==4 and result['scope']['subject']=='history'
    assert all(dict(r.header_items())['X-trusted-subject']=='host' for r in calls)
    assert calls[1].full_url.endswith('/api/v1/study-support?subject=history')
    assert json.loads(tool.get_study_support('history&other=1'))['error']['code']=='STUDY_SUPPORT_SCOPE_INVALID'
