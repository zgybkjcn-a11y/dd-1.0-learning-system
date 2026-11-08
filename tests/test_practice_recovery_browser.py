"""Reload, independent browser storage and conflicting tabs with synthetic APIs."""
from dataclasses import replace
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app, run_worker_once
from learning_service.browser_auth import SESSION_COOKIE
from learning_service.practice import bank, install
from test_browser_auth import assertion
from test_family_math import family

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [390, 1280])
def test_reload_new_device_conflicts_retry_and_profile_restore(family, tmp_path, width, playwright, launch_browser):
    _, db, original, _ = family; install(db)
    origin = 'https://recovery.example.invalid'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
        browser_auth_secret='synthetic-gateway-key-0123456789abcdef', browser_auth_issuer='synthetic-gateway',
        browser_identity_issuer='family-pilot-webui', browser_origin=origin, public_base_path='/learning',
        shared_learner_context_enabled=True, family_setup_code='synthetic-family-code-0123456789abcdef')
    api = TestClient(create_app(settings, db), base_url=origin)
    folder = Path(os.getenv('DD_RECOVERY_EVIDENCE_DIR', str(tmp_path))); folder.mkdir(parents=True, exist_ok=True)
    errors = []; external = []; answer_keys = []; drop_start = [True]; drop_answer = [True]
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        def context_for_device(number):
            login = TestClient(create_app(settings, db), base_url=origin)
            assert login.post('/api/v1/auth/session', headers={'Origin': origin,
                'Authorization': 'Bearer ' + assertion(settings, changes={'sub':'synthetic-parent', 'jti':f'recovery-{width}-{number}'})}).status_code == 201
            context = browser.new_context(viewport={'width': width, 'height':960}, service_workers='block')
            context.add_cookies([{'name':n, 'value':v, 'url':origin, 'secure':True, 'httpOnly':n==SESSION_COOKIE,
                                  'sameSite':'Strict'} for n,v in login.cookies.items()])
            context.route('**/*', handle)
            return context

        def handle(route):
            request = route.request; url = urlsplit(request.url)
            if url.scheme + '://' + url.netloc != origin:
                external.append(request.url); route.abort(); return
            if '/api/v1/attempts/' in url.path and request.method == 'GET': run_worker_once(db, settings)
            response = api.request(request.method, url.path.removeprefix('/learning'), headers=request.all_headers(),
                                   content=request.post_data_buffer, follow_redirects=False)
            if url.path.endswith('/test-sessions') and request.method == 'POST' and response.status_code == 201 and drop_start[0]:
                drop_start[0] = False
                route.fulfill(status=503, json={'error':{'message':'合成开题响应丢失'}}); return
            if url.path.endswith('/answers'):
                answer_keys.append(request.all_headers().get('idempotency-key'))
                if response.status_code == 202 and drop_answer[0]:
                    drop_answer[0] = False
                    route.fulfill(status=503, json={'error':{'message':'合成作答响应丢失'}}); return
            route.fulfill(status=response.status_code, body=response.content,
                headers={k:v for k,v in response.headers.items() if k not in ('content-length','set-cookie')})

        def page_for(context):
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(origin + '/learning/ui#testSection'); return page

        expect = playwright.expect
        first = context_for_device(1); a = page_for(first)
        a.locator('.profile-card[data-grade="7"]').click()
        expect(a.locator('#practiceChoices button')).to_have_count(30)
        a.locator('#textbookChapter').select_option('2')
        a.locator('#homeDifficulty').select_option('easy')
        a.locator('#scopeChallenge').click()
        expect(a.locator('#answer')).to_be_enabled()
        session_id = a.locator('#session').input_value(); qid = a.locator('#questionVersion').input_value()
        assert session_id
        with db.session() as conn: assert conn.execute('SELECT count(*) FROM test_sessions').fetchone()[0] == 1
        a.locator('#answer').fill('<script>local draft</script>')
        a.reload()
        expect(a.locator('#answer')).to_have_value('<script>local draft</script>')
        expect(a.locator('#testPrompt')).to_have_text(bank()[qid]['prompt'])
        a.locator('#requestHint').click()
        expect(a.locator('#gameHint')).to_contain_text('提示后练习')
        a.reload(); expect(a.locator('#gameHint')).to_contain_text('辅助作答')
        a.screenshot(path=str(folder / f'draft-restored-{width}.png'), full_page=True)
        a.locator('#answer').fill(bank()[qid]['answer']); a.locator('#submitAnswer').click()
        expect(a.locator('#testStatus')).to_contain_text('作答响应丢失')
        expect(a.locator('#answer')).to_have_value(bank()[qid]['answer'])
        a.locator('#submitAnswer').click()
        expect(a.locator('#feedbackTitle')).to_contain_text('答对了')
        assert answer_keys[:2] == [answer_keys[0], answer_keys[0]]
        second = context_for_device(2); b = page_for(second)
        expect(b.locator('#session')).to_have_value(session_id)
        expect(b.locator('#savedPracticeAnswer')).to_contain_text(bank()[qid]['answer'])
        expect(b.locator('#savedPracticeAnswer')).to_contain_text('提示后练习')
        expect(b.locator('#practiceDifficulty')).to_have_value('easy')
        expect(b.locator('#roundProgress')).to_contain_text('1 / 4')
        c = page_for(first)
        expect(c.locator('#session')).to_have_value(session_id)
        expect(c.locator('#roundProgress')).to_contain_text('1 / 4')
        b.locator('#nextChallenge').click()
        expect(b.locator('#answer')).to_be_enabled()
        next_session = b.locator('#session').input_value()
        assert next_session != session_id
        a.locator('#nextChallenge').click()  # stale revision: recover B's session
        expect(a.locator('#session')).to_have_value(next_session)
        expect(a.locator('#testStatus')).to_contain_text('另一页面')
        with db.session() as conn: assert conn.execute('SELECT count(*) FROM test_sessions').fetchone()[0] == 2
        a.locator('#answer').fill('10001'); b.locator('#answer').fill('<script>10002</script>')
        a.locator('#submitAnswer').click(); expect(a.locator('#feedbackTitle')).to_contain_text('值得再研究')
        b.locator('#submitAnswer').click()
        expect(b.locator('#savedPracticeAnswer')).to_contain_text('10001')
        expect(b.locator('#answer')).to_have_value('<script>10002</script>')
        expect(b.locator('#testStatus')).to_contain_text('尚未提交')
        expect(b.locator('#practiceAnswerConflict')).to_be_visible()
        b.locator('#practiceAnswerConflict summary').click()
        expect(b.locator('#practiceConflictAnswer')).to_have_text('<script>10002</script>')
        b.screenshot(path=str(folder / f'conflicting-answer-{width}.png'), full_page=True)
        for _ in range(2):
            a.locator('#nextChallenge').click(); expect(a.locator('#answer')).to_be_enabled()
            question = bank()[a.locator('#questionVersion').input_value()]
            a.locator('#answer').fill(question['answer']); a.locator('#submitAnswer').click()
            expect(a.locator('#feedbackTitle')).to_contain_text('答对了')
        expect(a.locator('#roundProgress')).to_contain_text('4 / 4')
        c.reload(); expect(c.locator('#roundProgress')).to_contain_text('4 / 4')
        c.locator('#restartRound').click(); expect(c.locator('#answer')).to_be_enabled()
        assert c.locator('#questionVersion').input_value() == qid
        restarted_session = c.locator('#session').input_value()
        a.reload(); expect(a.locator('#session')).to_have_value(restarted_session)
        c.locator('#answer').fill('unsent before switch')
        c.locator('[data-game-view="home"]').click()
        c.once('dialog', lambda dialog: dialog.dismiss())
        c.locator('.profile-card[data-grade="2"]').click()
        expect(c.locator('#learner')).to_have_value('family-g7')
        c.once('dialog', lambda dialog: dialog.accept())
        c.locator('.profile-card[data-grade="2"]').click()
        expect(c.locator('#learner')).to_have_value('family-g2')
        expect(c.locator('#practiceChoices button')).to_have_count(40)
        expect(c.locator('#session')).to_have_value('')
        a.locator('#answer').fill('stale profile answer'); a.locator('#submitAnswer').click()
        expect(a.locator('#contextStatus')).to_contain_text('学习者已变化')
        c.locator('.profile-card[data-grade="7"]').click()
        expect(c.locator('#practiceChoices button')).to_have_count(18)
        expect(c.locator('#textbookChapter')).to_have_value('2')
        expect(c.locator('#session')).to_have_value(restarted_session)
        expect(c.locator('#answer')).to_have_value('')
        with db.session() as conn:
            assert conn.execute('SELECT count(*) FROM attempts').fetchone()[0] == 4
            assert conn.execute('SELECT count(*) FROM grade_versions').fetchone()[0] == 4
            assert conn.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 0
        overflow = any(page.evaluate('document.documentElement.scrollWidth > innerWidth') for page in (a,b,c))
        assert not overflow and not errors and not external
        (folder / f'report-{width}.json').write_text(json.dumps({'width':width, 'browser_version':browser.version,
            'reload_draft_and_assistance_restored':True, 'new_tab_and_fresh_device_restored':True,
            'lost_start_recovered_without_duplicate':True, 'lost_answer_same_key_retry':True,
            'stale_start_fenced':True, 'different_answer_retained':True, 'round_restart_persisted':True,
            'profile_switch_guard_and_restore':True, 'attempts':4, 'grades':4,
            'external_requests':len(external), 'page_errors':errors, 'horizontal_overflow':overflow}, ensure_ascii=False, indent=2))
        first.close(); second.close(); browser.close()
