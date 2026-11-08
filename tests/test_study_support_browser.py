"""Offline template with synthetic references: parameter arithmetic, subject selection and export."""
import json
from pathlib import Path

import pytest

from test_math_references import reference_family
from test_family_math import family


@pytest.fixture
def offline_example(reference_family, tmp_path):
    from scripts.prepare_study_support_examples import HTML
    from learning_service.math_references import query_reference
    from learning_service.study_support import query_support
    from learning_service.textbooks import catalogue

    _, db, client, _ = reference_family
    directory = client.app.state.settings.textbook_dir
    payload = {'books': [], 'scopes': {}}
    for grade in (2, 7):
        curriculum = f'math-g{grade}-v1'
        for book in catalogue(curriculum):
            payload['books'].append({k: book[k] for k in ('id', 'grade', 'subject', 'subject_title', 'semester', 'chapters')})
            for chapter in ['', *[c['id'] for c in book['chapters']]]:
                with db.session() as conn:
                    args = dict(book_id=book['id'], chapter_id=chapter)
                    support = query_support(conn, f'family-g{grade}', curriculum, directory, **args)
                    math = query_reference(conn, f'family-g{grade}', curriculum, directory, **args) if book['subject'] == 'math' else None
                payload['scopes'][book['id'] + '|' + chapter] = {'support': support, 'math': math}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    path = tmp_path / 'offline-study.html'
    path.write_text(HTML.replace('__DATA__', encoded))
    return path


pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width',[390,1280])
def test_offline_understanding_workshop(width,tmp_path, playwright, launch_browser, offline_example):
    directory = tmp_path
    with playwright.sync_playwright() as runtime:
        browser=launch_browser(runtime)
        context=browser.new_context(viewport={'width':width,'height':950},service_workers='block',offline=True)
        page=context.new_page();page.set_default_timeout(5000);errors=[];requests=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.on('request',lambda req:requests.append(req.url))
        page.set_content(offline_example.read_text(),wait_until='load')
        assert page.locator('#grade').input_value()=='2'
        assert page.locator('#lineControls').is_hidden()
        page.locator('#each').evaluate('(e)=>{e.value=2;e.dispatchEvent(new Event("input"))}')
        page.locator('#groups').evaluate('(e)=>{e.value=5;e.dispatchEvent(new Event("input"))}')
        assert page.locator('#visual circle').count()==10
        assert '2 × 5 = 10' in page.locator('#calculation').inner_text()
        assert '10 ÷ 5 = 2（每组）' in page.locator('#calculation').inner_text()
        assert '10 ÷ 2 = 5（组数）' in page.locator('#calculation').inner_text()
        page.locator('#chapter').select_option('2')
        assert '÷' not in page.locator('#calculation').inner_text()
        page.locator('#chapter').select_option('3')
        assert '÷' in page.locator('#calculation').inner_text()
        page.locator('#grade').select_option('7')
        page.locator('#start').evaluate('(e)=>{e.value=-3;e.dispatchEvent(new Event("input"))}')
        page.locator('#change').evaluate('(e)=>{e.value=-5;e.dispatchEvent(new Event("input"))}')
        page.locator('#operation').select_option('subtract')
        assert '− (-5) = 2' in page.locator('#calculation').inner_text()
        assert page.locator('#groupControls').is_hidden()
        page.locator('#chapter').select_option('5')
        assert page.locator('#mathPanel').is_hidden()
        assert '零' in page.locator('#concepts').inner_text()
        for book in ('english-g7-upper','history-g7-upper','geography-g7-upper','biology-g7-upper'):
            page.locator('#book').select_option(book)
            page.locator('#chapter').select_option('2')
            assert page.locator('#mathPanel').is_hidden()
            assert page.locator('#steps article').count()==3
            assert '暂未建立精确' in page.locator('#mapping').inner_text()
            assert page.locator('#concepts article').count()==0
        with page.expect_download() as download:
            page.locator('#download').click()
        path=download.value.path()
        assert 'marp: true' in Path(path).read_text()
        assert '生物' in Path(path).read_text()
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(directory/f'offline-workshop-{width}.png'),full_page=True)
        assert not errors and not requests
        report={'width':width,'parameter_math':'passed','subjects':'passed','export':'passed','page_errors':errors,
                'network_requests':requests,'overflow':False}
        (directory/f'browser-{width}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        browser.close()
