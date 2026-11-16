"""Today's study path: ordering, budget, verbatim facts and zero writes."""
import hashlib
import json

import pytest

from learning_service.db import utc_now
from learning_service.practice import guidance
from test_family_math import family

PATH = '/api/v1/study-path'


def headers_for(headers, grade):
    return {**headers, 'X-Learner-Id': f'family-g{grade}'}


def choices(client, headers, grade):
    return client.get('/api/v1/question-choices', headers=headers_for(headers, grade)).json()


def scoped_choice(data):
    return next(item for item in data['items'] if item.get('textbook_scope'))


def set_scope(client, headers, grade, book, chapter, revision=0):
    return client.put('/api/v1/practice-workspace', headers=headers_for(headers, grade),
                      json={'expected_revision': revision, 'book_id': book, 'chapter_id': chapter,
                            'difficulty': 'auto', 'pool': 'initial'})


def start_item(client, headers, grade, question_version_id, book, chapter, revision):
    return client.post('/api/v1/test-sessions', headers=headers_for(headers, grade),
                       json={'question_version_id': question_version_id,
                             'textbook_book_id': book, 'textbook_chapter_id': chapter or None,
                             'workspace_revision': revision})


def add_card(db, learner_id, objective_id, *, state='review', due='2000-01-01T00:00:00Z', tag=''):
    with db.session(write=True) as conn:
        point = conn.execute('SELECT o.knowledge_point_id FROM review_objectives o WHERE o.id=?',
                             (objective_id,)).fetchone()[0]
        conn.execute('INSERT INTO review_cards(id,learner_id,knowledge_point_id,objective_id,state,stage,due_at,'
                     'timezone_snapshot,scheduler_version,revision,created_at,updated_at) '
                     'VALUES (?,?,?,?,?,0,?,?,?,1,?,?)',
                     (f'card-{tag}', learner_id, point, objective_id, state, due,
                      'Asia/Shanghai', 'synthetic-scheduler', utc_now(), utc_now()))


def add_extra_objectives(db, curriculum, count):
    objectives = []
    with db.session(write=True) as conn:
        for index in range(count):
            point, objective = f'kp-test-{index}', f'objective-test-{index}'
            conn.execute('INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)',
                         (point, curriculum, point, f'合成知识点{index}', utc_now()))
            conn.execute('INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)',
                         (objective, point, objective, f'合成目标{index}', utc_now()))
            objectives.append(objective)
    return objectives


def fingerprint(db):
    with db.session() as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result = {}
        for table in tables:
            rows = [tuple(row) for row in conn.execute(f'SELECT * FROM "{table}"')]
            result[table] = hashlib.sha256(repr(rows).encode()).hexdigest()
    return result


def stable(payload):
    return json.dumps({key: value for key, value in payload.items() if key != 'as_of'},
                      ensure_ascii=False, sort_keys=True)


def test_resume_then_review_then_practice_and_scope(family):
    _, db, client, headers = family
    data = choices(client, headers, 2)
    first = scoped_choice(data)
    scope = first['textbook_scope']
    workspace = set_scope(client, headers, 2, scope['book_id'], scope['chapter_id']).json()
    assert workspace['revision'] == 1
    session = start_item(client, headers, 2, first['question_version_id'],
                         scope['book_id'], scope['chapter_id'], workspace['revision'])
    assert session.status_code == 201
    add_card(db, 'family-g2', data['objectives'][0]['id'], tag='g2-first')

    result = client.get(PATH, headers=headers_for(headers, 2)).json()
    kinds = [step['kind'] for step in result['steps']]
    assert kinds == ['resume', 'review', 'practice']
    assert result['total_minutes'] == 5 + 4 + 10
    assert result['scope']['book_id'] == scope['book_id']
    assert result['scope']['chapter_id'] == scope['chapter_id']
    assert result['notice'].startswith('按已有记录给出建议顺序')


def test_review_step_matches_review_tasks_exactly(family):
    _, db, client, headers = family
    data = choices(client, headers, 2)
    add_card(db, 'family-g2', data['objectives'][0]['id'], state='relearning', due='2000-01-01T00:00:00Z', tag='a')
    add_card(db, 'family-g2', data['objectives'][1]['id'], state='review', due='2000-01-02T00:00:00Z', tag='b')

    tasks = client.get('/api/v1/review-tasks', headers=headers_for(headers, 2)).json()
    result = client.get(PATH, headers=headers_for(headers, 2)).json()
    review = next(step for step in result['steps'] if step['kind'] == 'review')
    assert review['count'] == len(tasks['items']) == 2
    assert review['earliest_due'] == tasks['items'][0]['due_at']
    assert review['minutes'] == 8


def test_practice_reason_is_the_guidance_text_verbatim(family):
    _, _, client, headers = family
    data = choices(client, headers, 2)
    first = scoped_choice(data)
    scope = first['textbook_scope']
    set_scope(client, headers, 2, scope['book_id'], scope['chapter_id'])

    expected = guidance([])
    result = client.get(PATH, headers=headers_for(headers, 2)).json()
    practice = next(step for step in result['steps'] if step['kind'] == 'practice')
    assert practice['difficulty'] == expected['difficulty'] == 'easy'
    assert practice['reason'] == expected['reason']


