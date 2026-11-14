"""New lower books: complete navigation and no misleading search/practice controls."""
import json
import os
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from learning_service.app import create_app
from learning_service.browser_auth import SESSION_COOKIE
from learning_service.textbooks import BOOKS, chapter_references
from test_browser_auth import assertion
from test_family_math import family

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [390, 1280])
def test_new_books_read_with_grade_isolation_and_page_navigation(family, tmp_path, width, textbook_sources, playwright, launch_browser):
    _, db, original, _ = family
    origin = 'https://textbook-completion.example.invalid'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
                       browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                       browser_auth_issuer='synthetic-gateway', browser_identity_issuer='family-pilot-webui',
                       browser_origin=origin, public_base_path='/learning', shared_learner_context_enabled=True,
                       family_setup_code='synthetic-family-code-0123456789abcdef', textbook_dir=textbook_sources)
    api = TestClient(create_app(settings, db), base_url=origin)
    assert api.post('/api/v1/auth/session', headers={'Origin': origin,
        'Authorization': 'Bearer ' + assertion(settings, changes={'sub': 'synthetic-parent'})}).status_code == 201
    out = Path(os.getenv('DD_TEXTBOOK_COMPLETION_EVIDENCE', str(tmp_path))); out.mkdir(exist_ok=True, parents=True)
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(viewport={'width': width, 'height': 960}, service_workers='block')
        context.add_cookies([{'name': n, 'value': v, 'url': origin, 'secure': True,
            'httpOnly': n == SESSION_COOKIE, 'sameSite': 'Strict'} for n,v in api.cookies.items()])
        calls=[]
        def handle(route):
            u=urlsplit(route.request.url)
            assert u.scheme+'://'+u.netloc==origin
            response=api.request(route.request.method,u.path.removeprefix('/learning'),
                headers=route.request.all_headers(),content=route.request.post_data_buffer,follow_redirects=False)
            if u.path.endswith('/textbooks/search') and response.status_code==200:
                scope=response.json(); assert scope['mode']=='browse'; calls.append(scope['book']['id'])
                route.fulfill(status=200,json=chapter_references(scope));return
            route.fulfill(status=response.status_code,body=response.content,
                headers={k:v for k,v in response.headers.items() if k not in ('content-length','set-cookie')})
        context.route('**/*',handle)
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(origin+'/learning/ui');expect=playwright.expect
        for grade in (2,7):
            page.locator(f'.profile-card[data-grade="{grade}"]').click()
            added=[b for b in BOOKS if b['grade']==grade and b.get('search_available') is False]
            for book in added:
                page.locator('#textbookSubject').select_option(book['subject'])
                page.locator('#textbookBook').select_option(book['id'])
                expect(page.locator('#textbookQuery')).to_be_disabled()
                expect(page.locator('#textbookFind')).to_be_disabled()
                expect(page.locator('#startAdventure')).to_be_disabled()
                page.locator('#textbookSearch').click()
                first=book['chapters'][0]['printed_page']
                expect(page.locator('#textbookPageRange')).to_have_text(f'第 {first} 页')
                expect(page.locator('#textbookPagePrev')).to_be_disabled()
                expect(page.locator('#textbookResults img')).to_have_count(1)
                page.locator('#textbookPageInput').fill(str(book['chapters'][1]['printed_page']-1))
                page.locator('#textbookJump').click()
                expect(page.locator('#textbookPageRange')).to_have_text(f"第 {book['chapters'][1]['printed_page']-1} 页")
                page.locator('#textbookResults img').click()
                page.locator('#textbookZoomNext').click()
                expect(page.locator('#textbookPageRange')).to_have_text(f"第 {book['chapters'][1]['printed_page']} 页")
                expect(page.locator('#textbookZoom')).to_be_visible()
                expect(page.locator('#textbookToc button[aria-current="true"]')).to_have_attribute('data-chapter',book['chapters'][1]['id'])
                page.locator('#textbookZoomClose').click()
                last=book['chapters'][-1];end=last['printed_page']+last['page_end']-last['page_start']
                page.locator('#textbookPageInput').fill(str(end));page.locator('#textbookJump').click()
                expect(page.locator('#textbookPageRange')).to_have_text(f'第 {end} 页')
                expect(page.locator('#textbookPageNext')).to_be_disabled()
                expect(page.locator('#textbookPagePrev')).to_be_enabled()
            page.screenshot(path=str(out/f'grade{grade}-lower-{width}.png'),full_page=True)
            page.locator('#textbookSubject').select_option('math')
            page.locator('#textbookBook').select_option(f'math-g{grade}-upper')
            expect(page.locator('#textbookQuery')).to_be_enabled()
            expect(page.locator('#textbookFind')).to_be_enabled()
        assert set(calls)>={b['id'] for b in BOOKS if b.get('search_available') is False}
        assert not errors
        context.close();browser.close()
