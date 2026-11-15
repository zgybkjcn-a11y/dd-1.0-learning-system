"""Read-only today's study path: composes existing study facts, never mastery.

Every statement here is a SELECT. The path only reorders facts that the
review, practice and textbook endpoints already expose, and it keeps their
wording verbatim so a different rule cannot appear in two places.
"""
from __future__ import annotations

from .db import utc_now

REVIEW_MINUTES_PER_CARD = 4
REVIEW_MAX_MINUTES = 20
TOTAL_MINUTES = 25
STEP_MINUTES = {'resume': 5, 'practice': 10, 'reading': 5, 'choose': 1}
NOTICE = '按已有记录给出建议顺序，不代表掌握程度；数据来自本机学习记录。'


class PathError(ValueError):
    pass


def _scope(conn, learner_id, curriculum):
    """Current practice scope, or (None, stale) when it no longer resolves."""
    from .textbooks import catalogue

    row = conn.execute(
        'SELECT book_id,chapter_id,current_session_id,revision FROM practice_workspaces WHERE learner_id=?',
        (learner_id,)).fetchone()
    if not row:
        return None, False
    books = catalogue(curriculum)
    book = next((b for b in books if b['id'] == row['book_id']), None)
    if not book:
        return None, True
    if row['chapter_id'] and not any(c['id'] == row['chapter_id'] for c in book['chapters']):
        return None, True
    chapter = next((c for c in book['chapters'] if c['id'] == row['chapter_id']), None)
    return {
        'book_id': book['id'], 'book_title': book['title'], 'subject': book['subject'],
        'chapter_id': row['chapter_id'],
        'chapter_title': chapter['title'] if chapter else '整本书',
        'printed_page': chapter['printed_page'] if chapter else book['chapters'][0]['printed_page'],
    }, False


def _resume(conn, learner_id):
    return conn.execute(
        'SELECT ti.id AS test_item_id,ti.status,ti.session_id,ti.question_version_id '
        'FROM practice_workspaces w JOIN test_sessions s ON s.id=w.current_session_id '
        'JOIN test_items ti ON ti.session_id=s.id AND ti.learner_id=w.learner_id '
        "WHERE w.learner_id=? AND ti.status IN ('reserved','presented') "
        'ORDER BY ti.rowid LIMIT 1',
        (learner_id,)).fetchone()


def _due_cards(conn, learner_id, now):
    return conn.execute(
        'SELECT c.id,c.state,c.due_at FROM review_cards c '
        'WHERE c.learner_id=? AND c.active=1 AND c.due_at<=? '
        "ORDER BY CASE c.state WHEN 'relearning' THEN 0 WHEN 'review' THEN 1 ELSE 2 END,"
        'c.due_at,c.id',
        (learner_id, now)).fetchall()


def _available(conn, learner_id, book_id, chapter_id):
    """Installed question versions placed in the given textbook scope."""
    from .practice import question
    from .textbooks import practice_scope

    rows = conn.execute(
        'SELECT v.id FROM question_versions v JOIN questions q ON q.id=v.question_id '
        'JOIN review_objectives o ON o.id=q.objective_id '
        'JOIN knowledge_points k ON k.id=o.knowledge_point_id '
        'JOIN learners l ON l.id=? AND l.curriculum_id=k.curriculum_id '
        "WHERE v.approval='approved' AND q.approval='approved' "
        'AND (q.visibility=? OR q.learner_id=?)',
        (learner_id, 'shared', learner_id)).fetchall()
    count = 0
    for row in rows:
        item = question(row['id'])
        placed = practice_scope(row['id']) or (item and {
            'book_id': item['book_id'], 'chapter_id': item['chapter_id']})
        if placed and placed['book_id'] == book_id and (not chapter_id or placed['chapter_id'] == chapter_id):
            count += 1
    return count


def _guidance(conn, learner_id, scope):
    from .practice import guidance, learner_guidance

    table = learner_guidance(conn, learner_id)
    key = scope['book_id'] + '|' + (scope['chapter_id'] or '')
    return table.get(key) or table.get(scope['book_id'] + '|') or guidance([])


def _step(kind, title, reason, minutes, **extra):
    return {'kind': kind, 'title': title, 'reason': reason, 'minutes': minutes,
            'enabled': True, **extra}


def compose(conn, learner_id, *, now=None):
    row = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()
    if not row:
        raise PathError('unknown learner')
    curriculum = row['curriculum_id']
    now = now or utc_now()
    scope, stale = _scope(conn, learner_id, curriculum)

    candidates = []
    resume = _resume(conn, learner_id)
    if resume and scope:
        candidates.append(_step(
            'resume', '继续上次练习', '上次还有一道题没有做完，先把这一道做完。',
            STEP_MINUTES['resume'],
            scope=scope, evidence=['practice_workspaces', 'test_items']))

    due = _due_cards(conn, learner_id, now)
    if due:
        minutes = min(REVIEW_MAX_MINUTES, REVIEW_MINUTES_PER_CARD * len(due))
        candidates.append(_step(
            'review', '到期复习', f'有 {len(due)} 张到期复习卡，先复习再学新的。',
            minutes, count=len(due), earliest_due=due[0]['due_at'],
            evidence=['review_cards']))

    if scope is None:
        candidates.append(_step(
            'choose', '先选课本和章节',
            '当前课本范围已变化，请重新选择。' if stale else '还没有选择课本和章节。',
            STEP_MINUTES['choose'], evidence=['practice_workspaces']))
    elif _available(conn, learner_id, scope['book_id'], scope['chapter_id']):
        advised = _guidance(conn, learner_id, scope)
        candidates.append(_step(
            'practice', '练习当前章节', advised['reason'], STEP_MINUTES['practice'],
            difficulty=advised['difficulty'], scope=scope,
            evidence=['question_versions', 'practice_guidance']))
    else:
        candidates.append(_step(
            'reading', '先读原页', '这一章还没有可练的题，先读原页，再回来试着说说。',
            STEP_MINUTES['reading'], scope=scope,
            printed_page=scope['printed_page'], evidence=['textbook_catalogue']))

    steps, next_time, total = [], [], 0
    for step in candidates:
        if not steps or total + step['minutes'] <= TOTAL_MINUTES:
            steps.append(step)
            total += step['minutes']
        else:
            next_time.append({key: step[key] for key in ('kind', 'title', 'reason')})

    return {'learner_id': learner_id, 'scope': scope, 'steps': steps,
            'next_time': next_time, 'total_minutes': total,
            'budget_minutes': TOTAL_MINUTES, 'notice': NOTICE, 'as_of': now}
