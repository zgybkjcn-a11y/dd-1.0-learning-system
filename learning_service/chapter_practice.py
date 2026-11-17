"""Frozen, locally authored chapter exercises, installed in explicit batches."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from .db import json_dumps, new_id, utc_now

PREFIX = 'family-chapter-'
DATA = Path(__file__).parent / 'data'
BATCHES = {
    'math': '3a79201353c7dd5d1eb42bfac21d9121210bf63523d4a30053ed87543fe66b83',
    'upper': 'cefca56440d184a09276e4401813340ef5af0221bab72dd2c44916f10c333bf9',
    'remaining': '6edf054792bf80451477ce99d86bc303d2f8e652f02c537d945e15ea6f50b335',
    'math_g2_depth': 'f2bbec2ff2c5fce881ed0882c514bd30452bb33e5e300845793cc800e4d2376f',
    'math_g7_depth': '77d23b07964e7023eab4ebdcfd8691b0c869db33732833fd82778ae01220d9b2',
    'math_g2_challenge': '8cb1e4ee26e279a956271ba5d4610f480e34d04bed2b10a8c63d2a21827abc63',
    'math_g2_multistep': 'f0fd9670d73dcc87aaf8cbf9b12e07e6d8556a0b789175f6732421ec56cc278c',
    'math_g7_multistep': 'cba621c29411b60d10fea0c22281bd0d6efbd7510e2c19428183f7d6b897bc66',
    'upper_variety': '9ec5c7228c2bc47c9131932005ae55aef0cb3091600af2ebfb4cba13231e0766',
    'remaining_variety': '871af83355955dd73127dfb601877d7d4b41cef0fb3b81193ef0d44dfa3b2952',
    'subject_knowledge': '5237f5d0146c7d0217505c00540deab8503bc8fbf7e8508b8531f6dea7d84ecb',
    'challenge_variety': '052a766923c99f1a11fa4459b3bfaaf74126caa9d0ed6793dcf2c2a9f3a55b3c',
    'math_gaps': '86e9623257b16467049e2bbc557ad49d8c9f94647cf4ea78f1d42afa7999bf3d',
    'subject_gaps': '19634b63ce45375319b8b041d1000b855a9c6a1fbb2f9cc824faaf0da96ca3c7',
    'math_g7_action_candidates': '61026253b37bde71555d7780833da6b231a77c746b4308a3fce4bdc2f207e713',
    'math_g7_chapter4_action_candidates': '9d0479b06dea7a68eb627016f41210cafad1be508f62c428d9ec720c524945d6',
}


@lru_cache(maxsize=16)
def _parse(raw):
    from .practice import arithmetic, LEVELS
    from .textbooks import learning_scope, PDF_SHA256
    data = json.loads(raw)
    result = {}
    for q in data['questions']:
        book, chapter = learning_scope(f"math-g{q['grade']}-v1", q['book_id'], q['chapter_id'])
        if (not q['id'].startswith(PREFIX) or q['id'] in result or not chapter['id']
                or book['subject'] != q['subject'] or q['difficulty'] not in LEVELS
                or q['review']['teacher_reviewed'] is not False
                or q['review']['status'] != 'assistant_checked' or q['source']['kind'] != 'authored'
                or q['source']['textbook_sha256'] != PDF_SHA256[q['book_id']]):
            raise ValueError('invalid chapter question')
        if q.get('response_protocol') in ('short-fields-v2','structured-fields-v3'):
            from .practice_response import validate_short_key, grade_short_fields
            values=stored(q)
            key=json.loads(values['answer_key_json'])
            validate_short_key(key['response_fields'],key['field_answers'])
            if any(f['kind'] in ('number','choice') and arithmetic(f['independent_check'])!=arithmetic(f['answer']) for f in q['responses']):
                raise ValueError('chapter short numeric check failed: '+q['id'])
            if q['response_protocol']=='short-fields-v2' and any(f['kind'] in ('multi','order') for f in q['responses']):
                raise ValueError('structured fields require v3')
            if grade_short_fields(q['answer'],key)[0]!='correct':
                raise ValueError('chapter short answer check failed: '+q['id'])
        elif 'responses' in q:
            from .practice_response import validate_fields
            validate_fields([{k: f[k] for k in ('id', 'label', 'units', 'options')} for f in q['responses']])
            if (json.loads(q['answer']) != {f['id']: f['answer'] for f in q['responses']}
                    or any(arithmetic(f['independent_check']) != arithmetic(f['answer'])
                           or (f['options'] and f['answer'] not in {str(i+1) for i in range(len(f['options']))})
                           for f in q['responses'])):
                raise ValueError('chapter field answer check failed: ' + q['id'])
        elif arithmetic(q['independent_check']) != arithmetic(q['answer']):
            raise ValueError('chapter answer check failed: ' + q['id'])
        if 'visual' in q:
            from .practice_design import validate_visual
            validate_visual(q['visual'])
        result[q['id']] = q
    return data['format'], data['batch'], result


def bank(batch=None):
    result = {}
    selected = BATCHES if batch is None else {batch: BATCHES[batch]}
    for name, digest in selected.items():
        path = DATA / ('family_chapter_' + name + '_v1.json')
        if path.is_symlink():
            raise ValueError('symlink chapter bank')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('chapter bank changed: ' + name)
        format_id, batch_name, questions = _parse(raw)
        if format_id != 'dd-family-chapter-practice-v1' or batch_name != name or result.keys() & questions.keys():
            raise ValueError('chapter bank identity changed')
        result.update(questions)
    return result


def objective(q):
    return 'objective-family-chapter-' + q['book_id'] + '-' + q['chapter_id']


def stored(q):
    from .practice_design import visual_fields
    from .practice_response import response_fields
    if q.get('response_protocol') in ('short-fields-v2','structured-fields-v3'):
        fields=[{k:f[k] for k in ('id','label','units','options','kind')} for f in q['responses']]
        answers=[]
        for f in q['responses']:
            a={k:f[k] for k in ('id','label','units','kind')}
            if f['kind']=='text':a.update(accepted=f['accepted'],case_sensitive=f['case_sensitive'])
            elif f['kind'] in ('multi','order'):a.update(selection=f['answer'],options=f['options'])
            else:a['numeric_answer']=f['answer']
            a['errors']=f.get('errors',[]);answers.append(a)
        return {'question_id':q['id'].removesuffix('-v1'),'version':1,
                'content_json':json_dumps({'prompt':q['prompt'],'hint':q['hint'],'input_type':'fields',
                    'source':q['source'],'practice_bank':'family-chapter-v1',**visual_fields(q),
                    **response_fields({'response_fields':fields})}),
                'answer_key_json':json_dumps({'response_fields':fields,'field_answers':answers,'explanation':q['explanation']}),
                'validator_version':q['response_protocol'],'variant_kind':'base','variant_group':None}
    if 'responses' in q:
        fields = [{k: f[k] for k in ('id', 'label', 'units', 'options')} for f in q['responses']]
        return {'question_id': q['id'].removesuffix('-v1'), 'version': 1,
                'content_json': json_dumps({'prompt': q['prompt'], 'hint': q['hint'],
                    'input_type': 'fields', 'source': q['source'], 'practice_bank': 'family-chapter-v1',
                    **visual_fields(q), **response_fields({'response_fields': fields})}),
                'answer_key_json': json_dumps({'field_answers': [
                    {'id': f['id'], 'label': f['label'], 'numeric_answer': f['answer'], 'units': f['units']}
                    for f in q['responses']], 'explanation': q['explanation']}),
                'validator_version': 'numeric-fields-v1', 'variant_kind': 'base', 'variant_group': None}
    units = list(q['units'])
    for name, aliases in {'米': ['m'], '厘米': ['cm'], '千米': ['km'], '度': ['°']}.items():
        if name in units:
            units.extend(aliases)
    return {'question_id': q['id'].removesuffix('-v1'), 'version': 1,
            'content_json': json_dumps({'prompt': q['prompt'], 'hint': q['hint'], 'input_type': 'text',
                                       'source': q['source'], 'practice_bank': 'family-chapter-v1', **visual_fields(q)}),
            'answer_key_json': json_dumps({'numeric_answer': q['answer'], 'units': units,
                                          'explanation': q['explanation']}),
            'validator_version': 'numeric-answer-v1', 'variant_kind': 'base', 'variant_group': None}


def metadata(q):
    from .practice_design import presentation
    return {k: deepcopy(q[k]) for k in ('title', 'difficulty', 'extension', 'source')} | {
        'chapter_supplement': True, 'teacher_reviewed': False, 'batch': q['batch']} | presentation(q)


def validate_installed(conn, version_id, questions=None):
    """Verify one installed version; `questions` lets a bulk caller reuse its load."""
    q = (bank() if questions is None else questions).get(version_id)
    row = conn.execute('SELECT v.*,q.objective_id,q.visibility,q.approval AS question_approval,'
                       'k.curriculum_id,o.knowledge_point_id FROM question_versions v '
                       'JOIN questions q ON q.id=v.question_id '
                       'JOIN review_objectives o ON o.id=q.objective_id '
                       'JOIN knowledge_points k ON k.id=o.knowledge_point_id WHERE v.id=?',
                       (version_id,)).fetchone()
    if (q is None or row is None or row['objective_id'] != objective(q) or row['visibility'] != 'shared'
            or row['approval'] != 'approved' or row['question_approval'] != 'approved'
            or row['curriculum_id'] != f"math-g{q['grade']}-v1"
            or row['knowledge_point_id'] != objective(q).replace('objective-', 'kp-', 1)
            or any(row[k] != v for k, v in stored(q).items())):
        raise ValueError('frozen chapter question changed')
    return q


def install(db, batch):
    """Add a reviewed batch atomically; never replace existing questions or attempts."""
    from .textbooks import learning_scope
    questions = bank(batch)
    added = 0
    with db.session(write=True) as conn:
        now = utc_now()
        for q in questions.values():
            obj = objective(q)
            kp = obj.replace('objective-', 'kp-', 1)
            curriculum = f"math-g{q['grade']}-v1"
            book, chapter = learning_scope(curriculum, q['book_id'], q['chapter_id'])
            title = book['subject_title'] + ' · ' + chapter['title']
            conn.execute('INSERT OR IGNORE INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES (?,?,?,?,?)',
                         (kp, curriculum, kp, title, now))
            conn.execute('INSERT OR IGNORE INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES (?,?,?,?,?)',
                         (obj, kp, obj, title, now))
            scope = conn.execute('SELECT k.curriculum_id,o.knowledge_point_id FROM review_objectives o '
                                 'JOIN knowledge_points k ON k.id=o.knowledge_point_id WHERE o.id=?', (obj,)).fetchone()
            if tuple(scope) != (curriculum, kp):
                raise ValueError('chapter objective changed')
            if conn.execute('SELECT 1 FROM question_versions WHERE id=?', (q['id'],)).fetchone():
                validate_installed(conn, q['id'])
                continue
            values = stored(q)
            conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,'shared','approved',?,?)",
                         (values['question_id'], obj, now))
            conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,variant_kind,variant_group,approval,created_at) VALUES (?,?,?,?,?,?,?,?,'approved',?)",
                         (q['id'], *(values[k] for k in ('question_id', 'version', 'content_json', 'answer_key_json',
                                                       'validator_version', 'variant_kind', 'variant_group')), now))
            added += 1
        if added:
            conn.execute('INSERT INTO audit_events(id,account_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?)',
                         (new_id('audit'), 'family-content-setup', 'install_chapter_practice', 'question_set', batch, 'applied',
                          json_dumps({'added': added, 'sha256': BATCHES[batch], 'teacher_reviewed': False}), now))
    return {'batch': batch, 'added': added, 'questions': len(questions), 'sha256': BATCHES[batch]}
