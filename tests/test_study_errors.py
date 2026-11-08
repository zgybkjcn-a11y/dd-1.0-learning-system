"""Failure recovery using synthetic sessions/transports; no external requests."""
import asyncio
from dataclasses import replace
import json
import re

import pytest

from learning_service.gateway_http import GatewayResult
from test_browser_auth import auth_env, csrf
from test_family_math import family
from test_learning_service import env
from test_login_gateway import gateway_env, gateway_login
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools, invoke, module
from test_textbooks import retrieval_gateway


def assert_private_failure(data, logs):
    raw = json.dumps(data, ensure_ascii=False) + logs
    for forbidden in ('synthetic-token', 'SECRET', 'subject-a', 'acct-a', 'learner-a',
                      'synthetic-parent', 'family-g7', 'Cookie', 'Traceback', 'answer_key', 'UNREVIEWED'):
        assert forbidden not in raw
    assert not {'pages', 'concepts', 'questions', 'identity', 'account_id', 'learner_id'} & data.keys()


def gateway_error(response, code, status, action, caplog):
    assert response.status_code == status
    error = response.json()['error']
    assert error['code'] == code and error['action'] == action
    assert re.fullmatch(r'ddreq_[a-f0-9]{32}', error['request_id'])
    assert response.headers['X-DD-Request-ID'] == error['request_id']
    assert response.headers['Cache-Control'] == 'no-store'
    logs = [r for r in caplog.records if r.name == 'dd.study.gateway']
    assert any(error['request_id'] in r.getMessage() and code in r.getMessage() for r in logs)
    assert all(r.exc_info is None for r in logs)
    assert_private_failure(response.json(), '\n'.join(r.getMessage() for r in logs))
    return error


@pytest.mark.parametrize('condition,code', [
    ('expired', 'BROWSER_SESSION_EXPIRED'), ('revoked', 'BROWSER_SESSION_INVALID'),
    ('unbound', 'BROWSER_SESSION_INVALID'), ('other_subject', 'LEARNING_IDENTITY_MISMATCH'),
])
def test_session_expiry_and_actual_identity_conflict_are_distinct(gateway_env, condition, code, caplog):
    s, db, _, bridge, client = gateway_env
    assert gateway_login(s, client)[0].status_code == 303
    if condition == 'other_subject':
        client.cookies.set('token', 'synthetic-token-b')
    else:
        with db.session(write=True) as conn:
            conn.execute("UPDATE browser_sessions SET expires_at='2000-01-01T00:00:00+00:00'")
            if condition == 'revoked': conn.execute("UPDATE browser_sessions SET revoked_at='2000-01-01T00:00:00+00:00'")
            if condition == 'unbound': conn.execute("DELETE FROM identity_bindings WHERE subject='subject-a'")
    bridge.calls.clear()
    response = client.get('/learning/api/v1/textbooks', headers={'X-DD-Request-ID': 'SECRET-user-selected-id'})
    gateway_error(response, code, 401, 'confirm_login' if condition == 'other_subject' else 'reenter', caplog)
    assert len(response.headers.get_list('set-cookie')) == 2
    assert not any(c[2] == '/api/v1/textbooks' for c in bridge.calls)


@pytest.mark.parametrize('condition,code,status', [
    ('webui_500', 'AUTH_UPSTREAM_UNAVAILABLE', 503),
    ('webui_timeout', 'AUTH_UPSTREAM_TIMEOUT', 504),
    ('session_500', 'LEARNING_UPSTREAM_UNAVAILABLE', 503),
    ('session_timeout', 'LEARNING_UPSTREAM_TIMEOUT', 504),
    ('session_malformed', 'LEARNING_UPSTREAM_INVALID', 502),
    ('session_bad_identity', 'LEARNING_UPSTREAM_INVALID', 502),
    ('unknown_exception', 'STUDY_REQUEST_UNAVAILABLE', 503),
])
def test_outage_or_malformed_response_never_claims_identity_mismatch(gateway_env, condition, code, status, caplog, monkeypatch):
    s, _, settings, bridge, client = gateway_env
    assert gateway_login(s, client)[0].status_code == 303
    original = bridge.send
    def fault(upstream, method, path, headers, body=b'', **kwargs):
        if condition.startswith('webui') and upstream == settings.openwebui_url:
            if condition.endswith('timeout'): raise TimeoutError('SECRET Cookie=synthetic-token-a')
            return GatewayResult(500, b'SECRET account_id=acct-a')
        if upstream == settings.learning_url and path == '/api/v1/auth/session':
            if condition == 'session_timeout': raise TimeoutError('SECRET learner-a')
            if condition == 'session_500': return GatewayResult(500, b'SECRET')
            if condition == 'session_malformed': return GatewayResult(200, b'{"identity":"SECRET"}')
            if condition == 'session_bad_identity': return GatewayResult(200, b'{"server_context_mode":true,"identity":{"subject":"SECRET"}}')
        return original(upstream, method, path, headers, body, **kwargs)
    bridge.send = fault
    if condition == 'unknown_exception':
        from learning_service import login_gateway
        monkeypatch.setattr(login_gateway, '_cookies', lambda _: (_ for _ in ()).throw(RuntimeError('SECRET Cookie acct-a')))
    response = client.get('/learning/api/v1/auth/session')
    gateway_error(response, code, status, 'retry_later', caplog)
    assert not response.headers.get_list('set-cookie')


