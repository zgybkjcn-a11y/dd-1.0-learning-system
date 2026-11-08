"""Offline coverage display at two viewports; no service, learner or model calls."""
import os
from pathlib import Path

import pytest

from scripts import prepare_chapter_coverage as coverage
from test_chapter_coverage import inputs, build

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [390, 1280])
def test_offline_coverage_rows_gaps_and_question_details(inputs, tmp_path, width, playwright, launch_browser):
    output = Path(os.getenv('DD_B01_EVIDENCE_DIR', str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    report = build(inputs)
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(viewport={'width': width, 'height': 960}, offline=True,
                                      service_workers='block')
        requests, errors = [], []
        context.route('**/*', lambda route: route.abort())
        page = context.new_page()
        page.on('request', lambda request: requests.append(request.url))
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_content(coverage.render_html(report))
        expect = playwright.expect
        expect(page.locator('tbody tr')).to_have_count(19)
        expect(page.locator('h1')).to_have_text('七上第二章内容覆盖表')
        expect(page.locator('[data-row-id="g7-ch2-power"]')).to_contain_text('无现有练习映射')
        expect(page.locator('[data-row-id="g7-ch2-multiply-laws"]')).to_contain_text('无当前有效片段映射')
        add = page.locator('[data-row-id="g7-add"]')
        add.locator('summary').click()
        expect(add.locator('details')).to_contain_text('family-word-g7-warming-v1')
        expect(add).to_contain_text('revision 1')
        expect(page.locator('body')).to_contain_text('实际复习卡与延迟观察未读取、未验收')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('tbody td').first.bounding_box()['width'] >= 150
        if width == 390:
            assert page.locator('.scroll').evaluate('(element) => element.scrollWidth > element.clientWidth')
        page.locator('.scroll').evaluate('(element) => element.scrollLeft = 0')
        assert not requests and not errors
        page.screenshot(path=str(output / f'coverage-{width}.png'), full_page=True)
        browser.close()
