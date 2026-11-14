"""B02 unseen pool on the family UI using synthetic databases and intercepted ASGI."""
import os
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app, run_worker_once
from learning_service.browser_auth import SESSION_COOKIE
from learning_service.practice import bank, install
from learning_service import reserve_practice as reserve
from test_browser_auth import assertion
from test_family_math import family

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [390, 1280])
def test_unseen_pool_counts_cancel_restore_tiers_and_parent_notice(
        family, tmp_path, width, textbook_sources, playwright, launch_browser):
    _, db, original, _ = family
    install(db)
    reserve.install(db)
    origin = 'https://reserve-family.example.invalid'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
                       browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                       browser_auth_issuer='synthetic-gateway', browser_identity_issuer='family-pilot-webui',
                       browser_origin=origin, public_base_path='/learning', shared_learner_context_enabled=True,
                       family_setup_code='synthetic-family-code-0123456789abcdef', textbook_dir=textbook_sources)
    api = TestClient(create_app(settings, db), base_url=origin)
    assert api.post('/api/v1/auth/session', headers={'Origin': origin,
                    'Authorization': 'Bearer ' + assertion(settings, changes={'sub': 'synthetic-parent'})}).status_code == 201
    screenshots = Path(os.getenv('DD_RESERVE_EVIDENCE_DIR', str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    questions = bank() | reserve.bank()
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(viewport={'width': width, 'height': 960}, service_workers='block')
        context.add_cookies([{'name': name, 'value': value, 'url': origin, 'secure': True,
                             'httpOnly': name == SESSION_COOKIE, 'sameSite': 'Strict'}
                            for name, value in api.cookies.items()])
        errors, presentations = [], []

        def handle(route):
            url = urlsplit(route.request.url)
            assert url.scheme + '://' + url.netloc == origin
            assert url.path.startswith('/learning/')
            if '/api/v1/attempts/' in url.path and route.request.method == 'GET':
                run_worker_once(db, settings)
            response = api.request(route.request.method, url.path.removeprefix('/learning'),
                                   headers=route.request.all_headers(), content=route.request.post_data_buffer,
                                   follow_redirects=False)
            if url.path.endswith('/test-sessions') and response.status_code == 201:
                assert response.json()['answer_key'] is None
                assert 'numeric_answer' not in response.text and 'explanation' not in response.text
                presentations.append(response.json()['items'][0]['question_version_id'])
            route.fulfill(status=response.status_code, body=response.content,
                          headers={k: v for k, v in response.headers.items() if k not in ('content-length', 'set-cookie')})

        context.route('**/*', handle)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin + '/learning/ui')
        expect = playwright.expect
        page.locator('.profile-card[data-grade="7"]').click()
        page.locator('#textbookChapter').select_option('2')
        expect(page.locator('#practiceChoices button')).to_have_count(18)
        expect(page.locator('#practicePool')).to_have_value('initial')
        expect(page.locator('#reserveAvailability')).to_have_text('简单 4 道未见题 · 正常 4 道未见题 · 困难 4 道未见题 · 挑战 0 道未见题')
        page.locator('#scopeChallenge').click()
        original_id = page.locator('#questionVersion').input_value()
        original_prompt = page.locator('#testPrompt').inner_text()
        page.reload()
        expect(page.locator('#questionVersion')).to_have_value(original_id)
        expect(page.locator('#testPrompt')).to_have_text(original_prompt)
        page.locator('#cancelTest').click()
        expect(page.locator('#practiceChoices button')).to_have_count(18)
        page.locator('#practicePool').select_option('reserve')
        expect(page.locator('#practiceChoices button')).to_have_count(12)
        page.screenshot(path=str(screenshots / f'reserve-selection-{width}.png'), full_page=True)
        page.locator('#homeDifficulty').select_option('easy')
        page.locator('#scopeChallenge').click()
        cancelled = page.locator('#questionVersion').input_value()
        assert questions[cancelled]['difficulty'] == 'easy'
        page.reload()
        expect(page.locator('#questionVersion')).to_have_value(cancelled)
        expect(page.locator('#practicePool')).to_be_disabled()
        expect(page.locator('#testPrompt')).to_have_text(questions[cancelled]['prompt'])
        expect(page.locator('#solutionDetails')).to_be_hidden()
        page.locator('#cancelTest').click()
        expect(page.locator('#practiceChoices button')).to_have_count(11)
        expect(page.locator('#reserveAvailability')).to_contain_text('简单 3 道未见题')
        page.reload()
        expect(page.locator('#practicePool')).to_have_value('reserve')
        expect(page.locator('#practiceChoices button')).to_have_count(11)
        page.locator('[data-game-view="home"]').click()
        expect(page.locator('#homeDifficulty')).to_be_visible()

        solved = []
        for level, count in [('easy', 3), ('normal', 4), ('hard', 4)]:
            page.locator('#homeDifficulty').select_option(level)
            for i in range(count):
                page.locator('#scopeChallenge').click()
                qid = page.locator('#questionVersion').input_value()
                q = questions[qid]
                assert q['difficulty'] == level and qid != cancelled and qid not in solved
                expect(page.locator('#solutionDetails')).to_be_hidden()
                expect(page.locator('#questionCredit')).to_contain_text('非教师审核')
                if q['template_relation']['kind'] == 'numeric_variant':
                    expect(page.locator('#questionCredit')).to_contain_text('同母题改数')
                    page.screenshot(path=str(screenshots / f'reserve-parent-{width}.png'), full_page=True)
                page.locator('#answer').fill(q['answer'] + (q['units'][0] if q['units'] else ''))
                page.locator('#submitAnswer').click()
                expect(page.locator('#feedbackTitle')).to_contain_text('答对了')
                expect(page.locator('#solutionDetails')).to_be_visible()
                expect(page.locator('#solutionText')).to_have_text(q['explanation'])
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                solved.append(qid)
                page.locator('#changeChapter').click()
                expect(page.locator('#practiceChoices button')).to_have_count(11 - len(solved))
            expect(page.locator('#reserveAvailability')).to_contain_text({'easy': '简单', 'normal': '正常', 'hard': '困难'}[level] + ' 0 道未见题')
        expect(page.locator('#scopeChallenge')).to_be_disabled()
        expect(page.locator('#scopeChallenge')).to_have_text('本档未见备用题已用完')
        expect(page.locator('#homeDifficultyNote')).to_contain_text('没有未见备用题')
        expect(page.locator('#restartRound')).to_be_hidden()
        page.screenshot(path=str(screenshots / f'reserve-exhausted-{width}.png'), full_page=True)
        page.reload()
        expect(page.locator('#practiceChoices button')).to_have_count(0)
        expect(page.locator('#scopeChallenge')).to_be_disabled()
        page.locator('[data-game-view="home"]').click()
        page.locator('#practicePool').select_option('initial')
        expect(page.locator('#practiceChoices button')).to_have_count(18)
        page.locator('#textbookChapter').select_option('5')
        expect(page.locator('#reservePicker')).to_be_hidden()
        expect(page.locator('#practiceChoices button')).to_have_count(12)
        page.locator('.profile-card[data-grade="2"]').click()
        expect(page.locator('#reservePicker')).to_be_hidden()
        expect(page.locator('#practiceChoices button')).to_have_count(40)
        assert len([q for q in presentations if q.startswith('family-reserve-')]) == 12
        with db.session() as conn:
            assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0
            assert conn.execute('SELECT COUNT(*) FROM grade_versions').fetchone()[0] == 11
        assert not errors, errors
        context.close()
        browser.close()
