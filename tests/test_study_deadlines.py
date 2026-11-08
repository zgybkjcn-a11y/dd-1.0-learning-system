"""Total budgets, cooperative cancellation and trickling sockets; loopback only."""
import asyncio
from dataclasses import replace
import http.client
import http.server
import json
from pathlib import Path
import threading
import time

import httpx
import pytest

from learning_service import study_deadline as budget
from learning_service.gateway_http import GatewayHTTP, GatewayResult
from learning_service.login_gateway import create_gateway
from test_login_gateway import gateway_env, gateway_login
from test_readonly_study_tools import chat_tools, module, invoke
from test_family_math import family
from test_math_references import reference_family
from test_browser_auth import auth_env
from test_learning_service import env


def test_standalone_helper_matches_service_exactly():
    source=Path('deploy/open-webui-reuse/readonly_study_tools.py').read_text()
    embedded=source.split('# BEGIN embedded study_deadline.py\n')[1].split('# END embedded study_deadline.py')[0]
    assert embedded==Path('learning_service/study_deadline.py').read_text()
    assert budget.STUDY_TOTAL_SECONDS==module.STUDY_TOTAL_SECONDS==12


@pytest.mark.parametrize('value,expected',[(None,12),('999999',12),('0',0),('125',.125)])
def test_budget_is_bounded(value,expected):assert budget.budget_seconds(value)==expected


@pytest.mark.parametrize('value',['-1','NaN','1.0','inf',' 12','9999999'])
def test_invalid_budget_rejected(value):
    with pytest.raises(ValueError):budget.budget_seconds(value)


def test_gateway_uses_one_budget_across_identity_session_and_read(gateway_env,monkeypatch):
    settings,db,config,bridge,client=gateway_env
    assert gateway_login(settings,client)[0].status_code==303
    original=bridge.send;seen=[]
    def slow(*args,**kwargs):
        seen.append((args[2],kwargs['timeout'],args[3].get(budget.STUDY_BUDGET_HEADER)))
        time.sleep(.045)
        return original(*args,**kwargs)
    monkeypatch.setattr(bridge,'send',slow)
    start=time.monotonic()
    result=client.get('/learning/api/v1/textbooks',headers={budget.STUDY_BUDGET_HEADER:'75'})
    assert result.status_code==504 and result.json()['error']['retryable']
    assert time.monotonic()-start < .225
    time.sleep(.06)
    assert len(seen)==2 and all(p!='/api/v1/textbooks' for p,_,_ in seen)
    assert seen[0][2] is None and 0<float(seen[1][2])<75
    assert seen[1][1]<seen[0][1]


@pytest.mark.parametrize('headers',[
    {budget.STUDY_BUDGET_HEADER:'0'},
    {budget.STUDY_BUDGET_HEADER:'invalid'},
    [(budget.STUDY_BUDGET_HEADER,'20'),(budget.STUDY_BUDGET_HEADER,'40')],
])
def test_gateway_rejects_expired_or_malformed_before_upstream(gateway_env,headers):
    _,_,_,bridge,client=gateway_env;bridge.calls.clear()
    result=client.get('/learning/api/v1/textbooks',headers=headers)
    assert result.status_code in {400,504} and not bridge.calls


def test_tool_total_budget_stops_followups_and_emits_no_late_citation(chat_tools,monkeypatch):
    tool,user,request,calls,*_=chat_tools;events=[]
    real_deadline=module.StudyDeadline
    monkeypatch.setattr(module,'StudyDeadline',lambda:real_deadline(.075))
    original=tool._fetch
    def slow(*args,**kw):time.sleep(.045);return original(*args,**kw)
    monkeypatch.setattr(tool,'_fetch',slow)
    async def scenario():
        async def emit(event):events.append(event)
        started=time.monotonic()
        result=json.loads(await tool.search_textbook(query='有理数减法',book_id='math-g7-upper',chapter_id='2',__user__=user,__request__=request,__event_emitter__=emit))
        elapsed=time.monotonic()-started
        await asyncio.sleep(.15)
        return result,elapsed
    result,elapsed=asyncio.run(scenario())
    assert result['error']=='RETRIEVAL_TIMEOUT' and elapsed<.225
    assert len(calls)<=2 and not events


