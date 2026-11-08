"""Reviewed excerpt reader and saved citation reopening through real gateway."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from test_runtime_passages import stack, runtime_bundle, reseal, invoke_search
from test_readonly_study_tools import chat_tools
from test_math_references import reference_family
from test_family_math import family

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [390, 1280])
def test_excerpt_reader_links_withdrawal_cached_navigation_and_profile_switch(stack, width, playwright, launch_browser, tmp_path):
    origin = stack['settings'].browser_origin
    gateway = stack['gateway']
    bridge_source = Path('deploy/open-webui-reuse/main-study/family-bridge.js').read_text()
    errors, calls = [], []
    data, _ = invoke_search(stack)
    saved_url = data['passages'][0]['url']
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(viewport={'width': width, 'height': 960}, service_workers='block')
        context.add_cookies([{'name': k, 'value': v, 'url': origin, 'secure': True, 'sameSite': 'Strict'} for k, v in gateway.cookies.items()])
        def handle(route):
            request = route.request; url = urlsplit(request.url)
            assert url.scheme + '://' + url.netloc == origin
            calls.append(url.path)
            response = gateway.request(request.method, url.path + ('?' + url.query if url.query else ''),
                headers=request.all_headers(), content=request.post_data_buffer, follow_redirects=False)
            body = response.content
            if url.path == '/learning/ui': body = response.text.replace('</body>', '<script>' + bridge_source + '</script></body>').encode()
            route.fulfill(status=response.status_code, body=body, headers={k: v for k, v in response.headers.items() if k not in ('content-length', 'set-cookie')})
        context.route('**/*', handle)
        page = context.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(origin + '/learning/ui')
        expect = playwright.expect
        expect(page.locator('#textbookBook')).to_have_value('math-g7-upper')
        page.locator('#textbookChapter').select_option('2')
        page.locator('#textbookReader').evaluate('(e) => e.open = true')
        page.locator('#textbookQuery').fill('减法规则与倒数定义分别是什么')
        page.locator('#textbookFind').click()
        expect(page.locator('.textbook-excerpt')).to_contain_text('原创合成规则测试 1')
        expect(page.locator('.textbook-excerpt-context')).to_contain_text('非教师审核')
        expect(page.locator('.textbook-excerpt-context')).to_contain_text('PDF 第 38 页')
        page.wait_for_function('document.querySelector(".textbook-page-image").naturalWidth > 0')
        assert not page.locator('main').evaluate('(e) => e.scrollWidth > e.clientWidth')
        out = Path(os.getenv('DD_PASSAGE_BROWSER_OUT', str(tmp_path))); out.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out / f'passages-{width}.png'))
        # Withdraw a hit while the reader retains its original search list.
        stack['manifest']['passages'][2]['enabled'] = False; reseal(stack)
        page.locator('#textbookNext').click()
        expect(page.locator('.textbook-excerpt')).to_have_count(0)
        expect(page.locator('#textbookStatus')).to_contain_text('失效')
        assert any('/passages/' in path for path in calls)
        # Citation reopening resolves identity and current validity; it cannot
        # recover an old quote by browsing the still-readable original page.
        url = saved_url
        page.evaluate('(url) => {location.hash = new URL(url).hash}', url)
        expect(page.locator('#dd-family-continue button')).to_be_visible()
        page.locator('#dd-family-continue button').click()
        expect(page.locator('.textbook-excerpt')).to_contain_text('原创合成规则测试 1')
        stack['manifest']['passages'][1]['enabled'] = False; reseal(stack)
        page.goto(url)
        expect(page.locator('#dd-family-continue button')).to_be_visible()
        page.locator('#dd-family-continue button').click()
        expect(page.locator('.textbook-excerpt')).to_have_count(0)
        expect(page.locator('#textbookStatus')).to_contain_text('失效')
        # Original-page browse remains available after withdrawal.
        page.locator('#textbookBrowse').click()
        expect(page.locator('.textbook-page-image')).to_be_visible()
        page.locator('.profile-card[data-grade="2"]').click()
        expect(page.locator('#textbookBook')).to_have_value('math-g2-upper')
        page.evaluate('(url) => {location.hash = new URL(url).hash}', url)
        expect(page.locator('#dd-family-continue')).to_contain_text('档案已变化')
        expect(page.locator('.textbook-excerpt')).to_have_count(0)
        assert not errors
        browser.close()
