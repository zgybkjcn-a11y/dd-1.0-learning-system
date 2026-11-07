"""Exercise real WebUI frontend with fully synthetic API responses; no live user data.

Only public HTML/static assets are retrieved from the deployment. Every API,
socket and model request is intercepted. No login, chat save or inference.
"""
import json
import os
from pathlib import Path
import ssl
from urllib.parse import urlsplit
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.getenv('DD_MAIN_STUDY_EVIDENCE', str(ROOT / 'learning_data/verification/main-study-20261106')))
ASSETS = ROOT / 'deploy/open-webui-reuse/main-study'
ORIGIN = 'https://172.19.116.53'
OUT.mkdir(parents=True, exist_ok=True)
CACHE = {}
LIVE_ASSETS = os.getenv('DD_MAIN_STUDY_DEPLOYED') == '1'


def main():
    reports = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        for width in (1280, 390):
            context = browser.new_context(viewport={'width': width, 'height': 960},
                                          ignore_https_errors=True, service_workers='block')
            context.add_init_script("localStorage.setItem('token','dd-synthetic-only');localStorage.setItem('locale','zh-CN');")
            calls, errors, writes = [], [], []

            def route_handler(route):
                req = route.request
                url = urlsplit(req.url)
                path = url.path
                calls.append((req.method, path))
                if req.method != 'GET':
                    writes.append((req.method, path))
                    route.fulfill(status=403, json={'detail': 'Synthetic probe: writes blocked'})
                    return
                if url.netloc != '172.19.116.53':
                    route.fulfill(status=403, body='External request blocked')
                    return
                # Preview uses native loader/custom.css hooks, currently empty upstream.
                if not LIVE_ASSETS and path in ('/static/loader.js', '/static/custom.css'):
                    suffix = 'js' if path.endswith('.js') else 'css'
                    route.fulfill(status=200, body=(ASSETS / ('study.' + suffix)).read_bytes(),
                                  content_type='text/javascript' if suffix == 'js' else 'text/css')
                    return
                if path.startswith('/api/'):
                    value = []
                    if path == '/api/config':
                        value = {'status': True, 'name': '初一AI智慧伴学', 'version': '0.12.5',
                                 'default_locale': 'zh-CN', 'features': {'auth': True, 'enable_signup': False,
                                 'enable_websocket': False, 'enable_autocomplete_generation': False},
                                 'oauth': {'providers': {}}, 'ui': {'default_models': 'synthetic-study-model'}}
                    elif path in ('/api/version', '/api/version/updates'):
                        value = {'version': '0.12.5', 'current': '0.12.5', 'latest': '0.12.5'}
                    elif path == '/api/v1/auths/':
                        value = {'id': 'dd-synthetic-user', 'name': '演示同学', 'email': 'demo@example.invalid',
                                 'role': 'user', 'profile_image_url': '/user.png', 'permissions': {}}
                    elif path == '/api/v1/users/user/settings':
                        value = {'ui': {'showSidebar': True, 'models': ['synthetic-study-model']}}
                    elif path in ('/api/models', '/api/v1/models/'):
                        value = {'data': [{'id': 'synthetic-study-model', 'name': '合成测试模型（禁用调用）',
                                          'object': 'model', 'owned_by': 'openai'}]}
                    elif path == '/api/v1/chats/':
                        value = []
                    elif path == '/api/v1/users/user/info':
                        value = {}
                    elif path == '/api/v1/tools/':
                        value = [{'id': 'dd_family_study_readonly_v1', 'name': '课本伴学（只读）',
                                  'user_id': 'dd-synthetic-user', 'meta': {'description': '当前课本的只读参考'},
                                  'created_at': 1, 'updated_at': 1, 'specs': []}]
                    route.fulfill(status=200, json=value)
                    return
                if path.startswith('/ws/'):
                    route.fulfill(status=403, body='Socket disabled')
                    return
                if path == '/learning/auth/login':
                    route.fulfill(status=200, content_type='text/html', body='<h1>家庭学习登录（合成路由）</h1>')
                    return
                if path == '/' or path.startswith(('/_app/', '/static/', '/assets/', '/dd-study/')) or path in ('/user.png', '/manifest.json', '/favicon.png'):
                    if path not in CACHE:
                        with urlopen(ORIGIN + path, context=ssl._create_unverified_context(), timeout=15) as res:
                            CACHE[path] = (res.read(), res.headers.get('Content-Type', 'application/octet-stream'))
                    body, mime = CACHE[path]
                    route.fulfill(status=200, body=body, content_type=mime)
                    return
                route.fulfill(status=404, body='Probe allowlist')

            context.route('**/*', route_handler)
            page = context.new_page()
            page.set_default_timeout(15000)
            page.set_default_navigation_timeout(60000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(ORIGIN + '/?tools=dd_family_study_readonly_v1', wait_until='networkidle')
            try:
                expect(page.locator('#dd-chat-study')).to_be_visible()
                expect(page.locator('#dd-chat-study a')).to_have_attribute('href', '/?tools=dd_family_study_readonly_v1')
                expect(page.get_by_text('1', exact=True)).to_be_visible()
                page.get_by_text('1', exact=True).click()
                expect(page.get_by_text('课本伴学（只读）', exact=True)).to_be_visible()
                page.keyboard.press('Escape')
                page.screenshot(path=str(OUT / f'chat-toolbar-{width}.png'))
                (OUT / f'chat-controls-{width}.txt').write_text(page.locator('body').inner_text())
                # Mobile sidebar starts closed; its own toggle must show our entries.
                if width == 390:
                    page.locator('#sidebar-toggle-button').first.click()
                else:
                    expect(page.locator('#dd-family-link-compact')).to_be_visible()
                    page.locator('#dd-study-open-compact').click()
                    expect(page.locator('#dd-study-panel')).to_be_visible()
                    page.keyboard.press('Escape')
                    page.locator('#sidebar button').first.click()
                expect(page.locator('#dd-family-link')).to_be_visible()
                expect(page.locator('#dd-family-link-compact')).to_have_count(0)
                expect(page.locator('#dd-family-link')).to_have_attribute('href', '/learning/auth/login')
                with context.expect_page() as popup:
                    page.locator('#dd-family-link').click()
                family = popup.value
                family.wait_for_load_state()
                assert family.url == ORIGIN + '/learning/auth/login'
                family.close()
                page.locator('#dd-study-open').click()
                expect(page.locator('#dd-study-panel')).to_be_visible()
                page.locator('#dd-study-topic').fill('有理数的加减法')
                page.locator('#dd-study-source').fill('人教版七上数学，第二章，页码待核对')
                page.locator('#dd-study-material').fill('从 -3 出发，增加 5，怎样解释？ <img src=x onerror=alert(1)>')
                page.locator('#dd-study-preview-box summary').click()
                preview = page.locator('#dd-study-preview').input_value()
                assert '待核对标签' in preview and '资料伴读' in preview
                assert page.locator('#dd-study-panel img').count() == 0
                page.screenshot(path=str(OUT / f'panel-{width}.png'))
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                for subject in ('数学', '语文', '英语', '道德与法治', '历史', '地理', '生物'):
                    page.locator('#dd-study-subject').select_option(label=subject)
                    assert '七年级' + subject in page.locator('#dd-study-preview').input_value()
                page.locator('#dd-study-subject').select_option(label='数学')
                page.locator('input[name="dd-study-mode"][value="lesson"]').check()
                assert '随后只开展第一步' in page.locator('#dd-study-preview').input_value()
                with page.expect_download() as dl:
                    page.locator('#dd-study-download').click()
                saved = Path(dl.value.path()).read_text()
                assert 'DeepTutor' in saved and 'OpenMAIC' in saved and '我的学习卡' in saved
                page.locator('#dd-study-insert').click()
                expect(page.locator('#dd-study-panel')).not_to_be_visible()
                expect(page.locator('#chat-input')).to_contain_text('有理数的加减法')
                expect(page.locator('#chat-input')).to_contain_text('随后只开展第一步')
                # Host submit control being enabled proves native editor state was updated.
                expect(page.locator('#send-message-button')).to_be_enabled()
                text_before = page.locator('#chat-input').inner_text()
                page.locator('#dd-study-open').click()
                page.locator('#dd-study-insert').click()
                expect(page.locator('#dd-study-status')).to_contain_text('已有草稿')
                assert page.locator('#chat-input').inner_text() == text_before
                page.keyboard.press('Escape')
                expect(page.locator('#dd-study-panel')).not_to_be_visible()
                # Host SPA navigation; extension must remain single and usable.
                page.locator('a#sidebar-new-chat-button').click()
                expect(page.locator('#dd-family-link')).to_have_count(1)
                if width == 1280:
                    page.evaluate("localStorage.setItem('sidebar','true')")
                page.reload(wait_until='networkidle')
                if width == 390:
                    page.locator('#sidebar-toggle-button').first.click()
                expect(page.locator('#dd-family-link')).to_be_visible()
                page.locator('#dd-family-link').click(trial=True)  # Wait for the host width animation.
                expect(page.locator('#dd-family-link-compact')).to_have_count(0)
                page.screenshot(path=str(OUT / f'sidebar-{width}.png'))
                assert not errors, errors
                assert not any('completion' in p or '/chats/new' in p for _, p in calls), calls
                reports.append({'width': width, 'passed': True, 'page_errors': errors,
                                'all_api_mocked': True, 'model_calls': 0, 'native_editor': True,
                                'draft_preserved': True, 'family_new_tab': True, 'reload': True,
                                'seven_subjects': True, 'download': True, 'blocked_writes': writes})
            except Exception:
                (OUT / f'failure-{width}.html').write_text(page.content())
                (OUT / f'failure-{width}.json').write_text(json.dumps({'calls': calls, 'errors': errors,
                           'body': page.locator('body').inner_text()[:6000]}, ensure_ascii=False, indent=2))
                page.screenshot(path=str(OUT / f'failure-{width}.png'))
                raise
            finally:
                context.close()
        browser.close()
    (OUT / ('browser-deployed.json' if LIVE_ASSETS else 'browser-preview.json')).write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    print(json.dumps(reports, ensure_ascii=False))


if __name__ == '__main__':
    main()