@pytest.mark.parametrize('condition,code,status,action', [
    ('revision', 'LEARNER_CONTEXT_CHANGED', 409, 'reselect_scope'),
    ('scope', 'TEXTBOOK_SCOPE_INVALID', 422, 'reselect_scope'),
    ('csrf', 'BROWSER_CSRF_REJECTED', 403, 'refresh'),
    ('timeout', 'TEXTBOOK_RETRIEVAL_TIMEOUT', 504, 'retry_later'),
    ('unavailable', 'TEXTBOOK_RETRIEVAL_UNAVAILABLE', 503, 'retry_later'),
    ('missing_pdf', 'TEXTBOOK_PAGE_UNAVAILABLE', 503, 'contact_maintainer'),
])
def test_gateway_scope_material_and_retrieval_recovery(retrieval_gateway, condition, code, status, action, caplog):
    s, _, bridge, client = retrieval_gateway
    headers = {**csrf(s, client), 'X-Learner-Context-Version': '1'}
    body = {'book_id': 'math-g7-upper', 'chapter_id': '1', 'query': '正数'}
    if condition == 'revision': headers['X-Learner-Context-Version'] = '0'
    if condition == 'scope': body['book_id'] = 'math-g2-upper'
    if condition == 'csrf': headers.pop('X-CSRF-Token')
    if condition == 'timeout': bridge.retrieval_error = True
    if condition == 'unavailable': bridge.retrieval_status = 500
    if condition == 'missing_pdf':
        bridge.api.app.state.settings = replace(bridge.api.app.state.settings, textbook_dir=None)
        response = client.get('/learning/api/v1/textbooks/math-g7-upper/pages/1/image', headers=headers)
    else:
        response = client.post('/learning/api/v1/textbooks/search', json=body, headers=headers)
    gateway_error(response, code, status, action, caplog)
    assert 'items' not in response.json()
    if condition in {'revision', 'scope', 'csrf'}:
        assert not any(c[2] == '/api/v1/retrieval/query/doc' for c in bridge.calls)


@pytest.mark.parametrize('status,body,expected', [
    (503, b'{"error":{"code":"MATH_REFERENCE_TEXTBOOK_UNAVAILABLE","message":"SECRET","details":{"answer_key":42}}}', 'MATH_REFERENCE_TEXTBOOK_UNAVAILABLE'),
    (500, b'{"error":{"code":"SECRET-user-id","message":"SECRET"}}', 'STUDY_REQUEST_UNAVAILABLE'),
    (500, b'{"error":{"code":"LEARNING_IDENTITY_MISMATCH","message":"SECRET"}}', 'STUDY_REQUEST_UNAVAILABLE'),
    (503, b'{"error":{"code":"MATH_REFERENCE_TEXTBOOK_UNAVAILABLE","code":"SECRET"}}', 'STUDY_REQUEST_UNAVAILABLE'),
])
def test_upstream_error_details_are_never_forwarded(gateway_env, status, body, expected, caplog):
    s, _, settings, bridge, client = gateway_env
    assert gateway_login(s, client)[0].status_code == 303
    original = bridge.send
    def fault(upstream, method, path, headers, payload=b'', **kwargs):
        if upstream == settings.learning_url and path.startswith('/api/v1/math-references'):
            return GatewayResult(status, body)
        return original(upstream, method, path, headers, payload, **kwargs)
    bridge.send = fault
    response = client.get('/learning/api/v1/math-references')
    gateway_error(response, expected, status, 'contact_maintainer' if expected.startswith('MATH_') else 'retry_later', caplog)


