"""
title: 课本伴学（只读）
author: DD-1.0
description: 按当前家庭档案查询教材、概念和关联练习，并提供原页核对链接。
required_open_webui_version: 0.12.5
version: 1.1.2
"""
from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import logging
import re
import secrets
from urllib.parse import urlencode
from fastapi import Request

ORIGIN = 'https://172.19.116.53'
WORKSPACE = ORIGIN + '/learning/ui'
SESSION = '__Host-dd_learning_session'
CSRF = '__Host-dd_learning_csrf'
ID = re.compile(r'[A-Za-z0-9_-]{1,128}')
SHA256 = re.compile(r'[a-f0-9]{64}')
REQUEST_ID = re.compile(r'ddreq_[a-f0-9]{32}')
LOGGER = logging.getLogger('dd.study.tool')
ERRORS = {
    'LOGIN_REQUIRED': ('请先登录主站，再从家庭学习入口重新进入。', 'sign_in', False),
    'SESSION_EXPIRED': ('学习会话已过期，请从家庭学习入口重新进入。', 'reenter', False),
    'SESSION_INVALID': ('学习会话已失效，请从家庭学习入口重新进入。', 'reenter', False),
    'IDENTITY_CHANGED': ('当前登录与学习会话不一致，已停止读取。请确认主站账号后重新进入家庭学习。', 'confirm_login', False),
    'CONTEXT_CHANGED': ('当前档案已变化，已丢弃旧资料。请刷新家庭学习，重新选择档案和课本范围。', 'reselect_scope', False),
    'CHOOSE_PROFILE': ('请打开家庭学习，选择当前档案和课本范围后再试。', 'reselect_scope', False),
    'INVALID_SCOPE': ('请从当前档案的目录中重新选择课本、章节或已列出的项目，再重试。', 'reselect_scope', False),
    'TEXTBOOK_UNAVAILABLE': ('当前教材原件缺失或版本校验未通过，请联系维护者核对材料后重试。', 'contact_maintainer', False),
    'REFERENCE_NOT_FOUND': ('当前范围暂未提供这项资料，请查看已有目录；不能编造来源或答案。', 'browse_available', False),
    'RETRIEVAL_TIMEOUT': ('教材检索超时，请稍后重试；本次没有可用证据，不能据此判断教材没有相关内容。', 'retry_later', True),
    'RETRIEVAL_UNAVAILABLE': ('教材检索暂不可用，请稍后重试或打开原页；本次没有可用证据。', 'retry_later', True),
    'AUTH_UNAVAILABLE': ('登录校验服务暂不可用，请稍后重试。', 'retry_later', True),
    'AUTH_TIMEOUT': ('登录校验超时，请稍后重试。', 'retry_later', True),
    'SERVICE_UNAVAILABLE': ('学习服务暂不可用，请稍后重试。', 'retry_later', True),
    'SERVICE_TIMEOUT': ('学习服务请求超时，请稍后重试。', 'retry_later', True),
    'REQUEST_REJECTED': ('请求校验未通过，请刷新家庭学习后重新操作。', 'refresh', False),
    'REFERENCE_INVALID': ('资料响应未通过校验，已停止引用；请稍后重试，持续失败时联系维护者。', 'retry_later', True),
    'CITATION_UNAVAILABLE': ('引用展示暂不可用，请稍后重试或打开家庭学习核对原页。', 'retry_later', True),
    'STUDY_REFERENCE_UNAVAILABLE': ('学习资料暂不可用，请稍后重试；若持续失败，请提供本次请求编号给维护者。', 'retry_later', True),
}
GATEWAY_ERRORS = {
    'WEBUI_LOGIN_REQUIRED': (401, 'LOGIN_REQUIRED'), 'WEBUI_LOGIN_REJECTED': (401, 'LOGIN_REQUIRED'),
    'BROWSER_LOGIN_REQUIRED': (401, 'SESSION_INVALID'), 'BROWSER_SESSION_INVALID': (401, 'SESSION_INVALID'),
    'BROWSER_SESSION_EXPIRED': (401, 'SESSION_EXPIRED'), 'LEARNING_IDENTITY_MISMATCH': (401, 'IDENTITY_CHANGED'),
    'LEARNER_CONTEXT_CHANGED': (409, 'CONTEXT_CHANGED'), 'LEARNER_CONTEXT_REQUIRED': (409, 'CHOOSE_PROFILE'),
    'TEXTBOOK_SCOPE_INVALID': (422, 'INVALID_SCOPE'), 'MATH_REFERENCE_SCOPE_INVALID': (422, 'INVALID_SCOPE'),
    'STUDY_SUPPORT_SCOPE_INVALID': (422, 'INVALID_SCOPE'), 'TEXTBOOK_PAGE_NOT_FOUND': (404, 'INVALID_SCOPE'),
    'TEXTBOOK_PAGE_UNAVAILABLE': (503, 'TEXTBOOK_UNAVAILABLE'), 'MATH_REFERENCE_TEXTBOOK_UNAVAILABLE': (503, 'TEXTBOOK_UNAVAILABLE'),
    'MATH_REFERENCE_NOT_FOUND': (404, 'REFERENCE_NOT_FOUND'), 'STUDY_SUPPORT_NOT_FOUND': (404, 'REFERENCE_NOT_FOUND'),
    'TEXTBOOK_RETRIEVAL_TIMEOUT': (504, 'RETRIEVAL_TIMEOUT'), 'TEXTBOOK_RETRIEVAL_UNAVAILABLE': (503, 'RETRIEVAL_UNAVAILABLE'),
    'AUTH_UPSTREAM_TIMEOUT': (504, 'AUTH_TIMEOUT'), 'AUTH_UPSTREAM_UNAVAILABLE': (503, 'AUTH_UNAVAILABLE'),
    'LEARNING_UPSTREAM_TIMEOUT': (504, 'SERVICE_TIMEOUT'), 'LEARNING_UPSTREAM_UNAVAILABLE': (503, 'SERVICE_UNAVAILABLE'),
    'BROWSER_CSRF_REJECTED': (403, 'REQUEST_REJECTED'), 'BROWSER_ORIGIN_REJECTED': (403, 'REQUEST_REJECTED'),
    'ORIGIN_REJECTED': (403, 'REQUEST_REJECTED'), 'COOKIE_REJECTED': (401, 'REQUEST_REJECTED'),
    'REQUEST_HEADERS_REJECTED': (400, 'REQUEST_REJECTED'), 'REQUEST_TOO_LARGE': (413, 'REQUEST_REJECTED'),
    'TEXTBOOK_RETRIEVAL_INVALID': (502, 'REFERENCE_INVALID'), 'LEARNING_UPSTREAM_INVALID': (502, 'REFERENCE_INVALID'),
    'AUTH_UPSTREAM_INVALID': (502, 'AUTH_UNAVAILABLE'), 'MATH_REFERENCE_UNAVAILABLE': (503, 'REFERENCE_INVALID'),
    'MATH_REFERENCE_VERSION_MISMATCH': (503, 'REFERENCE_INVALID'), 'STUDY_SUPPORT_UNAVAILABLE': (503, 'REFERENCE_INVALID'),
}


