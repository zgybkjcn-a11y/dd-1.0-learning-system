"""Authenticated reference reads with selection and access rechecks; no app import."""
from __future__ import annotations

from .api_types import APIError
from .learner_context import read_context
from .math_references import ReferenceError
from .textbook_passages import PassageError


def read_study_reference(request, ctx, db, settings, allowed, reader, *, learner_for):
    pairs = request.query_params.multi_items()
    if any(key not in allowed for key, _ in pairs) or len({key for key, _ in pairs}) != len(pairs):
        raise APIError(422, "MATH_REFERENCE_SCOPE_INVALID", "知识参考查询参数无效")
    learner_id = learner_for(ctx, db=db)
    def selection():
        with db.session() as conn:
            return read_context(conn, ctx.account_id)
    pinned = selection() if settings.shared_learner_context_enabled else None
    if pinned and (pinned["learner_id"] != learner_id
                   or request.headers.get("X-Learner-Context-Version") != str(pinned["context_version"])):
        raise APIError(409, "LEARNER_CONTEXT_CHANGED", "学习者已变化，请刷新工作台后重试")
    try:
        with db.session() as conn:
            curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
            result = reader(conn, learner_id, curriculum, settings.textbook_dir)
    except (ReferenceError, PassageError) as exc:
        raise APIError(exc.status, exc.code, exc.message) from None
    if pinned and selection() != pinned:
        raise APIError(409, "LEARNER_CONTEXT_CHANGED", "学习者已变化，请刷新工作台后重试")
    learner_for(ctx, db=db)  # Recheck access after filesystem/metadata reads.
    return result

