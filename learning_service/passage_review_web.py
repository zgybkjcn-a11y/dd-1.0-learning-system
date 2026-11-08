"""Explicitly constructed loopback-only maintenance UI; no default app or DB."""
from __future__ import annotations

from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .passage_review import ReviewError, ReviewStore
from .passage_review_ui import HTML


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_seq: int = Field(ge=1)
    action: str = Field(min_length=1, max_length=30)
    values: dict


def create_app(directory: Path, *, actor: dict, origin='http://127.0.0.1:8765'):
    parsed = urlsplit(origin)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('review server requires an explicit loopback origin')
    if actor.get('type') not in ('assistant', 'human') or not isinstance(actor.get('label'), str) or not actor['label'].strip():
        raise ValueError('explicit reviewer type and label required')
    store = ReviewStore(directory)
    token = secrets.token_urlsafe(32)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    actor = dict(actor)

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        if (request.headers.get('host') != parsed.netloc
                or request.headers.get('sec-fetch-site') == 'cross-site'
                or request.headers.get('origin') not in (None, origin)):
            return JSONResponse({'error': '仅允许本机同源复核'}, status_code=403)
        if request.url.path not in ('/', '/app.js', '/style.css') and not secrets.compare_digest(request.headers.get('x-review-token', ''), token):
            return JSONResponse({'error': '复核会话已失效，请刷新页面'}, status_code=403)
        if request.method != 'GET' and request.headers.get('origin') != origin:
            return JSONResponse({'error': '复核操作必须来自当前页面'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        return response

    @app.exception_handler(ReviewError)
    async def review_error(request, exc):
        return JSONResponse({'error': str(exc)}, status_code=exc.status)

    @app.exception_handler(OSError)
    @app.exception_handler(ValueError)
    @app.exception_handler(sqlite3.DatabaseError)
    async def material_error(request, exc):
        return JSONResponse({'error': '材料不可用，请核对本地工作目录'}, status_code=503)

    @app.get('/')
    def home():
        return HTMLResponse(HTML.replace('__TOKEN__', token))

    @app.get('/app.js')
    def javascript():
        from .passage_review_ui import SCRIPT
        return Response(SCRIPT, media_type='text/javascript')

    @app.get('/style.css')
    def stylesheet():
        from .passage_review_ui import STYLE
        return Response(STYLE, media_type='text/css')

    @app.get('/api/state')
    def state():
        return {**store.view(), 'operator': actor}

    @app.get('/api/history')
    def history():
        return {'events': store.history()}

    @app.get('/api/image')
    def image(seq: int):
        return Response(store.image(seq), media_type='image/png')

    @app.get('/api/evidence/{evidence_id}')
    def evidence(evidence_id: str):
        return store.evidence(evidence_id)

    @app.post('/api/commands')
    def command(body: Command):
        return store.mutate(body.expected_seq, body.action, body.values, actor)

    @app.post('/api/export')
    def export(body: Command):
        if body.action != 'export' or body.values:
            raise ReviewError(422, '导出只接受当前版本')
        destination = store.directory.parent / (store.directory.name + '-exports') / (str(body.expected_seq) + '-' + secrets.token_hex(6))
        manifest = store.export(destination, body.expected_seq)
        return {'directory': destination.name, 'manifest': manifest}

    return app
