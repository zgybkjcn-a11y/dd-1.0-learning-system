"""Frozen family word problems, numeric validation and transparent practice pacing.

Only the explicitly imported, content-reviewed subset can be offered. No runtime
model calls, upstream code execution, or unreviewed textbook/OCR generation.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .db import json_dumps, json_loads, new_id, utc_now

BANK_PATH = Path(__file__).parent / 'data/family_word_problems_v1.json'
BANK_SHA256 = '38e0903024ed9c402a8c66e8b02a3afd3e304ad55913fbdb0572a16589d211ef'
LEVELS = ('easy', 'normal', 'hard', 'challenge')
AUTO_PROMOTION_CORRECT = 4
LABELS = dict(zip(LEVELS, ('简单', '正常', '困难', '挑战')))
OBJECTIVES = {
    (2, '2'): '生活中的1～6表内乘法',
    (2, '3'): '生活中的1～6表内除法',
    (2, '5'): '生活中的7～9表内乘除法',
    (7, '2'): '用有理数运算解决生活问题',
    (7, '5'): '用一元一次方程解决生活问题',
}


class CollectionError(ValueError):
    def __init__(self, status, code, message):
        self.status, self.code = status, code
        super().__init__(message)


def fingerprint(value):
    return hashlib.sha256(json_dumps(value).encode()).hexdigest()


def question_snapshot(conn, version_id):
    row = conn.execute(
        'SELECT qv.id,qv.question_id,qv.version,qv.content_json,qv.answer_key_json,'
        'qv.validator_version,qv.variant_kind,qv.variant_group,qv.approval,q.objective_id,q.visibility,q.learner_id,'
        'q.approval AS question_approval FROM question_versions qv '
        'JOIN questions q ON q.id=qv.question_id WHERE qv.id=?', (version_id,)).fetchone()
    if not row:
        raise CollectionError(409, 'PRACTICE_VERSION_CHANGED', '题版已不可用，请保留原记录并联系家长核对。')
    return dict(row)


def frozen_question(conn, item_id, *, required=False, allow_retired=False):
    row = conn.execute('SELECT question_version_id,question_snapshot_json FROM test_items WHERE id=?', (item_id,)).fetchone()
    snapshot = json_loads(row['question_snapshot_json'], None) if row else None
    if row and row['question_snapshot_json'] is None and not required:
        return None
    if not isinstance(snapshot, dict):
        raise CollectionError(409, 'PRACTICE_SNAPSHOT_MISSING', '这次旧作答缺少出题时的题版快照，请使用手动收藏核对原题。')
    current = question_snapshot(conn, row['question_version_id'])
    # Existing variant revocation promises to finish already submitted work.
    # Only that worker path may ignore approval flags; content, key, ownership
    # and objective must still match the original presentation exactly.
    ignored = {'approval', 'question_approval'} if allow_retired else set()
    if {k:v for k,v in snapshot.items() if k not in ignored} != {k:v for k,v in current.items() if k not in ignored}:
        raise CollectionError(409, 'PRACTICE_VERSION_CHANGED', '出题时的题版已变化，请保留原记录并联系家长核对。')
    return snapshot


def collection_preview(conn, learner_id, attempt_id):
    from .textbooks import practice_scope
    row = conn.execute(
        'SELECT a.*,ti.question_version_id,ts.mode AS session_mode,g.id AS grade_id,g.outcome,g.feedback '
        'FROM attempts a JOIN test_items ti ON ti.id=a.test_item_id '
        'JOIN test_sessions ts ON ts.id=ti.session_id '
        'LEFT JOIN grade_versions g ON g.id=(SELECT gg.id FROM grade_versions gg '
        'WHERE gg.attempt_id=a.id ORDER BY gg.created_at DESC,gg.rowid DESC LIMIT 1) '
        'WHERE a.id=? AND a.learner_id=? AND ti.learner_id=?', (attempt_id, learner_id, learner_id)).fetchone()
    if not row:
        raise CollectionError(404, 'ATTEMPT_NOT_FOUND', '作答不存在')
    if row['status'] != 'graded' or row['outcome'] not in ('incorrect', 'partial'):
        raise CollectionError(409, 'PRACTICE_NOT_COLLECTIBLE', '仅已判分的错答或部分正确作答可以在此确认收藏。')
    snapshot = frozen_question(conn, row['test_item_id'], required=True)
    if snapshot['approval'] != 'approved' or snapshot['question_approval'] != 'approved':
        raise CollectionError(409, 'PRACTICE_VERSION_CHANGED', '题版已停用，请先核对。')
    content = json_loads(snapshot['content_json'], {})
    preview = {'attempt_id': attempt_id, 'test_item_id': row['test_item_id'], 'learner_id': learner_id,
               'question_version_id': row['question_version_id'], 'question_sha256': fingerprint(snapshot),
               'question_text': content.get('prompt', ''), 'student_answer': row['raw_answer'],
               'submitted_at': row['submitted_at'], 'grade_id': row['grade_id'], 'outcome': row['outcome'],
               'feedback': row['feedback'], 'assistance': row['assistance'],
               'assessment_eligibility': bool(row['assessment_eligibility']), 'session_mode': row['session_mode'],
               'objective_id': snapshot['objective_id'], 'diagnosis': None,
               'textbook_scope': practice_scope(row['question_version_id'])}
    from .practice_response import response_fields
    preview.update(response_fields(content))
    return {**preview, 'preview_sha256': fingerprint(preview)}


def saved_review_choices(conn, learner_id, objective_id):
    rows = conn.execute(
        "SELECT m.id,m.content_json FROM mistake_entries m JOIN mistake_sources s ON s.entry_id=m.id "
        "AND s.learner_id=m.learner_id WHERE m.learner_id=? AND m.objective_id=? AND m.status='active' "
        "AND s.active=1 AND s.source_kind='test_attempt' ORDER BY m.created_at,m.id",
        (learner_id, objective_id)).fetchall()
    choices = []
    for row in rows:
        content = json_loads(row['content_json'], {})
        if content.get('source_kind') != 'frozen_practice_attempt':
            continue
        available = False
        try:
            snapshot = question_snapshot(conn, content['question_version_id'])
            available = (fingerprint(snapshot) == content['question_sha256']
                         and snapshot['approval'] == snapshot['question_approval'] == 'approved'
                         and snapshot['objective_id'] == objective_id
                         and (snapshot['visibility'] != 'private' or snapshot['learner_id'] == learner_id))
        except (CollectionError, KeyError):
            pass
        choices.append({'mistake_id': row['id'], 'question_version_id': content.get('question_version_id'),
                        'prompt': content.get('question_text', ''), 'attempt_id': content.get('attempt_id'),
                        'assistance': content.get('assistance'), 'textbook_scope': content.get('textbook_scope'),
                        'available': available})
    return choices


def workspace_state(conn, learner_id):
    row = conn.execute('SELECT * FROM practice_workspaces WHERE learner_id=?', (learner_id,)).fetchone()
    if not row:
        return {'learner_id': learner_id, 'revision': 0, 'book_id': None, 'chapter_id': '',
                'difficulty': 'auto', 'pool': 'initial', 'current_session_id': None, 'completed_ids': []}
    completed = conn.execute(
        "SELECT DISTINCT ti.question_version_id,r.difficulty FROM practice_rounds r JOIN test_items ti "
        "ON ti.practice_round_id=r.id AND ti.practice_round_generation=r.generation "
        "WHERE r.learner_id=? AND r.book_id=? AND r.chapter_id=? AND r.pool=? "
        "AND ti.learner_id=? AND ti.status='graded' ORDER BY ti.question_version_id",
        (learner_id, row['book_id'], row['chapter_id'], row['pool'], learner_id)).fetchall()
    # A reclassified question starts in its corrected tier's round. Keep its
    # original attempt and original round intact; restarting the new tier must
    # not remain blocked by a completed item in an old, different tier.
    from .practice_design import presentation
    completed_ids = []
    for item in completed:
        q = question(item['question_version_id'])
        if q and presentation(q).get('difficulty', q['difficulty']) != item['difficulty']:
            continue
        completed_ids.append(item['question_version_id'])
    return {**dict(row), 'completed_ids': completed_ids}


def check_workspace_revision(conn, learner_id, revision):
    state = workspace_state(conn, learner_id)
    if state['revision'] != revision:
        raise CollectionError(409, 'PRACTICE_WORKSPACE_CHANGED', '另一页面已更新练习进度，请读取最新进度后再操作。')
    return state


def workspace_current_item(conn, learner_id, state):
    return conn.execute('SELECT * FROM test_items WHERE session_id=? AND learner_id=? ORDER BY rowid LIMIT 1',
                        (state['current_session_id'], learner_id)).fetchone()


def release_workspace_item(conn, learner_id, state, discard):
    item = workspace_current_item(conn, learner_id, state)
    if item and item['status'] == 'grading_pending':
        raise CollectionError(409, 'PRACTICE_GRADING_PENDING', '作答已保存，正在判分；请先查看结果。')
    if item and item['status'] in ('reserved', 'presented'):
        if not discard:
            raise CollectionError(409, 'PRACTICE_ACTIVE_ITEM', '还有未完成的题目，请继续作答或明确跳过。')
        conn.execute("UPDATE test_items SET status='cancelled' WHERE id=?", (item['id'],))
        conn.execute("UPDATE test_sessions SET status='cancelled',completed_at=? WHERE id=?", (utc_now(), item['session_id']))


def update_workspace(conn, learner_id, body):
    from .textbooks import learning_scope
    state = check_workspace_revision(conn, learner_id, body.expected_revision)
    curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
    try:
        book, chapter = learning_scope(curriculum, body.book_id, body.chapter_id or None)
    except ValueError:
        raise CollectionError(422, 'TEXTBOOK_SCOPE_INVALID', '请选择当前年级的课本和章节。')
    changed_scope = (state['book_id'], state['chapter_id'], state['pool']) != (book['id'], chapter['id'], body.pool)
    if changed_scope or body.restart_round:
        release_workspace_item(conn, learner_id, state, body.discard_current)
    elif body.discard_current:
        raise CollectionError(422, 'PRACTICE_DISCARD_SCOPE_REQUIRED', '跳过当前题请使用取消测验入口。')
    if body.restart_round:
        if body.pool == 'reserve':
            raise CollectionError(409, 'PRACTICE_RESERVE_NO_RESTART', '已见备用题不能重置为未见题。')
        level = body.difficulty
        if level == 'auto':
            level = learner_guidance(conn, learner_id).get(book['id'] + '|' + chapter['id'], {}).get('difficulty', 'easy')
        conn.execute("UPDATE practice_rounds SET generation=generation+1 WHERE learner_id=? AND book_id=? "
                     "AND chapter_id=? AND pool=? AND difficulty IN (?, 'starter')",
                     (learner_id, book['id'], chapter['id'], body.pool, level))
    session = None if changed_scope or body.restart_round else state['current_session_id']
    conn.execute('INSERT INTO practice_workspaces(learner_id,book_id,chapter_id,difficulty,pool,current_session_id,revision,updated_at) '
                 'VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(learner_id) DO UPDATE SET book_id=excluded.book_id,chapter_id=excluded.chapter_id,'
                 'difficulty=excluded.difficulty,pool=excluded.pool,current_session_id=excluded.current_session_id,'
                 'revision=excluded.revision,updated_at=excluded.updated_at',
                 (learner_id, book['id'], chapter['id'], body.difficulty, body.pool, session, state['revision'] + 1, utc_now()))
    return workspace_state(conn, learner_id)


def prepare_workspace_session(conn, learner_id, body):
    state = check_workspace_revision(conn, learner_id, body.workspace_revision)
    if not state['revision'] or (body.textbook_book_id, body.textbook_chapter_id or '') != (state['book_id'], state['chapter_id']):
        raise CollectionError(409, 'PRACTICE_WORKSPACE_SCOPE_CHANGED', '请先读取并确认当前练习范围。')
    release_workspace_item(conn, learner_id, state, body.replace_current)
    if body.card_id:
        return state, None
    info = metadata(body.question_version_id)
    pool = 'reserve' if info and info.get('reserve') else 'initial'
    if pool != state['pool']:
        raise CollectionError(409, 'PRACTICE_POOL_CHANGED', '题目与当前题池不一致，请刷新进度。')
    level = info['difficulty'] if info else 'starter'
    conn.execute('INSERT OR IGNORE INTO practice_rounds(id,learner_id,book_id,chapter_id,pool,difficulty) VALUES (?,?,?,?,?,?)',
                 (new_id('round'), learner_id, state['book_id'], state['chapter_id'], pool, level))
    round_row = conn.execute('SELECT * FROM practice_rounds WHERE learner_id=? AND book_id=? AND chapter_id=? AND pool=? AND difficulty=?',
                             (learner_id, state['book_id'], state['chapter_id'], pool, level)).fetchone()
    if conn.execute("SELECT 1 FROM test_items WHERE practice_round_id=? AND practice_round_generation=? "
                    "AND question_version_id=? AND status='graded'", (round_row['id'], round_row['generation'], body.question_version_id)).fetchone():
        raise CollectionError(409, 'PRACTICE_ROUND_ITEM_COMPLETED', '本轮已练过这道题，请选择下一题或明确再练一轮。')
    return state, round_row


def attach_workspace_session(conn, learner_id, state, round_row, session_id, item_id):
    if round_row:
        conn.execute('UPDATE test_items SET practice_round_id=?,practice_round_generation=? WHERE id=?',
                     (round_row['id'], round_row['generation'], item_id))
    conn.execute('UPDATE practice_workspaces SET current_session_id=?,revision=revision+1,updated_at=? WHERE learner_id=?',
                 (session_id, utc_now(), learner_id))
    return workspace_state(conn, learner_id)


def arithmetic(expression: str) -> Fraction:
    """Small rational arithmetic only; never eval repository verifier strings."""
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / right
        raise ValueError('unsupported independent arithmetic check')
    if len(expression) > 300: raise ValueError('check too long')
    return visit(ast.parse(expression, mode='eval').body)


@lru_cache(maxsize=1)
def bank() -> dict:
    payload = BANK_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != BANK_SHA256:
        raise ValueError('question bank changed: repeat content review before publication')
    questions = json.loads(payload)['questions']
    return {q['id']: q for q in questions}


def placement(version_id: str):
    item = question(version_id)
    return {k: item[k] for k in ('book_id', 'chapter_id')} if item else None


def question(version_id: str):
    if version_id.startswith('family-chapter-'):
        from .chapter_practice import bank as chapter_bank
        return chapter_bank().get(version_id)
    item = bank().get(version_id)
    if item is None and version_id.startswith('family-reserve-'):
        from .reserve_practice import bank as reserve_bank
        item = reserve_bank().get(version_id)
    return item


def questions(version_ids):
    """Bulk `question()`: each authored bank is loaded and verified once.

    The chapter and reserve banks are deliberately uncached, so asking
    `question` per version re-reads every bank file hundreds of times.
    """
    ids = list(version_ids)
    chapters, reserve = {}, {}
    if any(version_id.startswith('family-chapter-') for version_id in ids):
        from .chapter_practice import bank as chapter_bank
        chapters = chapter_bank()
    if any(version_id.startswith('family-reserve-') for version_id in ids):
        from .reserve_practice import bank as reserve_bank
        reserve = reserve_bank()
    core = bank()
    return {version_id: chapters.get(version_id) or core.get(version_id) or reserve.get(version_id)
            for version_id in ids}


def banks():
    """Every authored question version, each bank file read and verified once.

    Callers that need the whole inventory (the coverage reports, for example)
    share one dict instead of asking each module to load its bank again.
    """
    from .chapter_practice import bank as chapter_bank
    from .reserve_practice import bank as reserve_bank
    return bank() | chapter_bank() | reserve_bank()


def metadata_for(version_id: str, item):
    if not item: return None
    if version_id.startswith('family-chapter-'):
        from .chapter_practice import metadata as chapter_metadata
        return chapter_metadata(item)
    if version_id.startswith('family-reserve-'):
        from .reserve_practice import metadata as reserve_metadata
        return reserve_metadata(item)
    from .practice_design import presentation
    return {k: item[k] for k in ('title', 'difficulty', 'extension', 'source')} | presentation(item)


def metadata(version_id: str):
    return metadata_for(version_id, question(version_id))


def numeric_answer(raw: str, units: list[str]) -> Fraction | None:
    value = unicodedata.normalize('NFKC', raw).strip().replace('−', '-').replace('﹣', '-')
    for unit in sorted(units, key=len, reverse=True):
        unit = unicodedata.normalize('NFKC', unit)
        if unit and value.casefold().endswith(unit.casefold()):
            value = value[:-len(unit)].strip()
            break
    # No equations, arbitrary expressions, thousands grouping or mismatched units.
    if len(value) > 80 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*/\s*[+-]?\d+)?', value):
        return None
    try:
        return Fraction(value.replace(' ', ''))
    except (ValueError, ZeroDivisionError):
        return None


def grade_numeric(raw: str, key: dict) -> str:
    value = numeric_answer(raw, key.get('units', []))
    target = numeric_answer(str(key.get('numeric_answer', '')), [])
    return 'undetermined' if target is None else 'correct' if value is not None and value == target else 'incorrect'


def guidance(records: list[dict]) -> dict:
    """Four distinct independent correct answers at one level permit progression.

    The stored attempt history survives reload and profile changes. A repeated
    question counts once within a streak. Errors/hints reset that evidence, so
    deliberate relearning can recover even with a small bank. Manual difficulty
    changes do not raise the automatic recommendation from a single answer.
    """
    level, streak, streak_level = 0, 0, 0
    counted = set()
    reason = '先从简单题开始；同一难度连续独立答对 4 道不同题后，尝试下一档。'
    for record in records:
        if record['outcome'] not in ('correct', 'incorrect', 'partial'): continue
        difficulty = LEVELS.index(record['difficulty'])
        independent = record['assistance'] == 'none' and bool(record['assessment_eligibility'])
        if record['outcome'] != 'correct' or not independent:
            level = max(0, min(level, difficulty) - 1)
            streak = 0
            streak_level = level
            counted.clear()
            reason = '刚才做错或用了提示，先降低一档巩固，再慢慢进阶。' if level else '先用简单题巩固，独立答对后再进阶。'
        elif difficulty >= level:
            if difficulty != streak_level:
                streak, streak_level = 0, difficulty
                counted.clear()
            if record['question_version_id'] in counted:
                continue
            counted.add(record['question_version_id'])
            streak += 1
            if streak >= AUTO_PROMOTION_CORRECT:
                level = min(difficulty + 1, len(LEVELS)-1)
                reason = ('同一难度已连续独立答对 4 道不同题，可以尝试' + LABELS[LEVELS[level]] + '题。'
                          if difficulty < len(LEVELS)-1 else '挑战题已连续独立答对 4 道不同题，继续巩固或选择其他章节。')
                if difficulty < len(LEVELS)-1:
                    streak, streak_level = 0, level
                    counted.clear()
            else:
                reason = f'{LABELS[LEVELS[difficulty]]}题已连续独立答对 {streak} / {AUTO_PROMOTION_CORRECT} 道不同题；再答对 {AUTO_PROMOTION_CORRECT - streak} 道后尝试进阶。' if difficulty < len(LEVELS)-1 else '继续保持自己的节奏。'
        else:
            # Easier practice does not count toward a harder-level streak.
            streak, streak_level = 0, level
            counted.clear()
            reason = f'回到{LABELS[LEVELS[level]]}题后，重新累计连续独立答对的不同题。'
    return {'difficulty': LEVELS[level], 'streak': streak, 'reason': reason}


def learner_guidance(conn, learner_id: str, questions=None) -> dict:
    """Difficulty guidance per book/chapter; `questions` reuses a bulk caller's load."""
    from .practice_design import presentation
    records = conn.execute(
        "SELECT ti.question_version_id,a.assistance,a.assessment_eligibility,g.outcome "
        "FROM attempts a JOIN test_items ti ON ti.id=a.test_item_id "
        "JOIN grade_versions g ON g.id=(SELECT gg.id FROM grade_versions gg WHERE gg.attempt_id=a.id ORDER BY gg.created_at DESC,gg.rowid DESC LIMIT 1) "
        "WHERE a.learner_id=? AND a.status='graded' ORDER BY a.submitted_at,a.rowid", (learner_id,)).fetchall()
    scoped = {}
    for row in records:
        version_id = row['question_version_id']
        q = question(version_id) if questions is None else questions.get(version_id)
        if not q: continue
        for key in (q['book_id'] + '|', q['book_id'] + '|' + q['chapter_id']):
            scoped.setdefault(key, []).append({**dict(row), 'difficulty': presentation(q).get('difficulty', q['difficulty'])})
    return {key: guidance(items) for key, items in scoped.items()}