class StudyError(Exception):
    def __init__(self, code, request_id=None):
        if isinstance(code, str):
            code = {'INVALID_SOURCE': 'REFERENCE_INVALID', 'INVALID_EVIDENCE': 'REFERENCE_INVALID',
                    'UPSTREAM_REJECTED': 'REQUEST_REJECTED', 'ROUTE_REJECTED': 'REQUEST_REJECTED',
                    'HOST_CONTEXT_REQUIRED': 'REQUEST_REJECTED'}.get(code, code)
        self.code = code if isinstance(code, str) and code in ERRORS else 'STUDY_REFERENCE_UNAVAILABLE'
        self.request_id = request_id if isinstance(request_id, str) and REQUEST_ID.fullmatch(request_id) else None
        super().__init__(self.code)


class Tools:
    """Only public reading references. No account selection or learning writes."""

    def __init__(self):
        self.citation = False  # Emit explicit labelled citations, not opaque JSON citations.

    @staticmethod
    def _response(host, status, raw, request_id=None):
        try:
            if len(raw) > 262144:
                raise ValueError()
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError()
                    result[key] = value
                return result
            data = json.loads(raw, object_pairs_hook=pairs)
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, TypeError, RecursionError):
            data = None
        if host == 'open-webui':
            if status in {401, 403}:
                raise StudyError('LOGIN_REQUIRED')
            if status != 200 or data is None:
                raise StudyError('AUTH_TIMEOUT' if status == 504 else 'AUTH_UNAVAILABLE')
        elif status != 200:
            error = data.get('error') if data else None
            code = error.get('code') if isinstance(error, dict) else None
            mapped = GATEWAY_ERRORS.get(code) if isinstance(code, str) else None
            if mapped and mapped[0] == status:
                raise StudyError(mapped[1], request_id)
            raise StudyError('SERVICE_UNAVAILABLE' if status >= 500 else 'STUDY_REFERENCE_UNAVAILABLE', request_id)
        if data is None or 'error' in data:
            raise StudyError('REFERENCE_INVALID', request_id)
        return data

    @staticmethod
    def _failure(error):
        error = error if isinstance(error, StudyError) else StudyError('STUDY_REFERENCE_UNAVAILABLE')
        request_id = error.request_id or 'ddtool_' + secrets.token_hex(16)
        message, action, retryable = ERRORS[error.code]
        LOGGER.warning('study_failure request_id=%s code=%s', request_id, error.code)
        return json.dumps({'error': error.code, 'message': message, 'action': action,
                           'retryable': retryable, 'request_id': request_id, 'workbench_url': WORKSPACE}, ensure_ascii=False)

    @staticmethod
    def _fetch(host, port, path, cookies, revision=None, payload=None):
        # Fixed internal peers only, no redirects, proxies, environment or secrets.
        if (host, port) not in {('open-webui', 8080), ('learning-gateway', 8000)}:
            raise StudyError('UPSTREAM_REJECTED')
        allowed = {'/api/v1/auths/'} if host == 'open-webui' else {
            '/learning/api/v1/auth/session', '/learning/api/v1/textbooks',
            '/learning/api/v1/math-references', '/learning/api/v1/study-support',
            '/learning/api/v1/textbooks/search'}
        if path.split('?')[0] not in allowed or (payload is not None and path != '/learning/api/v1/textbooks/search'):
            raise StudyError('ROUTE_REJECTED')
        headers = {'Cookie': cookies, 'Accept': 'application/json'}
        if revision is not None:
            headers['X-Learner-Context-Version'] = str(revision)
        body = None
        if payload is not None:
            headers.update({'Content-Type': 'application/json', 'Origin': ORIGIN,
                            'X-CSRF-Token': dict(part.split('=', 1) for part in cookies.split('; ')).get(CSRF, '')})
            body = json.dumps(payload).encode()
        connection = http.client.HTTPConnection(host, port, timeout=12)
        try:
            connection.request('POST' if payload is not None else 'GET', path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(262145)
            request_id = response.getheader('X-DD-Request-ID') if host == 'learning-gateway' and hasattr(response, 'getheader') else None
            return Tools._response(host, response.status, raw, request_id)
        except TimeoutError:
            raise StudyError('AUTH_TIMEOUT' if host == 'open-webui' else 'RETRIEVAL_TIMEOUT' if payload is not None else 'SERVICE_TIMEOUT') from None
        except (OSError, http.client.HTTPException):
            raise StudyError('AUTH_UNAVAILABLE' if host == 'open-webui' else 'SERVICE_UNAVAILABLE') from None
        finally:
            connection.close()

    @staticmethod
    def _host(user, request):
        if not isinstance(request, Request) or not isinstance(user, dict) or not ID.fullmatch(str(user.get('id', ''))):
            raise StudyError('HOST_CONTEXT_REQUIRED')
        cookies = {}
        for header in request.headers.getlist('cookie'):
            for part in header.split(';'):
                key, sep, value = part.strip().partition('=')
                if key not in {'token', SESSION, CSRF}:
                    continue
                if not sep or key in cookies or not re.fullmatch(r'[A-Za-z0-9._~-]{1,8192}', value):
                    raise StudyError('REQUEST_REJECTED')
                cookies[key] = value
        if not cookies.get('token'):
            raise StudyError('LOGIN_REQUIRED')
        if not cookies.get(SESSION):
            raise StudyError('SESSION_INVALID')
        return cookies

    @staticmethod
    def _signature(session):
        if (session.get('server_context_mode') is not True or type(session.get('context_version')) is not int
                or session['context_version'] < 0 or not isinstance(session.get('account_id'), str)
                or not ID.fullmatch(session['account_id'])):
            raise StudyError('REFERENCE_INVALID')
        if not session.get('learner_id'):
            raise StudyError('CHOOSE_PROFILE')
        if not isinstance(session['learner_id'], str) or not ID.fullmatch(session['learner_id']):
            raise StudyError('REFERENCE_INVALID')
        return tuple(session.get(k) for k in ('account_id', 'learner_id', 'context_version'))

    def _read(self, kind, params, user, request):
        cookies = self._host(user, request)
        identity = self._fetch('open-webui', 8080, '/api/v1/auths/', 'token=' + cookies['token'])
        if not isinstance(identity.get('id'), str) or not ID.fullmatch(identity['id']) or not isinstance(identity.get('role'), str):
            raise StudyError('AUTH_UNAVAILABLE')
        if identity.get('role') not in {'user', 'admin'}:
            raise StudyError('LOGIN_REQUIRED')
        if identity['id'] != user['id']:
            raise StudyError('IDENTITY_CHANGED')
        header = '; '.join(k + '=' + v for k, v in cookies.items())
        session = self._fetch('learning-gateway', 8000, '/learning/api/v1/auth/session', header)
        pinned = self._signature(session)
        for key, value in params.items():
            if key == 'query':
                if type(value) is not str or not value.strip() or len(value) > 120 or any(ord(c) < 32 for c in value):
                    raise StudyError('INVALID_SCOPE')
            elif type(value) is not str or value and not ID.fullmatch(value):
                raise StudyError('INVALID_SCOPE')
        path = '/learning/api/v1/' + kind
        payload = params if kind == 'textbooks/search' else None
        if payload is None and params:
            path += '?' + urlencode(params)
        response = self._fetch('learning-gateway', 8000, path, header, pinned[2], payload)
        checked = self._fetch('learning-gateway', 8000, '/learning/api/v1/auth/session', header)
        current = self._signature(checked)
        if current[0] != pinned[0]:
            raise StudyError('IDENTITY_CHANGED')
        if current != pinned:
            raise StudyError('CONTEXT_CHANGED')
        return self._project(kind, response, pinned[2])

    @staticmethod
    def _text(value, size=1600):
        return value[:size] if isinstance(value, str) else ''

    def _fields(self, item, names):
        return {k: self._text(item[k]) if isinstance(item[k], str) else item[k]
                for k in names if isinstance(item, dict) and k in item and type(item[k]) in {str, int, bool}}

    @staticmethod
    def _rows(value, limit):
        return [item for item in value[:limit] if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _link(book, chapter, revision, page=None, question=None):
        if not ID.fullmatch(str(book)) or chapter and not ID.fullmatch(str(chapter)):
            raise StudyError('INVALID_SOURCE')
        params = {'studyBook': book, 'studyChapter': chapter, 'studyRevision': revision}
        if page is not None:
            if type(page) is not int or not 1 <= page <= 999: raise StudyError('INVALID_SOURCE')
            params['studyPage'] = page
        if question is not None:
            if not ID.fullmatch(str(question)): raise StudyError('INVALID_SOURCE')
            params['studyQuestion'] = question
        return WORKSPACE + '#' + urlencode(params)

    def _page_evidence(self, page, book, revision, chapter=''):
        """Project the service contract; never forward index metadata or URLs."""
        evidence = page.get('evidence')
        fixed = {'schema': 'dd-textbook-page-evidence-v1', 'kind': 'page_location',
                 'source_binding': 'catalogue_sha256', 'locator_precision': 'page',
                 'review_status': 'location_only', 'quote_status': 'unavailable',
                 'supports_textbook_answer': False, 'eligible_as_grading_basis': False}
        if not isinstance(evidence, dict) or any(
                type(evidence.get(k)) is not type(v) or evidence[k] != v for k, v in fixed.items()):
            raise StudyError('INVALID_EVIDENCE')
        strings = ('book_id', 'book_title', 'subject', 'semester', 'edition', 'edition_id',
                   'pdf_sha256', 'chapter_id', 'chapter_title', 'source_ref', 'evidence_id')
        if any(type(evidence.get(k)) is not str or not evidence[k] or len(evidence[k]) > 1600 for k in strings):
            raise StudyError('INVALID_EVIDENCE')
        if (evidence['book_id'] != book or chapter and evidence['chapter_id'] != chapter
                or not SHA256.fullmatch(evidence['pdf_sha256'])
                or evidence['edition_id'] != 'pep-2022-standard-current'
                or type(evidence.get('grade')) is not int or evidence['grade'] not in {2, 7}):
            raise StudyError('INVALID_EVIDENCE')
        for key in ('printed_page', 'pdf_page'):
            if (type(evidence.get(key)) is not int or not 1 <= evidence[key] <= 999
                    or type(page.get(key)) is not int or evidence[key] != page[key]):
                raise StudyError('INVALID_EVIDENCE')
        source_ref = 'dd-textbook-' + hashlib.sha256(
            f"{book}\n{evidence['edition_id']}\n{evidence['pdf_sha256']}".encode()).hexdigest()
        evidence_id = 'dd-page-' + hashlib.sha256(f"{source_ref}\n{evidence['pdf_page']}".encode()).hexdigest()
        if evidence['source_ref'] != source_ref or evidence['evidence_id'] != evidence_id:
            raise StudyError('INVALID_EVIDENCE')
        result = {**fixed, **self._fields(evidence, (*strings, 'grade', 'printed_page', 'pdf_page'))}
        result['url'] = self._link(book, evidence['chapter_id'], revision, page=evidence['printed_page'])
        return result

    @staticmethod
    def _local_evidence(node, reference_sha256):
        if not isinstance(reference_sha256, str) or not SHA256.fullmatch(reference_sha256) or not ID.fullmatch(node['id']):
            raise StudyError('INVALID_EVIDENCE')
        return {'schema': 'dd-local-explanation-evidence-v1', 'kind': 'local_explanation',
                'evidence_id': 'dd-explanation-' + hashlib.sha256(f"{reference_sha256}\n{node['id']}".encode()).hexdigest(),
                'source_ref': 'dd-local-reference-' + reference_sha256, 'reference_sha256': reference_sha256,
                'concept_id': node['id'], 'page_evidence_ids': [p['evidence']['evidence_id'] for p in node['pages']],
                'review_status': 'reference_only', 'quote_status': 'not_a_textbook_quote',
                'supports_textbook_answer': False, 'eligible_as_grading_basis': False}

    def _project(self, kind, data, revision):
        output = {'reference_only': True, 'eligible_as_grading_basis': False, 'teacher_reviewed': False,
                  'workbench_url': WORKSPACE,
                  'use': '按当前档案使用；资料不足请说明。知识参考不等于教材原句或标准答案。先提一个理解问题，等待学生回应。'}
        if kind == 'textbooks':
            output['books'] = []
            for book in self._rows(data.get('items'), 20):
                item = self._fields(book, ('id', 'title', 'subject', 'subject_title', 'grade', 'semester', 'edition'))
                item['chapters'] = [self._fields(c, ('id', 'title', 'printed_page')) for c in self._rows(book.get('chapters'), 50)]
                output['books'].append(item)
            return output
        if kind == 'textbooks/search':
            output.update(self._fields(data, ('book_id', 'chapter_id', 'notice')))
            coverage = data.get('retrieval')
            if coverage is not None and (not isinstance(coverage, dict)
                    or coverage.get('schema') != 'dd-retrieval-coverage-v1'
                    or coverage.get('status') != 'incomplete' or coverage.get('coverage_complete') is not False
                    or coverage.get('method') != 'collection_top_k_then_scope_filter'):
                raise StudyError('INVALID_SOURCE')
            output['retrieval'] = {'status': 'incomplete', 'coverage_complete': False,
                'reason': 'upstream_has_no_scope_filter' if coverage else 'coverage_not_reported',
                'fallback_action': 'browse'}
            output['pages'] = []
            for page in self._rows(data.get('items'), 4):
                item = self._fields(page, ('book_title', 'printed_page', 'pdf_page', 'content_title'))
                # Extracted maths/text can be distorted. Search supplies location,
                # never unreviewed OCR/text as an authoritative quote or answer.
                item['evidence'] = self._page_evidence(page, data['book_id'], revision, data['chapter_id'])
                item['url'] = item['evidence']['url']
                item['reference_type'] = '原页位置；需打开核对，未提供原文'
                output['pages'].append(item)
            output['grounding'] = {
                'status': 'incomplete',
                'can_quote_textbook': False, 'can_answer_from_textbook': False,
                'message': '本次检索可能遗漏所选范围的内容，请打开原页或清空关键词按页阅读；不据此断言教材没有相关内容，不编造引文、答案或页码。'}
            return output
        output['scope'] = self._fields(data.get('scope'), ('book_id', 'grade', 'semester', 'edition', 'chapter_id', 'chapter_title', 'subject', 'subject_title', 'title'))
        output.update(self._fields(data, ('mapping_status', 'mapped_question_count', 'notice')))
        output['provenance'] = self._fields(data.get('provenance'), ('structure_reference', 'commit', 'graph_license', 'question_license', 'implementation'))
        if data.get('reference_only') is not True or data.get('eligible_as_grading_basis') is not False:
            raise StudyError('INVALID_SOURCE')
        book = output['scope']['book_id']
        for group in ('concepts', 'prerequisites'):
            output[group] = []
            for node in self._rows(data.get(group), 18 if group == 'concepts' else 6):
                item = self._fields(node, ('id', 'title', 'explanation', 'depth', 'from_concept', 'strength', 'rationale'))
                item['checks'] = [self._text(x, 200) for x in (node.get('checks') or [])[:4] if isinstance(x, str)]
                item['pages'] = []
                for page in self._rows(node.get('pages'), 4):
                    if page.get('book_id') != book: continue
                    evidence = self._page_evidence(page, book, revision, page['chapter_id'])
                    item['pages'].append({'printed_page': page['printed_page'],
                        'pdf_page': page['pdf_page'], 'evidence': evidence, 'url': evidence['url']})
                item['evidence'] = self._local_evidence(item, data.get('reference_sha256'))
                output[group].append(item)
        output['questions'] = []
        for question in self._rows(data.get('questions'), 20):
            if question.get('book_id') != book: continue
            item = self._fields(question, ('question_version_id', 'title', 'difficulty', 'chapter_id', 'mapping_role'))
            item['source'] = self._fields(question.get('source'), ('kind', 'repository', 'commit', 'id', 'attribution', 'license', 'changes'))
            item['url'] = self._link(book, question['chapter_id'], revision, question=question['question_version_id'])
            output['questions'].append(item)
        output['study_steps'] = [self._fields(s, ('title', 'prompt')) for s in self._rows(data.get('study_steps'), 4)]
        return output

    async def _run(self, kind, params, user, request, emitter):
        try:
            output = await asyncio.to_thread(self._read, kind, params, user, request)
        except Exception as error:
            return self._failure(error)
        if emitter:
            sources = []
            for node in output.get('concepts', []) + output.get('prerequisites', []):
                for page in node['pages'][:1]:
                    sources.append((node['title'] + ' · 本地理解参考', '本地讲解：' + node.get('explanation', '') + '；原页需另外打开核对。', page, node['evidence']))
            for page in output.get('pages', []):
                sources.append((page['book_title'] + ' · 第' + str(page['printed_page']) + '页', page['content_title'] + '（检索定位，未提供原文）', page, page['evidence']))
            for title, text, page, evidence in sources[:6]:
                metadata = {**self._fields(page['evidence'], ('book_id', 'edition_id', 'pdf_sha256', 'printed_page', 'pdf_page')),
                            **self._fields(evidence, ('evidence_id', 'source_ref', 'kind', 'review_status', 'quote_status',
                                                      'reference_sha256', 'supports_textbook_answer', 'eligible_as_grading_basis')),
                            'page_evidence_id': page['evidence']['evidence_id'], 'source': page['url']}
                try:
                    await emitter({'type': 'citation', 'data': {'document': [text], 'metadata': [metadata],
                                  'source': {'id': evidence['evidence_id'], 'name': title, 'url': page['url']}}})
                except Exception:
                    return self._failure(StudyError('CITATION_UNAVAILABLE'))
        return json.dumps(output, ensure_ascii=False)

    async def get_study_catalogue(self, __user__: dict = None, __request__: Request = None) -> str:
        """先查询当前家庭档案可用的学科、课本和章节 ID；不要猜测或跨年级选书。"""
        return await self._run('textbooks', {}, __user__, __request__, None)

    async def get_math_scope(self, book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """查看当前数学课本的概念 ID 和关联题，章节可空；无映射就说明，不自动生成题。"""
        return await self._run('math-references', {'book_id': book_id, 'chapter_id': chapter_id}, __user__, __request__, __event_emitter__)

    async def get_math_concept_reference(self, concept_id: str, book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """解释已查询到的数学概念，返回先修参考、核对点及原页链接。先引导学生思考，不宣称掌握或确定错因。"""
        if not concept_id: return self._failure(StudyError('INVALID_SCOPE'))
        return await self._run('math-references', {'book_id': book_id, 'chapter_id': chapter_id, 'concept_id': concept_id}, __user__, __request__, __event_emitter__)

    async def get_math_question_reference(self, question_version_id: str, book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """查询已有题的知识点与相关练习；给出工作区链接供学生自己开始，不提交或判分。"""
        if not question_version_id: return self._failure(StudyError('INVALID_SCOPE'))
        return await self._run('math-references', {'book_id': book_id, 'chapter_id': chapter_id, 'question_version_id': question_version_id}, __user__, __request__, __event_emitter__)

    async def get_study_support(self, subject: str = '', book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """按当前年级获取语数英、道法、历史、地理、生物阅读问题串。结合材料分步引导；非数学不是已审核学科答案。"""
        return await self._run('study-support', {'subject': subject, 'book_id': book_id, 'chapter_id': chapter_id}, __user__, __request__, __event_emitter__)

    async def search_textbook(self, query: str, book_id: str, chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """用简短关键词查当前书章，返回最多四个原页位置及稳定证据 ID。仅定位不是已核验原文；按 grounding 说明证据不足，不编造引文或答案。只传概念关键词，不传学生姓名、作答或整段聊天。"""
        return await self._run('textbooks/search', {'query': query, 'book_id': book_id, 'chapter_id': chapter_id}, __user__, __request__, __event_emitter__)
