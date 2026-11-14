"""Explicit B10 loopback/TestClient diagnosis; never an acceptance baseline.

Run only in a frozen candidate checkout with DD_B10_HTTP_PLAN, OUTPUT and MODE.
Uses synthetic fixtures and the root conftest loopback-only network guard.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from functools import wraps
import hashlib
import http.client
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import socket
import sqlite3
import threading
import time

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from benchmark_study_performance import synthetic_pdf_set
from learning_service import app as service, login_gateway, textbooks
from learning_service.db import Database
from learning_service.gateway_http import GatewayHTTP
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools, invoke, module
from test_runtime_passages import stack, runtime_bundle, search, QUERY


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Trace:
    """In-memory spans only; never SQL parameters, cookies or response bodies."""
    def __init__(self, patch):
        self.rows = []
        trace = self
        real_connect = sqlite3.connect

        class Connection(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                start = time.perf_counter()
                try:
                    return super().execute(sql, *args, **kwargs)
                finally:
                    trace.record('sqlite_execute', start, category=sql.split()[0].upper())

            def close(self):
                start = time.perf_counter()
                try:
                    return super().close()
                finally:
                    trace.record('sqlite_close', start)

        def connect(*args, **kwargs):
            start = time.perf_counter()
            try:
                return real_connect(*args, **kwargs, factory=Connection)
            finally:
                self.record('sqlite_open', start)
        patch.setattr(sqlite3, 'connect', connect)
        original = Database.connect

        def db_connect(db):
            start = time.perf_counter()
            try:
                return original(db)
            finally:
                self.record('db_connect', start)
        patch.setattr(Database, 'connect', db_connect)

        import fastapi.routing
        import fastapi.dependencies.utils
        for owner in (service, login_gateway, fastapi.routing, fastapi.dependencies.utils):
            call = owner.run_in_threadpool

            async def timed(fn, *args, _call=call, **kwargs):
                start = time.perf_counter()

                @wraps(fn)
                def entered(*a, **kw):
                    self.record('worker_queue', start, function=fn.__name__)
                    began = time.perf_counter()
                    try:
                        return fn(*a, **kw)
                    finally:
                        self.record('worker_body', began, function=fn.__name__)
                return await _call(entered, *args, **kwargs)
            patch.setattr(owner, 'run_in_threadpool', timed)

    def record(self, kind, start, **fields):
        self.rows.append({'kind': kind, 'seconds': time.perf_counter() - start, **fields})

    def instrument_send(self, patch, transport):
        original = transport.send

        def send(upstream, method, path, *args, **kwargs):
            start = time.perf_counter()
            try:
                return original(upstream, method, path, *args, **kwargs)
            finally:
                self.record('gateway_hop', start, path=path.split('?')[0])
        patch.setattr(transport, 'send', send)


def child_server(role, app, listener, channel, transport):
    # fork inherits pytest's socket guard and isolated, synthetic settings.
    import uvicorn
    with pytest.MonkeyPatch.context() as patch:
        trace = Trace(patch)
        if transport is not None:
            trace.instrument_send(patch, transport)
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=0,
            loop='asyncio', http='h11', lifespan='on', access_log=False, log_level='error'))

        def control():
            while not server.started:
                time.sleep(.01)
            channel.send({'ready': role, 'pid': os.getpid()})
            while True:
                command = channel.recv()
                if command == 'clear_cache':
                    textbooks.clear_page_cache()
                    channel.send(True)
                elif command == 'clear_trace':
                    trace.rows.clear()
                    channel.send(True)
                elif command == 'spans':
                    channel.send(trace.rows)
                elif command == 'stop':
                    server.should_exit = True
                    return
                else:
                    raise AssertionError(command)
        threading.Thread(target=control, daemon=True).start()
        try:
            server.run(sockets=[listener])
        finally:
            channel.close()


class Peer:
    def __init__(self, role, app, transport=None):
        ctx = multiprocessing.get_context('fork')
        self.channel, child = ctx.Pipe()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('127.0.0.1', 0))
        self.port = listener.getsockname()[1]
        listener.listen(128)
        self.process = ctx.Process(target=child_server, args=(role, app, listener, child, transport))
        self.process.start()
        child.close()
        listener.close()
        try:
            assert self.channel.poll(20), f'{role} startup timed out'
            self.ready = self.channel.recv()
        except BaseException:
            self.close()
            raise

    def command(self, name):
        self.channel.send(name)
        assert self.channel.poll(20), f'control timed out: {name}'
        return self.channel.recv()

    def close(self):
        if self.process.is_alive():
            self.channel.send('stop')
            self.process.join(5)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(5)
        self.channel.close()


def test_http_diagnostic(stack, monkeypatch):
    mode = os.environ['DD_B10_HTTP_MODE']
    assert mode in {'testclient', 'loopback'}
    output = Path(os.environ['DD_B10_HTTP_OUTPUT']).resolve()
    plan_path = Path(os.environ['DD_B10_HTTP_PLAN']).resolve()
    plan = json.loads(plan_path.read_text())
    assert output.is_relative_to(plan_path.parent) and not output.exists()
    output.mkdir(parents=True)
    pdf = stack['settings'].textbook_dir / 'math-g7-upper.pdf'
    assert digest(pdf.read_bytes()) == plan['material_sha256']
    assert pdf.stat().st_size == plan['material_bytes']
    assert stack['settings'].textbook_passages_sha256 == plan['manifest_sha256']
    assert not stack['settings'].model_external_calls_enabled
    assert not stack['settings'].tencent_ocr_external_calls_enabled
    metadata = {'started_at': datetime.now(timezone.utc).isoformat(), 'mode': mode,
        'plan_sha256': digest(plan_path.read_bytes()), 'harness_sha256': digest(Path(__file__).read_bytes()),
        'material_sha256': digest(pdf.read_bytes()), 'manifest_sha256': stack['settings'].textbook_passages_sha256,
        'python': platform.python_version(), 'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'pid': os.getpid(), 'peers': {}, 'synthetic_only': True}
    (output/'run-before.json').write_text(json.dumps(metadata, indent=2)+'\n')
    with ExitStack() as cleanup:
        peers = {}
        if mode == 'loopback':
            # No network calls to the origin string: it is retained only for
            # Origin/CSRF validation and output equivalence with the baseline.
            identity = FastAPI()

            @identity.get('/api/v1/auths/')
            def who(request: Request):
                if request.headers.get('cookie') != 'token=synthetic-token-a':
                    return JSONResponse({'error': 'synthetic login required'}, status_code=401)
                return {'id': 'synthetic-parent', 'role': 'user'}

            for role, app in [('identity', identity), ('service', stack['api'].app)]:
                peers[role] = Peer(role, app)
                cleanup.callback(peers[role].close)
            settings = login_gateway.GatewaySettings(enabled=True, public_origin=stack['settings'].browser_origin,
                openwebui_url=f'http://127.0.0.1:{peers["identity"].port}',
                learning_url=f'http://127.0.0.1:{peers["service"].port}',
                assertion_secret=stack['settings'].browser_auth_secret, assertion_issuer='synthetic-gateway',
                identity_issuer='family-pilot-webui')
            transport = GatewayHTTP()
            peers['gateway'] = Peer('gateway', login_gateway.create_gateway(settings, transport), transport)
            cleanup.callback(peers['gateway'].close)
            metadata['peers'] = {k: {'host': '127.0.0.1', 'port': v.port, **v.ready} for k, v in peers.items()}
            (output/'run-before.json').write_text(json.dumps(metadata, indent=2)+'\n')
            # Restore the unmodified Tool fetch, redirect only socket endpoints
            # after its fixed-peer/path checks; no DNS/proxy/provider access.
            monkeypatch.delattr(stack['tool'], '_fetch')
            real_connection = http.client.HTTPConnection

            def local_connection(host, port=None, *args, **kwargs):
                mapping = {('open-webui', 8080): peers['identity'].port,
                           ('learning-gateway', 8000): peers['gateway'].port}
                if (host, port) in mapping:
                    host, port = '127.0.0.1', mapping[(host, port)]
                assert host == '127.0.0.1'
                return real_connection(host, port, *args, **kwargs)
            monkeypatch.setattr(http.client, 'HTTPConnection', local_connection)

        trace = Trace(monkeypatch)
        if mode == 'testclient':
            trace.instrument_send(monkeypatch, stack['bridge'])
        cookie = stack['fixture'][2].headers['cookie']

        def http_request(path, payload=None):
            connection = http.client.HTTPConnection('127.0.0.1', peers['gateway'].port, timeout=12)
            headers = {**stack['headers'], 'Cookie': cookie, 'Accept': 'application/json'}
            body = None
            if payload is not None:
                headers['Content-Type'] = 'application/json'
                body = json.dumps(payload).encode()
            try:
                connection.request('GET' if payload is None else 'POST', path, body=body, headers=headers)
                result = connection.getresponse()
                raw = result.read()
                assert result.status == 200, result.status
                return raw
            finally:
                connection.close()

        def call(operation):
            if operation == 'gateway_page':
                path = '/learning/api/v1/textbooks/math-g7-upper/pages/31/image'
                if mode == 'loopback':
                    raw = http_request(path)
                else:
                    result = stack['gateway'].get(path, headers=stack['headers'])
                    assert result.status_code == 200, result.status_code
                    raw = result.content
                assert raw.startswith(b'\x89PNG')
                return digest(raw)
            if operation == 'gateway_search':
                if mode == 'loopback':
                    data = json.loads(http_request('/learning/api/v1/textbooks/search', QUERY))['passage_result']
                else:
                    result = search(stack)
                    assert result.status_code == 200, result.status_code
                    data = result.json()['passage_result']
            else:
                data, events = invoke(stack['fixture'], 'search_textbook', **QUERY)
                assert 'error' not in data and len(events) == 1, data.get('error')
            assert data['answer']['claims']
            return digest(json.dumps(data['answer'], sort_keys=True, ensure_ascii=False).encode())

        def clear_cache():
            if mode == 'loopback':
                peers['service'].command('clear_cache')
            else:
                textbooks.clear_page_cache()

        def clear_trace():
            trace.rows.clear()
            for peer in peers.values():
                peer.command('clear_trace')

        records = []
        for operation in plan['matrix']['operation']:
            for concurrency in plan['matrix']['concurrency']:
                for cache in plan['matrix']['cache']:
                    clear_cache()
                    with ThreadPoolExecutor(max_workers=concurrency) as pool:
                        if cache == 'warm':
                            list(pool.map(lambda _: call(operation), range(concurrency)))
                        clear_trace()
                        rows = []
                        for wave in range(plan['waves']):
                            if cache == 'cold':
                                clear_cache()
                            barrier = threading.Barrier(concurrency)

                            def measured(index):
                                barrier.wait()
                                start = time.perf_counter()
                                row = dict(operation=operation, concurrency=concurrency, cache=cache, wave=wave, index=index)
                                try:
                                    row.update(ok=True, result_sha256=call(operation))
                                except Exception as exc:
                                    row.update(ok=False, error_type=type(exc).__name__, error=str(exc)[:200])
                                row['seconds'] = time.perf_counter() - start
                                return row
                            batch = list(pool.map(measured, range(concurrency)))
                            rows.extend(batch)
                            with (output/'samples.jsonl').open('a') as f:
                                for row in batch:
                                    f.write(json.dumps(row)+'\n')
                        records.extend(rows)
                    spans = {'client': trace.rows}
                    spans.update({role: peer.command('spans') for role, peer in peers.items()})
                    (output/f'spans-{operation}-{concurrency}-{cache}.json').write_text(json.dumps(spans)+'\n')
                    values = sorted(r['seconds'] for r in rows)
                    print(json.dumps(dict(operation=operation, concurrency=concurrency, cache=cache, n=len(rows),
                        p50=values[math.ceil(.5*len(values))-1], p95=values[math.ceil(.95*len(values))-1],
                        failed=sum(not r['ok'] for r in rows))), flush=True)
        with stack['db'].session() as connection:
            assert connection.execute('SELECT count(*) FROM provider_calls').fetchone()[0] == 0
        assert len(records) == plan['samples_per_run']
        assert all(row['ok'] for row in records)
