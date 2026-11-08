"""Two viewport synthetic collection/review flows, no external requests."""
from dataclasses import replace
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app, run_worker_once
from learning_service.browser_auth import SESSION_COOKIE, CSRF_COOKIE
from learning_service.practice import bank, install
from test_browser_auth import assertion
from test_family_math import family
from test_practice_collection import rows

pytestmark=pytest.mark.browser


@pytest.mark.parametrize('width',[390,1280])
def test_confirm_cancel_retry_due_review_and_context_change(family,tmp_path,width,playwright,launch_browser):
    _,db,original,_=family;install(db)
    origin='https://collection.example.invalid'
    settings=replace(original.app.state.settings,browser_auth_enabled=True,
        browser_auth_secret='synthetic-gateway-key-0123456789abcdef',browser_auth_issuer='synthetic-gateway',
        browser_identity_issuer='family-pilot-webui',browser_origin=origin,public_base_path='/learning',
        shared_learner_context_enabled=True,family_setup_code='synthetic-family-code-0123456789abcdef')
    api=TestClient(create_app(settings,db),base_url=origin)
    assert api.post('/api/v1/auth/session',headers={'Origin':origin,'Authorization':'Bearer '+assertion(settings,changes={'sub':'synthetic-parent'})}).status_code==201
    folder=Path(os.getenv('DD_COLLECTION_EVIDENCE_DIR',str(tmp_path)));folder.mkdir(parents=True,exist_ok=True)
    errors=[];requests=[];drop_response=[True];keys=[]
    with playwright.sync_playwright() as runtime:
        browser=launch_browser(runtime)
        context=browser.new_context(viewport={'width':width,'height':960},service_workers='block')
        context.add_cookies([{'name':n,'value':v,'url':origin,'secure':True,'httpOnly':n==SESSION_COOKIE,'sameSite':'Strict'} for n,v in api.cookies.items()])
        def handle(route):
            request=route.request;url=urlsplit(request.url)
            assert url.scheme+'://'+url.netloc==origin
            requests.append((request.method,url.path))
            if '/api/v1/attempts/' in url.path and request.method=='GET' and not url.path.endswith('collection-preview'):
                run_worker_once(db,settings)
            response=api.request(request.method,url.path.removeprefix('/learning'),headers=request.all_headers(),
                                 content=request.post_data_buffer,follow_redirects=False)
            if url.path.endswith('/collection'):
                keys.append(request.all_headers().get('idempotency-key'))
                if response.status_code==201 and drop_response[0]:
                    drop_response[0]=False
                    route.fulfill(status=503,json={'error':{'message':'合成：响应丢失，可重试'}});return
            route.fulfill(status=response.status_code,body=response.content,
                headers={k:v for k,v in response.headers.items() if k not in ('content-length','set-cookie')})
        context.route('**/*',handle)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        expect=playwright.expect
        page.goto(origin+'/learning/ui')
        page.locator('.profile-card[data-grade="7"]').click()
        expect(page.locator('#practiceChoices button')).to_have_count(30)
        page.locator('#textbookChapter').select_option('2')
        page.locator('#scopeChallenge').click()
        qid=page.locator('#questionVersion').input_value();question=bank()[qid]
        page.locator('#requestHint').click()
        expect(page.locator('#gameHint')).to_be_visible()
        page.locator('#answer').fill('<script>throw 1</script>')
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('值得再研究')
        expect(page.locator('#previewCollection')).to_be_visible()
        before=rows(db);request_start=len(requests)
        page.locator('#previewCollection').click()
        expect(page.locator('#collectionDialog')).to_be_visible()
        expect(page.locator('#collectionPrompt')).to_have_text(question['prompt'])
        expect(page.locator('#collectionAnswer')).to_contain_text('<script>throw 1</script>')
        expect(page.locator('#collectionAssistance')).to_contain_text('辅助练习')
        page.screenshot(path=str(folder/f'confirm-preview-{width}.png'),full_page=True)
        page.locator('#cancelCollection').click()
        expect(page.locator('#collectionDialog')).not_to_be_visible()
        expect(page.locator('#collectionStatus')).to_contain_text('未新增')
        assert rows(db)==before
        assert all(method=='GET' for method,path in requests[request_start:])
        page.locator('#previewCollection').click();page.locator('#confirmCollection').click()
        expect(page.locator('#collectionError')).to_contain_text('响应丢失')
        with db.session() as c:
            assert c.execute('SELECT count(*) FROM mistake_entries').fetchone()[0]==1
        page.locator('#confirmCollection').click()
        expect(page.locator('#collectionStatus')).to_contain_text('已保存')
        assert len(keys)==2 and keys[0]==keys[1]
        page.locator('[data-game-view="notebook"]').click()
        expect(page.locator('#mistakes .review-card')).to_have_count(1)
        page.locator('#mistakes button').click()
        expect(page.locator('#mistakes')).to_contain_text('辅助练习')
        expect(page.locator('#mistakes')).to_contain_text(qid)
        page.screenshot(path=str(folder/f'collection-saved-{width}.png'),full_page=True)
        # Advance only this synthetic card's due fixture, never real dates/results.
        with db.session(write=True) as c:
            c.execute("UPDATE review_cards SET due_at='2020-01-01T00:00:00+00:00'")
        page.locator('[data-game-view="home"]').click()
        expect(page.locator('#today')).to_contain_text('复习收藏原题')
        page.locator('#today button').click()
        expect(page.locator('#testPrompt')).to_have_text(question['prompt'])
        assert page.locator('#questionVersion').input_value()==qid
        page.locator('#answer').fill(question['answer']);page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对了')
        with db.session() as c:
            card=c.execute('SELECT stage,due_at FROM review_cards').fetchone()
            assert card['stage']==1 and card['due_at']>'2020-01-01T00:00:00+00:00'
            assert c.execute('SELECT count(*) FROM review_events').fetchone()[0]==1
            assert c.execute('SELECT count(*) FROM mistake_entries').fetchone()[0]==1
        # Reopen a new wrong attempt; another tab switches the shared learner
        # before confirmation. The stale dialog must clear without writing.
        page.locator('#nextChallenge').click()
        page.locator('#answer').fill('999999');page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('值得再研究')
        page.locator('#previewCollection').click();expect(page.locator('#collectionDialog')).to_be_visible()
        state=api.get('/api/v1/learner-context').json()
        response=api.post('/api/v1/learner-context',headers={'Origin':origin,'X-CSRF-Token':api.cookies[CSRF_COOKIE]},
                         json={'learner_id':'family-g2','expected_revision':state['context_version']})
        assert response.status_code==200,response.text
        before=rows(db)
        page.locator('#confirmCollection').click()
        expect(page.locator('#collectionDialog')).not_to_be_visible()
        expect(page.locator('#collectionPrompt')).to_have_text('')
        assert rows(db)==before
        page.reload()
        page.locator('[data-game-view="notebook"]').click()
        expect(page.locator('#mistakes')).to_contain_text('收藏夹还是空的')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert not errors,errors
        with db.session() as c:
            assert c.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0
        (folder/f'report-{width}.json').write_text(json.dumps({'width':width,'external_requests':0,
            'page_errors':errors,'cancel_business_rows_unchanged':True,'lost_response_retry_same_key':True,
            'due_original_review_scheduled_once':True,'stale_context_confirmation_blocked':True,
            'horizontal_overflow':False,'browser_version':browser.version},ensure_ascii=False,indent=2))
        context.close();browser.close()
