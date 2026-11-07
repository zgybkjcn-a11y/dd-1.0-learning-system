"""Family adventure UI: real controls, scoped synthetic data, no external calls."""
import os
import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import _ensure_review_card, create_app, run_worker_once
from learning_service.browser_auth import SESSION_COOKIE
from learning_service.textbooks import bounded_references, chapter_references
from test_browser_auth import assertion
from test_family_math import family
from learning_service.practice import install, bank
from test_textbooks import textbook_sources


@pytest.mark.parametrize('width', [390, 1280])
def test_word_problems_difficulty_next_question_and_restore(family, tmp_path, width, textbook_sources):
    playwright = pytest.importorskip('playwright.sync_api')
    _, db, original, _ = family
    install(db)
    origin = 'https://family-adventure.example.invalid'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
                       browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                       browser_auth_issuer='synthetic-gateway',
                       browser_identity_issuer='family-pilot-webui', browser_origin=origin,
                       public_base_path='/learning', shared_learner_context_enabled=True,
                       family_setup_code='synthetic-family-code-0123456789abcdef', textbook_dir=textbook_sources)
    api = TestClient(create_app(settings, db), base_url=origin)
    assert api.post('/api/v1/auth/session', headers={'Origin': origin,
                    'Authorization': 'Bearer ' + assertion(settings, changes={'sub': 'synthetic-parent'})}).status_code == 201
    screenshots = Path(os.getenv('DD_FAMILY_GAME_EVIDENCE_DIR', str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        context = browser.new_context(viewport={'width': width, 'height': 960}, service_workers='block')
        context.add_cookies([{'name': name, 'value': value, 'url': origin, 'secure': True,
                             'httpOnly': name == SESSION_COOKIE, 'sameSite': 'Strict'}
                            for name, value in api.cookies.items()])
        page_errors = []
        fail_preview_once = [True]

        def handle(route):
            url = urlsplit(route.request.url)
            assert url.scheme + '://' + url.netloc == origin
            assert url.path.startswith('/learning/')
            if url.path.endswith('/pages/144/image') and fail_preview_once[0]:
                fail_preview_once[0] = False
                route.fulfill(status=503, json={'error':{'message':'synthetic unavailable'}})
                return
            if '/api/v1/attempts/' in url.path and route.request.method == 'GET':
                run_worker_once(db, settings)
            response = api.request(route.request.method, url.path.removeprefix('/learning'),
                                   headers=route.request.all_headers(), content=route.request.post_data_buffer,
                                   follow_redirects=False)
            if url.path.endswith('/textbooks/search') and response.status_code == 200:
                scope = response.json()
                if scope['mode']=='browse':
                    route.fulfill(status=200,json=chapter_references(scope))
                    return
                numbers = [151,122] if scope['book']['id']=='math-g7-upper' and scope['chapter']['id']=='5' else [scope['chapter']['page_start']]
                refs = bounded_references(scope, {'documents':[['合成教材摘录 <script>throw 1</script>']*len(numbers)],
                    'metadatas':[[{'file_id':scope['book']['file_id'], 'page_number':number,
                                  'edition':'pep-2022-standard-current'} for number in numbers]]})
                route.fulfill(status=200, json=refs)
                return
            route.fulfill(status=response.status_code, body=response.content,
                          headers={key: value for key, value in response.headers.items()
                                   if key not in ('content-length', 'set-cookie')})

        context.route('**/*', handle)
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.goto(origin + '/learning/ui')
        expect = playwright.expect
        questions = bank()
        def solve(hint=False, wrong=False):
            qid = page.locator('#questionVersion').input_value()
            question = questions[qid]
            expect(page.locator('#testPrompt')).to_have_text(question['prompt'])
            expect(page.locator('#solutionDetails')).to_be_hidden()
            if hint:
                page.locator('#requestHint').click()
                expect(page.locator('#gameHint')).to_contain_text(question['hint'])
            page.locator('#answer').fill('99999' if wrong else question['answer'] + (question['units'][0] if question['units'] else ''))
            page.locator('#submitAnswer').click()
            expect(page.locator('#feedbackTitle')).to_contain_text('值得再研究' if wrong else '答对了')
            expect(page.locator('#solutionDetails')).to_be_visible()
            page.locator('#solutionDetails summary').click()
            expect(page.locator('#solutionText')).to_have_text(question['explanation'])
            expect(page.locator('#nextChallenge')).to_be_enabled()
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            return qid

        page.locator('.profile-card[data-grade="2"]').click()
        expect(page.locator('#practiceChoices button')).to_have_count(40)
        page.locator('#textbookChapter').select_option('2')
        expect(page.locator('#homeDifficulty')).to_have_value('auto')
        expect(page.locator('#homeDifficultyNote')).to_contain_text('简单')
        page.locator('#scopeChallenge').click()
        easy_ids=[]
        for i in range(4):
            easy_ids.append(solve())
            if i < 3:
                expect(page.locator('#nextChallenge')).to_contain_text('继续出题 · 简单')
                expect(page.locator('#practiceDifficultyNote')).to_contain_text(f'{i+1} / 4')
                page.reload()
                expect(page.locator('#practiceDifficultyNote')).to_contain_text(f'{i+1} / 4')
                expect(page.locator('#nextChallenge')).to_contain_text('简单')
                page.locator('#nextChallenge').click()
        assert len(set(easy_ids)) == 4
        expect(page.locator('#nextChallenge')).to_contain_text('正常')
        page.reload()
        expect(page.locator('#nextChallenge')).to_contain_text('正常')
        page.locator('#nextChallenge').click()
        assert questions[page.locator('#questionVersion').input_value()]['difficulty']=='normal'
        solve(hint=True)
        expect(page.locator('#practiceDifficultyNote')).to_contain_text('下一题：简单')
        expect(page.locator('#nextChallenge')).to_have_text('选择其他章节 →')
        page.locator('#restartRound').click()
        relearned=[]
        for i in range(4):
            relearned.append(solve())
            if i < 3:
                expect(page.locator('#nextChallenge')).to_contain_text('简单')
                page.locator('#nextChallenge').click()
        assert set(relearned)==set(easy_ids)
        expect(page.locator('#nextChallenge')).to_contain_text('正常')
        page.locator('#practiceDifficulty').select_option('hard')
        expect(page.locator('#nextChallenge')).to_contain_text('困难')
        page.locator('#nextChallenge').click()
        expect(page.locator('#questionBadge')).to_contain_text('思维拓展')
        hard=[]
        for i in range(4):
            hard.append(solve(wrong=i==0))
            if i<3: page.locator('#nextChallenge').click()
        assert len(set(hard))==4
        expect(page.locator('#roundProgress')).to_contain_text('本档已练完')
        expect(page.locator('#nextChallenge')).to_have_text('选择其他章节 →')
        expect(page.locator('#restartRound')).to_be_visible()
        page.screenshot(path=str(screenshots/f'word-problem-finished-{width}.png'),full_page=True)
        page.reload()
        expect(page.locator('#practiceDifficulty')).to_have_value('hard')
        expect(page.locator('#nextChallenge')).to_have_text('选择其他章节 →')
        page.locator('#practiceDifficulty').select_option('normal')
        page.locator('#nextChallenge').click()
        assert questions[page.locator('#questionVersion').input_value()]['difficulty']=='normal'
        solve()
        page.locator('#changeChapter').click()
        page.locator('#textbookChapter').select_option('3')
        page.locator('#homeDifficulty').select_option('easy')
        page.locator('#scopeChallenge').click()
        assert questions[page.locator('#questionVersion').input_value()]['chapter_id']=='3'
        solve()
        page.locator('#changeChapter').click()
        page.locator('.profile-card[data-grade="7"]').click()
        expect(page.locator('#homeDifficulty')).to_have_value('auto')
        expect(page.locator('#practiceChoices button')).to_have_count(30)
        page.locator('#textbookChapter').select_option('5')
        page.locator('#homeDifficulty').select_option('hard')
        page.locator('#scopeChallenge').click()
        question=questions[page.locator('#questionVersion').input_value()]
        assert question['grade']==7 and question['chapter_id']=='5' and question['difficulty']=='hard'
        expect(page.locator('#questionCredit')).to_be_visible()
        expect(page.locator('#questionBadge')).to_be_visible()
        expect(page.locator('#questionCredit')).to_contain_text('CC BY-NC 4.0')
        assert page.locator('#questionCredit a').first.get_attribute('href').startswith('https://github.com/xiaoyang111222/')
        page.screenshot(path=str(screenshots/f'word-problem-grade7-{width}.png'),full_page=True)
        solve()
        page.locator('#changeChapter').click()
        page.locator('#textbookSubject').select_option('chinese')
        expect(page.locator('#scopeChallenge')).to_be_disabled()
        with db.session() as c:
            assert c.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0
        assert not page_errors, page_errors
        context.close(); browser.close()
