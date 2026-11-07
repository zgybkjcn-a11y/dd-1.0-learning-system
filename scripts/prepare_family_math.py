#!/usr/bin/env python3
"""Create a new two-learner math database for one existing WebUI parent account."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.db import Database, json_dumps, utc_now
from learning_service.identity_admin import apply_identity, plan_identity

# Authored starter arithmetic, not model-generated variants or a full textbook.
STARTER_QUESTIONS = {
    'objective-math-g2-add-subtract-100': [
        ('23 + 15 = ?', '38'), ('46 + 27 = ?', '73'),
        ('58 - 24 = ?', '34'), ('72 - 38 = ?', '34'),
    ],
    'objective-math-g2-multiplication': [
        ('3 × 4 = ?', '12'), ('6 × 7 = ?', '42'),
        ('8 × 5 = ?', '40'), ('9 × 9 = ?', '81'),
    ],
    'objective-math-g7-subtract-negative-v1': [
        ('-3 - (-5) = ?', '2'), ('4 - (-6) = ?', '10'),
        ('-7 - (-2) = ?', '-5'), ('0 - (-8) = ?', '8'),
        ('-9 - (-9) = ?', '0'), ('12 - (-3) = ?', '15'),
    ],
}


def prepare(directory: Path, parent_subject: str | None = None, issuer: str = 'family-pilot-webui') -> dict:
    if directory.exists():
        raise ValueError('choose a new learning directory; existing data is preserved')
    manifest = {'format': 'dd-learning-identities-v1', 'initialize_math': True,
                'accounts': [{'id': 'family-parent'}],
                'learners': [{'id': f'family-g{grade}', 'display_name': f'{label}数学',
                              'timezone': 'Asia/Shanghai', 'curriculum_id': f'math-g{grade}-v1'}
                             for grade, label in ((7, '七年级'), (2, '二年级'))],
                'bindings': [{'account_id': 'family-parent', 'provider': 'open-webui',
                              'issuer': issuer, 'subject': parent_subject}] if parent_subject else [],
                'grants': [{'account_id': 'family-parent', 'learner_id': f'family-g{grade}', 'role': 'guardian'}
                           for grade in (7, 2)], 'revocations': [], 'unbinds': []}
    database = directory / 'learning.db'
    plan = plan_identity(manifest, database, 'family-pilot-setup')
    directory.mkdir(mode=0o700, parents=True)
    apply_identity(manifest, database, 'family-pilot-setup', plan['plan_sha256'])
    db = Database(database)
    with db.session(write=True) as conn:
        now = utc_now()
        for objective, exercises in STARTER_QUESTIONS.items():
            for index, (prompt, answer) in enumerate(exercises, 1):
                question = f'family-starter-{objective}-{index}'
                conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES (?,'shared','approved',?,?)", (question, objective, now))
                content = {'prompt': prompt, 'input_type': 'text', 'source': 'authored_family_starter_math_v1'}
                conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES (?,?,1,?,?,'exact-text-v1','approved',?)",
                             (question + '-v1', question, json_dumps(content), json_dumps({'accepted': [answer]}), now))
        conn.execute("INSERT INTO audit_events(id,account_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES ('family-starter-setup','family-pilot-setup','install_authored_starter_math','question_set','family-starter-v1','applied',?,?)",
                     (json_dumps({'questions': 14, 'model_generated': False}), now))
    return {'status': 'prepared', 'learners': 2, 'parent_accounts': 1, 'starter_questions': 14,
            'model_calls': 0, 'existing_webui_modified': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--parent-subject', help='Optional existing WebUI user ID; otherwise claim once using the family setup code')
    p.add_argument('--issuer', default='family-pilot-webui')
    args = p.parse_args()
    print(json.dumps(prepare(args.directory, args.parent_subject, args.issuer), ensure_ascii=False))
