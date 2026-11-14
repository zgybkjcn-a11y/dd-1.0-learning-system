"""B10 follow-up: database/worker timing on synthetic read paths only."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

from benchmark_study_performance import synthetic_pdf_set
from learning_service import app as service, login_gateway
from learning_service.db import Database
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools
from test_runtime_passages import stack, runtime_bundle, search


def test_read_path_timing(stack, monkeypatch):
    output = Path(os.environ['DD_B10_OUTPUT']).absolute()
    assert output.is_relative_to(Path.cwd() / 'learning_data/verification') and not output.exists()
    output.mkdir(parents=True)
    config = {'created_at': datetime.now(timezone.utc).isoformat(),
              'operations': ['session', 'page', 'search'], 'concurrency': [1, 4], 'waves': 30,
              'cache': 'warm', 'samples': 450, 'material': 'same B10 synthetic 8MiB PDF/5 entries',
              'timing': 'nested spans, no SQL parameters or cookies; do not add overlapping durations',
              'purpose': 'diagnostic only; existing acceptance matrix and thresholds unchanged'}
    (output/'plan-before.json').write_text(json.dumps(config, indent=2)+'\n')
    spans=[]
    def record(kind, start, **fields):
        spans.append({'kind': kind, 'seconds': time.perf_counter()-start, **fields})
    real_connect=sqlite3.connect
    class TimedConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            started=time.perf_counter()
            try: return super().execute(sql, *args, **kwargs)
            finally:
                category = (sql if sql.startswith('PRAGMA ') else sql.split()[0]).split('=')[0].strip()
                record('sqlite_execute',started,category=category)
        def close(self):
            started=time.perf_counter()
            try: return super().close()
            finally:record('sqlite_close',started)
    def connect(*args, **kwargs):
        started=time.perf_counter()
        try: return real_connect(*args, **kwargs, factory=TimedConnection)
        finally:record('sqlite_open',started)
    monkeypatch.setattr(sqlite3,'connect',connect)
    original=Database.connect
    def db_connect(self):
        started=time.perf_counter()
        try:return original(self)
        finally:record('db_connect',started)
    monkeypatch.setattr(Database,'connect',db_connect)
    # Patch the real dispatch entry points, preserving their cancellation policy.
    import fastapi.routing
    import fastapi.dependencies.utils
    for module in [service,login_gateway,fastapi.routing,fastapi.dependencies.utils]:
        call=module.run_in_threadpool
        async def timed(fn,*args,_call=call,**kwargs):
            start=time.perf_counter()
            @wraps(fn)
            def entered(*a,**kw):
                record('worker_queue',start,function=fn.__name__)
                began=time.perf_counter()
                try:return fn(*a,**kw)
                finally:record('worker_body',began,function=fn.__name__)
            return await _call(entered,*args,**kwargs)
        monkeypatch.setattr(module,'run_in_threadpool',timed)
    original_send=stack['bridge'].send
    def send(upstream,method,path,*args,**kwargs):
        started=time.perf_counter()
        try:return original_send(upstream,method,path,*args,**kwargs)
        finally:record('gateway_hop',started,path=path)
    monkeypatch.setattr(stack['bridge'],'send',send)
    for operation in config['operations']:
        def call():
            if operation=='session':r=stack['gateway'].get('/learning/api/v1/auth/session')
            elif operation=='page':r=stack['gateway'].get('/learning/api/v1/textbooks/math-g7-upper/pages/31/image',headers=stack['headers'])
            else:r=search(stack)
            assert r.status_code==200,r.status_code
        for concurrency in config['concurrency']:
            call();spans.clear();samples=[]
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                for wave in range(config['waves']):
                    barrier=threading.Barrier(concurrency)
                    def measured(index):
                        barrier.wait();started=time.perf_counter()
                        row={'wave':wave,'index':index}
                        try:call();row['ok']=True
                        except Exception as exc:row.update(ok=False,error=type(exc).__name__)
                        row['seconds']=time.perf_counter()-started
                        return row
                    samples.extend(pool.map(measured,range(concurrency)))
            (output/f'{operation}-{concurrency}.json').write_text(json.dumps({'operation':operation,'concurrency':concurrency,'samples':samples,'spans':spans},indent=2)+'\n')
            assert len(samples)==30*concurrency and all(s['ok'] for s in samples)
