"""Human review of durable variant drafts, with frozen private publication."""
from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .db import json_dumps, json_loads, new_id, utc_now


class VariantReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    decision: Literal['approve', 'reject']
    result_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    note: str = Field(min_length=1, max_length=4000)

    @field_validator('note')
    @classmethod
    def nonempty_note(cls, value):
        if not value.strip():
            raise ValueError('human review note required')
        return value.strip()


class VariantRevokeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    note: str = Field(min_length=1, max_length=4000)

    @field_validator('note')
    @classmethod
    def nonempty_note(cls, value):
        if not value.strip():
            raise ValueError('revocation note required')
        return value.strip()


def fingerprint(job) -> str:
    material = {'job_id': job['id'], 'learner_id': job['learner_id'], 'status': job['status'],
                'input': json_loads(job['input_json'], {}), 'result': json_loads(job['result_json'], {})}
    return hashlib.sha256(json_dumps(material).encode()).hexdigest()


def checked_draft(snapshot: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the same restricted integer template at the approval boundary."""
    if result.get('status') != 'needs_review' or result.get('approval_required') is not True or result.get('payload', {}).get('approval_required') is not True:
        raise ValueError('human review required')
    draft = result.get('payload', {}).get('draft')
    if not isinstance(draft, dict) or not snapshot.get('source_question_version_id'):
        raise ValueError('missing draft or approved source')
    if result.get('source_snapshot_hash') != snapshot['snapshot_hash']:
        raise ValueError('source changed')
    if snapshot.get('template_id') != 'signed_number_subtraction' or snapshot.get('domain') != 'integers' or snapshot.get('unit') is not None:
        raise ValueError('source domain unsupported')
    content = draft.get('content', {})
    parameters = content.get('parameters', {}) if isinstance(content, dict) else {}
    if not isinstance(parameters, dict) or set(parameters) != {'start', 'subtrahend'}:
        raise ValueError('invalid parameters')
    if any(type(parameters.get(k)) is not int or not -100 <= parameters[k] <= 100 for k in ('start', 'subtrahend')):
        raise ValueError('invalid integer domain')
    source_parameters = snapshot.get('parameters', {})
    if not isinstance(source_parameters, dict) or any(type(source_parameters.get(k)) is not int or not -100 <= source_parameters[k] <= 100 for k in ('start','subtrahend')):
        raise ValueError('source parameters unsupported')
    if parameters == source_parameters:
        raise ValueError('unchanged source')
    start, subtrahend = parameters['start'], parameters['subtrahend']
    expected = {'objective_id': snapshot['objective_id'], 'source_question_version_id': snapshot['source_question_version_id'],
                'content': {'template_id': 'signed_number_subtraction', 'prompt': f'{start} - ({subtrahend}) = ?',
                            'parameters': parameters, 'domain': 'integers', 'unit': None},
                'answer_key': {'accepted': [str(start - subtrahend)]}, 'validator_version': 'exact-text-v1', 'approval': 'draft'}
    if draft != expected:
        raise ValueError('candidate differs from reconstructed content/key/scope')
    return expected


def publish(conn, job, draft, account_id, note, result_fingerprint) -> dict:
    question_id, version_id, review_id, now = new_id('question'), new_id('qv'), new_id('variant_review'), utc_now()
    conn.execute('INSERT INTO questions(id,learner_id,visibility,approval,objective_id,created_at) VALUES (?,?,?,?,?,?)',
                 (question_id, job['learner_id'], 'private', 'approved', draft['objective_id'], now))
    conn.execute('INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,variant_kind,variant_group,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                 (version_id, question_id, 1, json_dumps(draft['content']), json_dumps(draft['answer_key']), draft['validator_version'],
                  'approved', 'variant', job['id'], now))
    conn.execute('INSERT INTO variant_reviews(id,job_id,learner_id,objective_id,source_question_version_id,result_fingerprint,decision,note,reviewed_by_account_id,question_version_id,frozen_draft_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                 (review_id, job['id'], job['learner_id'], draft['objective_id'], draft['source_question_version_id'], result_fingerprint,
                  'approve', note, account_id, version_id, json_dumps(draft), now))
    return {'review_id': review_id, 'job_id': job['id'], 'status': 'approved', 'question_version_id': version_id, 'version': 1}


def review_audit(conn, account_id, learner_id, operation, resource_id, metadata):
    conn.execute('INSERT INTO audit_events(id,account_id,learner_id,operation,resource_type,resource_id,result,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                 (new_id('audit'), account_id, learner_id, operation, 'variant_review', resource_id, 'accepted', json_dumps(metadata), utc_now()))
