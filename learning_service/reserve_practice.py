"""Frozen B02 trial questions and unseen selection. No import-time DB/provider work."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .practice import arithmetic, BANK_PATH, BANK_SHA256, LEVELS
from .db import json_dumps, utc_now

PATH = Path(__file__).parent / 'data/family_reserve_practice_v1.json'
SHA256 = '9de56afa82d70e108b3e0eaab9b319dbce66a7c8057669915d07b3be24f0c4a8'
PREFIX = 'family-reserve-'
OBJECTIVE = 'objective-family-word-math-g7-ch2'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def mathematical_check(q):
    """Exact rational checks plus separate inverse/decimal invariants."""
    answer = Fraction(q['answer'])
    check = q['mathematical_check']
    if arithmetic(q['independent_check']) != answer:
        raise ValueError('independent answer mismatch: ' + q['id'])
    kind = check['kind']
    if kind == 'rational':
        valid = arithmetic(check['expression']) == answer
    elif kind == 'reciprocal':
        value = Fraction(check['value'])
        valid = value != 0 and value * answer == 1
    elif kind == 'scientific_exponent':
        value, mantissa = Fraction(check['value']), Fraction(check['mantissa'])
        exponent = answer.numerator
        if answer.denominator != 1 or not 1 <= exponent <= 12 or not 1 <= mantissa < 10:
            raise ValueError('invalid scientific exponent')
        ratio, count = value / mantissa, 0
        while ratio > 1 and count <= 12:
            ratio /= 10
            count += 1
        valid = value == mantissa * 10 ** exponent and ratio == 1 and count == exponent
    elif kind == 'round_half_up':
        value, step = Decimal(check['value']), Decimal(check['precision'])
        rounded = value.quantize(step, rounding=ROUND_HALF_UP)
        # Positive length: verify the independent exact interval as well.
        valid = (value > 0 and step > 0 and Fraction(rounded) == answer
                 and answer - Fraction(step) / 2 <= Fraction(value) < answer + Fraction(step) / 2)
    else:
        raise ValueError('unsupported mathematical check')
    if not valid:
        raise ValueError('mathematical answer mismatch: ' + q['id'])


def bank():
    """Read bytes on each use so a cached registry cannot hide a changed source."""
    if any(p.is_symlink() for p in (PATH, *PATH.parents, BANK_PATH, *BANK_PATH.parents)):
        raise ValueError('symlink question source')
    raw = PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('reserve bank changed; create and review a new version')
    payload = json.loads(raw)
    if (payload['format'] != 'dd-family-reserve-practice-v1' or payload['teacher_reviewed'] is not False
            or payload['base_bank_sha256'] != BANK_SHA256 or len(payload['questions']) != 12):
        raise ValueError('invalid reserve bank')
    base_raw = BANK_PATH.read_bytes()
    if hashlib.sha256(base_raw).hexdigest() != BANK_SHA256:
        raise ValueError('base question version changed')
    parents = {q['id']: q for q in json.loads(base_raw)['questions']}
    questions = {q['id']: q for q in payload['questions']}
    if len(questions) != 12 or any(sum(q['difficulty'] == level for q in questions.values()) != 4 for level in LEVELS):
        raise ValueError('reserve counts do not reconcile')
    for q in questions.values():
        r = q['review']
        if (not q['id'].startswith(PREFIX) or q['id'] in parents or q['grade'] != 7
                or q['book_id'] != 'math-g7-upper' or q['chapter_id'] != '2'
                or q['difficulty'] not in LEVELS or r['status'] != 'assistant_checked'
                or r['reviewer_type'] != 'assistant' or r['teacher_reviewed'] is not False
                or r['revision'] != 1 or not r['conditions_complete'] or not r['units_checked']
                or r['unresolved_issues'] or q['source']['kind'] != 'authored'):
            raise ValueError('unreviewed reserve question')
        relation = q['template_relation']
        parent = relation['parent_question_version_id']
        if relation['kind'] == 'numeric_variant':
            if parent not in parents or hashlib.sha256(canonical(parents[parent])).hexdigest() != relation['parent_question_sha256']:
                raise ValueError('parent question changed')
        elif relation['kind'] not in {'new_authored_situation', 'new_authored_calculation'} or parent is not None:
            raise ValueError('unbound template relationship')
        mathematical_check(q)
    return questions


def stored(q):
    units = list(q['units'])
    for name, aliases in {'米': ['m'], '升': ['L', 'l'], '℃': ['摄氏度', '度']}.items():
        if name in units:
            units += aliases
    relation = q['template_relation']
    return {
        'question_id': q['id'].removesuffix('-v1'), 'version': 1,
        'content_json': json_dumps({'prompt': q['prompt'], 'hint': q['hint'], 'input_type': 'text',
                                   'source': q['source'], 'practice_bank': 'family-reserve-v1',
                                   'template_relation': relation}),
        'answer_key_json': json_dumps({'numeric_answer': q['answer'], 'units': units, 'explanation': q['explanation']}),
        'validator_version': 'numeric-answer-v1',
        'variant_kind': 'variant' if relation['kind'] == 'numeric_variant' else 'base',
        'variant_group': relation['family_id'] if relation['kind'] == 'numeric_variant' else None,
    }


def validate_version(row):
    q = bank().get(row['id'])
    if q is None or row['objective_id'] != OBJECTIVE or row['visibility'] != 'shared':
        raise ValueError('reserve placement/ownership changed')
    expected = stored(q)
    if any(row[key] != value for key, value in expected.items()):
        raise ValueError('frozen reserve version changed')
    return q


def validate_installed(conn, question_version_id):
    row = conn.execute('SELECT v.*,q.objective_id,q.visibility,q.approval AS question_approval,'
                       'k.curriculum_id,o.knowledge_point_id FROM question_versions v '
                       'JOIN questions q ON q.id=v.question_id '
                       'JOIN review_objectives o ON o.id=q.objective_id '
                       'JOIN knowledge_points k ON k.id=o.knowledge_point_id WHERE v.id=?',
                       (question_version_id,)).fetchone()
    if (row is None or row['approval'] != 'approved' or row['question_approval'] != 'approved'
            or row['curriculum_id'] != 'math-g7-v1' or row['knowledge_point_id'] != 'kp-family-word-g7-ch2'):
        raise ValueError('reserve approval or curriculum changed')
    return validate_version(row)


def unseen(conn, learner_id, question_version_id):
    # Creation returns the prompt, so cancelled/presented sessions remain exposure.
    return conn.execute('SELECT 1 FROM test_items WHERE learner_id=? AND question_version_id=? LIMIT 1',
                        (learner_id, question_version_id)).fetchone() is None


def metadata(q):
    return {key: deepcopy(q[key]) for key in ('title', 'difficulty', 'extension', 'source', 'template_relation')} | {
        'reserve': True, 'bank_version': '2026-11-08-b02-v1', 'teacher_reviewed': False}


def install(db):
    """Explicit additive installation; caller chooses an authorized database."""
    questions = list(bank().values())
    added = 0
    with db.session(write=True) as conn:
        kp = 'kp-family-word-g7-ch2'
        now = utc_now()
        conn.execute('INSERT OR IGNORE INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)',
                     (kp, 'math-g7-v1', kp, '用有理数运算解决生活问题', now))
        conn.execute('INSERT OR IGNORE INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)',
                     (OBJECTIVE, kp, OBJECTIVE, '用有理数运算解决生活问题', now))
        scope = conn.execute('SELECT k.curriculum_id,o.knowledge_point_id FROM review_objectives o '
                             'JOIN knowledge_points k ON k.id=o.knowledge_point_id WHERE o.id=?', (OBJECTIVE,)).fetchone()
        if tuple(scope) != ('math-g7-v1', kp):
            raise ValueError('existing reserve curriculum differs')
        for q in questions:
            old = conn.execute('SELECT v.*,q.objective_id,q.visibility,q.approval AS question_approval '
                               'FROM question_versions v JOIN questions q ON q.id=v.question_id WHERE v.id=?', (q['id'],)).fetchone()
            if old:
                validate_version(old)
                if old['approval'] != 'approved' or old['question_approval'] != 'approved':
                    raise ValueError('existing reserve approval changed')
                continue
            values = stored(q)
            if conn.execute('SELECT 1 FROM questions WHERE id=?', (values['question_id'],)).fetchone():
                raise ValueError('existing reserve question identity differs')
            conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,'shared','approved',?,?)",
                         (values['question_id'], OBJECTIVE, now))
            conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,variant_kind,variant_group,approval,created_at) VALUES (?,?,?,?,?,?,?,?,'approved',?)",
                         (q['id'], *(values[key] for key in ('question_id', 'version', 'content_json', 'answer_key_json',
                                                            'validator_version', 'variant_kind', 'variant_group')), now))
            added += 1
        if added:
            conn.execute("INSERT INTO audit_events(id,account_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES ('family-reserve-v1-install','family-pilot-setup','install_curated_reserve','question_set','family-reserve-v1','applied',?,?)",
                         (json_dumps({'added': added, 'bank_sha256': SHA256, 'teacher_reviewed': False, 'external_model_calls': 0}), now))
    return {'added': added, 'questions': 12, 'sha256': SHA256, 'teacher_reviewed': False}
