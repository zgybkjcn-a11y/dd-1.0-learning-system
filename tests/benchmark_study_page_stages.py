"""Explicit B10 per-request page phase diagnosis on synthetic inputs only."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import sqlite3
import threading
import time
from types import SimpleNamespace

from benchmark_study_http import Trace
from benchmark_study_performance import synthetic_pdf_set
from benchmark_study_portals import database_digest
from learning_service import study_routes, textbooks, textbook_cache
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools
from test_runtime_passages import stack, runtime_bundle

SAMPLE = ContextVar('b10_diagnostic_sample', default=None)


class PageTrace(Trace):
    def record(self, kind, start, **fields):
        sample = SAMPLE.get()
        if sample is not None:
            self.rows.append(dict(sample=sample, kind=kind, start=start,
                                  seconds=time.perf_counter() - start, **fields))

    def wrap(self, patch, owner, name, kind):
        original = getattr(owner, name)

        @wraps(original)
        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                self.record(kind, start)
        patch.setattr(owner, name, timed)

    def __init__(self, patch, bridge):
        real_connect = sqlite3.connect
        super().__init__(patch)
        trace = self

        class Connection(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                # Fixed category labels only, never retain SQL or parameters.
                category = sql.split()[0].upper()
                if category == 'PRAGMA':
                    match = re.match(r'PRAGMA\s+(\w+)', sql, re.I)
                    category += ':' + (match.group(1).lower() if match else 'unknown')
                start = time.perf_counter()
                try:
                    return super().execute(sql, *args, **kwargs)
                finally:
                    trace.record('sqlite_execute', start, category=category)

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
        self.instrument_send(patch, bridge)
        for owner, name, kind in [
            (textbook_cache, 'fingerprint', 'source_fingerprint'),
            (textbook_cache, 'verified_pdf', 'verified_pdf'),
            (textbooks, 'render_page', 'render_page'),
            (textbooks, '_render_pdf', 'render_pdf'),
        ]:
            self.wrap(patch, owner, name, kind)
        patch.setattr(study_routes, 'render_textbook_page', textbooks.render_page)
        original_sha = textbook_cache.hashlib.sha256

        def timed_sha(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original_sha(*args, **kwargs)
            finally:
                self.record('pdf_sha256', start)
        patch.setattr(textbook_cache, 'hashlib', SimpleNamespace(sha256=timed_sha))
        real_os = textbook_cache.os

        class Reader:
            def __init__(self, wrapped): self.wrapped = wrapped
            def __enter__(self): self.wrapped.__enter__(); return self
            def __exit__(self, *args): return self.wrapped.__exit__(*args)
            def __getattr__(self, name): return getattr(self.wrapped, name)
            def read(self, *args, **kwargs):
                start = time.perf_counter()
                try:
                    return self.wrapped.read(*args, **kwargs)
                finally:
                    trace.record('pdf_file_read', start)

        class OSProxy:
            def __getattr__(self, name): return getattr(real_os, name)
            def fdopen(self, *args, **kwargs): return Reader(real_os.fdopen(*args, **kwargs))
        patch.setattr(textbook_cache, 'os', OSProxy())

        class Lock:
            def __init__(self, wrapped, kind): self.wrapped, self.kind = wrapped, kind
            def __enter__(self):
                start = time.perf_counter()
                self.wrapped.acquire()
                trace.record(self.kind, start)
                return self
            def __exit__(self, *args): self.wrapped.release()
        for name in ['PDF_LOCKS', 'PAGE_LOCKS']:
            patch.setattr(textbook_cache, name, tuple(Lock(lock, name.lower() + '_wait')
                                                      for lock in getattr(textbook_cache, name)))
        patch.setattr(textbooks, '_RENDER_LOCK', Lock(textbooks._RENDER_LOCK, 'native_lock_wait'))
        import fitz
        for owner, name, kind in [(fitz.Document, '__init__', 'pdf_open'),
                                  (fitz.Document, 'load_page', 'pdf_load_page'),
                                  (fitz.Page, 'get_pixmap', 'pdf_pixmap'),
                                  (fitz.Pixmap, 'tobytes', 'png_encode')]:
            self.wrap(patch, owner, name, kind)


def test_page_stages(stack, monkeypatch):
    plan_path = Path(os.environ['DD_B10_STAGE_PLAN']).resolve()
    output = Path(os.environ['DD_B10_STAGE_OUTPUT']).resolve()
    assert output.is_relative_to(plan_path.parent) and not output.exists()
    output.mkdir(parents=True)
    plan = json.loads(plan_path.read_text())
    pdf = stack['settings'].textbook_dir / 'math-g7-upper.pdf'
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == plan['material_sha256']
    assert stack['settings'].textbook_passages_sha256 == plan['manifest_sha256']
    assert pdf.stat().st_size == plan['material_bytes']
    assert not stack['settings'].model_external_calls_enabled
    assert not stack['settings'].tencent_ocr_external_calls_enabled
    before = database_digest(stack['db'])
    metadata = dict(plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python=platform.python_version(),cpu_affinity=sorted(os.sched_getaffinity(0)),
        material_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        manifest_sha256=stack['settings'].textbook_passages_sha256,database_before=before)
    (output/'run-before.json').write_text(json.dumps(metadata, indent=2)+'\n')
    trace = PageTrace(monkeypatch, stack['bridge'])

    def call():
        r = stack['gateway'].get('/learning/api/v1/textbooks/math-g7-upper/pages/31/image',
                                 headers=stack['headers'])
        assert r.status_code == 200, r.status_code
        assert r.content.startswith(b'\x89PNG')
        return hashlib.sha256(r.content).hexdigest()

    all_rows = []
    for config in plan['configurations']:
        concurrency, cache = config['concurrency'], config['cache']
        textbooks.clear_page_cache()
        trace.rows.clear()
        rows = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            if cache == 'warm': list(pool.map(lambda _: call(), range(concurrency)))
            for wave in range(plan['waves']):
                if cache == 'cold': textbooks.clear_page_cache()
                barrier = threading.Barrier(concurrency)

                def measured(index):
                    tag = f'{concurrency}-{cache}-{wave}-{index}'
                    token = SAMPLE.set(tag)
                    barrier.wait()
                    start = time.perf_counter()
                    row = dict(**config, wave=wave, index=index, sample=tag, start=start)
                    try:
                        row.update(ok=True, result_sha256=call())
                    except Exception as exc:
                        row.update(ok=False, error_type=type(exc).__name__)
                    finally:
                        row['seconds'] = time.perf_counter() - start
                        SAMPLE.reset(token)
                    return row
                batch = list(pool.map(measured, range(concurrency)))
                rows.extend(batch)
                with (output/'samples.jsonl').open('a') as f:
                    for row in batch: f.write(json.dumps(row)+'\n')
        (output/f'spans-{concurrency}-{cache}.json').write_text(json.dumps(trace.rows)+'\n')
        all_rows.extend(rows)
        v = sorted(r['seconds'] for r in rows)
        print(json.dumps(dict(**config,n=len(rows),p50=v[math.ceil(.5*len(v))-1],
            p95=v[math.ceil(.95*len(v))-1],errors=sum(not r['ok'] for r in rows))),flush=True)
    after = database_digest(stack['db'])
    (output/'database-after.json').write_text(json.dumps(dict(before=before,after=after,unchanged=before==after))+'\n')
    assert before == after
    assert len(all_rows) == plan['total_samples']
    assert all(r['ok'] for r in all_rows)