def test_reading_step_when_the_scope_has_no_installed_questions(family):
    _, _, client, headers = family
    set_scope(client, headers, 2, 'math-g2-upper', '1')
    result = client.get(PATH, headers=headers_for(headers, 2)).json()
    assert [step['kind'] for step in result['steps']] == ['reading']
    assert result['steps'][0]['printed_page'] == 1
    assert result['steps'][0]['scope']['chapter_title'] == '一 分类与整理'


def test_choose_step_without_a_workspace_or_with_a_stale_book(family):
    _, db, client, headers = family
    result = client.get(PATH, headers=headers_for(headers, 2)).json()
    assert [step['kind'] for step in result['steps']] == ['choose']
    assert result['steps'][0]['reason'] == '还没有选择课本和章节。'

    with db.session(write=True) as conn:
        conn.execute('INSERT INTO practice_workspaces(learner_id,book_id,chapter_id,difficulty,pool,current_session_id,'
                     'revision,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                     ('family-g2', 'book-removed-in-new-edition', '', 'auto', 'initial', None, 1, utc_now()))
    result = client.get(PATH, headers=headers_for(headers, 2)).json()
    assert [step['kind'] for step in result['steps']] == ['choose']
    assert '已变化' in result['steps'][0]['reason']


def test_budget_moves_overflow_to_next_time(family):
    _, db, client, headers = family
    data = choices(client, headers, 2)
    first = scoped_choice(data)
    scope = first['textbook_scope']
    set_scope(client, headers, 2, scope['book_id'], scope['chapter_id'])
    for index, objective in enumerate(add_extra_objectives(db, 'math-g2-v1', 5)):
        add_card(db, 'family-g2', objective, tag=f'extra-{index}')

    result = client.get(PATH, headers=headers_for(headers, 2)).json()
    assert [step['kind'] for step in result['steps']] == ['review']
    assert result['steps'][0]['minutes'] == 20
    assert [step['kind'] for step in result['next_time']] == ['practice']
    assert result['total_minutes'] == 20
    assert sum(step['minutes'] for step in result['steps']) == result['total_minutes']


def test_read_is_deterministic_and_writes_nothing(family):
    _, db, client, headers = family
    data = choices(client, headers, 2)
    first = scoped_choice(data)
    scope = first['textbook_scope']
    workspace = set_scope(client, headers, 2, scope['book_id'], scope['chapter_id']).json()
    start_item(client, headers, 2, first['question_version_id'],
               scope['book_id'], scope['chapter_id'], workspace['revision'])
    add_card(db, 'family-g2', data['objectives'][0]['id'], tag='zero-write')

    before = fingerprint(db)
    with db.session() as conn:
        audits = conn.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]
    first_read = client.get(PATH, headers=headers_for(headers, 2)).json()
    second_read = client.get(PATH, headers=headers_for(headers, 2)).json()
    assert fingerprint(db) == before
    assert stable(first_read) == stable(second_read)
    with db.session() as conn:
        assert conn.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM learning_events').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0] == audits


def test_resume_disappears_once_the_item_is_graded(family):
    _, db, client, headers = family
    data = choices(client, headers, 2)
    first = scoped_choice(data)
    scope = first['textbook_scope']
    workspace = set_scope(client, headers, 2, scope['book_id'], scope['chapter_id']).json()
    start_item(client, headers, 2, first['question_version_id'],
               scope['book_id'], scope['chapter_id'], workspace['revision'])
    assert client.get(PATH, headers=headers_for(headers, 2)).json()['steps'][0]['kind'] == 'resume'

    with db.session(write=True) as conn:
        conn.execute("UPDATE test_items SET status='graded' WHERE learner_id='family-g2'")
    kinds = [step['kind'] for step in client.get(PATH, headers=headers_for(headers, 2)).json()['steps']]
    assert 'resume' not in kinds


def test_placements_load_the_chapter_bank_once(family, monkeypatch):
    """The chapter bank is uncached by design, so one request must ask it once.

    Counting the placements per version made this endpoint reload and re-verify
    the whole bank for every approved question (about four seconds on the family
    database), which kept the page's textbook selector disabled while loading.
    """
    from learning_service import chapter_practice

    _, db, client, headers = family
    chapter_practice.install(db, 'math')
    sample = next(q for q in chapter_practice.bank('math').values() if q['book_id'].startswith('math-g2'))
    calls = []
    original = chapter_practice.bank

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(chapter_practice, 'bank', counting)
    assert set_scope(client, headers, 2, sample['book_id'], sample['chapter_id']).status_code == 200
    data = client.get(PATH, headers=headers_for(headers, 2)).json()
    assert [step['kind'] for step in data['steps']] == ['practice']
    assert len(calls) <= 1


def test_untrusted_caller_is_rejected(family):
    _, _, client, _ = family
    response = client.get(PATH)
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'UNTRUSTED_CONTEXT'
