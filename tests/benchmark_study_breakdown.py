"""B10 diagnostic follow-up for unresolved P95; explicit invocation only."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import threading
import time

from benchmark_study_performance import synthetic_pdf_set
from learning_service import textbooks, textbook_cache
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools
from test_runtime_passages import stack, runtime_bundle, search


def test_warm_gateway_phase_breakdown(stack,monkeypatch):
    output=Path(os.environ['DD_B10_OUTPUT']).absolute()
    assert output.is_relative_to(Path.cwd()/'learning_data/verification') and not output.exists()
    output.mkdir(parents=True)
    rows=[];local=threading.local()
    original=stack['bridge'].send
    def traced(upstream,method,path,*a,**kw):
        start=time.perf_counter()
        try:return original(upstream,method,path,*a,**kw)
        finally:rows.append({'phase':path,'seconds':time.perf_counter()-start})
    monkeypatch.setattr(stack['bridge'],'send',traced)
    for owner,name in [(textbooks,'render_page'),(textbook_cache,'verified_pdf')]:
        original_call=getattr(owner,name)
        def wrap(*a,_fn=original_call,_name=name,**kw):
            start=time.perf_counter()
            try:return _fn(*a,**kw)
            finally:rows.append({'phase':_name,'seconds':time.perf_counter()-start})
        monkeypatch.setattr(owner,name,wrap)
    # The router imported the function alias before instrumentation.
    from learning_service import study_routes
    monkeypatch.setattr(study_routes,'render_textbook_page',textbooks.render_page)
    for op in ['page','search']:
        def call():
            response=(stack['gateway'].get('/learning/api/v1/textbooks/math-g7-upper/pages/31/image',headers=stack['headers']) if op=='page' else search(stack))
            assert response.status_code==200
        for concurrency in [1,4]:
            call();rows.clear();latencies=[]
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                for _ in range(30):
                    barrier=threading.Barrier(concurrency)
                    def run(index):
                        barrier.wait();start=time.perf_counter();call();return time.perf_counter()-start
                    latencies.extend(pool.map(run,range(concurrency)))
            (output/f'{op}-{concurrency}.json').write_text(json.dumps({'operation':op,'concurrency':concurrency,'waves':30,'cache':'warm','latencies':latencies,'phases':rows},indent=2)+'\n')
