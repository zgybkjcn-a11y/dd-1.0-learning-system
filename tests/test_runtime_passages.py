"""A07 integration: synthetic reviewed material, real auth/service/gateway/Tool."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import importlib.util
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from learning_service import textbook_passages as runtime
from learning_service.app import create_app
from learning_service.login_gateway import GatewaySettings, create_gateway
from learning_service.passage_evidence import canonical, digest, text_digest
from learning_service.passage_retrieval import PILOT_CONCEPTS
from learning_service.textbooks import catalogue, page_evidence, render_page
from test_readonly_study_tools import chat_tools, invoke, module
from test_math_references import reference_family
from test_family_math import family

DAY = date(2026, 11, 7)
QUERY = {'query': '请查减法规则', 'book_id': 'math-g7-upper', 'chapter_id': '2'}


@pytest.fixture
def runtime_bundle(reference_family, tmp_path):
    settings = reference_family[2].app.state.settings
    directory = tmp_path / 'reviewed'; (directory / 'source').mkdir(parents=True)
    ids = list(PILOT_CONCEPTS)
    checks = canonical({'checks': {key: {'passed': True, 'case_count': 3, 'method': 'exact_rational_checks'} for key in ids}})
    (directory / 'semantic-checks.json').write_bytes(checks)
    verifier = b'# Synthetic review evidence; never executed.\n'
    (directory / 'verify_semantics.py').write_bytes(verifier)
    book = next(b for b in catalogue('math-g7-v1') if b['id'] == 'math-g7-upper')
    rows = []
    for i, (key, pdf_page) in enumerate(zip(ids, (34, 38, 47, 48, 49))):
        page = page_evidence(book, pdf_page)
        image = render_page(settings.textbook_dir, book['id'], pdf_page)
        image_path = f'source/page{i}.png'; (directory / image_path).write_bytes(image)
        text = '原创合成规则测试 ' + str(i) + '：本句仅用于集成测试，不是教材正文。'
        context = '原创合成上下文：使用前检查规则条件。'
        binding = {k: page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')}
        binding.update(text_sha256=text_digest(text), context_sha256=text_digest(context), image_sha256=digest(image))
        review = {'revision': 1, 'scope': 'selected_excerpt', 'binding': deepcopy(binding),
                  'teacher_reviewed': False, 'reviewed_on': '2026-11-07', 'valid_until': '2026-12-07', 'unresolved_issues': [],
                  'transcription': {'status': 'checked', 'reviewer_type': 'assistant', 'method': 'visual_original_comparison', 'layout_checked': True, 'notes': 'synthetic comparison'},
                  'semantic': {'status': 'checked', 'reviewer_type': 'assistant', 'method': 'independent_mathematical_reasoning_and_exact_checks',
                               'conditions_complete': True, 'derivation': 'synthetic exact check', 'diagram_dependency': 'none_for_selected_excerpt',
                               'checks_sha256': digest(checks), 'verifier_sha256': digest(verifier)}}
        rows.append({'id': key, 'curriculum_id': 'math-g7-v1', 'book_id': book['id'],
            **{k: page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')},
            'text': text, 'context': context, 'text_policy': 'layout_normalized_transcription',
            'image_path': image_path, 'retrieval_terms': ['合成规则'], 'enabled': True, 'binding': binding, 'review': review})
    manifest = {'format': 'dd-textbook-excerpt-pilot-v1', 'passages': rows}
    (directory / 'passages.json').write_bytes(canonical(manifest))
    return directory, manifest


@pytest.fixture
def stack(chat_tools, runtime_bundle, monkeypatch):
    tool, user, request, calls, race, db, bridge = chat_tools
    directory, manifest = runtime_bundle
    settings = replace(bridge.api.app.state.settings, textbook_passages_enabled=True,
                       family_setup_code="synthetic-family-code-0123456789abcdef",
                       textbook_passages_dir=directory, textbook_passages_sha256=digest((directory / 'passages.json').read_bytes()))
    bridge.api = TestClient(create_app(settings, db), base_url=settings.browser_origin)
    monkeypatch.setattr(runtime, 'current_day', lambda: DAY)
    monkeypatch.setattr(module.Tools, '_today', staticmethod(lambda: DAY))
    gateway = TestClient(create_gateway(GatewaySettings(enabled=True, public_origin=settings.browser_origin,
        openwebui_url='http://webui.invalid:8080', learning_url='http://learning.invalid:8000',
        assertion_secret=settings.browser_auth_secret, assertion_issuer='synthetic-gateway', identity_issuer='family-pilot-webui'), bridge), base_url=settings.browser_origin)
    cookies = dict(part.split('=', 1) for part in request.headers['cookie'].split('; '))
    for key, value in cookies.items(): gateway.cookies.set(key, value)
    headers = {'Origin': settings.browser_origin, 'X-CSRF-Token': cookies[module.CSRF], 'X-Learner-Context-Version': '1'}
    return {'fixture': chat_tools, 'tool': tool, 'api': bridge.api, 'gateway': gateway, 'headers': headers,
            'directory': directory, 'manifest': manifest, 'settings': settings, 'bridge': bridge, 'db': db}


def search(stack, query=None):
    return stack['gateway'].post('/learning/api/v1/textbooks/search', headers=stack['headers'], json=query or QUERY)


def detail(stack, item, suffix='', **params):
    return stack['gateway'].get('/learning' + item['detail_path'] + suffix, headers=stack['headers'], params=params)


def reseal(stack):
    raw = canonical(stack['manifest']); (stack['directory'] / 'passages.json').write_bytes(raw)
    stack['api'].app.state.settings = replace(stack['api'].app.state.settings, textbook_passages_sha256=digest(raw))


def invoke_search(stack, **kw):
    return invoke(stack['fixture'], 'search_textbook', **(QUERY | kw))


def test_service_tool_quote_citation_image_and_no_vector_or_model_calls(stack):
    result = search(stack)
    assert result.status_code == 200, result.text
    body = result.json(); r = body['passage_result']; item = r['items'][0]
    assert body['mode'] == 'passages' and 'retrieval' not in body
    assert body['items'][0]['evidence']['kind'] == 'page_location' and body['items'][0]['text'] == ''
    assert r['answer']['claims'][0]['text'] == item['text']
    response = detail(stack, item); assert response.status_code == 200 and response.json()['item'] == item
    image = detail(stack, item, '/image')
    assert image.status_code == 200 and digest(image.content) == item['evidence']['image_sha256']
    assert image.headers['cache-control'] == 'no-store'
    data, events = invoke_search(stack)
    assert data['passages'][0]['text'] == item['text']
    assert data['answer'] == r['answer'] and len(events) == 1
    c = events[0]['data']; e = item['evidence']
    assert c['document'] == [item['text']]
    assert c['source']['id'] == c['metadata'][0]['evidence_id'] == e['evidence_id']
    assert c['metadata'][0]['page_evidence_id'] == e['page_evidence_id']
    assert c['metadata'][0]['printed_page'] == 31 and c['metadata'][0]['pdf_page'] == 38
    assert 'studyEvidence=' + e['evidence_id'] in c['source']['url']
    assert not any(path == '/api/v1/retrieval/query/doc' for _, _, path, *_ in stack['bridge'].calls)
    with stack['db'].session() as conn: assert conn.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 0


def test_default_off_startup_validation_and_bad_material_preserves_browsing(stack):
    assert runtime.startup_status(stack['settings']) == {'status': 'ready', 'available_count': 5, 'checked_on': DAY.isoformat()}
    off = replace(stack['settings'], textbook_passages_enabled=False)
    assert runtime.startup_status(off) == {'status': 'disabled'}
    missing = replace(stack['settings'], textbook_passages_dir=stack['directory'] / 'missing')
    app = create_app(missing, stack['db'])
    assert app.state.passage_status == {'status': 'unavailable'}
    stack['api'].app.state.settings = missing
    assert search(stack).status_code == 503
    assert search(stack, QUERY | {'query': ''}).json()['mode'] == 'browse'
    assert stack['gateway'].get('/learning/api/v1/textbooks/math-g7-upper/pages/31/image', headers=stack['headers']).status_code == 200
    stack['api'].app.state.settings = off
    data, events = invoke_search(stack)
    assert 'passages' not in data and data['grounding']['can_quote_textbook'] is False and events


@pytest.mark.parametrize('day,available', [(date(2026,11,6),False), (DAY,True), (date(2026,12,7),True), (date(2026,12,8),False)])
def test_inclusive_expiry_and_future_boundary(stack, monkeypatch, day, available):
    old = search(stack).json()['passage_result']['items'][0]
    monkeypatch.setattr(runtime, 'current_day', lambda: day)
    monkeypatch.setattr(module.Tools, '_today', staticmethod(lambda: day))
    response = search(stack); assert response.status_code == 200
    assert bool(response.json()['passage_result']['items']) is available
    assert detail(stack, old).status_code == (200 if available else 404)
    assert detail(stack, old, '/image').status_code == (200 if available else 404)
    data, events = invoke_search(stack)
    assert data['grounding']['can_quote_textbook'] is available and bool(events) is available


@pytest.mark.parametrize('change', ['disabled', 'unresolved', 'pending', 'review', 'text', 'context', 'source', 'image', 'checks', 'verifier', 'missing', 'escape', 'symlink', 'parent_symlink'])
def test_stale_review_files_and_path_escape_never_reuse_cached_quote(stack, change, tmp_path):
    old = search(stack).json()['passage_result']['items'][0]
    entry = stack['manifest']['passages'][1]
    if change == 'disabled': entry['enabled'] = False
    if change == 'unresolved': entry['review']['unresolved_issues'] = ['withdrawn for review']
    if change == 'pending': entry['review']['semantic']['status'] = 'pending'
    if change == 'review': entry['review']['revision'] += 1
    if change == 'text': entry['text'] += ' altered'
    if change == 'context': entry['context'] += ' altered'
    if change == 'escape': entry['image_path'] = '../private.png'
    if change in {'source', 'image', 'checks', 'verifier', 'missing'}:
        path = {'source': stack['settings'].textbook_dir / 'math-g7-upper.pdf',
                'image': stack['directory'] / entry['image_path'], 'checks': stack['directory'] / 'semantic-checks.json',
                'verifier': stack['directory'] / 'verify_semantics.py', 'missing': stack['directory'] / 'semantic-checks.json'}[change]
        if change == 'missing': path.unlink()
        else: path.write_bytes(path.read_bytes() + b'changed')
    if change == 'symlink':
        path = stack['directory'] / entry['image_path']; copy = tmp_path / 'outside.png'; path.rename(copy); path.symlink_to(copy)
    if change == 'parent_symlink':
        link = tmp_path / 'linked'; link.symlink_to(stack['directory'].parent, target_is_directory=True)
        stack['api'].app.state.settings = replace(stack['settings'], textbook_passages_dir=link / stack['directory'].name)
    reseal(stack)
    assert detail(stack, old).status_code in {404, 503}
    assert detail(stack, old, '/image').status_code in {404, 503}
    result = search(stack)
    if change == 'review':
        assert result.status_code == 200
        assert result.json()['passage_result']['items'][0]['evidence']['evidence_id'] != old['evidence']['evidence_id']
    elif change in {'disabled', 'unresolved', 'pending'}:
        assert result.status_code == 200 and result.json()['passage_result']['items'] == []
    else: assert result.status_code == 503


def test_changed_manifest_without_repin_is_rejected(stack):
    path = stack['directory'] / 'passages.json'; path.write_bytes(path.read_bytes() + b' ')
    assert search(stack).status_code == 503
    data, events = invoke_search(stack)
    assert data['error'] == 'TEXTBOOK_UNAVAILABLE' and not events


@pytest.mark.parametrize('param', ['as_of', 'today', 'path', 'bundle', 'manifest_sha256', 'learner_id', 'account_id'])
def test_client_cannot_select_material_time_or_identity(stack, param):
    item = search(stack).json()['passage_result']['items'][0]
    assert search(stack, QUERY | {param: 'unsafe'}).status_code == 422
    assert detail(stack, item, **{param: 'unsafe'}).status_code == 422
    assert detail(stack, item, '/image', **{param: 'unsafe'}).status_code == 422


def test_scope_and_profile_switch_reject_stale_detail(stack):
    item = search(stack).json()['passage_result']['items'][0]
    assert detail(stack, item, chapter_id='5').status_code == 404
    assert search(stack, QUERY | {'chapter_id': '5'}).json()['passage_result']['items'] == []
    assert search(stack, QUERY | {'book_id': 'math-g2-upper'}).status_code == 422
    stack['fixture'][4][0] = True
    data, events = invoke_search(stack)
    assert data['error'] == 'CONTEXT_CHANGED' and not events
    assert detail(stack, item).status_code == 409


@pytest.mark.parametrize('stage', ['service', 'gateway', 'tool_detail', 'tool_final'])
def test_material_or_identity_races_drop_response(stack, monkeypatch, stage):
    if stage == 'service':
        original = runtime.retrieve
        def race(*args, **kw):
            result = original(*args, **kw)
            with stack['db'].session(write=True) as conn: conn.execute('UPDATE account_contexts SET revision=revision+1')
            return result
        monkeypatch.setattr(runtime, 'retrieve', race)
    elif stage == 'gateway':
        original = stack['bridge'].send
        def race(upstream, method, path, *args, **kw):
            result = original(upstream, method, path, *args, **kw)
            if path == '/api/v1/textbooks/search':
                with stack['db'].session(write=True) as conn: conn.execute('UPDATE account_contexts SET revision=revision+1')
            return result
        monkeypatch.setattr(stack['bridge'], 'send', race)
    else:
        original = stack['tool']._fetch; count = [0]
        def race(host, port, path, *args, **kw):
            result = original(host, port, path, *args, **kw)
            if path.endswith('/textbooks/search'): count[0] += 1
            trigger = '/passages/' in path if stage == 'tool_detail' else path.endswith('/textbooks/search') and count[0] == 1
            if trigger:
                stack['manifest']['passages'][1]['enabled'] = False; reseal(stack)
            return result
        stack['tool']._fetch = race
    data, events = invoke_search(stack)
    assert 'error' in data and not events


@pytest.mark.parametrize('field', ['text', 'context', 'review_sha256', 'evidence_id', 'page_evidence_id', 'printed_page', 'teacher_reviewed', 'valid_until', 'claim', 'image_path'])
def test_tool_rejects_tampered_quote_evidence_and_claims(stack, field):
    data = search(stack).json(); item = data['passage_result']['items'][0]
    if field in {'text', 'context', 'image_path'}: item[field] += 'forged'
    elif field == 'claim': data['passage_result']['answer']['claims'] = []
    elif field == 'printed_page': item['evidence'][field] += 1
    elif field == 'teacher_reviewed': item['evidence'][field] = True
    elif field == 'valid_until': item['evidence'][field] = '2026-11-06'
    else: item['evidence'][field] = '0' * 64
    with pytest.raises((module.StudyError, KeyError, TypeError, ValueError)):
        stack['tool']._project('textbooks/search', data, 1)


def test_actual_old_tool_with_new_service_and_new_tool_with_old_service(stack):
    path = Path(__file__).parent / 'fixtures/readonly_study_tools_v1_1_2.py'
    assert digest(path.read_bytes()) == 'a158f47774062a454d6c12bb9944d1b480542ddafba384b71fd0103987afedd1'
    spec = importlib.util.spec_from_file_location('old_readonly_tool', path)
    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    tool = old.Tools(); tool._fetch = stack['tool']._fetch
    fixture = (tool, *stack['fixture'][1:])
    data, events = invoke(fixture, 'search_textbook', **QUERY)
    assert data['pages'] and data['grounding']['status'] == 'incomplete' and not data['grounding']['can_quote_textbook']
    assert all(e['data']['metadata'][0]['kind'] == 'page_location' for e in events)
    assert '原创合成' not in json.dumps(data, ensure_ascii=False)
    stack['api'].app.state.settings = replace(stack['settings'], textbook_passages_enabled=False)
    data, events = invoke_search(stack)
    assert data['pages'] and data['grounding']['can_quote_textbook'] is False and 'passages' not in data


def test_imported_runtime_has_no_script_dependency_and_contract_is_published(stack):
    root = Path(__file__).parents[1]
    for name in ('passage_evidence', 'passage_retrieval', 'textbook_passages'):
        assert 'from scripts' not in (root / 'learning_service' / (name + '.py')).read_text()
    schema = stack['api'].app.openapi()
    assert 'PassageSearchResponse' in schema['components']['schemas']
    assert '/api/v1/textbooks/{book_id}/passages/{evidence_id}' in schema['paths']


def test_multi_excerpt_native_fixture_and_date_rollover(stack, monkeypatch):
    query = QUERY | {'query': '减法规则与倒数定义分别是什么'}
    result = search(stack, query).json()
    assert len(result['passage_result']['items']) == 2
    data, events = invoke_search(stack, query=query['query'])
    assert len(events) == len(data['answer']['claims']) == 2
    destination = os.getenv('DD_PASSAGE_FIXTURE_OUT')
    if destination:
        Path(destination).write_text(json.dumps({'query': query['query'], 'search': result,
            'details': {p['evidence']['evidence_id']: detail(stack, p).json() for p in result['passage_result']['items']}}, ensure_ascii=False, indent=2))
    days = iter([date(2026,12,7), date(2026,12,8)])
    monkeypatch.setattr(runtime, 'current_day', lambda: next(days))
    assert search(stack).status_code == 409


@pytest.mark.parametrize('suffix', ['', '/image'])
def test_gateway_rechecks_profile_after_detail_and_image(stack, monkeypatch, suffix):
    item = search(stack).json()['passage_result']['items'][0]
    original = stack['bridge'].send
    def race(upstream, method, path, *args, **kwargs):
        result = original(upstream, method, path, *args, **kwargs)
        if '/passages/' in path:
            with stack['db'].session(write=True) as conn: conn.execute('UPDATE account_contexts SET revision=revision+1')
        return result
    monkeypatch.setattr(stack['bridge'], 'send', race)
    assert detail(stack, item, suffix).status_code == 409


@pytest.mark.parametrize('utc_hour,expected', [(15, '2026-12-07'), (16, '2026-12-08')])
def test_current_day_uses_beijing_midnight(monkeypatch, utc_hour, expected):
    from datetime import datetime, timezone
    class Clock:
        @staticmethod
        def now(tz): return datetime(2026, 12, 7, utc_hour, 59, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(runtime, 'datetime', Clock)
    assert runtime.current_day().isoformat() == expected


def test_service_snapshot_detects_expiry_during_query(stack, monkeypatch):
    original = runtime.retrieve
    def expire(*args, **kw):
        result = original(*args, **kw)
        monkeypatch.setattr(runtime, 'current_day', lambda: date(2026,12,8))
        return result
    monkeypatch.setattr(runtime, 'retrieve', expire)
    assert search(stack).status_code == 409


def test_openapi_snapshot_matches_current_routes(stack):
    snapshot = Path(__file__).parents[1] / 'docs/contracts/openapi-v1.json'
    assert stack['api'].app.openapi() == json.loads(snapshot.read_text())
