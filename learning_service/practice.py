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

from .db import json_dumps, json_loads, utc_now

BANK_PATH = Path(__file__).parent / 'data/family_word_problems_v1.json'
BANK_SHA256 = '38e0903024ed9c402a8c66e8b02a3afd3e304ad55913fbdb0572a16589d211ef'
LEVELS = ('easy', 'normal', 'hard')
AUTO_PROMOTION_CORRECT = 4
LABELS = dict(zip(LEVELS, ('简单', '正常', '困难')))
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
    item = bank().get(version_id)
    if item is None and version_id.startswith('family-reserve-'):
        from .reserve_practice import bank as reserve_bank
        item = reserve_bank().get(version_id)
    return item


def metadata(version_id: str):
    item = question(version_id)
    if not item: return None
    if version_id.startswith('family-reserve-'):
        from .reserve_practice import metadata as reserve_metadata
        return reserve_metadata(item)
    return {k: item[k] for k in ('title', 'difficulty', 'extension', 'source')}


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
                level = min(difficulty + 1, 2)
                reason = ('同一难度已连续独立答对 4 道不同题，可以尝试' + LABELS[LEVELS[level]] + '题。'
                          if difficulty < 2 else '困难题已连续独立答对 4 道不同题，继续巩固或选择其他章节。')
                if difficulty < 2:
                    streak, streak_level = 0, level
                    counted.clear()
            else:
                reason = f'{LABELS[LEVELS[difficulty]]}题已连续独立答对 {streak} / {AUTO_PROMOTION_CORRECT} 道不同题；再答对 {AUTO_PROMOTION_CORRECT - streak} 道后尝试进阶。' if difficulty < 2 else '继续保持自己的节奏。'
        else:
            # Easier practice does not count toward a harder-level streak.
            streak, streak_level = 0, level
            counted.clear()
            reason = f'回到{LABELS[LEVELS[level]]}题后，重新累计连续独立答对的不同题。'
    return {'difficulty': LEVELS[level], 'streak': streak, 'reason': reason}


def learner_guidance(conn, learner_id: str) -> dict:
    records = conn.execute(
        "SELECT ti.question_version_id,a.assistance,a.assessment_eligibility,g.outcome "
        "FROM attempts a JOIN test_items ti ON ti.id=a.test_item_id "
        "JOIN grade_versions g ON g.id=(SELECT gg.id FROM grade_versions gg WHERE gg.attempt_id=a.id ORDER BY gg.created_at DESC,gg.rowid DESC LIMIT 1) "
        "WHERE a.learner_id=? AND a.status='graded' ORDER BY a.submitted_at,a.rowid", (learner_id,)).fetchall()
    scoped = {}
    for row in records:
        q = question(row['question_version_id'])
        if not q: continue
        for key in (q['book_id'] + '|', q['book_id'] + '|' + q['chapter_id']):
            scoped.setdefault(key, []).append({**dict(row), 'difficulty': q['difficulty']})
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
