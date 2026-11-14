"""Recent direct-action mappings must use installed, independently useful tasks."""
from learning_service import practice_coverage, subject_coverage
from learning_service.chapter_practice import bank as chapter_bank
from learning_service.practice import bank as practice_bank
from learning_service.reserve_practice import bank as reserve_bank


def available_ids():
    candidate_ids = {
        'family-chapter-math-g7-upper-2-01-v1',
        'family-chapter-math-g7-upper-2-02-v1',
        'family-chapter-math-g7-upper-4-action-subtract-expression-v1',
    }
    return (set(practice_bank()) | set(reserve_bank()) | set(chapter_bank())) - candidate_ids


def report_rows(report):
    return {row['id']: row for row in report['items']}


def task(rows, point, name):
    return next(item for item in rows[point]['tasks'] if item['id'] == name)


def test_math_v15_uses_installed_distinct_actions_and_preserves_human_requirements():
    ids = available_ids()
    math_rows = {2: report_rows(practice_coverage.report('math-g2-v1', ids)),
                 7: report_rows(practice_coverage.report('math-g7-v1', ids))}
    expected = [
        (2, 'math-g2-upper:3:equal', 'understand', 2),
        (2, 'math-g2-upper:3:quotient', 'distinguish', 2),
        (2, 'math-g2-upper:3:quotient', 'apply', 2),
        (2, 'math-g2-upper:5:quotient', 'transfer', 2),
        (2, 'math-g2-upper:5:quotient', 'distinguish', 3),
        (2, 'math-g2-upper:2:tables', 'transfer', 2),
        (2, 'math-g2-upper:2:tables', 'apply', 2),
        (2, 'math-g2-upper:4:units', 'apply', 2),
        (2, 'math-g2-upper:5:tables', 'apply', 2),
        (2, 'math-g2-upper:5:quotient', 'apply', 3),
        (7, 'math-g7-upper:1:signed', 'apply', 2),
        (7, 'math-g7-upper:1:absolute', 'apply', 2),
        (7, 'math-g7-upper:1:signed', 'distinguish', 2),
        (7, 'math-g7-upper:1:rational', 'apply', 2),
        (7, 'math-g7-upper:3:pattern', 'understand', 2),
        (7, 'math-g7-upper:5:solve', 'transfer', 2),
        (7, 'math-g7-upper:5:model', 'understand', 2),
    ]
    for grade, point, name, family_count in expected:
        item = task(math_rows[grade], point, name)
        assert item['family_count'] == family_count
        assert item['status'] == 'configured'

    subject_rows = {2: report_rows(subject_coverage.report('math-g2-v1', ids)),
                    7: report_rows(subject_coverage.report('math-g7-v1', ids))}
    manual = task(subject_rows[2], 'math-g2-upper:3:equal', 'transfer')
    assert manual['assessment_mode'] == 'human' and manual['family_count'] == 0
    assert subject_rows[2]['math-g2-upper:3:equal']['manual_task']['automatically_graded'] is False
    assert task(subject_rows[7], 'math-g7-upper:3:pattern', 'apply')['assessment_mode'] == 'human'


def test_math_v15_keeps_nonmatching_variants_as_supporting():
    ids = available_ids()
    rows = report_rows(practice_coverage.report('math-g2-v1', ids))
    apply = task(rows, 'math-g2-upper:2:tables', 'apply')
    assert apply['family_count'] == 2
    assert apply['supporting_question_count'] == 2
    assert 'family-chapter-math-g2-upper-2-multistep-array-count-v1' in apply['question_ids']
    assert 'family-chapter-math-g2-upper-2-challenge-rectangle-options-v1' in apply['question_ids']


def test_subject_v14_g2_word_mappings_are_direct_bounded_recognition():
    ids = available_ids()
    rows = report_rows(subject_coverage.report('math-g2-v1', ids))
    tables = task(rows, 'math-g2-upper:2:tables', 'apply')
    quotient = task(rows, 'math-g2-upper:3:quotient', 'apply')
    groups = task(rows, 'math-g2-upper:2:word', 'understand')
    total = task(rows, 'math-g2-upper:5:word', 'understand')
    assert tables['family_count'] == 2 and tables['status'] == 'configured'
    assert 'family-chapter-math-g2-upper-2-multistep-array-count-v1' in tables['question_ids']
    assert quotient['family_count'] == 2 and quotient['status'] == 'configured'
    assert 'family-word-g2-share-1-v1' in quotient['question_ids']
    assert groups['family_count'] == total['family_count'] == 2
    assert groups['status'] == total['status'] == 'configured'
    assert 'family-chapter-math-g2-upper-2-depth-word-understand-2-v1' in groups['question_ids']
    assert 'family-chapter-math-g2-upper-5-depth-word-understand-2-v1' in total['question_ids']
    assert groups['assessment_mode'] == total['assessment_mode'] == 'bounded'


def test_subject_v14_g7_signed_and_absolute_actions_are_distinct():
    ids = available_ids()
    rows = report_rows(subject_coverage.report('math-g7-v1', ids))
    signed = task(rows, 'math-g7-upper:1:signed', 'apply')
    absolute = task(rows, 'math-g7-upper:1:absolute', 'apply')
    assert signed['family_count'] == absolute['family_count'] == 2
    assert signed['status'] == absolute['status'] == 'configured'
    assert 'family-chapter-math-g7-upper-1-depth-signed-04-v1' in signed['question_ids']
    assert 'family-chapter-math-g7-upper-1-depth-absolute-01-v1' in absolute['question_ids']


