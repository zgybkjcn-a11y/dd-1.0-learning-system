"""Reviewed coverage must distinguish actual performances and solving actions."""
import json

import pytest

from learning_service import subject_coverage
from learning_service.chapter_practice import bank
from learning_service.practice import bank as initial


def rows(available_ids=None):
    ids=set(bank()) | set(initial()) if available_ids is None else set(available_ids)
    return {r['id']:r for g in (2,7) for r in subject_coverage.report(f'math-g{g}-v1',ids)['items']}


def task(point, name):
    return next(t for t in rows()[point]['tasks'] if t['id']==name)


def test_real_measurement_cannot_be_completed_by_given_number_calculations():
    for point, name in [('math-g2-upper:activity2:body','apply'),
                        ('math-g2-upper:4:estimate','apply'),
                        ('math-g2-upper:4:ruler','transfer'),
                        ('math-g7-upper:1:line','apply'),
                        ('math-g7-upper:6:angle','apply')]:
        t=task(point,name)
        assert t['assessment_mode']=='human' and t['family_count']==0 and t['status']!='configured'
        assert rows()[point]['manual_task']['automatically_graded'] is False
    t=task('math-g2-upper:activity2:body','distinguish')
    assert t['family_count']==3 and t['supporting_question_count']==4


def test_recognition_and_both_division_models_have_exact_mapping():
    assert task('math-g2-upper:1:compare','understand')['family_count']==1
    # Choosing an explanation cannot satisfy independent explanation.
    assert task('math-g2-upper:2:meaning','understand')['family_count']==0
    t=task('math-g2-upper:3:word','apply')
    assert t['status']=='configured' and t['family_count']==2 and t['question_count']==5
    assert 'family-chapter-math-g2-upper-3-depth-quotient-apply-a01955df4637-v1' in t['question_ids']


def test_same_solving_action_does_not_inflate_family_count():
    assert task('math-g7-upper:2:power','transfer')['family_count']==1
    assert task('math-g7-upper:6:bisect','transfer')['family_count']==2
    assert task('math-g7-upper:4:polynomial','apply')['family_count']==2
    assert task('math-g7-upper:1:absolute','transfer')['family_count']==2


def test_language_gap_mappings_match_the_question_and_keep_human_work_separate():
    for point in ('chinese-g2-upper:1:words','chinese-g2-upper:2:radical',
                  'chinese-g2-upper:4:dictionary','chinese-g2-upper:9:usage',
                  'chinese-g7-upper:1:poetry','chinese-g7-upper:2:evidence',
                  'english-g7-upper:1:alphabet','english-g7-upper:3:there',
                  'english-g7-upper:11:reading','english-g7-upper:14:be',
                  'english-g7-upper:14:can','english-g7-upper:15:context',
                  'english-g7-upper:16:entry','english-g7-upper:18:calendar'):
        result=task(point,'check')
        assert result['family_count']==1 and result['status']=='partial'
        assert any(question_id.startswith('family-chapter-') and 'subject_gaps-' in question_id
                   for question_id in result['question_ids'])
    assert task('chinese-g2-upper:3:comparison','check')['family_count']==1
    assert task('chinese-g2-upper:5:fable','check')['family_count']==1
    assert task('chinese-g7-upper:3:contrast','check')['family_count']==1
    assert task('chinese-g7-upper:4:structure','check')['family_count']==1
    assert task('chinese-g7-upper:6:satire','check')['family_count']==1
    repair=task('chinese-g2-upper:8:repair','check')
    assert repair['family_count']==1 and repair['supporting_question_count']==1
    collocation=task('english-g7-upper:15:collocation','check')
    assert collocation['status']=='configured' and collocation['family_count']==2
    assert task('english-g7-upper:14:be','express')['assessment_mode']=='human'
    assert task('english-g7-upper:14:be','express')['family_count']==0


def test_subject_gaps_mappings_are_not_counted_before_installation():
    installed_before=set(bank())-set(bank('subject_gaps')) | set(initial())
    current=rows(installed_before)
    for point in ('chinese-g2-upper:1:words','chinese-g2-upper:2:radical',
                  'chinese-g2-upper:4:dictionary','chinese-g7-upper:1:poetry',
                  'chinese-g7-upper:2:evidence','english-g7-upper:1:alphabet',
                  'english-g7-upper:3:there','english-g7-upper:11:reading',
                  'english-g7-upper:14:be','english-g7-upper:14:can',
                  'english-g7-upper:15:context','english-g7-upper:16:entry',
                  'english-g7-upper:18:calendar'):
        check=next(item for item in current[point]['tasks'] if item['id']=='check')
        assert check['family_count']==0
        assert not any('subject_gaps-' in question_id for question_id in check['question_ids'])


@pytest.mark.parametrize('tamper',['missing_mode','missing_task','direct_human'])
def test_manual_boundary_fails_closed(tmp_path, monkeypatch, tamper):
    data=json.loads(subject_coverage.PATH.read_bytes())
    row=next(r for r in data['rows'] if r['id']=='math-g2-upper:activity2:body')
    if tamper=='missing_mode':row['assessment_modes'].pop('apply')
    elif tamper=='missing_task':row.pop('manual_task')
    else:next(m for m in row['mappings'] if m['task']=='apply')['role']='direct'
    import hashlib
    raw=json.dumps(data).encode();p=tmp_path/'plan.json';p.write_bytes(raw)
    monkeypatch.setattr(subject_coverage,'PATH',p)
    monkeypatch.setattr(subject_coverage,'SHA256',hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError):subject_coverage.report('math-g2-v1',set(bank()))


def test_without_installed_questions_nothing_is_counted():
    result=subject_coverage.report('math-g2-v1',set())
    assert all(t['status']=='gap' and t['family_count']==0 for r in result['items'] for t in r['tasks'])
