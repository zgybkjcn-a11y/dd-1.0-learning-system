"""Edition/grade/chapter and authenticated retrieval boundaries, synthetic only."""
from dataclasses import replace
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from learning_service.gateway_http import GatewayResult
from learning_service.login_gateway import create_gateway
from learning_service.textbooks import catalogue, search_scope, bounded_references, chapter_references, PDF_SHA256, BOOKS
from test_family_math import family
from test_login_gateway import gateway_env, gateway_login, SyntheticBridge
from test_browser_auth import auth_env, csrf
from test_learning_service import env


def test_family_catalogue_and_search_cannot_cross_grades_or_accept_collections(family):
    _,_,client,headers=family
    for grade,books in [(2,4),(7,9)]:
        h={**headers,'X-Learner-Id':f'family-g{grade}'}
        response=client.get('/api/v1/textbooks',headers=h)
        assert response.status_code==200
        assert len(response.json()['items'])==books
        assert all(b['grade']==grade for b in response.json()['items'])
        assert {s['id'] for s in response.json()['subjects'] if s['available']} == ({'math','chinese','ethics'} if grade==2 else {'math','chinese','english','ethics','history','geography','biology'})
        book=response.json()['items'][0]
        body={'book_id':book['id'],'chapter_id':book['chapters'][0]['id']}
        assert client.post('/api/v1/textbooks/search',headers=h,json=body).status_code==200
        for bad in [dict(body,collection='other'),dict(body,chapter_id='unknown'),
                    dict(body,book_id=f'math-g{7 if grade==2 else 2}-upper'),
                    dict(body,query='a'*161),dict(body,query=['a']),dict(body,page_offset=True),
                    dict(body,page_offset=-1),dict(body,page_offset=500),dict(body,page_offset=1,query='keyword')]:
            assert client.post('/api/v1/textbooks/search',headers=h,json=bad).status_code==422
        for book in response.json()['items']:
            for chapter in book['chapters']:
                body={'book_id':book['id'],'chapter_id':chapter['id']}
                scope=client.post('/api/v1/textbooks/search',headers=h,json=body)
                assert scope.status_code==200 and scope.json()['book']['collection']==book['collection']


def test_retrieval_excludes_old_editions_other_files_chapters_and_untrusted_links():
    scope=search_scope('math-g7-v1',{'book_id':'math-g7-upper','chapter_id':'2'})
    meta={'file_id':scope['book']['file_id'],'page_number':31,'edition':'pep-2022-standard-current'}
    bad=[dict(meta,file_id='old-file'),dict(meta,page_number=8),dict(meta,page_number='31'),
         dict(meta,edition='old'),dict(meta,page_number=True),None]
    result={'documents':[['wrong']*len(bad)+['<script>bad()</script>'+'a'*1500]*6],
            'metadatas':[bad+[dict(meta,url='javascript:bad()',source='private-path')]*6]}
    refs=bounded_references(scope,result)
    assert len(refs['items'])==1  # Multiple chunks on the same page share one original image.
    assert all(x['printed_page']==24 and x['review_status']=='reference_only' for x in refs['items'])
    assert all(len(x['text'])==1400 and x['page_image_path']=='/api/v1/textbooks/math-g7-upper/pages/24/image' for x in refs['items'])
    assert 'private-path' not in json.dumps(refs) and 'javascript:' not in json.dumps(refs)
    for bad_result in [[],{}, {'documents':[['x']],'metadatas':[[]]}]:
        with pytest.raises(ValueError): bounded_references(scope,bad_result)
    result['metadatas']=[[dict(meta,page_number=31+i) for i in range(6)]]
    result['documents']=[['reference']*6]
    assert len(bounded_references(scope,result)['items'])==4


def test_related_pages_follow_book_order_with_readable_content_titles():
    scope=search_scope('math-g7-v1',{'book_id':'math-g7-upper','chapter_id':'5'})
    pages=[151,122,122,130,117,118]
    result={'documents':[['unreliable extracted text']*len(pages)],
            'metadatas':[[{'file_id':scope['book']['file_id'],'page_number':p,'edition':'pep-2022-standard-current'} for p in pages]]}
    items=bounded_references(scope,result)['items']
    assert [i['printed_page'] for i in items]==[110,115,123,144]
    assert items[1]['content_title']=='一元一次方程的定义与等式的性质'
    assert items[3]['content_title']=='杠杆平衡探究：列一元一次方程'
    assert items[0]['content_title']==scope['chapter']['title']
    chinese=search_scope('math-g2-v1',{'book_id':'chinese-g2-lower','chapter_id':'2'})
    ref=bounded_references(chinese,{'documents':[['raw pinyin']], 'metadatas':[[{
        'file_id':chinese['book']['file_id'],'page_number':26,'edition':'pep-2022-standard-current'}]]})
    assert ref['items'][0]['content_title']=='课文：我不是最弱小的'


