"""Exercise automatic notebook goals in the real UI with synthetic ASGI data."""
from dataclasses import replace
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app
from learning_service.browser_auth import SESSION_COOKIE
from test_browser_auth import assertion
from test_family_math import family


@pytest.mark.parametrize('width', [390, 1280])
def test_auto_objective_matches_scope_preserves_manual_choice_and_saves_card(family, width):
    playwright = pytest.importorskip('playwright.sync_api')
    _, db, original, _ = family
    origin = 'https://family-objective.example.invalid'
    settings = replace(original.app.state.settings,
                       browser_auth_enabled=True,
                       browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                       browser_auth_issuer='synthetic-gateway',
                       browser_identity_issuer='family-pilot-webui',
                       browser_origin=origin, public_base_path='/learning',
                       shared_learner_context_enabled=True,
                       family_setup_code='synthetic-family-code-0123456789abcdef')
    api = TestClient(create_app(settings, db), base_url=origin)
    response = api.post('/api/v1/auth/session', headers={
        'Origin': origin,
        'Authorization': 'Bearer ' + assertion(settings, changes={'sub': 'synthetic-parent'}),
    })
    assert response.status_code == 201
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        context = browser.new_context(viewport={'width': width, 'height': 900}, service_workers='block')
        context.add_cookies([{'name': name, 'value': value, 'url': origin, 'secure': True,
                             'httpOnly': name == SESSION_COOKIE, 'sameSite': 'Strict'}
                            for name, value in api.cookies.items()])
        page_errors = []

        def handle(route):
            url = urlsplit(route.request.url)
            assert url.scheme + '://' + url.netloc == origin
            assert url.path.startswith('/learning/')
            response = api.request(route.request.method, url.path.removeprefix('/learning'),
                                   headers=route.request.all_headers(),
                                   content=route.request.post_data_buffer, follow_redirects=False)
            route.fulfill(status=response.status_code, body=response.content,
                          headers={key: value for key, value in response.headers.items()
                                   if key not in ('content-length', 'set-cookie')})

        context.route('**/*', handle)
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.goto(origin + '/learning/ui')
        page.wait_for_function("document.querySelector('#learner').options.length === 3")
        question = page.locator('#manualQuestion')
        objective = page.locator('#manualObjective')

        def grade(number):
            page.locator(f'.profile-card[data-learner="family-g{number}"]').click()
            count = 3 if number == 2 else 2
            page.wait_for_function(f"document.querySelector('#manualObjective').options.length === {count}")
            page.locator('[data-game-view="notebook"]').click()

        def check(text, goal):
            question.fill(text)
            playwright.expect(objective).to_have_value(goal)

        grade(2)
        add = 'objective-math-g2-add-subtract-100'
        multiply = 'objective-math-g2-multiplication'
        for text in ['23 + 15 = ?', '56-19', '３８＋２７＝？', '计算 3 加上 4']:
            check(text, add)
        for text in ['3 × 4 = ?', '6乘以7等于多少', '8x5=?']:
            check(text, multiply)
        for text in ['100+1', '12*9', '5/2', '3.5+2', '38+27和6×7',
                     '长方形的面积是多少？', '3+4x', '3+(4*2)', '-3-(-5)']:
            check(text, '')
        check('6 × 7 = ?', multiply)
        objective.select_option(add)
        question.fill('8 × 5 = ?')
        playwright.expect(objective).to_have_value(add)
        page.evaluate("document.querySelector('#loadToday').click()")
        playwright.expect(objective).to_have_value(add)
        objective.select_option('')
        page.evaluate("document.querySelector('#loadToday').click()")
        question.fill('3 × 4 = ?')
        playwright.expect(objective).to_have_value('')

        grade(7)
        playwright.expect(question).to_have_value('')
        subtract = 'objective-math-g7-subtract-negative-v1'
        for text in ['-3 - (-5) = ?', '4 − （−6）', '(-7)-(-2)', '12减去-3']:
            check(text, subtract)
        for text in ['3 × 4 = ?', '20+30', '解方程 3+4x', '长方形的面积是多少？']:
            check(text, '')
        grade(2)
        check('6 × 7 = ?', multiply)
        page.locator('#manualCorrectAnswer').fill('42')
        page.locator('#saveManualMistake').click()
        page.wait_for_function("document.querySelector('#manualStatus').textContent.includes('已保存')")
        playwright.expect(question).to_have_value('')
        check('23+15', add)
        with db.session() as connection:
            entry = connection.execute('SELECT learner_id,objective_id FROM mistake_entries').fetchone()
            assert tuple(entry) == ('family-g2', multiply)
            assert connection.execute('SELECT COUNT(*) FROM review_cards WHERE learner_id=? AND objective_id=?',
                                      ('family-g2', multiply)).fetchone()[0] == 1
            assert connection.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0
        assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
        assert page_errors == []
        context.close()
        browser.close()
