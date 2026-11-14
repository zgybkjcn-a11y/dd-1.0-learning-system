"""B11 host failures and recovery: synthetic intercepted browser requests only."""
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / 'deploy/open-webui-reuse/main-study'
pytestmark = pytest.mark.browser


def wait_for_held_request(page, state):
    end = time.monotonic() + 5
    while not state['pending'] and time.monotonic() < end:
        page.wait_for_timeout(20)  # Pump intercepted request callbacks after the click.
    assert state['pending']


@pytest.fixture
def host(playwright, launch_browser, tmp_path):
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        contexts = []

        def create(editor='<div id="chat-input" contenteditable="true"></div>', width=1280):
            context = browser.new_context(viewport={'width': width, 'height': 1000},
                has_touch=width < 500, service_workers='block')
            contexts.append(context)
            state = {'revision': 1, 'learner': 'synthetic-one', 'offline': False, 'hold': False,
                     'pending': [], 'calls': [], 'errors': []}
            shell = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
            <link rel="stylesheet" href="/static/custom.css"><script defer src="/static/loader.js"></script>
            <style>body{margin:8px}#chat-input{box-sizing:border-box;min-height:80px;width:100%;border:1px solid}nav{width:180px}</style>
            </head><body><nav><div><div><a id="sidebar-new-chat-button" href="/">新对话</a></div></div></nav>
            <form onsubmit="window.submits++;return false">''' + editor + '''<button id="send-message-button">发送</button></form>
            <script>window.submits=0;window.inputs=0;document.addEventListener('input',()=>window.inputs++);</script></body></html>'''

            def handle(route):
                request = route.request
                parsed = urlsplit(request.url)
                assert parsed.netloc == 'b11.example.invalid'
                state['calls'].append((request.method, parsed.path))
                assert request.method == 'GET', 'No host submit or model calls allowed'
                if parsed.path in ('/', '/c/synthetic-chat'):
                    route.fulfill(status=200, content_type='text/html', body=shell); return
                asset = {'/static/loader.js': 'study.js', '/static/custom.css': 'study.css'}.get(parsed.path)
                if asset:
                    route.fulfill(status=200, content_type='text/css' if asset.endswith('.css') else 'text/javascript',
                        body=(ASSETS/asset).read_bytes()); return
                assert parsed.path.startswith('/learning/api/v1/')
                if state['offline']:
                    route.abort('internetdisconnected'); return
                session = dict(account_id='synthetic-parent', learner_id=state['learner'],
                    context_version=state['revision'], server_context_mode=True)
                if parsed.path.endswith('/auth/session'):
                    if state['hold']:
                        state['hold'] = False; state['pending'].append((route, session)); return
                    result = session
                elif parsed.path.endswith('/learners'):
                    result = {'items': [{'id': state['learner'], 'display_name': '合成档案'}]}
                elif parsed.path.endswith('/textbooks'):
                    result = {'items': [dict(id='math-g7-upper', subject='math', subject_title='数学', grade=7,
                        title='合成数学课本', edition='合成版', chapters=[])]}
                elif parsed.path.endswith('/study-support'):
                    result = dict(reference_only=True, scope=dict(book_id='math-g7-upper', chapter_id='', grade=7,
                        subject_title='数学', title='合成数学课本', chapter_title='整本书'),
                        concepts=[], prerequisites=[], study_steps=[], sources=[], page_links=[])
                else: raise AssertionError(parsed.path)
                route.fulfill(status=200, json=result)

            context.route('**/*', handle)
            context.route_web_socket('**/*', lambda ws: ws.close())
            page = context.new_page(); page.on('pageerror', lambda e: state['errors'].append(str(e)))
            page.goto('https://b11.example.invalid/c/synthetic-chat')
            return page, state, context

        yield create, playwright.expect
        for context in contexts: context.close()
        browser.close()


@pytest.mark.parametrize('mutation', ['readonly', 'duplicate', 'missing', 'inert', 'unsupported', 'disabled', 'hidden'])
def test_host_mismatch_disables_insertion_with_visible_reason(host, mutation):
    create, expect = host
    page, state, _ = create('<textarea id="chat-input"></textarea>')
    page.locator('#dd-study-open').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    page.evaluate('''kind => {
        const editor=document.getElementById('chat-input');
        if(kind==='readonly')editor.readOnly=true;
        if(kind==='disabled')editor.disabled=true;
        if(kind==='hidden')editor.style.display='none';
        if(kind==='duplicate')editor.after(editor.cloneNode());
        if(kind==='missing')editor.remove();
        if(kind==='inert')editor.parentElement.inert=true;
        if(kind==='unsupported'){const x=document.createElement('input');x.id=editor.id;editor.replaceWith(x)}
    }''', mutation)
    expect(page.locator('#dd-study-insert')).to_be_disabled()
    expect(page.locator('#dd-study-host-status')).to_contain_text('暂停填入')
    assert page.evaluate('window.submits') == 0
    assert not state['errors']


def test_editor_replaced_during_async_check_never_receives_prompt(host):
    create, expect = host
    page, state, _ = create()
    state['hold'] = True
    page.locator('[data-study-action="search"]').click()
    wait_for_held_request(page, state)
    page.evaluate('''() => {const old=document.getElementById('chat-input');window.detached=old;
        old.replaceWith(old.cloneNode());}''')
    route, session = state['pending'].pop()
    route.fulfill(status=200, json=session)
    expect(page.locator('#dd-chat-study-status')).to_contain_text('聊天页面已变化')
    assert page.locator('#chat-input').inner_text() == ''
    assert page.evaluate('window.detached.innerText') == ''
    assert page.evaluate('window.submits') == 0
    assert not state['errors']


@pytest.mark.parametrize('changed', [False, True])
def test_offline_recovery_preserves_only_same_identity_panel_draft(host, changed):
    create, expect = host
    page, state, _ = create()
    page.locator('#chat-input').fill('已有聊天草稿：−3 + 5 = 2')
    page.locator('#dd-study-open').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    page.locator('#dd-study-material').fill('同一档案的待写问题')
    state['offline'] = True
    page.locator('#dd-study-sync').click()
    expect(page.locator('#dd-study-insert')).to_be_disabled()
    expect(page.locator('#dd-study-family-status')).to_contain_text('暂存')
    assert page.locator('#dd-study-material').input_value() == ''
    state['offline'] = False
    if changed: state.update(revision=2, learner='synthetic-two')
    page.locator('#dd-study-sync').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    expect(page.locator('#dd-study-material')).to_have_value('' if changed else '同一档案的待写问题')
    assert page.locator('#chat-input').inner_text() == '已有聊天草稿：−3 + 5 = 2'
    if changed:
        expect(page.locator('#dd-study-context-notice')).to_contain_text('历史聊天')
        expect(page.locator('#dd-study-context-notice a')).to_have_attribute('href', '/?tools=dd_family_study_readonly_v1')
    assert page.evaluate('window.submits') == 0
    assert not state['errors']


@pytest.mark.parametrize('width', [1280, 390])
def test_keyboard_touch_reflow_and_native_textarea_draft(host, width, tmp_path):
    create, expect = host
    page, state, context = create('<textarea id="chat-input"></textarea>', width)
    page.locator('#dd-study-open').focus(); page.keyboard.press('Enter')
    expect(page.locator('#dd-study-panel')).to_be_visible()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    page.locator('#dd-study-material').fill('中文公式：−3 + 5 = 2；x × 2 = 6')
    page.keyboard.press('Escape')
    expect(page.locator('#dd-study-open')).to_be_focused()
    if width == 390: page.locator('#dd-study-open').tap()
    else: page.locator('#dd-study-open').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    # 200% CSS zoom exercises layout; actual browser/pinch zoom is a device check.
    page.evaluate("document.documentElement.style.zoom='2'")
    page.set_viewport_size({'width': 640, 'height': 1000})
    assert not page.locator('#dd-study-panel').evaluate('(e)=>e.scrollWidth>e.clientWidth+1')
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
    page.evaluate("document.documentElement.style.zoom='1'")
    page.set_viewport_size({'width': 320, 'height': 1000})
    assert not page.locator('#dd-study-panel').evaluate('(e)=>e.scrollWidth>e.clientWidth+1')
    page.locator('#dd-study-insert').click()
    expect(page.locator('#chat-input')).to_have_value(re.compile('中文公式：−3 \\+ 5 = 2'))
    assert '中文公式：−3 + 5 = 2' in page.locator('#chat-input').input_value()
    expect(page.locator('#chat-input')).to_be_focused()
    draft = page.locator('#chat-input').input_value()
    page.locator('#dd-study-open').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    page.locator('#dd-study-insert').click()
    expect(page.locator('#dd-study-status')).to_contain_text('已有草稿')
    assert page.locator('#chat-input').input_value() == draft
    assert page.evaluate('window.submits') == 0 and not state['errors']
    viewport = page.locator('meta[name="viewport"]').get_attribute('content')
    assert 'maximum-scale' not in viewport and 'user-scalable' not in viewport and 'viewport-fit=cover' in viewport
    out = Path(os.getenv('DD_B11_HOST_EVIDENCE', str(tmp_path))); out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out/f'host-{width}.png'))
    (out/f'host-{width}.json').write_text(json.dumps(dict(width=width, keyboard=True, touch_emulated=width==390,
        css_zoom=2, reflow_width=320, draft_preserved=True, automatically_submitted=0, errors=state['errors'])))


@pytest.mark.parametrize('change', ['draft', 'url', 'readonly'])
def test_async_insert_rechecks_current_target_and_user_draft(host, change):
    create, expect = host
    page, state, _ = create('<textarea id="chat-input"></textarea>')
    page.locator('#dd-study-open').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    state['hold'] = True
    page.locator('#dd-study-insert').click()
    wait_for_held_request(page, state)
    page.evaluate('''change => {
        if(change==='draft')document.getElementById('chat-input').value='用户新写的草稿';
        if(change==='url')history.pushState({},'', '/c/another-chat');
        if(change==='readonly')document.getElementById('chat-input').readOnly=true;
    }''', change)
    route, session = state['pending'].pop(); route.fulfill(status=200, json=session)
    expect(page.locator('#dd-study-status')).to_contain_text('已有草稿' if change == 'draft' else '聊天页面已变化')
    assert page.locator('#chat-input').input_value() == ('用户新写的草稿' if change == 'draft' else '')
    assert page.evaluate('window.submits') == 0 and not state['errors']


def test_sidebar_remount_and_mismatch_only_affect_sidebar(host):
    create, expect = host
    page, state, _ = create()
    page.evaluate("document.querySelector('nav').remove()")
    expect(page.locator('#dd-study-nav')).to_have_count(0)
    expect(page.locator('#dd-study-host-status')).to_contain_text('侧栏入口不可用')
    expect(page.locator('[data-study-action="assistant"]')).to_be_enabled()
    page.evaluate('''() => {const side=document.createElement('div');side.id='sidebar';side.role='navigation';
        side.innerHTML='<div><button>宿主侧栏</button></div>';document.body.prepend(side);}''')
    expect(page.locator('#dd-study-nav-compact')).to_have_count(1)
    page.locator('#dd-study-open-compact').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    page.keyboard.press('Escape')
    expect(page.locator('#dd-study-open-compact')).to_be_focused()
    assert page.evaluate('window.submits') == 0 and not state['errors']


def test_closed_panel_still_warns_after_profile_storage_signal(host):
    create, expect = host
    page, state, _ = create()
    page.locator('#chat-input').fill('上一档案聊天草稿')
    page.locator('#dd-study-open').click()
    expect(page.locator('#dd-study-insert')).to_be_enabled()
    page.locator('#dd-study-material').fill('上一档案面板输入')
    page.keyboard.press('Escape')
    state.update(revision=2, learner='synthetic-two')
    page.evaluate("window.dispatchEvent(new StorageEvent('storage',{key:'dd-study-family-pulse-v1'}))")
    expect(page.locator('#dd-chat-context-notice')).to_contain_text('历史聊天')
    expect(page.locator('#dd-chat-context-notice a')).to_have_attribute('target', '_blank')
    assert page.locator('#chat-input').inner_text() == '上一档案聊天草稿'
    assert page.locator('#dd-study-material').input_value() == ''
    assert page.evaluate('window.submits') == 0 and not state['errors']


@pytest.mark.parametrize('missing', ['chapter', 'namespace'])
def test_family_bridge_missing_contract_clears_stale_entry(playwright, launch_browser, missing):
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(service_workers='block')
        script = (ASSETS/'family-bridge.js').read_text()
        html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><body>
        <main><select id="learner"><option>synthetic</option></select>
        <select id="textbookBook"><option>math-g7-upper</option></select><select id="textbookChapter"><option>2</option></select></main>
        <script>let contextVersion=1;function contextNamespace(){return 'synthetic:revision1'};
        function selectLearningScope(){throw Error('Should not launch')};</script></body></html>'''
        context.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=html))
        context.route_web_socket('**/*', lambda ws: ws.close())
        page=context.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('https://b11.example.invalid/learning/ui#studyBook=math-g7-upper&studyRevision=1')
        page.add_script_tag(content=script)
        playwright.expect(page.locator('#dd-family-continue button')).to_have_count(1)
        page.evaluate("kind=>{if(kind==='chapter')document.getElementById('textbookChapter').remove();else {contextNamespace=null;document.body.append(document.createElement('hr'));}}",missing)
        playwright.expect(page.locator('#dd-family-bridge-status')).to_contain_text('暂停关联入口')
        playwright.expect(page.locator('#dd-family-continue')).to_have_count(0)
        assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('dd-study-family-scope-v1:')).length") == 0
        assert not errors
        context.close();browser.close()