def test_chapter_browsing_is_complete_contiguous_and_bounded():
    for book in BOOKS:
        for chapter in book['chapters']:
            offset=0;seen=[]
            while offset is not None:
                scope=search_scope(f"math-g{book['grade']}-v1",{'book_id':book['id'],'chapter_id':chapter['id'],'page_offset':offset})
                result=chapter_references(scope)
                assert result['mode']=='browse' and 1<=len(result['items'])<=4
                assert result['previous_offset']==(max(0,offset-4) if offset else None)
                seen.extend(i['pdf_page'] for i in result['items'])
                offset=result['next_offset']
            assert seen==list(range(chapter['page_start'],chapter['page_end']+1))


def test_optional_chapter_browses_whole_book_and_titles_follow_actual_chapter():
    for book in BOOKS:
        curriculum = f"math-g{book['grade']}-v1"
        for omitted in ({}, {'chapter_id': ''}, {'chapter_id': None}):
            scope = search_scope(curriculum, {'book_id': book['id'], **omitted})
            assert scope['chapter']['id'] == ''
            assert chapter_references(scope)['items'][0]['printed_page'] == book['chapters'][0]['printed_page']
        first = book['chapters'][0]['page_start']
        for chapter in book['chapters']:
            scope = search_scope(curriculum, {'book_id': book['id'], 'page_offset': chapter['page_start'] - first})
            ref = chapter_references(scope)['items'][0]
            scoped = chapter_references(search_scope(curriculum, {'book_id': book['id'], 'chapter_id': chapter['id']}))['items'][0]
            assert ref == scoped
        last = book['chapters'][-1]['page_end'] - first
        result = chapter_references(search_scope(curriculum, {'book_id': book['id'], 'page_offset': last}))
        assert len(result['items']) == 1 and result['next_offset'] is None
        with pytest.raises(ValueError):
            search_scope(curriculum, {'book_id': book['id'], 'page_offset': last + 1})
    scope = search_scope('math-g7-v1', {'book_id': 'math-g7-upper', 'query': '有理数'})
    assert scope['query'] == '有理数' and scope['mode'] == 'search'


def test_challenge_rejects_different_subject_book_or_chapter_without_writes(family):
    _, db, client, headers = family
    for grade in (2, 7):
        h = {**headers, 'X-Learner-Id': f'family-g{grade}'}
        choices = client.get('/api/v1/question-choices', headers=h).json()['items']
        mapped = [item for item in choices if item['textbook_scope']]
        assert len(mapped) == (4 if grade == 2 else 6)
        assert [i['textbook_scope']['chapter_id'] for i in mapped] == (['2','5','5','5'] if grade == 2 else ['2'] * 6)
        for choice in mapped:
            placement = choice['textbook_scope']
            valid = {'question_version_id': choice['question_version_id'], 'textbook_book_id': placement['book_id']}
            for chapter_id in (None, '', placement['chapter_id']):
                assert client.post('/api/v1/test-sessions', headers=h, json={**valid, 'textbook_chapter_id': chapter_id}).status_code == 201
            with db.session() as conn:
                before = conn.execute('SELECT count(*) FROM test_sessions').fetchone()[0]
            for invalid in ({'textbook_chapter_id':'1'}, {'textbook_book_id':f'chinese-g{grade}-upper'},
                            {'textbook_book_id':f'math-g{grade}-lower'}, {'textbook_book_id':None, 'textbook_chapter_id':'2'}):
                assert client.post('/api/v1/test-sessions', headers=h, json={**valid, **invalid}).status_code == 422
            with db.session() as conn:
                assert conn.execute('SELECT count(*) FROM test_sessions').fetchone()[0] == before
        for choice in choices:
            if not choice['textbook_scope']:
                assert client.post('/api/v1/test-sessions', headers=h, json={
                    'question_version_id':choice['question_version_id'], 'textbook_book_id':f'math-g{grade}-upper'}).status_code == 422


