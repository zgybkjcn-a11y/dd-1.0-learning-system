"""Offline public example: parameter arithmetic, subject selection and export."""
import json
import os
from pathlib import Path

import pytest


@pytest.mark.parametrize('width',[390,1280])
def test_offline_understanding_workshop(width,tmp_path):
    playwright=pytest.importorskip('playwright.sync_api')
    directory=Path(os.getenv('DD_STUDY_EXAMPLES_DIR', str(Path(__file__).parents[1]/'learning_data/verification/scenarios-integration-20261106/examples-v3')))
    if not (directory/'offline-study.html').is_file():
        pytest.skip('generate the public offline examples before browser verification')
    with playwright.sync_playwright() as runtime:
        browser=runtime.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True)
        context=browser.new_context(viewport={'width':width,'height':950},service_workers='block')
        page=context.new_page();page.set_default_timeout(5000);errors=[];requests=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.on('request',lambda req:requests.append(req.url))
        page.set_content((directory/'offline-study.html').read_text(),wait_until='load')
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
