"""Authenticated family workbench support, scope races and source-page links."""
from dataclasses import replace
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.browser_auth import SESSION_COOKIE
from learning_service.textbooks import chapter_references
from test_browser_auth import assertion
from test_family_math import family
from test_math_references import reference_family


pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width',[390,1280])
def test_study_support_in_authenticated_family_workbench(reference_family,tmp_path,width, playwright, launch_browser):
    _,db,original,_=reference_family
    origin='https://study-support.example.invalid'
    settings=replace(original.app.state.settings,browser_auth_enabled=True,
                     browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                     browser_auth_issuer='synthetic-gateway',browser_identity_issuer='family-pilot-webui',
                     browser_origin=origin,public_base_path='/learning',shared_learner_context_enabled=True,
                     family_setup_code='synthetic-family-code-0123456789abcdef')
    api=TestClient(create_app(settings,db),base_url=origin)
    assert api.post('/api/v1/auth/session',headers={'Origin':origin,
                    'Authorization':'Bearer '+assertion(settings,changes={'sub':'synthetic-parent'})}).status_code==201
    evidence=Path(os.getenv('DD_STUDY_WORKBENCH_EVIDENCE',str(tmp_path)))
    evidence.mkdir(parents=True,exist_ok=True)
    with playwright.sync_playwright() as runtime:
        browser=launch_browser(runtime)
        context=browser.new_context(viewport={'width':width,'height':960},service_workers='block')
        context.add_cookies([{'name':name,'value':value,'url':origin,'secure':True,'httpOnly':name==SESSION_COOKIE,'sameSite':'Strict'}
                            for name,value in api.cookies.items()])
        page=context.new_page();page.set_default_timeout(10000)
        errors=[];calls=[];delay=[False];pending=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        def handle(route):
            request=route.request;url=urlsplit(request.url)
            assert url.scheme+'://'+url.netloc==origin
            path=url.path.removeprefix('/learning')+('?' + url.query if url.query else '')
            calls.append((request.method,path))
            response=api.request(request.method,path,headers=request.all_headers(),content=request.post_data_buffer,
                                 follow_redirects=False)
            if path=='/api/v1/textbooks/search' and response.status_code==200:
                route.fulfill(status=200,json=chapter_references(response.json()));return
            if path.startswith('/api/v1/study-support') and delay[0]:
                delay[0]=False;pending.append((route,response));return
            route.fulfill(status=response.status_code,body=response.content,
                          headers={k:v for k,v in response.headers.items() if k not in ('content-length','set-cookie')})
        context.route('**/*',handle)
        page.goto(origin+'/learning/ui');expect=playwright.expect
        assert not errors, errors
        expect(page.locator('#studySupportOpen')).to_be_disabled()
        page.locator('.profile-card[data-grade="2"]').click()
        expect(page.locator('#studySupportOpen')).to_be_enabled()
        page.locator('#textbookChapter').select_option('2')
        page.locator('#studySupportOpen').click()
        expect(page.locator('#studySteps article')).to_have_count(3)
        expect(page.locator('#studyCalculation')).to_contain_text('3 × 4 = 12')
        assert '÷' not in page.locator('#studyCalculation').inner_text()  # No future division in ch2.
        page.locator('#textbookChapter').select_option('3')
        expect(page.locator('#studyCalculation')).to_contain_text('12 ÷ 4 = 3（每组）')
        page.locator('#studyEach').evaluate('(e)=>{e.value=2;e.dispatchEvent(new Event("input"))}')
        page.locator('#studyGroups').evaluate('(e)=>{e.value=5;e.dispatchEvent(new Event("input"))}')
        expect(page.locator('#studyCalculation')).to_contain_text('10 ÷ 2 = 5（组数）')
        assert page.locator('#studyVisual circle').count()==10
        expect(page.locator('#studyConcepts article')).not_to_have_count(0)
        page.locator('#studyConcepts button').first.click()
        expect(page.locator('#textbookZoom')).to_be_visible()
        page.wait_for_function('document.getElementById("textbookZoomImage").naturalWidth > 0')
        page.locator('#textbookZoomClose').click()
        assert page.locator('#textbookChapter').input_value()=='3'
        with page.expect_download() as download:page.locator('#studyDownload').click()
        assert '本册原页' in Path(download.value.path()).read_text()
        page.reload()
        expect(page.locator('#textbookChapter')).to_have_value('3')
        page.locator('#studySupportOpen').click()
        expect(page.locator('#studyCalculation')).to_contain_text('12 ÷ 4')
        page.locator('.profile-card[data-grade="7"]').click()
        expect(page.locator('#studySupport')).not_to_have_attribute('open','')
        expect(page.locator('#studyConcepts article')).to_have_count(0)
        expect(page.locator('#textbookBook')).to_have_value('math-g7-upper')
        page.locator('#textbookChapter').select_option('2')
        page.locator('#studySupportOpen').click()
        expect(page.locator('#studyStart')).to_be_visible()
        page.locator('#studyChange').evaluate('(e)=>{e.value=-5;e.dispatchEvent(new Event("input"))}')
        page.locator('#studyOperation').select_option('subtract')
        expect(page.locator('#studyCalculation')).to_contain_text('− (-5) = 2')
        page.locator('#textbookChapter').select_option('5')
        expect(page.locator('#studyDemo')).to_be_hidden()
        expect(page.locator('#studyConcepts')).to_contain_text('零')
        # Leave a previous scope's response pending while opening biology.
        delay[0]=True;page.locator('#textbookChapter').select_option('2')
        page.wait_for_function('document.getElementById("studySupportStatus").textContent.includes("正在")')
        assert pending
        page.locator('#textbookSubject').select_option('biology')
        expect(page.locator('#studySteps')).to_contain_text('观察结构')
        old_route,old_response=pending.pop()
        old_route.fulfill(status=old_response.status_code,body=old_response.content,content_type='application/json')
        expect(page.locator('#studySupportStatus')).to_contain_text('生物')
        expect(page.locator('#studyConcepts article')).to_have_count(0)
        expect(page.locator('#studyDemo')).to_be_hidden()
        for subject,text in [('history','定位时空'),('geography','先看地图'),('english','先理解情境'),('chinese','整体理解'),('ethics','辨认情境')]:
            page.locator('#textbookSubject').select_option(subject)
            expect(page.locator('#studySteps')).to_contain_text(text)
            expect(page.locator('#studyConcepts article')).to_have_count(0)
        with page.expect_download() as download:page.locator('#studyDiagram').click()
        assert '学习步骤' in Path(download.value.path()).read_text()
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(evidence/f'study-workbench-{width}.png'),full_page=True)
        assert not errors
        assert not any(method=='POST' and ('test-sessions' in path or 'variant' in path or 'mistakes/manual' in path) for method,path in calls)
        with db.session() as conn:
            assert conn.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==0
            assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0]==0
        report={'width':width,'page_errors':errors,'scope_switch_race':'passed','profile_switch':'passed',
                'math_parameters':'passed','page_image':'decoded','chapter_restoration':'passed',
                'seven_subjects':'passed','exports':'passed','horizontal_overflow':False,'attempts_created':0,'provider_calls':0}
        (evidence/f'study-workbench-{width}.json').write_text(json.dumps(report,indent=2)+'\n')
        browser.close()