def test_gateway_chapter_browse_does_not_depend_on_vector_ranking(retrieval_gateway):
    s,db,bridge,client=retrieval_gateway
    bridge.retrieval_error=True
    h={**csrf(s,client),'X-Learner-Context-Version':'1'}
    body={'book_id':'math-g7-upper','chapter_id':'5'}
    response=client.post('/learning/api/v1/textbooks/search',headers=h,json=body)
    assert response.status_code==200
    assert [i['printed_page'] for i in response.json()['items']]==[110,111,112,113]
    next_page=client.post('/learning/api/v1/textbooks/search',headers=h,json=dict(body,page_offset=4))
    assert [i['printed_page'] for i in next_page.json()['items']]==[114,115,116,117]
    assert not any(c[2]=='/api/v1/retrieval/query/doc' for c in bridge.calls)


@pytest.fixture
def textbook_sources(tmp_path, monkeypatch):
    import fitz
    directory=tmp_path/'textbooks'; directory.mkdir()
    for book in BOOKS:
        book_id=book['id'];offset=book['chapters'][0]['page_start']-book['chapters'][0]['printed_page']
        total=book['chapters'][-1]['page_end']
        with fitz.open() as doc:
            for n in range(1,total+1):
                page=doc.new_page(width=320,height=440)
                page.insert_text((30,40), f'{book_id} - printed page {n-offset}')
                page.insert_text((40,100), 'n * x = l / 2', fontsize=18)
                page.draw_line((60,200),(240,200))
                page.draw_rect((100,230,115,250),fill=(0.2,0.5,0.7))
                page.draw_line((150,200),(150,160))
                page.insert_text((30,410), str(n-offset))
            path=directory/(book_id+'.pdf'); doc.save(path)
        monkeypatch.setitem(PDF_SHA256,book_id,hashlib.sha256(path.read_bytes()).hexdigest())
    return directory


def test_page_renders_exact_source_preserving_diagram_and_pdf_page_offset(family,textbook_sources):
    import fitz
    _,_,client,headers=family
    client.app.state.settings=replace(client.app.state.settings,textbook_dir=textbook_sources)
    for book_id,printed,physical,grade in [('math-g7-upper',144,151,7),('math-g7-upper',115,122,7),
                                         ('math-g7-lower',87,94,7),('math-g2-upper',10,15,2)]:
        result=client.get(f'/api/v1/textbooks/{book_id}/pages/{printed}/image',headers={**headers,'X-Learner-Id':f'family-g{grade}'})
        assert result.status_code==200 and result.headers['content-type']=='image/png'
        assert result.headers['cache-control']=='no-store'
        with fitz.open(textbook_sources/(book_id+'.pdf')) as doc:
            expected=doc[physical-1].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).tobytes('png')
        assert result.content==expected
    h={**headers,'X-Learner-Id':'family-g7'}
    for book_id,page in [('math-g2-upper',10),('math-g7-upper',0),('math-g7-upper',195),('unknown',1)]:
        assert client.get(f'/api/v1/textbooks/{book_id}/pages/{page}/image',headers=h).status_code==404
    path='/api/v1/textbooks/math-g7-upper/pages/144/image'
    assert client.get(path).status_code==401
    (textbook_sources/'math-g7-upper.pdf').write_bytes(b'wrong edition')
    result=client.get(path,headers=h)
    assert result.status_code==503 and 'wrong edition' not in result.text
    (textbook_sources/'math-g7-upper.pdf').unlink()
    assert client.get(path,headers=h).status_code==503
    for book in catalogue('math-g7-v1'):
        if book['subject']=='math':continue
        response=client.get(f"/api/v1/textbooks/{book['id']}/pages/{book['chapters'][0]['printed_page']}/image",headers=h)
        assert response.status_code==200 and response.headers['content-type']=='image/png'


