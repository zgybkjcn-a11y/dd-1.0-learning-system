"""Existing B05/B06 routes through the real gateway with synthetic cookies."""
import pytest

from learning_service.practice import install,bank
from test_runtime_passages import stack, runtime_bundle
from test_readonly_study_tools import chat_tools
from test_math_references import reference_family
from test_family_math import family
from test_practice_collection import answer


def test_gateway_workspace_read_update_context_conflict_and_csrf(stack):
    gateway=stack['gateway'];headers=stack['headers'];path='/learning/api/v1/practice-workspace'
    result=gateway.get(path,headers=headers)
    assert result.status_code==200,result.text
    assert result.headers['cache-control']=='no-store'
    body={'book_id':'math-g7-upper','chapter_id':'2','difficulty':'easy','pool':'initial','expected_revision':result.json()['revision']}
    assert gateway.put(path,headers={k:v for k,v in headers.items() if k!='X-CSRF-Token'},json=body).status_code==403
    assert gateway.put(path,headers=headers,json=body).status_code==200
    stale=gateway.put(path,headers=headers,json=body)
    assert stale.status_code==409 and stale.json()['error']['code']=='PRACTICE_WORKSPACE_CHANGED'
    assert gateway.get(path,headers={**headers,'X-Learner-Context-Version':'0'}).status_code==409
    gateway.cookies.clear()
    assert gateway.get(path).status_code==401


def test_gateway_collection_preview_confirm_retry_and_context_isolation(stack):
    db=stack['db'];install(db)
    question=next(q for q in bank().values() if q['grade']==7 and q['chapter_id']=='2')
    adapter={'X-Adapter-Secret':stack['settings'].adapter_secret,'X-Trusted-Provider':'open-webui',
        'X-Trusted-Issuer':'family-pilot-webui','X-Trusted-Subject':'synthetic-parent',
        'X-Learner-Id':'family-g7','X-Learner-Context-Version':'1'}
    attempt,_=answer((db,stack['api'],adapter,question))
    gateway=stack['gateway'];headers=stack['headers'];path=f'/learning/api/v1/attempts/{attempt}'
    preview=gateway.get(path+'/collection-preview',headers=headers)
    assert preview.status_code==200,preview.text
    body={'confirmed':True,'preview_sha256':preview.json()['preview_sha256']}
    assert gateway.post(path+'/collection',headers={k:v for k,v in headers.items() if k!='X-CSRF-Token'},json=body).status_code==403
    assert gateway.post(path+'/collection',headers=headers,json=body).status_code==422
    first=gateway.post(path+'/collection',headers={**headers,'Idempotency-Key':'synthetic-collection'},json=body)
    assert first.status_code==201,first.text
    again=gateway.post(path+'/collection',headers={**headers,'Idempotency-Key':'synthetic-collection'},json=body)
    assert again.status_code==201 and again.json()==first.json()
    with db.session() as conn:
        assert conn.execute('SELECT count(*) FROM mistake_sources').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM review_cards').fetchone()[0]==1
    switch=gateway.post('/learning/api/v1/learner-context',headers=headers,json={'learner_id':'family-g2','expected_revision':1})
    assert switch.status_code==200
    assert gateway.get(path+'/collection-preview',headers=headers).status_code==409
    current={**headers,'X-Learner-Context-Version':str(switch.json()['context_version'])}
    assert gateway.get(path+'/collection-preview',headers=current).status_code==404
    assert gateway.post(path+'/collection',headers={**current,'Idempotency-Key':'wrong-profile'},json=body).status_code==404


@pytest.mark.parametrize('method,path',[('POST','/api/v1/practice-workspace'),('DELETE','/api/v1/practice-workspace'),
    ('GET','/api/v1/attempts/synthetic/collection'),('PUT','/api/v1/attempts/synthetic/collection'),
    ('POST','/api/v1/attempts/synthetic/collection-preview'),('GET','/api/v1/attempts/synthetic/collection-preview/extra')])
def test_gateway_new_allowlist_entries_do_not_expand_other_methods_or_paths(stack,method,path):
    before=len(stack['bridge'].calls)
    result=stack['gateway'].request(method,'/learning'+path,headers=stack['headers'])
    assert result.status_code==404 and result.json()['error']['code']=='ROUTE_REJECTED'
    assert len(stack['bridge'].calls)==before
