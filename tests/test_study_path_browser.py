"""Family home study path: ordering cards, step actions, two viewports, no external calls."""
from dataclasses import replace
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.browser_auth import SESSION_COOKIE
from learning_service.db import utc_now
from test_browser_auth import assertion
from test_family_math import family


pytestmark = pytest.mark.browser


def prepare_path(api, db, origin):
    csrf = api.cookies.get('__Host-dd_learning_csrf')
    selected = api.post('/api/v1/learner-context',
                        json={'learner_id': 'family-g2', 'expected_revision': 0},
                        headers={'Origin': origin, 'X-CSRF-Token': csrf})
    assert selected.status_code == 200
    headers = {'X-Learner-Context-Version': str(selected.json()['context_version'])}
    write_headers = {**headers, 'Origin': origin, 'X-CSRF-Token': csrf}
    data = api.get('/api/v1/question-choices', headers=headers).json()
    item = next(entry for entry in data['items'] if entry.get('textbook_scope'))
    scope = item['textbook_scope']
    workspace = api.put('/api/v1/practice-workspace', headers=write_headers,
                        json={'expected_revision': 0, 'book_id': scope['book_id'],
                              'chapter_id': scope['chapter_id'], 'difficulty': 'auto', 'pool': 'initial'}).json()
    session = api.post('/api/v1/test-sessions', headers=write_headers,
                       json={'question_version_id': item['question_version_id'],
                             'textbook_book_id': scope['book_id'],
                             'textbook_chapter_id': scope['chapter_id'],
                             'workspace_revision': workspace['revision']})
    assert session.status_code == 201
    objective = data['objectives'][0]['id']
    with db.session(write=True) as conn:
        point = conn.execute('SELECT knowledge_point_id FROM review_objectives WHERE id=?', (objective,)).fetchone()[0]
        conn.execute('INSERT INTO review_cards(id,learner_id,knowledge_point_id,objective_id,state,stage,due_at,'
                     'timezone_snapshot,scheduler_version,revision,created_at,updated_at) '
                     'VALUES (?,?,?,?,?,0,?,?,?,1,?,?)',
                     ('card-browser-path', 'family-g2', point, objective, 'review', '2000-01-01T00:00:00Z',
                      'Asia/Shanghai', 'synthetic-scheduler', utc_now(), utc_now()))


@pytest.mark.parametrize('width', [390, 1280])
def test_study_path_cards_and_actions(family, width, textbook_sources, playwright, launch_browser):
    _, db, original, _ = family
    origin = 'https://study-path.example.invalid'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
                       browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                       browser_auth_issuer='synthetic-gateway',
                       browser_identity_issuer='family-pilot-webui', browser_origin=origin,
                       public_base_path='/learning', shared_learner_context_enabled=True,
                       family_setup_code='synthetic-family-code-0123456789abcdef', textbook_dir=textbook_sources)
    api = TestClient(create_app(settings, db), base_url=origin)
    assert api.post('/api/v1/auth/session', headers={'Origin': origin,
                    'Authorization': 'Bearer ' + assertion(settings, changes={'sub': 'synthetic-parent'})}).status_code == 201
    prepare_path(api, db, origin)

    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(viewport={'width': width, 'height': 960}, service_workers='block')
        context.add_cookies([{'name': name, 'value': value, 'url': origin, 'secure': True,
                             'httpOnly': name == SESSION_COOKIE, 'sameSite': 'Strict'}
                            for name, value in api.cookies.items()])
        page_errors = []

        def handle(route):
            url = urlsplit(route.request.url)
            assert url.scheme + '://' + url.netloc == origin
            assert url.path.startswith('/learning/')
            response = api.request(route.request.method, url.path.removeprefix('/learning'),
                                   headers=route.request.all_headers(), content=route.request.post_data_buffer,
                                   follow_redirects=False)
            route.fulfill(status=response.status_code, body=response.content,
                          headers={key: value for key, value in response.headers.items()
                                   if key not in ('content-length', 'set-cookie')})

        context.route('**/*', handle)
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.goto(origin + '/learning/ui')
        expect = playwright.expect
        page.locator('.profile-card[data-grade="2"]').click()

        expect(page.locator('#studyPath')).to_be_visible()
        expect(page.locator('.study-path-step')).to_have_count(3)
        expect(page.locator('.study-path-step strong').nth(0)).to_have_text('继续上次练习')
        expect(page.locator('.study-path-step strong').nth(1)).to_have_text('到期复习')
        expect(page.locator('.study-path-step strong').nth(2)).to_have_text('练习当前章节')
        expect(page.locator('#studyPathTotal')).to_contain_text('19 分钟')
        expect(page.locator('#studyPathNotice')).to_contain_text('不代表掌握程度')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth') is True

        page.locator('.study-path-step button').nth(1).click()
        expect(page.locator('#familyReview')).to_be_visible()

        page.locator('.study-path-step button').nth(2).click()
        expect(page.locator('body')).to_have_attribute('data-view', 'practice')
        expect(page.locator('#testPrompt')).not_to_be_empty()

        page.locator('[data-game-view="home"]').click()
        expect(page.locator('#studyPath')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth') is True
        assert page_errors == []
        browser.close()
