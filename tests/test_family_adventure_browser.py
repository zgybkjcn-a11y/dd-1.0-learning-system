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


pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [390, 1280])
def test_adventure_profiles_practice_feedback_restore_notebook_and_progress(family, tmp_path, width, textbook_sources, playwright, launch_browser):
    _, db, original, _ = family
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
        browser = launch_browser(runtime)
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
                if scope['query'].endswith('synthetic-empty'):
                    numbers = []
                refs = bounded_references(scope, {'documents':[['合成教材摘录 <script>throw 1</script>']*len(numbers)],
                    'metadatas':[[{'file_id':scope['book']['file_id'], 'page_number':number,
                                  'edition':'pep-2022-standard-current'} for number in numbers]]}, candidate_limit=40)
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
        expect(page.locator('.profile-card')).to_have_count(2)
        expect(page.locator('#startAdventure')).to_be_disabled()
        page.locator('.profile-card[data-grade="2"]').click()
        expect(page.locator('#textbookSubject option')).to_have_count(3)
        expect(page.locator('#textbookSubjectNote')).to_contain_text('学校安排暂未开设')
        expect(page.locator('#textbookChapter')).to_have_value('')
        expect(page.locator('#textbookChapter option')).to_have_count(9)
        expect(page.locator('#practiceChoices button')).to_have_count(4)
        expect(page.locator('#practicePicker')).not_to_have_attribute('open', '')
        expect(page.locator('#practiceChoices')).not_to_contain_text('100以内加减法')
        expect(page.locator('#selectedChapterTitle')).to_contain_text('整本书')
        expect(page.locator('#familyReview')).to_be_hidden()
        expect(page.locator('#loadToday')).to_be_hidden()
        expect(page.locator('.warmup-route')).to_have_count(0)
        page.locator('#textbookSearch').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 1 页')
        expect(page.locator('#textbookResults img')).to_have_count(1)
        expect(page.locator('#textbookPrev')).to_be_disabled()
        page.locator('#textbookNext').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 2 页')
        page.locator('#textbookPageInput').fill('10')
        page.locator('#textbookJump').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 10 页')
        expect(page.locator('#textbookResults details')).to_have_count(1)
        page.locator('#textbookResults img').click()
        expect(page.locator('#textbookZoom')).to_be_visible()
        assert page.locator('#textbookZoomImage').evaluate('(img) => img.complete && img.naturalWidth > 0')
        page.locator('#textbookZoomIn').click()
        expect(page.locator('#textbookZoomLevel')).to_have_text('125%')
        page.locator('#textbookZoomOut').click()
        expect(page.locator('#textbookZoomLevel')).to_have_text('100%')
        page.keyboard.press('Escape')
        expect(page.locator('#textbookZoom')).not_to_be_visible()
        expect(page.locator('#textbookPageRange')).to_have_text('第 10 页')
        page.locator('#textbookResults img').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#textbookZoom')).to_be_visible()
        page.locator('#textbookZoomClose').click()
        page.locator('#textbookContents').evaluate('(el) => el.open = true')
        page.locator('#textbookToc button[data-chapter="2"]').click()
        expect(page.locator('#textbookChapter')).to_have_value('2')
        expect(page.locator('#textbookPageRange')).to_have_text('第 10 页')
        expect(page.locator('#practiceChoices button')).to_have_count(1)
        page.locator('#textbookPageInput').fill('30')
        page.locator('#textbookJump').click()
        expect(page.locator('#textbookStatus')).to_contain_text('10～29')
        expect(page.locator('#textbookPageRange')).to_have_text('第 10 页')
        page.locator('#textbookCollapseAll').click()
        expect(page.locator('#textbookResults img')).not_to_be_visible()
        page.locator('#textbookExpandAll').click()
        expect(page.locator('#textbookResults img')).to_be_visible()
        page.locator('#textbookResults .textbook-close-page').click()
        expect(page.locator('#textbookResults img')).not_to_be_visible()
        page.locator('#textbookResults summary').click()
        expect(page.locator('#textbookResults img')).to_be_visible()
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(screenshots / f'grade2-reader-{width}.png'), full_page=True)

        # The chapter is optional, while selected chapter cards really constrain questions.
        page.locator('#textbookChapter').select_option('')
        expect(page.locator('#practiceChoices button')).to_have_count(4)
        page.locator('#textbookChapter').select_option('1')
        expect(page.locator('#practiceChoices button')).to_have_count(0)
        expect(page.locator('#scopeChallenge')).to_be_disabled()
        expect(page.locator('#scopeAvailability')).to_contain_text('暂未配题')
        page.locator('#textbookSubject').select_option('chinese')
        expect(page.locator('#textbookBook option')).to_have_count(2)
        expect(page.locator('#practiceChoices button')).to_have_count(0)
        expect(page.locator('#startAdventure')).to_be_disabled()
        page.locator('#textbookBook').select_option('chinese-g2-lower')
        expect(page.locator('#textbookChapter')).to_have_value('')
        page.locator('#textbookSearch').click()
        expect(page.locator('#textbookResults')).to_contain_text('古诗：咏柳')
        page.locator('#textbookSubject').select_option('ethics')
        page.locator('#textbookSearch').click()
        expect(page.locator('#textbookResults')).to_contain_text('过好节假日')
        page.locator('#textbookSubject').select_option('math')
        page.locator('#textbookChapter').select_option('2')
        page.locator('#scopeChallenge').click()
        expect(page.locator('#testPrompt')).to_have_text('3 × 4 = ?')
        session = page.locator('#session').input_value()
        page.reload()
        expect(page.locator('#testPrompt')).to_have_text('3 × 4 = ?')
        expect(page.locator('#textbookChapter')).to_have_value('2')
        assert page.locator('#session').input_value() == session
        page.locator('#answer').fill('12')
        page.locator('#answer').press('Enter')
        expect(page.locator('#feedbackTitle')).to_contain_text('答对了')
        expect(page.locator('#heroGraded')).to_have_text('1')
        page.reload()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对了')
        expect(page.locator('#heroGraded')).to_have_text('1')
        expect(page.locator('#roundProgress')).to_contain_text('本轮已完成 1 / 1')
        expect(page.locator('#nextChallenge')).to_have_text('选择其他章节 →')
        expect(page.locator('#restartRound')).to_be_visible()
        page.screenshot(path=str(screenshots / f'one-question-complete-{width}.png'), full_page=True)
        with db.session() as connection:
            sessions_before = connection.execute('SELECT COUNT(*) FROM test_sessions').fetchone()[0]
        page.locator('#nextChallenge').click()
        expect(page.locator('body')).to_have_attribute('data-view', 'home')
        expect(page.locator('#scopeChallenge')).to_contain_text('再练一轮')
        with db.session() as connection:
            assert connection.execute('SELECT COUNT(*) FROM test_sessions').fetchone()[0] == sessions_before
        page.locator('[data-game-view="practice"]').click()
        page.locator('#restartRound').click()
        expect(page.locator('#testPrompt')).to_have_text('3 × 4 = ?')
        expect(page.locator('#answer')).to_be_enabled()
        page.locator('#answer').fill('0')
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('值得再研究')
        expect(page.locator('#heroGraded')).to_have_text('2')
        page.locator('#changeChapter').click()
        page.locator('#chapterPickerLabel').click()
        page.locator('.chapter-option[data-chapter="5"]').click()
        expect(page.locator('#textbookChapter')).to_have_value('5')
        expect(page.locator('#practiceChoices button')).to_have_count(3)
        page.locator('#practicePickerSummary').click()
        page.locator('#practiceChoices button').last.click()
        expect(page.locator('#testPrompt')).to_have_text('9 × 9 = ?')
        # Recover a pre-scope saved question to its precise textbook chapter.
        page.evaluate("Object.keys(sessionStorage).filter(key => key.startsWith('dd-learning-chapter:')).forEach(key => sessionStorage.removeItem(key))")
        page.reload()
        expect(page.locator('#testPrompt')).to_have_text('9 × 9 = ?')
        expect(page.locator('#textbookChapter')).to_have_value('5')
        page.locator('#answer').fill('81')
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对了')
        expect(page.locator('#heroGraded')).to_have_text('3')
        expect(page.locator('#roundProgress')).to_contain_text('1 / 3')
        page.locator('#nextChallenge').click()
        expect(page.locator('#testPrompt')).to_have_text('6 × 7 = ?')
        page.locator('#answer').fill('42')
        page.locator('#submitAnswer').click()
        expect(page.locator('#roundProgress')).to_contain_text('2 / 3')
        page.reload()
        expect(page.locator('#roundProgress')).to_contain_text('2 / 3')
        page.locator('#nextChallenge').click()
        expect(page.locator('#testPrompt')).to_have_text('8 × 5 = ?')
        page.locator('#answer').fill('40')
        page.locator('#submitAnswer').click()
        expect(page.locator('#roundProgress')).to_contain_text('本轮已完成 3 / 3')
        expect(page.locator('#nextChallenge')).to_have_text('选择其他章节 →')
        page.reload()
        expect(page.locator('#roundProgress')).to_contain_text('本轮已完成 3 / 3')
        page.screenshot(path=str(screenshots / f'three-question-complete-{width}.png'), full_page=True)
        page.locator('#nextChallenge').click()
        expect(page.locator('#scopeChallenge')).to_contain_text('再练一轮')
        page.locator('#scopeChallenge').click()
        expect(page.locator('#testPrompt')).to_have_text('6 × 7 = ?')
        expect(page.locator('#answer')).to_be_enabled()
        unfinished = page.locator('#session').input_value()
        page.locator('#answer').fill('42')
        page.locator('#changeChapter').click()
        page.once('dialog', lambda dialog: dialog.dismiss())
        page.locator('#textbookSubject').select_option('chinese')
        expect(page.locator('#textbookSubject')).to_have_value('math')
        expect(page.locator('#textbookChapter')).to_have_value('5')
        expect(page.locator('#answer')).to_have_value('42')
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('#textbookSubject').select_option('chinese')
        expect(page.locator('#textbookSubject')).to_have_value('chinese')
        expect(page.locator('#practiceChoices button')).to_have_count(0)
        expect(page.locator('#session')).to_have_value('')
        with db.session() as connection:
            assert connection.execute('SELECT status FROM test_sessions WHERE id=?', (unfinished,)).fetchone()[0] == 'cancelled'
        page.reload()
        expect(page.locator('#textbookSubject')).to_have_value('chinese')
        expect(page.locator('#startAdventure')).to_be_disabled()
        page.locator('[data-game-view="notebook"]').click()
        page.locator('#manualQuestion').fill('6 × 7 = ?')
        expect(page.locator('#manualObjective')).to_have_value('objective-math-g2-multiplication')
        page.locator('#manualStudentAnswer').fill('35')
        page.locator('#manualCorrectAnswer').fill('42')
        page.locator('#saveManualMistake').click()
        expect(page.locator('#manualStatus')).to_contain_text('已保存')
        expect(page.locator('#mistakes')).to_contain_text('6 × 7')
        page.locator('[data-game-view="home"]').click()
        page.locator('#textbookSubject').select_option('math')
        page.locator('#textbookChapter').select_option('2')
        with db.session(write=True) as connection:
            _ensure_review_card(connection, 'family-g2', 'objective-math-g2-multiplication', settings)
            connection.execute("UPDATE review_cards SET due_at='2000-01-01T00:00:00Z' WHERE learner_id='family-g2'")
        page.locator('[data-game-view="notebook"]').click()
        page.locator('[data-game-view="home"]').click()
        expect(page.locator('#familyReview')).to_be_visible()
        expect(page.locator('#today button')).to_have_count(1)
        page.locator('#today button').click()
        expect(page.locator('#testPrompt')).to_have_text('3 × 4 = ?')
        page.locator('#cancelTest').click()

        page.locator('.profile-card[data-grade="7"]').click()
        expect(page.locator('#textbookSubject option')).to_have_count(7)
        expect(page.locator('#textbookChapter')).to_have_value('')
        expect(page.locator('#practiceChoices button')).to_have_count(6)
        expect(page.locator('#familyReview')).to_be_hidden()
        expect(page.locator('#practicePicker')).not_to_have_attribute('open', '')
        page.locator('#textbookReader').evaluate('(el) => el.open = false')
        page.locator('#textbookMap').screenshot(path=str(screenshots / f'grade7-home-compact-{width}.png'))
        page.locator('#practicePickerSummary').click()
        expect(page.locator('#practiceChoices button').first).to_be_visible()
        page.locator('#textbookMap').screenshot(path=str(screenshots / f'grade7-pick-question-{width}.png'))
        page.locator('#textbookChapter').select_option('5')
        expect(page.locator('#practiceChoices button')).to_have_count(0)
        expect(page.locator('#practicePicker')).to_be_hidden()
        page.locator('#textbookSearch').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 110 页')
        page.locator('#textbookQuery').fill('等式')
        page.locator('#textbookFind').click()
        expect(page.locator('#textbookResults details')).to_have_count(1)
        expect(page.locator('#textbookPageRange')).to_have_text('第 115 页')
        expect(page.locator('#textbookStatus')).to_contain_text('检索可能遗漏')
        expect(page.locator('#textbookResultCount')).to_contain_text('候选原页')
        expect(page.locator('#textbookResults')).to_contain_text('一元一次方程的定义')
        page.locator('#textbookNext').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 144 页')
        expect(page.locator('#textbookResults')).to_contain_text('原页暂未加载成功')
        page.get_by_role('button', name='重新加载原页').click()
        expect(page.locator('#textbookResults img')).to_have_count(1)
        page.locator('#textbookResults img').click()
        expect(page.locator('#textbookZoomTitle')).to_contain_text('144')
        page.locator('#textbookZoomClose').click()
        page.locator('#textbookPrev').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 115 页')
        page.locator('#textbookQuery').fill('synthetic-empty')
        page.locator('#textbookFind').click()
        expect(page.locator('#textbookStatus')).to_contain_text('检索可能遗漏')
        expect(page.locator('#textbookResultCount')).to_have_text('本次没有可展示的候选页')
        expect(page.locator('#textbookResults img')).to_have_count(0)
        page.locator('#textbookQuery').fill('')
        page.locator('#textbookSearch').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 110 页')
        expect(page.locator('#textbookStatus')).to_contain_text('按页阅读')
        for subject in ['english','ethics','history','geography','biology','chinese']:
            page.locator('#textbookSubject').select_option(subject)
            expect(page.locator('#practiceChoices button')).to_have_count(0)
            expect(page.locator('#startAdventure')).to_be_disabled()
            expect(page.locator('#textbookQuery')).to_have_value('')
            page.locator('#textbookSearch').click()
            expect(page.locator('#textbookResults img')).to_have_count(1)
        page.locator('#textbookSubject').select_option('geography')
        page.locator('#textbookChapter').select_option('4')
        page.locator('#textbookSearch').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 43 页')
        expect(page.locator('#selectedChapterTitle')).to_contain_text('陆地和海洋')
        expect(page.locator('#practiceChoices button')).to_have_count(0)
        expect(page.locator('#startAdventure')).to_be_disabled()
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(screenshots / f'geography-reader-{width}.png'), full_page=True)
        page.locator('#textbookSubject').select_option('math')
        page.locator('#textbookBook').select_option('math-g7-lower')
        expect(page.locator('#practiceChoices button')).to_have_count(0)
        expect(page.locator('#startAdventure')).to_be_disabled()
        page.locator('#textbookChapter').select_option('10')
        page.locator('#textbookSearch').click()
        expect(page.locator('#textbookPageRange')).to_have_text('第 87 页')
        page.locator('#textbookBook').select_option('math-g7-upper')
        expect(page.locator('#practiceChoices button')).to_have_count(6)
        page.locator('#scopeChallenge').click()
        expect(page.locator('#testPrompt')).to_have_text('-3 - (-5) = ?')
        expect(page.locator('#practiceChapter')).to_contain_text('整本书')
        page.locator('#requestHint').click()
        expect(page.locator('#gameHint')).to_be_visible()
        page.locator('#answer').fill('2')
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对了')
        expect(page.locator('#heroIndependent')).to_have_text('0')
        page.locator('[data-game-view="notebook"]').click()
        expect(page.locator('#mistakes')).not_to_contain_text('6 × 7')
        page.locator('.profile-card[data-grade="2"]').click()
        expect(page.locator('#heroGraded')).to_have_text('5')
        expect(page.locator('#textbookChapter')).to_have_value('')
        expect(page.locator('#session')).to_have_value('')
        page.locator('[data-game-view="notebook"]').click()
        expect(page.locator('#mistakes')).to_contain_text('6 × 7')
        assert page_errors == []
        with db.session() as connection:
            assert connection.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0
            assert connection.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 6
        context.close()
        browser.close()