def test_subject_v14_g7_chapter2_reclassifies_calculation_and_error_analysis():
    ids = available_ids()
    rows = report_rows(subject_coverage.report('math-g7-v1', ids))

    subtract = rows['math-g7-upper:2:subtract']
    subtract_apply = task(rows, 'math-g7-upper:2:subtract', 'apply')
    subtract_distinguish = task(rows, 'math-g7-upper:2:subtract', 'distinguish')
    assert subtract_apply['family_count'] == 2
    assert 'family-chapter-math-g7-upper-2-depth-subtract-03-v1' in subtract_apply['question_ids']
    assert subtract_distinguish['family_count'] == 0
    assert subtract_distinguish['supporting_question_count'] == 1
    assert 'family-chapter-math-g7-upper-2-01-v1' not in subtract_distinguish['question_ids']
    assert subtract['manual_task']['automatically_graded'] is False

    multiply = rows['math-g7-upper:2:multiply']
    multiply_apply = task(rows, 'math-g7-upper:2:multiply', 'apply')
    multiply_distinguish = task(rows, 'math-g7-upper:2:multiply', 'distinguish')
    assert multiply_apply['family_count'] == 2
    assert 'family-chapter-math-g7-upper-2-depth-multiply-03-v1' in multiply_apply['question_ids']
    assert multiply_distinguish['family_count'] == 0
    assert multiply_distinguish['supporting_question_count'] == 1
    assert 'family-chapter-math-g7-upper-2-02-v1' not in multiply_distinguish['question_ids']
    assert multiply['manual_task']['automatically_graded'] is False


def test_g7_chapter4_maps_actions_without_counting_uninstalled_candidate():
    import json
    from pathlib import Path

    ids = available_ids()
    math_rows = report_rows(practice_coverage.report('math-g7-v1', ids))
    subject_rows = report_rows(subject_coverage.report('math-g7-v1', ids))

    subtract_apply = task(subject_rows, 'math-g7-upper:4:application', 'apply')
    subtract_distinguish = task(subject_rows, 'math-g7-upper:4:application', 'distinguish')
    assert 'family-chapter-math-g7-upper-4-depth-application-03-v1' in subtract_apply['question_ids']
    assert 'family-chapter-math-g7-upper-4-depth-application-03-v1' in subtract_distinguish['question_ids']
    assert subtract_distinguish['supporting_question_count'] >= 1
    assert 'family-chapter-math-g7-upper-4-action-subtract-expression-v1' not in subtract_distinguish['question_ids']

    bracket_apply = task(math_rows, 'math-g7-upper:4:bracket', 'apply')
    coefficient_task = 'family-chapter-math-g7-upper-4-math_g7_multistep-coefficients-v1'
    assert coefficient_task in bracket_apply['question_ids']

    plan = json.loads(Path('learning_service/data/family_subject_coverage_plan_v14.json').read_bytes())
    mappings = {row['id']: row['mappings'] for row in plan['rows']}
    candidate_mapping = next(m for m in mappings['math-g7-upper:4:application']
                             if m['question_version_id'] == 'family-chapter-math-g7-upper-4-action-subtract-expression-v1')
    assert candidate_mapping['task'] == 'distinguish' and candidate_mapping['role'] == 'direct'


def test_g7_chapter6_keeps_manual_geometry_skills_out_of_direct_auto_coverage():
    ids = available_ids()
    math_rows = report_rows(practice_coverage.report('math-g7-v1', ids))
    subject_rows = report_rows(subject_coverage.report('math-g7-v1', ids))

    shapes_math = task(math_rows, 'math-g7-upper:6:shapes', 'distinguish')
    shapes_subject = task(subject_rows, 'math-g7-upper:6:shapes', 'distinguish')
    assert shapes_math['family_count'] == shapes_subject['family_count'] == 2
    assert shapes_math['status'] == shapes_subject['status'] == 'configured'
    shape_question = 'family-chapter-math-g7-upper-6-depth-shapes-01-v1'
    assert shape_question in shapes_math['question_ids']
    assert shape_question in shapes_subject['question_ids']

    for point, question_id in (
        ('math-g7-upper:6:lines', 'family-chapter-math-g7-upper-6-depth-lines-02-v1'),
        ('math-g7-upper:6:angle', 'family-chapter-math-g7-upper-6-depth-angle-02-v1'),
    ):
        automatic = task(math_rows, point, 'apply')
        manual = task(subject_rows, point, 'apply')
        assert automatic['family_count'] == 0 and automatic['supporting_question_count'] >= 1
        assert question_id in automatic['question_ids']
        assert manual['assessment_mode'] == 'human'
        assert subject_rows[point]['manual_task']['automatically_graded'] is False


def test_current_math_and_subject_plans_agree_on_shared_question_roles():
    import json
    from pathlib import Path

    math = json.loads(Path('learning_service/data/family_math_coverage_plan_v15.json').read_bytes())
    subject = json.loads(Path('learning_service/data/family_subject_coverage_plan_v14.json').read_bytes())
    math_rows = {row['id']: row for row in math['rows']}
    subject_rows = {row['id']: row for row in subject['rows']}
    mismatches = []
    for row_id in math_rows.keys() & subject_rows.keys():
        math_mappings = {(m['task'], m['question_version_id']): m.get('role', 'direct')
                         for m in math_rows[row_id]['mappings']}
        subject_mappings = {(m['task'], m['question_version_id']): m.get('role', 'direct')
                             for m in subject_rows[row_id]['mappings']}
        for key in math_mappings.keys() & subject_mappings.keys():
            if math_mappings[key] != subject_mappings[key]:
                mismatches.append((row_id, *key, math_mappings[key], subject_mappings[key]))
    assert mismatches == []