@pytest.mark.parametrize('condition,expected,action', [
    ('expired', 'SESSION_EXPIRED', 'reenter'), ('identity', 'IDENTITY_CHANGED', 'confirm_login'),
    ('revision', 'CONTEXT_CHANGED', 'reselect_scope'), ('scope', 'INVALID_SCOPE', 'reselect_scope'),
    ('material', 'TEXTBOOK_UNAVAILABLE', 'contact_maintainer'),
    ('timeout', 'RETRIEVAL_TIMEOUT', 'retry_later'), ('unknown', 'STUDY_REFERENCE_UNAVAILABLE', 'retry_later'),
])
def test_tool_reports_cause_and_discards_evidence(chat_tools, condition, expected, action, caplog):
    tool, _, _, _, race, db, bridge = chat_tools
    if condition == 'expired':
        with db.session(write=True) as conn: conn.execute("UPDATE browser_sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    if condition == 'identity': bridge.identities['synthetic-token-a'] = 'different-subject'
    if condition == 'revision': race[0] = True
    if condition == 'material': bridge.api.app.state.settings = replace(bridge.api.app.state.settings, textbook_dir=None)
    if condition == 'unknown':
        tool._fetch = lambda *a, **kw: (_ for _ in ()).throw(ValueError('SECRET Cookie=synthetic-token-a answer_key=42'))
    if condition == 'timeout':
        original = bridge.send
        def timeout(upstream, method, path, headers, body=b'', **kwargs):
            if path == '/api/v1/retrieval/query/doc': raise TimeoutError('SECRET Cookie')
            return original(upstream, method, path, headers, body, **kwargs)
        bridge.send = timeout
    if condition == 'material':
        data, events = invoke(chat_tools, 'get_math_scope', book_id='math-g7-upper', chapter_id='2')
    else:
        data, events = invoke(chat_tools, 'search_textbook', query='减法', book_id='math-g2-upper' if condition == 'scope' else 'math-g7-upper', chapter_id='2')
    assert data['error'] == expected and data['action'] == action
    assert data['retryable'] == (action == 'retry_later')
    assert re.fullmatch(r'dd(?:req|tool)_[a-f0-9]{32}', data['request_id'])
    assert not events
    assert_private_failure(data, caplog.text)
    assert any(data['request_id'] in r.getMessage() for r in caplog.records if r.name == 'dd.study.tool')
    if condition not in {'unknown', 'revision'}:
        assert any(data['request_id'] in r.getMessage() for r in caplog.records if r.name == 'dd.study.gateway')


@pytest.mark.parametrize('stage', ['before', 'after'])
def test_tool_rejects_real_account_mismatch_before_returning_evidence(chat_tools, stage):
    tool, user, request, *_ = chat_tools
    if stage == 'before':
        result = json.loads(asyncio.run(tool.get_study_catalogue(__user__={'id':'different-user'}, __request__=request)))
        assert result['error'] == 'IDENTITY_CHANGED'
        return
    original = tool._fetch
    count = 0
    def swapped(*args, **kwargs):
        nonlocal count
        data = original(*args, **kwargs)
        if args[2].endswith('/auth/session'):
            count += 1
            if count == 2: data['account_id'] = 'different-account'
        return data
    tool._fetch = swapped
    data, events = invoke(chat_tools, 'get_math_scope', chapter_id='2')
    assert data['error'] == 'IDENTITY_CHANGED' and not events and 'concepts' not in data


@pytest.mark.parametrize('host,status,body,expected', [
    ('open-webui', 401, b'SECRET', 'LOGIN_REQUIRED'),
    ('open-webui', 500, b'SECRET', 'AUTH_UNAVAILABLE'),
    ('open-webui', 200, b'{"id":"one","id":"two"}', 'AUTH_UNAVAILABLE'),
    ('learning-gateway', 401, b'{"error":{"code":"BROWSER_SESSION_EXPIRED","message":"SECRET"}}', 'SESSION_EXPIRED'),
    ('learning-gateway', 409, b'{"error":{"code":"LEARNER_CONTEXT_CHANGED","details":"SECRET"}}', 'CONTEXT_CHANGED'),
    ('learning-gateway', 504, b'{"error":{"code":"TEXTBOOK_RETRIEVAL_TIMEOUT"}}', 'RETRIEVAL_TIMEOUT'),
    ('learning-gateway', 500, b'{"error":{"code":"LEARNING_IDENTITY_MISMATCH"}}', 'SERVICE_UNAVAILABLE'),
    ('learning-gateway', 503, b'{"error":{"code":"SECRET"}}', 'SERVICE_UNAVAILABLE'),
    ('learning-gateway', 200, b'[]', 'REFERENCE_INVALID'),
    ('learning-gateway', 200, b'x' * 262145, 'REFERENCE_INVALID'),
])
def test_tool_transport_uses_closed_error_codes_and_validated_ids(monkeypatch, host, status, body, expected, caplog):
    class Response:
        def read(self, limit): return body
        def getheader(self, name): return 'SECRET\nCookie=synthetic-token'
    Response.status = status
    closed = []
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): closed.append(True)
    monkeypatch.setattr(module.http.client, 'HTTPConnection', Connection)
    with pytest.raises(module.StudyError) as error:
        module.Tools._fetch(host, 8080 if host == 'open-webui' else 8000,
                           '/api/v1/auths/' if host == 'open-webui' else '/learning/api/v1/textbooks', 'token=synthetic')
    data = json.loads(module.Tools._failure(error.value))
    assert data['error'] == expected and closed == [True]
    assert data['request_id'].startswith('ddtool_')
    assert_private_failure(data, caplog.text)


