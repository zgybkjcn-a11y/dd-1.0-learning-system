"""Pure evidence imports, exact response shapes and retained access checks."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
import pytest

from learning_service import api_types, evidence_contracts as contracts, study_routes
from learning_service.app import APIError, Context, create_app
from learning_service.db import Database
from learning_service import textbook_passages
from learning_service.textbooks import catalogue, search_scope
from test_family_math import family
from test_math_references import reference_family
from test_runtime_passages import stack, runtime_bundle, search, QUERY
from test_readonly_study_tools import chat_tools


def test_evidence_imports_need_no_app_database_directory_network_or_configuration(tmp_path):
    root=Path(__file__).parents[1]
    code='''import os, pathlib, sqlite3, socket, sys
def forbidden(*a, **k): raise AssertionError('side effect while importing evidence modules')
sqlite3.connect=forbidden
socket.socket.connect=forbidden
os.mkdir=forbidden
from learning_service import api_types,evidence_contracts,study_reference,study_routes
assert 'learning_service.app' not in sys.modules
assert not list(pathlib.Path.cwd().iterdir())
assert callable(study_routes.create_study_router)
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=tmp_path,
        env={'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'},text=True,capture_output=True,timeout=15)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert list(tmp_path.iterdir())==[]


def test_existing_imports_keep_shared_error_identity_and_contract_aliases():
    assert APIError is api_types.APIError and Context is api_types.Context
    assert textbook_passages.PassageDetail is contracts.PassageDetail
    assert textbook_passages.PassageSearchResponse is contracts.PassageSearchResponse


@pytest.mark.parametrize('grade',[2,7])
def test_catalogue_preserves_optional_fields_and_scope_payloads_exactly(family,grade):
    _,_,api,headers=family;headers={**headers,'X-Learner-Id':f'family-g{grade}'}
    books=catalogue(f'math-g{grade}-v1')
    response=api.get('/api/v1/textbooks',headers=headers)
    assert response.status_code==200 and response.json()['items']==books
    for book in books:
        for query in ('','synthetic'):
            body={'book_id':book['id'],'query':query}
            response=api.post('/api/v1/textbooks/search',headers=headers,json=body)
            assert response.status_code==200
            assert response.json()==search_scope(f'math-g{grade}-v1',body)
            assert response.headers['cache-control']=='no-store'


@pytest.mark.parametrize('change',['mode','extra','page_authority','page_id','review_status','quote_authority','version'])
def test_precise_search_contract_rejects_malformed_evidence_without_dict_fallback(stack,change):
    payload=search(stack).json()
    adapter=TypeAdapter(contracts.TextbookSearchResponse)
    assert adapter.validate_python(payload).model_dump(by_alias=True,exclude_unset=True)==payload
    if change=='mode':payload['mode']='invented'
    elif change=='extra':payload['PRIVATE']='must not silently escape validation'
    elif change=='page_authority':payload['items'][0]['evidence']['supports_textbook_answer']=True
    elif change=='page_id':payload['items'][0]['evidence']['evidence_id']='dd-excerpt-'+'a'*64
    elif change=='review_status':payload['passage_result']['items'][0]['evidence']['review_status']='teacher_approved'
    elif change=='quote_authority':payload['passage_result']['grounding']['eligible_as_grading_basis']=True
    else:payload['passage_result']['schema']='future-version'
    with pytest.raises(ValidationError):adapter.validate_python(payload)


@pytest.mark.parametrize('payload',[{'mode':'passages','PRIVATE':'invalid'},{'mode':'browse','book':{}},{'mode':'unknown'}])
def test_route_rejects_malformed_backend_output_instead_of_falling_back_to_dict(stack,monkeypatch,payload):
    monkeypatch.setattr(textbook_passages,'search',lambda *a,**k:payload)
    headers={'X-Adapter-Secret':stack['settings'].adapter_secret,'X-Trusted-Provider':'open-webui',
             'X-Trusted-Issuer':'family-pilot-webui','X-Trusted-Subject':'synthetic-parent',
             'X-Learner-Id':'family-g7','X-Learner-Context-Version':'1'}
    with TestClient(stack['api'].app) as direct:
        with pytest.raises(ResponseValidationError):
            direct.post('/api/v1/textbooks/search',headers=headers,json=QUERY)
    response=search(stack)
    assert response.status_code==503 and response.json()['error']['code']=='LEARNING_UPSTREAM_UNAVAILABLE'
    assert 'PRIVATE' not in response.text


def test_access_revoked_during_reference_read_drops_result(reference_family,monkeypatch):
    _,db,api,headers=reference_family
    original=study_routes.query_math_reference
    def revoke(*args,**kwargs):
        result=original(*args,**kwargs)
        with db.session(write=True) as conn:
            conn.execute("UPDATE learner_access SET active=0 WHERE learner_id='family-g7'")
        return result
    monkeypatch.setattr(study_routes,'query_math_reference',revoke)
    response=api.get('/api/v1/math-references',headers={**headers,'X-Learner-Id':'family-g7'})
    assert response.status_code==404 and response.json()['error']['code']=='LEARNER_NOT_FOUND'
    assert 'concepts' not in response.text


def test_router_dependencies_are_per_application(family,tmp_path):
    _,_,first,headers=family;headers={**headers,'X-Learner-Id':'family-g7'}
    separate=tmp_path/'separate';db=Database(separate/'learning.db')
    settings=replace(first.app.state.settings,data_dir=separate,db_path=db.path,
                     attachment_dir=separate/'attachments',export_dir=separate/'exports')
    other=TestClient(create_app(settings,db))
    assert other.get('/api/v1/textbooks',headers=headers).status_code==401
    assert first.get('/api/v1/textbooks',headers=headers).status_code==200