def test_gateway_image_requires_identity_grade_and_current_context(retrieval_gateway,textbook_sources):
    s,db,bridge,client=retrieval_gateway
    bridge.api.app.state.settings=replace(bridge.api.app.state.settings,textbook_dir=textbook_sources)
    path='/learning/api/v1/textbooks/math-g7-upper/pages/144/image'
    response=client.get(path,headers={'X-Learner-Context-Version':'1'})
    assert response.status_code==200 and response.content.startswith(b'\x89PNG')
    assert response.headers['content-type']=='image/png'
    assert client.get(path).status_code==409
    assert client.get(path,headers={'X-Learner-Context-Version':'0'}).status_code==409
    assert client.get(path.replace('g7','g2'),headers={'X-Learner-Context-Version':'1'}).status_code==404
    for book in catalogue('math-g7-v1'):
        page=book['chapters'][0]['printed_page']
        response=client.get(f"/learning/api/v1/textbooks/{book['id']}/pages/{page}/image",headers={'X-Learner-Context-Version':'1'})
        assert response.status_code==200 and response.content.startswith(b'\x89PNG')
    assert not any(c[2]=='/api/v1/retrieval/query/doc' for c in bridge.calls)
    client.cookies.clear()
    assert client.get(path,headers={'X-Learner-Context-Version':'1'}).status_code==401


class RetrievalBridge(SyntheticBridge):
    retrieval_status=200
    retrieval_body=None
    retrieval_error=False

    def send(self,upstream,method,path,headers,body=b'',**kwargs):
        if path=='/api/v1/retrieval/query/doc':
            self.calls.append((upstream,method,path,dict(headers),body))
            assert headers=={'Cookie':'token=synthetic-token-a','Accept':'application/json','Content-Type':'application/json'}
            assert method=='POST' and upstream=='http://webui.invalid:8080'
            if self.retrieval_error: raise TimeoutError('synthetic-token-a SECRET')
            book=catalogue('math-g7-v1')[0]
            payload={'documents':[['chapter reference']], 'metadatas':[[{'file_id':book['file_id'],
                     'page_number':8,'edition':'pep-2022-standard-current'}]]}
            return GatewayResult(self.retrieval_status,self.retrieval_body or json.dumps(payload).encode(),
                                 (('Set-Cookie','token=do-not-forward'),))
        return super().send(upstream,method,path,headers,body,**kwargs)


@pytest.fixture
def retrieval_gateway(gateway_env):
    s,db,settings,old,_=gateway_env
    with db.session(write=True) as conn:
        conn.execute("UPDATE learners SET curriculum_id='math-g7-v1' WHERE id='learner-a'")
    bridge=RetrievalBridge(old.api)
    client=TestClient(create_gateway(settings,bridge),base_url=s.browser_origin)
    client.cookies.set('token','synthetic-token-a')
    assert gateway_login(s,client)[0].status_code==303
    assert client.post('/learning/api/v1/learner-context',json={'learner_id':'learner-a','expected_revision':0},
                       headers=csrf(s,client)).status_code==200
    return s,db,bridge,client


@pytest.mark.parametrize('case',['success','csrf','stale','grade','large','upstream','malformed','timeout'])
def test_gateway_authorizes_before_retrieval_and_never_leaks_tokens(retrieval_gateway,case):
    s,db,bridge,client=retrieval_gateway
    headers={**csrf(s,client),'X-Learner-Context-Version':'1'}
    body={'book_id':'math-g7-upper','chapter_id':'1','query':'正数和负数'}
    if case=='csrf': headers.pop('X-CSRF-Token')
    if case=='stale': headers['X-Learner-Context-Version']='0'
    if case=='grade': body['book_id']='math-g2-upper'
    if case=='large': body['query']='a'*4100
    if case=='upstream': bridge.retrieval_status=401
    if case=='malformed': bridge.retrieval_body=b'[]'
    if case=='timeout': bridge.retrieval_error=True
    result=client.post('/learning/api/v1/textbooks/search',headers=headers,json=body)
    calls=[c for c in bridge.calls if c[2]=='/api/v1/retrieval/query/doc']
    if case=='success':
        assert result.status_code==200
        assert result.json()['items'][0]['text']=='chapter reference'
        request=json.loads(calls[0][4])
        assert request['collection_name']==catalogue('math-g7-v1')[0]['collection']
        assert request['hybrid'] is False
        assert not result.headers.get_list('set-cookie')
    elif case in ['csrf','stale','grade','large']:
        assert result.status_code in {403,409,413,422} and not calls
    else:
        assert result.status_code in {502,503} and len(calls)==1
    assert 'synthetic-token-a' not in result.text and 'SECRET' not in result.text