def install(db) -> dict:
    """Add immutable shared questions in one transaction, retaining all prior data."""
    from .textbooks import learning_scope
    questions = list(bank().values())
    if len({q['prompt'] for q in questions}) != len(questions): raise ValueError('duplicate prompts')
    for q in questions:
        if q['difficulty'] not in LEVELS or (q['grade'], q['chapter_id']) not in OBJECTIVES:
            raise ValueError('unreviewed objective or difficulty')
        learning_scope(f"math-g{q['grade']}-v1", q['book_id'], q['chapter_id'])
        if arithmetic(q['independent_check']) != Fraction(q['answer']):
            raise ValueError('answer/check mismatch: ' + q['id'])
    added = 0
    with db.session(write=True) as conn:
        now = utc_now()
        for (grade, chapter), title in OBJECTIVES.items():
            kp = f'kp-family-word-g{grade}-ch{chapter}'
            objective = f'objective-family-word-math-g{grade}-ch{chapter}'
            conn.execute('INSERT OR IGNORE INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)', (kp, f'math-g{grade}-v1', kp, title, now))
            conn.execute('INSERT OR IGNORE INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)', (objective, kp, objective, title, now))
        for q in questions:
            qid = q['id'].removesuffix('-v1')
            objective = f"objective-family-word-math-g{q['grade']}-ch{q['chapter_id']}"
            content = json_dumps({'prompt': q['prompt'], 'hint': q['hint'], 'input_type': 'text', 'source': q['source'], 'practice_bank': 'family-word-v1'})
            units = list(q['units'])
            for name, aliases in {'米':['m'], '厘米':['cm'], '千米':['km'], '℃':['摄氏度','度']}.items():
                if name in units: units += aliases
            key = json_dumps({'numeric_answer': q['answer'], 'units': units, 'explanation': q['explanation']})
            old = conn.execute('SELECT content_json,answer_key_json,validator_version,question_id FROM question_versions WHERE id=?', (q['id'],)).fetchone()
            if old:
                if tuple(old) != (content, key, 'numeric-answer-v1', qid):
                    raise ValueError('existing frozen question differs: ' + q['id'])
                existing = conn.execute('SELECT objective_id,visibility,approval FROM questions WHERE id=?', (qid,)).fetchone()
                if tuple(existing) != (objective, 'shared', 'approved'): raise ValueError('existing question differs')
                continue
            conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,'shared','approved',?,?)", (qid, objective, now))
            conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,1,?,?,'numeric-answer-v1','approved',?)", (q['id'], qid, content, key, now))
            added += 1
        if added:
            conn.execute("INSERT INTO audit_events(id,account_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES ('family-word-v1-install','family-pilot-setup','install_curated_word_problems','question_set','family-word-v1','applied',?,?)", (json_dumps({'added':added,'bank_sha256':BANK_SHA256,'teacher_reviewed':False,'external_model_calls':0}), now))
    return {'added':added,'bank_questions':len(questions),'sha256':BANK_SHA256}
