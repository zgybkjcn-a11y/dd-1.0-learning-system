"""Curated content, independent answer checks, learner isolation and difficulty transitions."""
import json
from fractions import Fraction
from collections import Counter

import pytest
from learning_service.practice import bank, arithmetic, install, guidance, numeric_answer, grade_numeric
from test_family_math import family


def test_curated_bank_independent_checks_and_scope(family):
    _, db, api, headers = family
    questions = bank()
    assert len(questions) == 60
    assert set(Counter((q['grade'],q['chapter_id'],q['difficulty']) for q in questions.values()).values()) == {4}
    for q in questions.values():
        assert arithmetic(q['independent_check']) == Fraction(q['answer'])
        assert q['hint'] and q['explanation'] and len(q['prompt']) > 30
        assert not q['review']['teacher_reviewed']
    before = {}
    with db.session() as c:
        for t in ('questions','question_versions','accounts','learners','identity_bindings'):
            before[t] = [tuple(r) for r in c.execute('SELECT * FROM '+t)]
    assert install(db)['added'] == 60
    assert install(db)['added'] == 0
    with db.session() as c:
        for t, rows in before.items():
            now = {tuple(r) for r in c.execute('SELECT * FROM '+t)}
            assert set(rows) <= now
    for grade, count in ((2,44),(7,30)):
        h = {**headers, 'X-Learner-Id':f'family-g{grade}'}
        choices = api.get('/api/v1/question-choices',headers=h).json()
        assert len(choices['items']) == count
        assert 'numeric_answer' not in json.dumps(choices) and 'explanation' not in json.dumps(choices)
        for item in choices['items']:
            if item['practice']:
                q = questions[item['question_version_id']]
                assert q['grade'] == grade
                response = api.post('/api/v1/test-sessions', headers=h, json={'question_version_id':q['id'], 'textbook_book_id':q['book_id'], 'textbook_chapter_id':q['chapter_id']})
                assert response.status_code == 201
                assert q['explanation'] not in response.text
                assert response.json()['items'][0]['prompt'] == q['prompt']
                assert api.post('/api/v1/test-sessions',headers=h,json={'question_version_id':q['id'],'textbook_book_id':q['book_id'],'textbook_chapter_id':'1'}).status_code == 422
    q=next(q for q in questions.values() if q['grade']==7)
    assert api.post('/api/v1/test-sessions',headers={**headers,'X-Learner-Id':'family-g2'},json={'question_version_id':q['id']}).status_code == 403
    with db.session() as c:
        assert c.execute('SELECT count(*) FROM provider_calls').fetchone()[0]==0


def test_numeric_answers_accept_equivalence_not_wrong_units_or_code():
    for raw in ['12', '12.0', '１２', '+12', '24/2', '12 ℃', '12摄氏度']:
        assert grade_numeric(raw,{'numeric_answer':'12','units':['℃','摄氏度']})=='correct'
    for raw in ['12米','12+0','x=12','1/0','12/1/1','1e999','__import__("os")','-12','1 2']:
        assert grade_numeric(raw,{'numeric_answer':'12','units':['℃']})=='incorrect'
    assert grade_numeric('−7米',{'numeric_answer':'-7','units':['米']})=='correct'
    with pytest.raises(ValueError): arithmetic('__import__("os")')


def test_progression_uses_different_independent_questions_and_consolidates():
    def record(i,level='easy',outcome='correct',assistance='none'):
        return dict(question_version_id=str(i),difficulty=level,outcome=outcome,assistance=assistance,assessment_eligibility=assistance=='none')
    assert guidance([])['difficulty']=='easy'
    for count in (1, 2, 3):
        result = guidance([record(i) for i in range(count)])
        assert result['difficulty']=='easy'
        assert f'{count} / 4' in result['reason']
        assert f'再答对 {4-count} 道' in result['reason']
    assert guidance([record(1)]*8)['difficulty']=='easy'
    easy = [record(i) for i in range(4)]
    assert guidance(easy)['difficulty']=='normal'
    for count in (1, 2, 3):
        assert guidance(easy+[record(i+4,'normal') for i in range(count)])['difficulty']=='normal'
    normal = [record(i+4,'normal') for i in range(4)]
    hard = easy + normal
    assert guidance(hard)['difficulty']=='hard'
    assert guidance(hard+[record(8,'hard',assistance='hint')])['difficulty']=='normal'
    assert guidance(hard+[record(8,'hard',outcome='incorrect'),record(9,'normal',outcome='incorrect')])['difficulty']=='easy'
    # A mistaken/hinted attempt breaks the streak, but relearning four distinct
    # questions from the same finite bank must remain able to progress.
    for failed in (record(3,outcome='incorrect'), record(3,assistance='hint')):
        history = easy[:3] + [failed]
        assert guidance(history)['streak']==0
        for count in (1, 2, 3):
            assert guidance(history+easy[:count])['difficulty']=='easy'
        assert guidance(history+easy)['difficulty']=='normal'
    # Trying a harder tier manually once must not bypass the four-answer rule.
    assert guidance([record(10,'hard')])['difficulty']=='easy'
    assert guidance([record(10+i,'normal') for i in range(3)])['difficulty']=='easy'
    assert guidance([record(10+i,'normal') for i in range(4)])['difficulty']=='hard'
    # Successes at different tiers are not combined into a four-answer streak.
    assert guidance(easy[:3]+[record(10,'normal')]+easy[:1])['streak']==1
    assert guidance(hard+[record(10+i,'hard') for i in range(8)])['difficulty']=='hard'