@pytest.mark.parametrize('host,search,exception,expected', [
    ('open-webui', False, TimeoutError, 'AUTH_TIMEOUT'),
    ('learning-gateway', False, TimeoutError, 'SERVICE_TIMEOUT'),
    ('learning-gateway', True, TimeoutError, 'RETRIEVAL_TIMEOUT'),
    ('learning-gateway', False, ConnectionError, 'SERVICE_UNAVAILABLE'),
])
def test_tool_transport_timeout_and_connection_loss_are_distinct(monkeypatch, host, search, exception, expected):
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): raise exception('SECRET')
        def close(self): pass
    monkeypatch.setattr(module.http.client, 'HTTPConnection', Connection)
    path = '/api/v1/auths/' if host == 'open-webui' else '/learning/api/v1/textbooks/search' if search else '/learning/api/v1/textbooks'
    with pytest.raises(module.StudyError) as error:
        module.Tools._fetch(host, 8080 if host == 'open-webui' else 8000, path, 'token=synthetic', payload={'query':'a'} if search else None)
    assert error.value.code == expected


def test_citation_callback_failure_is_sanitized(chat_tools, caplog):
    tool, user, request, *_ = chat_tools
    async def failed_emit(event): raise RuntimeError('SECRET answer_key=42')
    result = json.loads(asyncio.run(tool.get_math_concept_reference(concept_id='g7-subtract', chapter_id='2',
                         __user__=user, __request__=request, __event_emitter__=failed_emit)))
    assert result['error'] == 'CITATION_UNAVAILABLE'
    assert_private_failure(result, caplog.text)


def test_gateway_request_ids_ignore_even_well_formed_caller_ids(gateway_env, caplog):
    *_, client = gateway_env
    client.cookies.clear()
    incoming = 'ddreq_' + 'a' * 32
    results = [client.get('/learning/api/v1/auth/session', headers={'X-DD-Request-ID': incoming}) for _ in range(2)]
    ids = [gateway_error(r, 'WEBUI_LOGIN_REQUIRED', 401, 'sign_in', caplog)['request_id'] for r in results]
    assert len(set(ids)) == 2 and incoming not in ids and incoming not in caplog.text


@pytest.mark.parametrize('cookies,expected', [
    ('', 'LOGIN_REQUIRED'), ('token=synthetic', 'SESSION_INVALID'),
    ('token=one; token=two', 'REQUEST_REJECTED'),
])
def test_missing_learning_session_does_not_instruct_account_rebinding(cookies, expected):
    from fastapi import Request
    request = Request({'type': 'http', 'headers': [(b'cookie', cookies.encode())]})
    result = json.loads(asyncio.run(module.Tools().get_study_catalogue(__user__={'id':'synthetic-parent'}, __request__=request)))
    assert result['error'] == expected and '绑定' not in result['message']
