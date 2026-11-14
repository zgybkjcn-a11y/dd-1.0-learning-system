"""Explicit B10 CPU/wall and event-loop diagnosis, synthetic data only."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import selectors
import sys
import threading
import time

from benchmark_study_page_stages import PageTrace, SAMPLE
from benchmark_study_performance import synthetic_pdf_set
from benchmark_study_portals import database_digest
from learning_service import app as service, login_gateway, textbooks
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools
from test_runtime_passages import stack, runtime_bundle


def cpu_snapshot():
    usage = resource.getrusage(resource.RUSAGE_THREAD)
    return time.thread_time(), usage.ru_nvcsw, usage.ru_nivcsw


class CPUTrace(PageTrace):
    def record_cpu(self, kind, start, cpu, *, loop_id=None, **fields):
        stop = time.perf_counter()
        after = cpu_snapshot()
        row = dict(kind=kind, start=start, seconds=stop-start,
                   thread_cpu_seconds=after[0]-cpu[0], voluntary_switches=after[1]-cpu[1],
                   involuntary_switches=after[2]-cpu[2], native_thread=threading.get_native_id(), **fields)
        if loop_id is not None:
            if self.active:
                self.scheduler_rows.append(dict(row, loop_id=loop_id))
        elif SAMPLE.get() is not None:
            self.cpu_rows.append(dict(row, sample=SAMPLE.get()))

    def wrap(self, patch, owner, name, kind):
        original = getattr(owner, name)

        @wraps(original)
        def timed(*args, **kwargs):
            start = time.perf_counter(); cpu = cpu_snapshot()
            try:
                return original(*args, **kwargs)
            finally:
                self.record(kind, start)
                self.record_cpu(kind, start, cpu)
        patch.setattr(owner, name, timed)

    def __init__(self, patch, bridge):
        import fastapi.routing
        import fastapi.dependencies.utils
        owners = (service, login_gateway, fastapi.routing, fastapi.dependencies.utils)
        original_dispatch = {owner: owner.run_in_threadpool for owner in owners}
        self.cpu_rows, self.scheduler_rows, self.loop_bindings = [], [], []
        self.active = False
        self.loops, self.selector_ids = {}, {}
        self.loop_lock = threading.Lock()
        super().__init__(patch, bridge)
        for owner in owners:
            call = original_dispatch[owner]

            async def dispatch(fn, *args, _call=call, **kwargs):
                start = time.perf_counter()
                loop_id = self.identify(asyncio.get_running_loop())
                if self.active:
                    self.loop_bindings.append(dict(loop_id=loop_id, sample=SAMPLE.get(),
                                                   function=fn.__name__))

                @wraps(fn)
                def entered(*a, **kw):
                    self.record('worker_queue', start, function=fn.__name__)
                    began = time.perf_counter(); cpu = cpu_snapshot()
                    try:
                        return fn(*a, **kw)
                    finally:
                        self.record('worker_body', began, function=fn.__name__)
                        self.record_cpu('worker_body', began, cpu, function=fn.__name__)
                return await _call(entered, *args, **kwargs)
            patch.setattr(owner, 'run_in_threadpool', dispatch)

        original_cycle = asyncio.BaseEventLoop._run_once

        def cycle(loop):
            loop_id = self.identify(loop)
            start = time.perf_counter(); cpu = cpu_snapshot()
            try:
                return original_cycle(loop)
            finally:
                self.record_cpu('loop_cycle', start, cpu, loop_id=loop_id)
        patch.setattr(asyncio.BaseEventLoop, '_run_once', cycle)
        original_select = selectors.DefaultSelector.select

        def select(selector, timeout=None):
            start = time.perf_counter(); cpu = cpu_snapshot()
            try:
                return original_select(selector, timeout)
            finally:
                loop_id = self.selector_ids.get(selector)
                if loop_id is not None:
                    self.record_cpu('selector_wait', start, cpu, loop_id=loop_id)
        patch.setattr(selectors.DefaultSelector, 'select', select)

    def identify(self, loop):
        with self.loop_lock:
            if loop not in self.loops:
                self.loops[loop] = len(self.loops) + 1
                selector = getattr(loop, '_selector', None)
                if selector is not None: self.selector_ids[selector] = self.loops[loop]
            return self.loops[loop]


def test_thread_scheduling(stack, monkeypatch):
    plan_path = Path(os.environ['DD_B10_CPU_PLAN']).resolve()
    output = Path(os.environ['DD_B10_CPU_OUTPUT']).resolve()
    assert output.is_relative_to(plan_path.parent) and not output.exists()
    output.mkdir(parents=True)
    plan = json.loads(plan_path.read_text())
    pdf = stack['settings'].textbook_dir / 'math-g7-upper.pdf'
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == plan['material_sha256']
    assert stack['settings'].textbook_passages_sha256 == plan['manifest_sha256']
    assert not stack['settings'].model_external_calls_enabled
    assert not stack['settings'].tencent_ocr_external_calls_enabled
    before = database_digest(stack['db'])
    metadata = dict(plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python=platform.python_version(),cpu_affinity=sorted(os.sched_getaffinity(0)),
        material_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        manifest_sha256=stack['settings'].textbook_passages_sha256,
        switch_interval_seconds=sys.getswitchinterval(),database_before=before,
        clock_thread=time.get_clock_info('thread_time').implementation,
        clock_wall=time.get_clock_info('perf_counter').implementation)
    (output/'run-before.json').write_text(json.dumps(metadata,indent=2)+'\n')
    trace = CPUTrace(monkeypatch, stack['bridge'])

    def call():
        r=stack['gateway'].get('/learning/api/v1/textbooks/math-g7-upper/pages/31/image',headers=stack['headers'])
        assert r.status_code==200 and r.content.startswith(b'\x89PNG'),r.status_code
        return hashlib.sha256(r.content).hexdigest()

    records=[]
    for config in plan['configurations']:
        concurrency,cache=config['concurrency'],config['cache']
        textbooks.clear_page_cache()
        for collection in (trace.rows,trace.cpu_rows,trace.scheduler_rows,trace.loop_bindings):collection.clear()
        rows=[];waves=[]
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            if cache=='warm':list(pool.map(lambda _:call(),range(concurrency)))
            trace.active=True
            for wave in range(plan['waves']):
                if cache=='cold':textbooks.clear_page_cache()
                barrier=threading.Barrier(concurrency)

                def measured(index):
                    token=SAMPLE.set(f'{concurrency}-{cache}-{wave}-{index}')
                    barrier.wait();start=time.perf_counter();cpu=time.thread_time()
                    row=dict(**config,wave=wave,index=index,sample=SAMPLE.get(),start=start)
                    try:row.update(ok=True,result_sha256=call())
                    except Exception as exc:row.update(ok=False,error_type=type(exc).__name__)
                    finally:
                        row.update(seconds=time.perf_counter()-start,driver_thread_cpu_seconds=time.thread_time()-cpu)
                        SAMPLE.reset(token)
                    return row
                started=time.perf_counter();process_started=time.process_time();usage=resource.getrusage(resource.RUSAGE_SELF)
                batch=list(pool.map(measured,range(concurrency)))
                ended=resource.getrusage(resource.RUSAGE_SELF)
                waves.append(dict(wave=wave,seconds=time.perf_counter()-started,process_cpu_seconds=time.process_time()-process_started,
                    voluntary_switches=ended.ru_nvcsw-usage.ru_nvcsw,involuntary_switches=ended.ru_nivcsw-usage.ru_nivcsw))
                rows.extend(batch)
                with (output/'samples.jsonl').open('a') as f:
                    for row in batch:f.write(json.dumps(row)+'\n')
            trace.active=False
        payload=dict(phase_spans=trace.rows,cpu_spans=trace.cpu_rows,scheduler_spans=trace.scheduler_rows,
                     loop_bindings=trace.loop_bindings,waves=waves)
        (output/f'threads-{concurrency}-{cache}.json').write_text(json.dumps(payload)+'\n')
        records.extend(rows);v=sorted(r['seconds'] for r in rows)
        print(json.dumps(dict(**config,n=len(rows),p50=v[math.ceil(.5*len(v))-1],p95=v[math.ceil(.95*len(v))-1],
            errors=sum(not r['ok'] for r in rows),wave_cpu_wall_ratio=sum(w['process_cpu_seconds'] for w in waves)/sum(w['seconds'] for w in waves))),flush=True)
    after=database_digest(stack['db'])
    (output/'database-after.json').write_text(json.dumps(dict(before=before,after=after,unchanged=before==after))+'\n')
    assert before==after
    assert len(records)==plan['total_samples'] and all(r['ok'] for r in records)
    assert sys.getswitchinterval()==metadata['switch_interval_seconds']
