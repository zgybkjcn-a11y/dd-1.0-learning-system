"""Main study + real family workbench/API, synthetic identities and public PDFs."""
from dataclasses import replace
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.login_gateway import GatewaySettings, create_gateway
from test_login_gateway import SyntheticBridge, gateway_login
from test_math_references import reference_family, PUBLIC_BOOKS
from test_family_math import family

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / 'deploy/open-webui-reuse/main-study'


@pytest.mark.parametrize('width', [1280, 390])
def test_family_main_shared_materials_and_identity_races(reference_family, tmp_path, width):
    playwright = pytest.importorskip('playwright.sync_api')
    _, db, original, _ = reference_family
    origin = 'https://study-bridge.example.invalid'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
        browser_auth_secret='synthetic-gateway-key-0123456789abcdef', browser_auth_issuer='synthetic-gateway',
        browser_identity_issuer='family-pilot-webui', browser_origin=origin, public_base_path='/learning',
        shared_learner_context_enabled=True, family_setup_code='synthetic-family-code-0123456789abcdef',
        textbook_dir=PUBLIC_BOOKS)
    api = TestClient(create_app(settings, db), base_url=origin)
    transport = SyntheticBridge(api)
    transport.identities['synthetic-token-a'] = 'synthetic-parent'
    gateway = TestClient(create_gateway(GatewaySettings(enabled=True, public_origin=origin,
        openwebui_url='http://webui.invalid:8080', learning_url='http://learning.invalid:8000',
        assertion_secret=settings.browser_auth_secret, assertion_issuer='synthetic-gateway',
        identity_issuer='family-pilot-webui'), transport), base_url=origin)
    gateway.cookies.set('token', 'synthetic-token-a')
    assert gateway_login(settings, gateway)[0].status_code == 303
    out = Path(os.getenv('DD_STUDY_BRIDGE_EVIDENCE', str(tmp_path)))
    out.mkdir(parents=True, exist_ok=True)
    calls, errors, delayed = [], [], []
    delay = [False]
    delay_math = [False]
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        context = browser.new_context(viewport={'width': width, 'height': 1000}, service_workers='block')
        context.add_cookies([{'name': k, 'value': v, 'url': origin, 'secure': True, 'sameSite': 'Strict'}
                            for k, v in gateway.cookies.items()])
        shell = '''<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/custom.css"><script defer src="/static/loader.js"></script></head><body>
        <nav><div><div><a id="sidebar-new-chat-button" href="/">新对话</a></div></div></nav>
        <div id="chat-input" contenteditable="true" style="min-height:80px;border:1px solid"></div></body></html>'''

        def handle(route):
            request = route.request
            parsed = urlsplit(request.url)
            assert parsed.scheme + '://' + parsed.netloc == origin
            calls.append((request.method, parsed.path))
            if parsed.path == '/': route.fulfill(status=200, content_type='text/html', body=shell); return
            asset = {'/static/loader.js': 'study.js', '/static/custom.css': 'study.css',
                     '/static/dd-family-bridge.js': 'family-bridge.js'}.get(parsed.path)
            if asset:
                route.fulfill(status=200, content_type='text/css' if asset.endswith('.css') else 'text/javascript',
                              body=(ASSETS / asset).read_bytes()); return
            assert parsed.path.startswith('/learning/'), parsed.path
            response = gateway.request(request.method, parsed.path + ('?' + parsed.query if parsed.query else ''),
                headers=request.all_headers(), content=request.post_data_buffer, follow_redirects=False)
            body = response.content
            if parsed.path == '/learning/ui':
                body = response.text.replace('</body>', '<script src="/static/dd-family-bridge.js"></script></body>').encode()
            if parsed.path == '/learning/api/v1/study-support' and delay[0]:
                delay[0] = False; delayed.append((route, response)); return
            if parsed.path == '/learning/api/v1/math-references' and delay_math[0]:
                delay_math[0] = False; delayed.append((route, response)); return
            route.fulfill(status=response.status_code, body=body,
                          headers={k: v for k, v in response.headers.items() if k not in ('content-length', 'set-cookie')})

        context.route('**/*', handle)
        main = context.new_page(); main.on('pageerror', lambda e: errors.append(str(e)))
        main.goto(origin); main.locator('#dd-study-open').click()
        expect = playwright.expect
        expect(main.locator('#dd-study-family-status')).to_contain_text('选择一个档案')
        expect(main.locator('#dd-study-insert')).to_be_disabled()
        family_page = context.new_page(); family_page.on('pageerror', lambda e: errors.append(str(e)))
        family_page.goto(origin + '/learning/ui')
        family_page.locator('.profile-card[data-grade="7"]').click()
        expect(family_page.locator('#textbookBook')).to_have_value('math-g7-upper')
        family_page.locator('#textbookChapter').select_option('2')
        expect(main.locator('#dd-study-family-status')).to_contain_text('第二章')
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        main.locator('#dd-study-family-content summary').click()
        expect(main.locator('#dd-study-family-cards')).to_contain_text('有理数')
        main.locator('#dd-study-read-page').click()
        expect(main.locator('#dd-study-page')).to_be_visible()
        main.wait_for_function('document.querySelector("#dd-study-page img").naturalWidth > 0')
        expect(main.locator('#dd-study-page strong')).to_contain_text('第 24 页')
        main.locator('#dd-study-page [data-page="next"]').click()
        expect(main.locator('#dd-study-page strong')).to_contain_text('第 25 页')
        main.locator('#dd-study-page [data-page="close"]').click()
        main.locator('#dd-study-preview-box summary').click()
        main.locator('#dd-study-topic').fill('怎样理解有理数的运算')
        preview = main.locator('#dd-study-preview').input_value()
        assert '家庭学习提供的公开参考' in preview and '有理数' in preview
        assert 'family-g7' not in preview and 'synthetic' not in preview
        assert '[参考 1]' in preview
        # Two named upstream projects now form a public concept-to-practice path.
        main.locator('#dd-study-route summary').first.click()
        main.locator('#dd-study-route-concept').select_option('g7-subtract')
        expect(main.locator('#dd-study-route-cards')).to_contain_text('先回顾')
        expect(main.locator('#dd-study-route-cards')).to_contain_text('→')
        expect(main.locator('#dd-study-route-questions')).to_contain_text('记录一天温差')
        main.locator('#dd-study-route-questions details').first.locator('summary').click()
        expect(main.locator('#dd-study-route-questions')).to_contain_text('cn-math-taxonomy')
        expect(main.locator('#dd-study-route-questions')).to_contain_text('CC BY-NC 4.0')
        assert not main.locator('#dd-study-panel').evaluate('(e) => e.scrollWidth > e.clientWidth')
        main.screenshot(path=str(out / f'knowledge-route-{width}.png'))
        qid = 'family-word-cnm_012_q5-v1'
        chosen = main.locator(f'#dd-study-route-questions a[href*="studyQuestion={qid}"]')
        saved_link = chosen.get_attribute('href')
        def session_count():
            with db.session() as conn: return conn.execute('SELECT COUNT(*) FROM test_sessions').fetchone()[0]
        before_start = session_count()
        with context.expect_page() as popup: chosen.click()
        practice = popup.value; practice.on('pageerror', lambda e: errors.append(str(e)))
        expect(practice.locator('#dd-family-continue')).to_contain_text('记录一天温差')
        assert session_count() == before_start  # Opening a link does not start a test.
        practice.locator('#dd-family-continue button').click()
        expect(practice.locator('#questionVersion')).to_have_value(qid)
        expect(practice.locator('#testItem')).not_to_have_value('')
        expect(practice.locator('#questionCredit')).to_contain_text('cn-math-taxonomy')
        first_item = practice.locator('#testItem').input_value()
        expect(main.locator('#dd-study-route-concept')).to_be_visible()
        expect(main.locator('#dd-study-route-concept')).to_have_value('g7-subtract')
        main.locator('#dd-study-route-difficulty').select_option('normal')
        expect(main.locator('#dd-study-route-questions')).to_contain_text('暂无关联题')
        main.locator('#dd-study-route-difficulty').select_option('hard')
        expect(main.locator('#dd-study-route-questions')).to_contain_text('本地编写')
        hard_link = main.locator('#dd-study-route-questions .dd-study-practice-link').first.get_attribute('href')
        practice.evaluate('(url) => {location.hash = new URL(url, location.href).hash}', hard_link)
        practice.once('dialog', lambda dialog: dialog.dismiss())
        practice.locator('#dd-family-continue button').click()
        expect(practice.locator('#testItem')).to_have_value(first_item)
        practice.once('dialog', lambda dialog: dialog.accept())
        practice.locator('#dd-family-continue button').click()
        expect(practice.locator('#testItem')).not_to_have_value(first_item)
        # Cross-chapter links also retain the unfinished-exercise confirmation.
        main.locator('#dd-study-chapter').select_option('5')
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        main.locator('#dd-study-route-concept').select_option('g7-solve')
        chapter_link = main.locator('#dd-study-route-questions a[href*="studyQuestion=family-word-cnm_045_q3-v1"]')
        expect(chapter_link).to_be_visible()
        practice.evaluate('(url) => {location.hash = new URL(url, location.href).hash}', chapter_link.get_attribute('href'))
        practice.once('dialog', lambda dialog: dialog.dismiss())
        practice.locator('#dd-family-continue button').click()
        expect(practice.locator('#textbookChapter')).to_have_value('2')
        practice.once('dialog', lambda dialog: dialog.accept())
        practice.locator('#dd-family-continue button').click()
        expect(practice.locator('#textbookChapter')).to_have_value('5')
        expect(practice.locator('#questionVersion')).to_have_value('family-word-cnm_045_q3-v1')
        expect(practice.locator('#testItem')).not_to_have_value('')
        practice.screenshot(path=str(out / f'linked-practice-{width}.png'))
        # Forged cross-grade IDs and stale revisions cannot create test sessions.
        before_reject = session_count()
        practice.evaluate('(url) => {location.hash = new URL(url, location.href).hash.replace("family-word-cnm_012_q5-v1", "family-word-cnm_p039_q1-v1")}', saved_link)
        expect(practice.locator('#dd-family-continue')).to_contain_text('不在当前档案')
        expect(practice.locator('#dd-family-continue button')).to_have_count(0)
        practice.evaluate('(url) => {const p = new URLSearchParams(new URL(url, location.href).hash.slice(1)); p.set("studyRevision", "0"); location.hash = p.toString()}', saved_link)
        expect(practice.locator('#dd-family-continue')).to_contain_text('家庭档案已变化')
        expect(practice.locator('#dd-family-continue button')).to_have_count(0)
        assert session_count() == before_reject
        # A native chat citation opens the exact printed page via the original reader.
        practice.evaluate('(url) => {const p = new URLSearchParams(new URL(url, location.href).hash.slice(1)); p.delete("studyQuestion"); p.set("studyPage", "30"); location.hash = p.toString()}', saved_link)
        expect(practice.locator('#dd-family-continue button')).to_have_text('查看引用的第 30 页')
        practice.once('dialog', lambda dialog: dialog.accept())
        practice.locator('#dd-family-continue button').click()
        expect(practice.locator('#textbookPageInput')).to_have_value('30')
        practice.wait_for_function('document.querySelector("#textbookResults img")?.naturalWidth > 0')
        practice.evaluate('(url) => {const p = new URLSearchParams(new URL(url, location.href).hash.slice(1)); p.delete("studyQuestion"); p.set("studyPage", "999"); location.hash = p.toString()}', saved_link)
        expect(practice.locator('#dd-family-continue')).to_contain_text('不在当前档案的课本范围')
        expect(practice.locator('#dd-family-continue button')).to_have_count(0)
        practice.close()
        main.locator('#dd-study-chapter').select_option('1')
        expect(main.locator('#dd-study-route-status')).to_contain_text('尚无精确数学映射')
        expect(main.locator('#dd-study-route-questions a')).to_have_count(0)
        main.locator('#dd-study-chapter').select_option('2')
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        # Actual four-stage classroom with scope-bound references and numeric demo.
        main.locator('#dd-study-classroom-open').click()
        expect(main.locator('#dd-study-classroom')).to_be_visible()
        main.locator('#dd-lesson-concept').select_option('g7-subtract')
        main.locator('#dd-lesson-next').click()
        main.locator('#dd-lesson-operation').select_option('subtract')
        main.locator('#dd-lesson-b').evaluate('(e)=>{e.value=-5;e.dispatchEvent(new Event("input"))}')
        expect(main.locator('#dd-lesson-calculation')).to_contain_text('-3 − (-5) = 2')
        expect(main.locator('#dd-lesson-sources')).to_contain_text('参考')
        main.locator('#dd-lesson-sources button').first.click()
        main.wait_for_function('document.querySelector("#dd-study-page img").naturalWidth > 0')
        main.locator('#dd-study-page [data-page="close"]').click()
        main.locator('#dd-lesson-next').click()
        expect(main.locator('#dd-lesson-body')).to_contain_text('自己的话')
        main.locator('#dd-lesson-next').click()
        expect(main.locator('#dd-lesson-body input[type="checkbox"]')).to_have_count(3)
        main.locator('#dd-lesson-body input').first.check()
        expect(main.locator('#dd-lesson-next')).to_be_disabled()
        main.screenshot(path=str(out / f'classroom-{width}.png'))
        main.locator('#dd-study-classroom').get_by_role('button', name='关闭课堂').click()
        # Offline export is public-only and executes without any network calls.
        main.locator('#dd-study-material').fill('PRIVATE_STUDENT_TEXT <script>alert(1)</script>')
        with main.expect_download() as offline_download: main.locator('#dd-study-classroom-download').click()
        offline_html = Path(offline_download.value.path()).read_text()
        assert 'PRIVATE_STUDENT_TEXT' not in offline_html and 'family-g7' not in offline_html and 'synthetic' not in offline_html
        offline_file = out / f'classroom-{width}.html'; offline_file.write_text(offline_html)
        offline_context = browser.new_context(viewport={'width': width, 'height': 1000}, offline=True)
        offline_page = offline_context.new_page(); offline_requests = []
        offline_page.on('request', lambda r: offline_requests.append(r.url))
        offline_page.on('pageerror', lambda e: errors.append(str(e)))
        offline_page.goto(offline_file.resolve().as_uri())
        offline_page.locator('#dd-lesson-concept').select_option('g7-subtract')
        offline_page.locator('#dd-lesson-next').click()
        offline_page.locator('#dd-lesson-operation').select_option('subtract')
        offline_page.locator('#dd-lesson-b').evaluate('(e)=>{e.value=-5;e.dispatchEvent(new Event("input"))}')
        expect(offline_page.locator('#dd-lesson-calculation')).to_contain_text('-3 − (-5) = 2')
        expect(offline_page.locator('#dd-lesson-sources')).to_contain_text('未包含教材原图')
        assert not any(url.startswith(('https:', 'http:')) for url in offline_requests)
        assert not offline_page.evaluate('document.documentElement.scrollWidth > innerWidth')
        offline_context.close()
        main.locator('#dd-study-include').uncheck()
        assert '家庭学习提供的公开参考' not in main.locator('#dd-study-preview').input_value()
        main.locator('#dd-study-include').check()
        main.locator('#dd-study-subject').select_option('历史')
        expect(main.locator('#dd-study-family-status')).to_contain_text('历史')
        main.locator('#dd-study-chapter').select_option('1')
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        expect(main.locator('#dd-study-family-cards')).to_contain_text('定位时空')
        expect(main.locator('#dd-study-route-status')).to_contain_text('尚无精确数学映射')
        expect(main.locator('#dd-study-route-questions a')).to_have_count(0)
        main.locator('#dd-study-classroom-open').click()
        expect(main.locator('#dd-lesson-body')).to_contain_text('没有该章已核验的知识讲解')
        expect(main.locator('#dd-lesson-concept')).to_be_disabled()
        main.locator('#dd-lesson-next').click()
        expect(main.locator('#dd-lesson-body')).to_contain_text('时间和地点')
        expect(main.locator('#dd-lesson-calculation')).to_have_count(0)
        main.locator('#dd-study-classroom').get_by_role('button', name='关闭课堂').click()
        main.locator('#dd-study-topic').fill('怎样理解史料')
        with main.expect_download() as dl: main.locator('#dd-study-download').click()
        assert '定位时空' in Path(dl.value.path()).read_text()
        main.screenshot(path=str(out / f'connected-{width}.png'))
        assert not main.evaluate('document.documentElement.scrollWidth > innerWidth')
        with context.expect_page() as popup: main.locator('#dd-study-family-continue').click()
        continued = popup.value; continued.on('pageerror', lambda e: errors.append(str(e)))
        continued.wait_for_load_state()
        continued.locator('#dd-family-continue button').click()
        expect(continued.locator('#textbookBook')).to_have_value('history-g7-upper')
        expect(continued.locator('#textbookChapter')).to_have_value('1')
        continued.close()
        # An in-flight old-profile response must not revive grade-seven references.
        delay[0] = True
        main.locator('#dd-study-sync').click()
        for _ in range(100):
            if delayed: break
            main.wait_for_timeout(50)
        assert delayed
        family_page.locator('.profile-card[data-grade="2"]').click()
        expect(family_page.locator('#textbookBook')).to_have_value('math-g2-upper')
        family_page.locator('#textbookChapter').select_option('2')
        expect(main.locator('#dd-study-profile')).to_contain_text('二年级')
        old_route, old_response = delayed.pop()
        try: old_route.fulfill(status=old_response.status_code, body=old_response.content, content_type='application/json')
        except playwright.Error: pass  # AbortController may already have cancelled it.
        expect(main.locator('#dd-study-book')).to_have_value('math-g2-upper')
        expect(main.locator('#dd-study-chapter')).to_have_value('2')
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        assert main.locator('#dd-study-subject option').count() == 3
        main.locator('#dd-study-route-concept').select_option('g2-groups')
        expect(main.locator('#dd-study-route-questions a[href*="studyQuestion="]')).to_have_count(4)
        assert 'g7' not in main.locator('#dd-study-route-questions').inner_html()
        # A late concept response is discarded when the chapter changes.
        delay_math[0] = True
        main.locator('#dd-study-route-retry').click()
        for _ in range(100):
            if delayed: break
            main.wait_for_timeout(50)
        assert delayed
        main.locator('#dd-study-chapter').select_option('3')
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        old_route, old_response = delayed.pop()
        try: old_route.fulfill(status=old_response.status_code, body=old_response.content, content_type='application/json')
        except playwright.Error: pass
        main.locator('#dd-study-route-concept').select_option('g2-share')
        expect(main.locator('#dd-study-route-cards')).to_contain_text('平均分')
        expect(main.locator('#dd-study-route-questions a[href*="studyChapter=2"]')).to_have_count(0)
        main.locator('#dd-study-route-concept').select_option('g2-small-table')
        expect(main.locator('#dd-study-route-cards')).to_contain_text('前章基础')
        main.locator('#dd-study-route-cards').get_by_role('button', name='前章基础', exact=False).first.click()
        main.wait_for_function('document.querySelector("#dd-study-page img").naturalWidth > 0')
        main.locator('#dd-study-page [data-page="close"]').click()
        # A grade-seven link saved before switching cannot be resumed in grade two.
        rejected = context.new_page(); rejected.goto(origin + saved_link)
        expect(rejected.locator('#dd-family-continue')).to_contain_text('家庭档案已变化')
        expect(rejected.locator('#dd-family-continue button')).to_have_count(0)
        rejected.close()
        main.locator('#dd-study-chapter').select_option('2')
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        assert main.locator('#dd-study-material').input_value() == ''
        main.locator('#dd-study-classroom-open').click()
        main.locator('#dd-lesson-concept').select_option('g2-groups')
        main.locator('#dd-lesson-next').click()
        expect(main.locator('#dd-lesson-calculation')).to_contain_text('3 × 4 = 12')
        assert '÷' not in main.locator('#dd-lesson-calculation').inner_text()
        main.locator('#dd-lesson-a').evaluate('(e)=>{e.value=2;e.dispatchEvent(new Event("input"))}')
        expect(main.locator('#dd-lesson-calculation')).to_contain_text('2 × 4 = 8')
        expect(main.locator('#dd-lesson-body svg circle')).to_have_count(8)
        main.locator('#dd-study-classroom').get_by_role('button', name='关闭课堂').click()
        main.locator('#dd-study-close').click()
        expect(main.locator('#dd-chat-study a')).to_have_attribute('href', '/?tools=dd_family_study_readonly_v1')
        main.locator('#dd-chat-study [data-study-action="search"]').click()
        expect(main.locator('#chat-input')).to_contain_text('search_textbook')
        expect(main.locator('#chat-input')).to_contain_text('math-g2-upper')
        expect(main.locator('#chat-input')).to_contain_text('二年级数学')
        quick_draft = main.locator('#chat-input').inner_text()
        assert 'family-g2' not in quick_draft and 'synthetic' not in quick_draft
        main.locator('#dd-chat-study [data-study-action="explain"]').click()
        expect(main.locator('#dd-chat-study-status')).to_contain_text('已有草稿')
        assert main.locator('#chat-input').inner_text()==quick_draft
        main.locator('#chat-input').fill('')
        main.locator('#dd-chat-study [data-study-action="assistant"]').click()
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        main.locator('#dd-study-topic').fill('乘法表示什么')
        preview = main.locator('#dd-study-preview').input_value()
        assert '二年级' in preview and '七年级' not in preview and 'family-g2' not in preview
        main.locator('#dd-study-insert').click()
        expect(main.locator('#chat-input')).to_contain_text('二年级数学')
        expect(main.locator('#chat-input')).to_contain_text('家庭学习提供的公开参考')
        # A saved draft is kept; user/account change prevents any later export.
        draft = main.locator('#chat-input').inner_text()
        main.locator('#dd-study-open').click()
        expect(main.locator('#dd-study-insert')).to_be_enabled()
        main.locator('#dd-study-insert').click()
        expect(main.locator('#dd-study-status')).to_contain_text('已有草稿')
        assert main.locator('#chat-input').inner_text() == draft
        transport.webui_status = 401
        # The periodic identity check may disable export before a user click.
        main.locator('#dd-study-download').evaluate('(e) => {if (!e.disabled) e.click()}')
        expect(main.locator('#dd-study-family-status')).to_contain_text('旧资料已清空')
        assert main.locator('#dd-study-family-cards article').count() == 0
        expect(main.locator('#dd-study-insert')).to_be_disabled()
        expect(main.locator('#dd-study-classroom-open')).to_be_disabled()
        expect(main.locator('#dd-study-classroom')).not_to_be_visible()
        assert not errors, errors
        with db.session() as conn:
            assert conn.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 0
            assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0
        assert not any('retrieval' in p or 'completion' in p or 'mistakes' in p and method == 'POST' for method, p in calls)
        (out / f'bridge-{width}.json').write_text(json.dumps({'width': width, 'passed': True,
            'real_family_api_with_synthetic_accounts': True, 'cross_tab_scope': True,
            'g7_to_g2_race': True, 'page_images': True, 'continue_same_chapter': True,
            'draft_preserved': True, 'expired_identity_blocks_export': True, 'classroom_four_stages': True,
            'source_citations': True, 'signed_subtraction_demo': True, 'g2_no_future_division': True,
            'offline_html_zero_http_requests': True, 'public_only_export': True,
            'concept_prerequisites_and_practice': True, 'attributed_adapted_questions': True,
            'explicit_launch_only': True, 'unfinished_confirmation_preserved': True,
            'cross_grade_stale_and_unmapped_rejected': True, 'late_concept_response_discarded': True,
            'chat_shortcuts_preserve_draft': True, 'chat_citation_exact_page': True,
            'provider_calls': 0, 'page_errors': errors}))
        browser.close()
