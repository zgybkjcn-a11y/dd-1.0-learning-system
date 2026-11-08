"""Explicit B10 synthetic benchmark; not part of ordinary pytest collection.

DD_B10_OUTPUT must name a new directory under learning_data/verification.
Run with the locked A03 interpreter and pytest's network isolation.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import threading
import time

import pytest

import conftest
from learning_service import textbooks
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools, invoke
from test_runtime_passages import stack, runtime_bundle, search, QUERY


@pytest.fixture(scope='session')
def synthetic_pdf_set(tmp_path_factory):
    directory = conftest.synthetic_pdf_set.__wrapped__(tmp_path_factory)
    # Valid trailing PDF comments create a reproducible 8 MiB I/O workload.
    # Rebinding in textbook_sources and reference_textbooks happens afterwards.
    path = directory / 'math-g7-upper.pdf'
    raw = path.read_bytes()
    path.write_bytes(raw + b'\n%' + b'B10 synthetic padding ' * ((8*1024*1024-len(raw))//22) + b'\n')
    return directory


def test_measure_frozen_matrix(stack):
    output = Path(os.environ['DD_B10_OUTPUT']).absolute()
    allowed = Path.cwd() / 'learning_data/verification'
    assert output.is_relative_to(allowed) and not output.exists()
    output.mkdir(parents=True)
    pdf = stack['settings'].textbook_dir / 'math-g7-upper.pdf'
    plan = {
        'schema': 'dd-b10-synthetic-performance-v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(), 'platform': platform.platform(),
        'cpu_model': next(x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),
        'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'memory_total': next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')),
        'material_bytes': pdf.stat().st_size,
        'material_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
        'manifest_sha256': stack['settings'].textbook_passages_sha256,
        'materials': 'original synthetic PDF and 5 synthetic reviewed entries; no publisher or student data',
        'matrix': {'operation': ['gateway_page', 'gateway_search', 'tool_search'], 'concurrency': [1,4], 'cache': ['cold','warm']},
        'waves': 30, 'requests_per_configuration': '30 * concurrency',
        'cold': 'clear process application caches before each concurrent wave; OS filesystem cache uncontrolled',
        'warm': 'one excluded warmup wave; same book/page/query repeated with cache retained',
        'latency': 'monotonic from simultaneous worker release through complete response/Tool citations, includes queue and authorization',
        'percentiles': 'nearest rank ceil(p*n), all failed requests retained in denominator',
        'scope': 'ASGI synthetic transport; not network or production latency',
    }
    (output / 'plan-before.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n')
    # Keep fixture material and exact pins as reproducibility evidence.
    import shutil
    shutil.copyfile(pdf, output / 'synthetic.pdf')
    shutil.copytree(stack['directory'], output / 'synthetic-passages')
    records=[]

    def clear():
        reset = getattr(textbooks, 'clear_page_cache', None)
        if reset: reset()

    def call(operation):
        if operation == 'gateway_page':
            result=stack['gateway'].get('/learning/api/v1/textbooks/math-g7-upper/pages/31/image',headers=stack['headers'])
            assert result.status_code == 200 and result.content.startswith(b'\x89PNG'), result.status_code
            return hashlib.sha256(result.content).hexdigest()
        if operation == 'gateway_search':
            result=search(stack)
            assert result.status_code == 200, result.status_code
            data=result.json()['passage_result']
        else:
            data,events=invoke(stack['fixture'],'search_textbook',**QUERY)
            assert 'error' not in data and len(events)==1, data
        assert data['answer']['claims'], data
        return hashlib.sha256(json.dumps(data['answer'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    for operation in plan['matrix']['operation']:
        for concurrency in [1,4]:
            for cache in ['cold','warm']:
                clear()
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    if cache=='warm': list(pool.map(lambda _:call(operation),range(concurrency)))
                    for wave in range(30):
                        if cache=='cold': clear()
                        barrier=threading.Barrier(concurrency)
                        def measured(index):
                            barrier.wait(); started=time.perf_counter()
                            row={'operation':operation,'concurrency':concurrency,'cache':cache,'wave':wave,'index':index}
                            try: row.update(ok=True,result_sha256=call(operation))
                            except Exception as exc: row.update(ok=False,error_type=type(exc).__name__,error=str(exc)[:300])
                            row['seconds']=time.perf_counter()-started
                            return row
                        batch=list(pool.map(measured,range(concurrency)))
                        records.extend(batch)
                        with (output/'samples.jsonl').open('a') as f:
                            for row in batch:f.write(json.dumps(row,ensure_ascii=False)+'\n')
                rows=[r for r in records if (r['operation'],r['concurrency'],r['cache'])==(operation,concurrency,cache)]
                values=sorted(r['seconds'] for r in rows)
                print(json.dumps({'operation':operation,'concurrency':concurrency,'cache':cache,'n':len(rows),'p50':values[math.ceil(.5*len(values))-1],'p95':values[math.ceil(.95*len(values))-1],'failed':sum(not r['ok'] for r in rows)}),flush=True)
    assert all(r['ok'] for r in records)
    assert len(records)==900
