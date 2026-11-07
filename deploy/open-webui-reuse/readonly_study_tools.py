"""
title: 课本伴学（只读）
author: DD-1.0
description: 按当前家庭档案查询教材、概念和关联练习，并提供原页核对链接。
required_open_webui_version: 0.12.5
version: 1.0.0
"""
from __future__ import annotations

import asyncio
import http.client
import json
import re
from urllib.parse import urlencode
from fastapi import Request

ORIGIN = 'https://172.19.116.53'
WORKSPACE = ORIGIN + '/learning/ui'
SESSION = '__Host-dd_learning_session'
CSRF = '__Host-dd_learning_csrf'
ID = re.compile(r'[A-Za-z0-9_-]{1,128}')


class StudyError(Exception):
    pass


class Tools:
    """Only public reading references. No account selection or learning writes."""

    def __init__(self):
        self.citation = False  # Emit explicit labelled citations, not opaque JSON citations.

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
            if response.status != 200 or len(raw) > 262144:
                raise StudyError('REFERENCE_UNAVAILABLE')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise StudyError('REFERENCE_UNAVAILABLE')
            return data
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
                    raise StudyError('LOGIN_REQUIRED')
                cookies[key] = value
        if not cookies.get('token') or not cookies.get(SESSION):
            raise StudyError('LOGIN_REQUIRED')
        return cookies

    @staticmethod
    def _signature(session):
        if session.get('server_context_mode') is not True or type(session.get('context_version')) is not int or not session.get('learner_id'):
            raise StudyError('CHOOSE_PROFILE')
        return tuple(session.get(k) for k in ('account_id', 'learner_id', 'context_version'))

    def _read(self, kind, params, user, request):
        cookies = self._host(user, request)
        identity = self._fetch('open-webui', 8080, '/api/v1/auths/', 'token=' + cookies['token'])
        if identity.get('id') != user['id'] or identity.get('role') not in {'user', 'admin'}:
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
        if self._signature(checked) != pinned:
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
            output['pages'] = []
            for page in self._rows(data.get('items'), 4):
                item = self._fields(page, ('book_title', 'printed_page', 'content_title'))
                # Extracted maths/text can be distorted. Search supplies location,
                # never unreviewed OCR/text as an authoritative quote or answer.
                item['url'] = self._link(data['book_id'], data['chapter_id'], revision, page=page['printed_page'])
                item['reference_type'] = '原页位置；需打开核对，未提供原文'
                output['pages'].append(item)
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
                    item['pages'].append({'printed_page': page['printed_page'],
                        'url': self._link(book, page['chapter_id'], revision, page=page['printed_page'])})
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
        except Exception:
            return json.dumps({'error': 'STUDY_REFERENCE_UNAVAILABLE', 'message': '请打开家庭学习，确认登录与当前档案、课本范围后重试。不要改用其他年级或编造来源。', 'workbench_url': WORKSPACE}, ensure_ascii=False)
        if emitter:
            sources = []
            for node in output.get('concepts', []) + output.get('prerequisites', []):
                for page in node['pages'][:1]:
                    sources.append((node['title'] + ' · 本地理解参考', '本地讲解：' + node.get('explanation', '') + '；原页需另外打开核对。', page['url']))
            for page in output.get('pages', []):
                sources.append((page['book_title'] + ' · 第' + str(page['printed_page']) + '页', page['content_title'] + '（检索定位，未提供原文）', page['url']))
            for title, text, url in sources[:6]:
                await emitter({'type': 'citation', 'data': {'document': [text], 'metadata': [{'source': url}], 'source': {'name': title, 'url': url}}})
        return json.dumps(output, ensure_ascii=False)

    async def get_study_catalogue(self, __user__: dict = None, __request__: Request = None) -> str:
        """先查询当前家庭档案可用的学科、课本和章节 ID；不要猜测或跨年级选书。"""
        return await self._run('textbooks', {}, __user__, __request__, None)

    async def get_math_scope(self, book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """查看当前数学课本的概念 ID 和关联题，章节可空；无映射就说明，不自动生成题。"""
        return await self._run('math-references', {'book_id': book_id, 'chapter_id': chapter_id}, __user__, __request__, __event_emitter__)

    async def get_math_concept_reference(self, concept_id: str, book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """解释已查询到的数学概念，返回先修参考、核对点及原页链接。先引导学生思考，不宣称掌握或确定错因。"""
        if not concept_id: return json.dumps({'error': 'CONCEPT_REQUIRED'})
        return await self._run('math-references', {'book_id': book_id, 'chapter_id': chapter_id, 'concept_id': concept_id}, __user__, __request__, __event_emitter__)

    async def get_math_question_reference(self, question_version_id: str, book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """查询已有题的知识点与相关练习；给出工作区链接供学生自己开始，不提交或判分。"""
        if not question_version_id: return json.dumps({'error': 'QUESTION_REQUIRED'})
        return await self._run('math-references', {'book_id': book_id, 'chapter_id': chapter_id, 'question_version_id': question_version_id}, __user__, __request__, __event_emitter__)

    async def get_study_support(self, subject: str = '', book_id: str = '', chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """按当前年级获取语数英、道法、历史、地理、生物阅读问题串。结合材料分步引导；非数学不是已审核学科答案。"""
        return await self._run('study-support', {'subject': subject, 'book_id': book_id, 'chapter_id': chapter_id}, __user__, __request__, __event_emitter__)

    async def search_textbook(self, query: str, book_id: str, chapter_id: str = '', __user__: dict = None, __request__: Request = None, __event_emitter__=None) -> str:
        """用简短课本关键词查当前书章，返回最多四个原页链接。只传概念关键词，不传学生姓名、作答或整段聊天；未命中时不要补造页码。"""
        return await self._run('textbooks/search', {'query': query, 'book_id': book_id, 'chapter_id': chapter_id}, __user__, __request__, __event_emitter__)
