"""Synthetic HTTP/WebSocket client; only mounted into a new isolated probe container."""
from __future__ import annotations

import json
import os
import re
import signal
import sys
import threading
import time
from pathlib import Path

import requests
import socketio

STATE = Path('/state')
ORIGIN = 'https://172.19.116.53'
BASE = 'https://learning-proxy'
CA = '/run/isolated-ca.pem'


def write(name, data):
    path = STATE / name
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, sort_keys=True) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def read(name):
    return json.loads((STATE / name).read_text())


def session():
    s = requests.Session()
    s.trust_env = False
    s.verify = CA
    s.headers.update({'Origin': ORIGIN})
    if (STATE / 'cookies.private.json').exists():
        # requests appends .local to a single-label host for host-only cookies.
        # A domainless restored cookie would coexist with a refreshed token,
        # sending duplicate names and correctly tripping the gateway guard.
        for name, value in read('cookies.private.json').items():
            s.cookies.set(name, value, domain='learning-proxy.local', path='/', secure=True)
    return s


def persist(s):
    write('cookies.private.json', s.cookies.get_dict())


def request(s, method, path, **kwargs):
    return s.request(method, BASE + path, timeout=12, allow_redirects=False, **kwargs)


def login():
    credentials = json.loads(Path('/run/isolated-login.json').read_text())
    s = session()
    for attempt in range(90):
        try:
            r = request(s, 'POST', '/api/v1/auths/signin', json=credentials)
            assert r.status_code == 200 and r.json()['role'] == 'admin'
            break
        except (requests.RequestException, AssertionError):
            if attempt == 89:
                raise RuntimeError('isolated WebUI login unavailable') from None
            time.sleep(1)
    user = r.json()
    assert 'token' in s.cookies.get_dict()
    models = request(s, 'GET', '/api/models')
    assert models.status_code == 200 and models.json()['data'] == []
    write('subject.private.json', {'subject': user['id']})
    persist(s)
    return {'synthetic_login': True, 'model_count': 0}


def nonce():
    s = session()
    r = request(s, 'GET', '/learning/auth/login')
    assert r.status_code == 200
    csrf = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
    write('nonce.private.json', {'csrf': csrf})
    return {'nonce_issued': True}


def learning_login(stale=False):
    if not stale:
        nonce()
    s = session()
    r = request(s, 'POST', '/learning/auth/session', data=read('nonce.private.json'))
    if stale:
        assert r.status_code == 403 and r.json()['error']['code'] == 'LOGIN_CSRF_REJECTED'
        persist(s)
        return {'stale_nonce_rejected_after_gateway_restart': True}
    assert r.status_code == 303 and r.headers['Location'] == '/learning/ui'
    persist(s)
    r = request(s, 'GET', '/learning/api/v1/auth/session')
    assert r.status_code == 200 and r.json()['account_id'] == 'fault-account'
    return {'learning_session_created': True}


def check():
    s = session()
    output = {}
    for name, url in (('webui', BASE + '/api/v1/auths/'),
                      ('learning', BASE + '/learning/api/v1/auth/session'),
                      ('learning_health', 'http://learning-api:31010/health')):
        t = time.monotonic()
        try:
            r = s.get(url, timeout=12, allow_redirects=False)
        except requests.RequestException:
            output[name] = {'status': None, 'transport_error': True,
                            'seconds': round(time.monotonic() - t, 3)}
            continue
        row = {'status': r.status_code, 'seconds': round(time.monotonic() - t, 3)}
        try:
            data = r.json()
            if name == 'webui' and r.status_code == 200:
                row['same_subject'] = data.get('id') == read('subject.private.json')['subject']
            if name == 'learning' and r.status_code == 200:
                row['same_account'] = data.get('account_id') == 'fault-account'
            code = data.get('error', {}).get('code')
            if isinstance(code, str) and re.fullmatch('[A-Z_]{1,80}', code):
                row['error_code'] = code
        except ValueError:
            pass
        output[name] = row
    return output


def websocket():
    # The peer lives in another container so a server stop cannot kill the observer.
    s = session()
    client = socketio.Client(http_session=s, reconnection=False, logger=False,
                             engineio_logger=False,
                             websocket_extra_options={'origin': ORIGIN})
    disconnected = threading.Event()
    report = {'transport': 'websocket', 'connected': False, 'authenticated_join': False,
              'currently_connected': False, 'server_disconnect_observed': False,
              'self_timeout': False, 'elapsed_seconds': 0}
    started = time.monotonic()

    @client.event
    def disconnect(reason=None):
        report['server_disconnect_observed'] = not report['self_timeout']
        report['currently_connected'] = False
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        write('websocket-report.json', report)
        disconnected.set()

    token = s.cookies.get('token')
    assert token
    client.connect(BASE, auth={'token': token}, transports=['websocket'],
                   socketio_path='ws/socket.io', wait_timeout=20)
    # Native authenticated room join. No chat, model, tool, or student payload.
    result = client.call('user-join', {'auth': {'token': token}}, timeout=15)
    assert isinstance(result, dict) and result.get('id') == read('subject.private.json')['subject']
    report.update(connected=client.connected, currently_connected=client.connected, authenticated_join=True)
    write('websocket-report.json', report)
    deadline = time.monotonic() + 240
    while not disconnected.wait(1) and time.monotonic() < deadline:
        report['currently_connected'] = client.connected
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        write('websocket-report.json', report)
    if not disconnected.is_set():
        report['self_timeout'] = True
        client.disconnect()
        write('websocket-report.json', report)
    return report


def main():
    assert os.environ.get('DD_ISOLATED_FAULT_CLIENT') == '1'
    action = sys.argv[1]
    if action == 'resident':
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        while True:
            time.sleep(1)
    commands = {'login': login, 'nonce': nonce, 'learning-login': learning_login,
                'stale-nonce': lambda: learning_login(stale=True), 'check': check,
                'websocket': websocket}
    try:
        result = commands[action]()
    except Exception:
        # Never expose cookies, credentials, response bodies or request headers.
        print(json.dumps({'action': action, 'failed': True}), flush=True)
        raise SystemExit(1) from None
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
