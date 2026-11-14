"""Explicit B10 portal attribution; does not change the acceptance benchmark.

Use the frozen 97-file runtime, DD_B10_PORTAL_MODE=per_request|persistent and
the DD_B10_HTTP_* variables understood by benchmark_study_http.
"""
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import anyio.from_thread

from benchmark_study_http import test_http_diagnostic as measure
from benchmark_study_performance import synthetic_pdf_set
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools
from test_runtime_passages import stack, runtime_bundle


def database_digest(db):
    with db.session() as connection:
        return hashlib.sha256('\n'.join(connection.iterdump()).encode()).hexdigest()


def test_portal_lifecycle(stack, monkeypatch):
    mode = os.environ['DD_B10_PORTAL_MODE']
    assert mode in {'per_request', 'persistent'}
    assert os.environ['DD_B10_HTTP_MODE'] == 'testclient'
    output = Path(os.environ['DD_B10_HTTP_OUTPUT']).resolve()
    assert not output.exists()
    plan_path = Path(os.environ['DD_B10_HTTP_PLAN']).resolve()
    plan = json.loads(plan_path.read_text())
    assert mode in plan['order']
    assert not stack['api'].app.router.on_startup
    assert not stack['api'].app.router.on_shutdown
    assert not stack['gateway'].app.router.on_startup
    assert not stack['gateway'].app.router.on_shutdown
    original = anyio.from_thread.start_blocking_portal
    events = []

    @contextmanager
    def timed_portal(*args, **kwargs):
        start = time.perf_counter()
        closing = None
        try:
            with original(*args, **kwargs) as portal:
                events.append({'kind': 'start', 'seconds': time.perf_counter() - start})
                try:
                    yield portal
                finally:
                    closing = time.perf_counter()
        finally:
            if closing is not None:
                events.append({'kind': 'close', 'seconds': time.perf_counter() - closing})

    monkeypatch.setattr(anyio.from_thread, 'start_blocking_portal', timed_portal)
    before = database_digest(stack['db'])
    snapshot = {'created_at': datetime.now(timezone.utc).isoformat(), 'mode': mode,
                'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'database_before': before, 'events_include_excluded_warmup': True}
    try:
        with (stack['api'] if mode == 'persistent' else nullcontext()):
            with (stack['gateway'] if mode == 'persistent' else nullcontext()):
                measure(stack, monkeypatch)
    finally:
        after = database_digest(stack['db'])
        snapshot.update(database_after=after, database_unchanged=before == after,
                        events=events, started=sum(e['kind'] == 'start' for e in events),
                        closed=sum(e['kind'] == 'close' for e in events))
        # A fixture failure may precede output creation; preserve it separately.
        destination = output / 'portal-lifecycle.json' if output.exists() else output.with_suffix('.failure.json')
        destination.write_text(json.dumps(snapshot, indent=2)+'\n')
    assert before == after
    expected = 2 if mode == 'persistent' else 4 * (plan['samples_per_run'] + sum(plan['matrix']['concurrency']))
    assert snapshot['started'] == snapshot['closed'] == expected