def test_tool_cancel_stops_next_fetch_and_has_no_citation(chat_tools,monkeypatch):
    tool,user,request,calls,*_=chat_tools;entered=threading.Event();events=[]
    original=tool._fetch
    def slow(*args,**kw):entered.set();time.sleep(.1);return original(*args,**kw)
    monkeypatch.setattr(tool,'_fetch',slow)
    async def scenario():
        async def emit(e):events.append(e)
        task=asyncio.create_task(tool.search_textbook(query='有理数减法',book_id='math-g7-upper',__user__=user,__request__=request,__event_emitter__=emit))
        while not entered.is_set():await asyncio.sleep(.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        await asyncio.sleep(.15)
    asyncio.run(scenario())
    assert len(calls)==1 and not events


@pytest.mark.parametrize('component',['gateway','tool'])
@pytest.mark.parametrize('part',['headers','body'])
def test_trickling_http_has_total_deadline(component,part,monkeypatch):
    paths=[]
    class Slow(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            try:
                raw=b'HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\n'
                if part=='body':self.wfile.write(raw);raw=b'{"items":[]}'
                for char in raw:
                    self.wfile.write(bytes([char]));self.wfile.flush();time.sleep(.02)
            except (BrokenPipeError,ConnectionResetError):pass
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Slow)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    operation=budget.StudyDeadline(.075) if component=='gateway' else module.StudyDeadline(.075)
    context=budget.CURRENT_DEADLINE if component=='gateway' else module.CURRENT_DEADLINE
    token=context.set(operation)
    real_connection=http.client.HTTPConnection
    if component=='tool':
        monkeypatch.setattr(module.http.client,'HTTPConnection',lambda host,port,timeout:real_connection('127.0.0.1',server.server_port,timeout=timeout))
    try:
        start=time.monotonic()
        if component=='gateway':
            with pytest.raises(TimeoutError):GatewayHTTP().send(f'http://127.0.0.1:{server.server_port}','GET','/',{})
        else:
            with pytest.raises(module.StudyError) as error:module.Tools._fetch('learning-gateway',8000,'/learning/api/v1/textbooks','token=synthetic')
            assert error.value.code=='SERVICE_TIMEOUT'
        assert time.monotonic()-start<.225 and len(paths)==1
    finally:
        context.reset(token);operation.cancel();server.shutdown();server.server_close();thread.join()


def test_service_deadline_includes_sync_worker_and_discards_late_read(family,monkeypatch):
    from learning_service import study_routes
    _,_,client,headers=family
    def slow(*args):time.sleep(.12);return []
    monkeypatch.setattr(study_routes,'textbook_catalogue',slow)
    async def scenario():
        sent=[];start=time.monotonic();body_sent=False
        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent=True
                return {'type':'http.request','body':b'','more_body':False}
            await asyncio.Event().wait()
        async def send(message):sent.append((time.monotonic()-start,message))
        scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'GET','scheme':'https',
            'path':'/api/v1/textbooks','raw_path':b'/api/v1/textbooks','query_string':b'',
            'headers':[(k.lower().encode(),v.encode()) for k,v in {**headers,'X-Learner-Id':'family-g7',budget.STUDY_BUDGET_HEADER:'35'}.items()],
            'client':('127.0.0.1',1),'server':('testserver',443)}
        await client.app(scope,receive,send)
        assert next(m['status'] for _,m in sent if m['type']=='http.response.start')==504
        body=[(t,m) for t,m in sent if m['type']=='http.response.body']
        assert body[-1][0]<.185 and b'items' not in b''.join(m['body'] for _,m in body)
    asyncio.run(scenario())


def test_browser_disconnect_cancels_gateway_before_followup(gateway_env,monkeypatch):
    settings,_,_,bridge,client=gateway_env
    assert gateway_login(settings,client)[0].status_code==303
    original=bridge.send;calls=[];entered=threading.Event()
    def slow(*args,**kwargs):
        calls.append(args[2]);entered.set();time.sleep(.1);return original(*args,**kwargs)
    monkeypatch.setattr(bridge,'send',slow)
    async def scenario():
        first=True;sent=[]
        async def receive():
            nonlocal first
            if first:first=False;return {'type':'http.request','body':b'','more_body':False}
            while not entered.is_set():await asyncio.sleep(.001)
            return {'type':'http.disconnect'}
        async def send(message):sent.append(message)
        scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'GET','scheme':'https',
            'path':'/learning/api/v1/textbooks','raw_path':b'/learning/api/v1/textbooks','query_string':b'',
            'headers':[(b'cookie','; '.join(k+'='+v for k,v in client.cookies.items()).encode())],
            'client':('127.0.0.1',1),'server':('testserver',443)}
        await client.app(scope,receive,send)
        await asyncio.sleep(.15)
        assert not sent
    asyncio.run(scenario())
    assert calls==['/api/v1/auths/']
