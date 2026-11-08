"""Local excerpt review journal. Explicit workspace; no runtime DB or provider access.

Every edit is an appended snapshot guarded by an expected sequence number. Review
statements are attributed attestations; exact arithmetic does not prove prose.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from .passage_evidence import canonical, digest, load_bundle, text_digest
from .textbook_quality import check_arithmetic_claim
from .textbooks import learning_scope, page_evidence, render_page, _RENDER_LOCK


class ReviewError(ValueError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai'))


def safe_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ReviewError(503, '材料路径不能为软链接')
    return path


def required_text(value, maximum, label, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ReviewError(422, label + '须填写具体内容')
    return value.strip()


def binding(content):
    return {**content['source'], 'text_sha256': text_digest(content['text']),
            'context_sha256': text_digest(content['context'])}


def source_page(config, pdf_page):
    book, chapter = learning_scope(config['curriculum_id'], config['book_id'], config['chapter_id'])
    if type(pdf_page) is not int or not chapter['page_start'] <= pdf_page <= chapter['page_end']:
        raise ReviewError(422, '原页必须在已固定的本章范围内')
    directory = safe_path(config['textbook_dir'])
    pdf = safe_path(directory / (book['id'] + '.pdf'))
    raw = pdf.read_bytes()
    if digest(raw) != config['pdf_sha256']:
        raise ReviewError(503, '来源PDF已变化，需重新核定来源')
    image = render_page(directory, book['id'], pdf_page)
    import fitz
    with _RENDER_LOCK:
        with fitz.open(stream=raw, filetype='pdf') as document:
            native = document[pdf_page - 1].get_text()
    page = page_evidence(book, pdf_page)
    source = {key: page[key] for key in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')}
    source.update(image_sha256=digest(image), native_text_sha256=text_digest(native))
    return source, image, native


def prepare(destination, bundle, manifest_sha256, textbook_dir, passage_id):
    """Copy one currently valid A07 excerpt as an UNREVIEWED new local draft."""
    destination, bundle, textbook_dir = map(safe_path, (destination, bundle, textbook_dir))
    if destination.exists() or any(destination.is_relative_to(p) for p in (bundle, textbook_dir)):
        raise ReviewError(409, '请选择不存在的独立工作目录')
    day = now().date()
    rows = load_bundle(bundle, manifest_sha256, textbook_dir, as_of=day)
    original = next((row for row in rows if row['id'] == passage_id), None)
    if original is None:
        raise ReviewError(422, '所选片段当前不可用')
    evidence = original['evidence']
    config = {'format': 'dd-passage-review-workspace-v1', 'passage_id': passage_id,
              'curriculum_id': 'math-g7-v1', 'book_id': evidence['book_id'], 'chapter_id': evidence['chapter_id'],
              'textbook_dir': str(textbook_dir), 'pdf_sha256': evidence['pdf_sha256'],
              'valid_until': evidence['valid_until'], 'parent_manifest_sha256': manifest_sha256,
              'parent_evidence_id': evidence['evidence_id'], 'created_at': now().isoformat()}
    # The first workbench is deliberately limited to the B01/A07 native-PDF scope.
    if config['book_id'] != 'math-g7-upper' or config['chapter_id'] != '2':
        raise ReviewError(422, '本批仅支持七上第二章原生PDF片段')
    source, image, native = source_page(config, evidence['pdf_page'])
    if not native.strip():
        raise ReviewError(422, '原页无原生文字，保留待核，不启动OCR')
    if now().date() != day:
        raise ReviewError(409, '日期已变化，请重新准备')
    destination.mkdir(parents=True, mode=0o700)
    (destination / 'assets').mkdir()
    (destination / 'workspace.json').write_bytes(canonical(config))
    store = ReviewStore(destination)
    store._asset(image, '.png')
    store._asset(native.encode(), '.txt')
    state = {'revision': 1, 'content': {'text': original['text'], 'context': original['context'], 'source': source},
             'transcription': None, 'semantic': None, 'issues': [], 'enabled': False,
             'withdrawn': False, 'evidence_id': None}
    with sqlite3.connect(destination / 'review.sqlite') as conn:
        conn.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,previous_hash TEXT NOT NULL,hash TEXT NOT NULL,payload TEXT NOT NULL)')
        store._append(conn, state, 'import_pending', {'type': 'assistant', 'label': 'workspace preparation'}, '', '导入待核草稿；原审核仅作为历史来源')
    return store.view()


class ReviewStore:
    def __init__(self, directory):
        self.directory = safe_path(directory)
        self.config = json.loads(safe_path(self.directory / 'workspace.json').read_bytes())
        if self.config.get('format') != 'dd-passage-review-workspace-v1':
            raise ReviewError(503, '工作目录格式不匹配')
        self.config_hash = digest(canonical(self.config))

    def _asset(self, raw, suffix):
        path = safe_path(self.directory / 'assets' / (digest(raw) + suffix))
        if path.exists():
            if path.read_bytes() != raw:
                raise ReviewError(503, '素材内容不一致')
        else:
            # Content addressed assets are append-only; an interrupted edit may
            # leave an unused asset, never a partially committed review state.
            with path.open('xb') as stream:
                stream.write(raw)
        return path

    @contextmanager
    def _connection(self, write=False):
        config = json.loads(safe_path(self.directory / 'workspace.json').read_bytes())
        if digest(canonical(config)) != self.config_hash:
            raise ReviewError(503, '工作目录配置已变化，请重新核定')
        path = safe_path(self.directory / 'review.sqlite')
        if not path.is_file():
            raise ReviewError(503, '审核日志不存在')
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            if write:
                conn.execute('BEGIN IMMEDIATE')
            yield conn
            if write:
                conn.commit()
        except BaseException:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()

    def _events(self, conn):
        result, previous = [], ''
        for seq, row in enumerate(conn.execute('SELECT * FROM events ORDER BY seq'), 1):
            event = json.loads(row['payload'])
            expected = digest(canonical({'previous_hash': previous, 'event': event}))
            if (row['seq'] != seq or row['previous_hash'] != previous or row['hash'] != expected
                    or event['seq'] != seq or event['config_sha256'] != self.config_hash):
                raise ReviewError(503, '审核日志或配置绑定已变化')
            result.append(event | {'event_hash': expected})
            previous = expected
        if not result:
            raise ReviewError(503, '审核日志为空')
        return result

    def _append(self, conn, state, action, actor, previous, reason):
        seq = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0] + 1
        event = {'seq': seq, 'action': action, 'actor': actor, 'at': now().isoformat(), 'reason': reason,
                 'config_sha256': self.config_hash, 'state': state}
        checksum = digest(canonical({'previous_hash': previous, 'event': event}))
        conn.execute('INSERT INTO events VALUES (?,?,?,?)', (seq, previous, checksum, canonical(event).decode()))

    def _validate_source(self, state):
        source = state['content']['source']
        directory = safe_path(self.config['textbook_dir'])
        pdf = safe_path(directory / (self.config['book_id'] + '.pdf'))
        if digest(pdf.read_bytes()) != self.config['pdf_sha256']:
            raise ReviewError(503, '来源PDF已变化，已停止使用审核证据')
        book, chapter = learning_scope(self.config['curriculum_id'], self.config['book_id'], self.config['chapter_id'])
        page = page_evidence(book, source['pdf_page'])
        if page['chapter_id'] != chapter['id'] or any(source[k] != page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')):
            raise ReviewError(503, '原页范围绑定已变化')
        for key, suffix in (('image_sha256', '.png'), ('native_text_sha256', '.txt')):
            asset = safe_path(self.directory / 'assets' / (source[key] + suffix))
            if digest(asset.read_bytes()) != source[key]:
                raise ReviewError(503, '原页素材已变化，已停止使用审核证据')

    def _gate(self, state):
        reasons = []
        if state['withdrawn']:
            reasons.append('已撤回，须新建修订并重审')
        if not self.config['created_at'][:10] <= now().date().isoformat() <= self.config['valid_until']:
            reasons.append('复核有效期已到期')
        if any(issue['resolution'] is None for issue in state['issues']):
            reasons.append('仍有未解决问题')
        for kind in ('transcription', 'semantic'):
            review = state[kind]
            if review is None or review['binding'] != binding(state['content']):
                reasons.append('缺少本版本的' + ('原图转写复核' if kind == 'transcription' else '独立内容核验'))
        return reasons

    def _view(self, event):
        state = deepcopy(event['state'])
        self._validate_source(state)
        reasons = self._gate(state)
        available = bool(state['enabled'] and not reasons)
        source = state['content']['source']
        native = safe_path(self.directory / 'assets' / (source['native_text_sha256'] + '.txt')).read_text()
        return {'seq': event['seq'], 'event_hash': event['event_hash'], **state,
                'available': available, 'evidence_id': state['evidence_id'] if available else None,
                'blockers': reasons, 'native_text': native,
                'valid_until': self.config['valid_until'], 'scope': 'selected_excerpt',
                'teacher_reviewed': False, 'fully_reviewed_page': False, 'eligible_as_grading_basis': False,
                'publication_scope': 'local_review_workspace_only'}

    def view(self):
        with self._connection() as conn:
            return self._view(self._events(conn)[-1])

    def history(self):
        with self._connection() as conn:
            return self._events(conn)

    def image(self, seq):
        with self._connection() as conn:
            event = self._events(conn)[-1]
            if event['seq'] != seq:
                raise ReviewError(409, '原页版本已变化，请刷新')
            self._validate_source(event['state'])
            checksum = event['state']['content']['source']['image_sha256']
            return safe_path(self.directory / 'assets' / (checksum + '.png')).read_bytes()

    def evidence(self, evidence_id):
        result = self.view()
        if not result['available'] or result['evidence_id'] != evidence_id:
            raise ReviewError(404, '片段证据已失效或撤回')
        return {key: result[key] for key in ('seq', 'revision', 'content', 'transcription', 'semantic', 'evidence_id',
                                            'valid_until', 'scope', 'teacher_reviewed', 'fully_reviewed_page',
                                            'eligible_as_grading_basis', 'publication_scope')}

    def mutate(self, seq, action, values, actor):
        if type(seq) is not int or actor.get('type') not in ('assistant', 'human'):
            raise ReviewError(422, '审核版本或操作者类型无效')
        actor = {'type': actor['type'], 'label': required_text(actor.get('label'), 100, '操作者')}
        with self._connection(write=True) as conn:
            previous = self._events(conn)[-1]
            if previous['seq'] != seq:
                raise ReviewError(409, '其他复核已更新此版本；请刷新并保留未提交内容')
            state = deepcopy(previous['state'])
            # Retraction remains possible when source bytes are damaged.
            if action not in ('disable', 'withdraw'):
                self._validate_source(state)
            allowed = {
                'revise': {'text', 'context', 'pdf_page', 'reason'},
                'transcription': {'notes', 'scope_notes', 'layout_notes'},
                'semantic': {'derivation', 'conditions', 'units', 'diagram', 'checks'},
                'issue': {'description'}, 'resolve': {'issue_id', 'resolution'},
                'enable': {'reason'}, 'disable': {'reason'}, 'withdraw': {'reason'},
            }
            if action not in allowed or set(values) != allowed[action]:
                raise ReviewError(422, '操作字段不完整或含未知字段')
            reason = ''
            state['enabled'], state['evidence_id'] = False, None
            if action == 'revise':
                reason = required_text(values['reason'], 1000, '修改原因')
                text = required_text(values['text'], 1400, '片段转写')
                context = required_text(values['context'], 4000, '上下文')
                source, image, native = source_page(self.config, values['pdf_page'])
                self._asset(image, '.png'); self._asset(native.encode(), '.txt')
                state.update(revision=state['revision'] + 1, content={'text': text, 'context': context, 'source': source},
                             transcription=None, semantic=None, withdrawn=False)
            elif action in ('transcription', 'semantic'):
                if state['withdrawn']:
                    raise ReviewError(422, '已撤回版本必须先新建修订')
                review = {'actor': actor, 'at': now().isoformat(), 'binding': binding(state['content'])}
                if action == 'transcription':
                    review.update({k: required_text(values[k], 3000, k, 8) for k in ('notes', 'scope_notes', 'layout_notes')})
                    review['method'] = 'visual_original_comparison'
                else:
                    if check_arithmetic_claim(state['content']['text'])['status'] == 'rejected':
                        raise ReviewError(422, '原文等式不成立，保留原文并记录问题，不可启用')
                    review.update({k: required_text(values[k], 6000, k, 8) for k in ('derivation', 'conditions', 'units')})
                    if values['diagram'] != 'none_for_selected_excerpt':
                        raise ReviewError(422, '依赖图形的片段本批保持待核')
                    checks = values['checks']
                    if not isinstance(checks, list) or not 1 <= len(checks) <= 20:
                        raise ReviewError(422, '须提供独立核算及其与片段的关系')
                    results = []
                    for check in checks:
                        if not isinstance(check, dict) or set(check) != {'claim', 'purpose'}:
                            raise ReviewError(422, '核算须包含完整等式和说明')
                        claim = required_text(check['claim'], 200, '完整算式')
                        purpose = required_text(check['purpose'], 1000, '核算与片段的关系', 8)
                        result = check_arithmetic_claim(claim)
                        if result['status'] != 'verified':
                            raise ReviewError(422, '独立算式未通过；请纠正或记录未决问题')
                        results.append({'claim': claim, 'purpose': purpose, 'result': result})
                    review.update(method='independent_reasoning_and_exact_arithmetic', checks=results, diagram=values['diagram'])
                state[action] = review
            elif action == 'issue':
                reason = required_text(values['description'], 2000, '问题描述')
                state['issues'].append({'id': 'issue-' + str(seq + 1), 'description': reason,
                                        'opened_by': actor, 'opened_at': now().isoformat(), 'resolution': None})
                state['transcription'] = state['semantic'] = None
            elif action == 'resolve':
                reason = required_text(values['resolution'], 2000, '解决依据', 8)
                issue = next((i for i in state['issues'] if i['id'] == values['issue_id'] and i['resolution'] is None), None)
                if issue is None:
                    raise ReviewError(422, '未找到待解决的问题')
                issue['resolution'] = {'notes': reason, 'actor': actor, 'at': now().isoformat()}
                state['transcription'] = state['semantic'] = None
            else:
                reason = required_text(values['reason'], 2000, '操作原因', 4)
                if action == 'withdraw':
                    state.update(withdrawn=True, transcription=None, semantic=None)
                elif action == 'enable':
                    blockers = self._gate(state)
                    if blockers:
                        raise ReviewError(422, '；'.join(blockers))
                    state['enabled'] = True
                    state['evidence_id'] = 'dd-review-' + digest(canonical({'seq': seq + 1, 'state': state}))
            if action not in ('disable', 'withdraw'):
                self._validate_source(state)
            self._append(conn, state, action, actor, previous['event_hash'], reason)
            return {'seq': seq + 1, 'revision': state['revision'], 'action': action}

    def export(self, destination, seq):
        """Write a historical review packet, never an A07 runtime manifest."""
        destination = safe_path(destination)
        if destination.exists() or destination == self.directory or destination.is_relative_to(self.directory):
            raise ReviewError(409, '导出必须使用工作目录外的新目录')
        with self._connection(write=True) as conn:
            events = self._events(conn)
            if events[-1]['seq'] != seq:
                raise ReviewError(409, '候选已变化，请刷新')
            state = self._view(events[-1])
            if not state['available']:
                raise ReviewError(422, '当前片段未启用或未通过本地复核')
            image = safe_path(self.directory / 'assets' / (state['content']['source']['image_sha256'] + '.png')).read_bytes()
            record = {'format': 'dd-passage-review-snapshot-v1', 'exported_at': now().isoformat(),
                      'source_config': self.config, 'state': state, 'journal': events,
                      'historical_snapshot_only': True, 'runtime_manifest': False}
            files = {'review.json': canonical(record), 'original.png': image}
            manifest = {'format': 'dd-passage-review-export-v1', 'files': {k: digest(v) for k, v in files.items()},
                        'seq': seq, 'runtime_publish_performed': False}
            self._validate_source(events[-1]['state'])
            if self._gate(events[-1]['state']):
                raise ReviewError(409, '复核状态已失效')
            destination.mkdir(parents=True, mode=0o700)
            for name, raw in files.items():
                (destination / name).write_bytes(raw)
            (destination / 'manifest.json').write_bytes(canonical(manifest))
            return manifest
