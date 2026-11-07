CREATE TABLE variant_reviews (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    objective_id TEXT NOT NULL REFERENCES review_objectives(id),
    source_question_version_id TEXT REFERENCES question_versions(id),
    result_fingerprint TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('approve','reject')),
    note TEXT NOT NULL,
    reviewed_by_account_id TEXT NOT NULL REFERENCES accounts(id),
    question_version_id TEXT UNIQUE REFERENCES question_versions(id),
    frozen_draft_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE variant_revocations (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL UNIQUE REFERENCES variant_reviews(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    revoked_by_account_id TEXT NOT NULL REFERENCES accounts(id),
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Review evidence and published content are immutable. Revocation is a new
-- record; it never edits the frozen key, content, provenance, or prior grade.
CREATE TRIGGER frozen_variant_version BEFORE UPDATE ON question_versions
WHEN EXISTS (SELECT 1 FROM variant_reviews WHERE question_version_id=OLD.id)
AND (NEW.id IS NOT OLD.id OR NEW.question_id IS NOT OLD.question_id OR NEW.version IS NOT OLD.version
 OR NEW.content_json IS NOT OLD.content_json OR NEW.answer_key_json IS NOT OLD.answer_key_json
 OR NEW.validator_version IS NOT OLD.validator_version OR NEW.variant_kind IS NOT OLD.variant_kind
 OR NEW.variant_group IS NOT OLD.variant_group OR NEW.created_at IS NOT OLD.created_at)
BEGIN SELECT RAISE(ABORT, 'FROZEN_VARIANT_VERSION'); END;
CREATE TRIGGER frozen_variant_scope BEFORE UPDATE ON questions
WHEN EXISTS (SELECT 1 FROM variant_reviews r JOIN question_versions v ON v.id=r.question_version_id WHERE v.question_id=OLD.id)
AND (NEW.id IS NOT OLD.id OR NEW.learner_id IS NOT OLD.learner_id OR NEW.visibility IS NOT OLD.visibility
 OR NEW.objective_id IS NOT OLD.objective_id OR NEW.created_at IS NOT OLD.created_at)
BEGIN SELECT RAISE(ABORT, 'FROZEN_VARIANT_SCOPE'); END;
CREATE TRIGGER immutable_variant_review BEFORE UPDATE ON variant_reviews
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_VARIANT_REVIEW'); END;
CREATE TRIGGER immutable_variant_revocation BEFORE UPDATE ON variant_revocations
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_VARIANT_REVOCATION'); END;
CREATE TRIGGER revoked_variant_cannot_reapprove BEFORE UPDATE OF approval ON question_versions
WHEN NEW.approval='approved' AND EXISTS (
 SELECT 1 FROM variant_reviews r JOIN variant_revocations x ON x.review_id=r.id WHERE r.question_version_id=OLD.id)
BEGIN SELECT RAISE(ABORT, 'VARIANT_REVOKED'); END;
CREATE TRIGGER frozen_variant_job BEFORE UPDATE ON jobs
WHEN EXISTS (SELECT 1 FROM variant_reviews WHERE job_id=OLD.id)
AND (NEW.id IS NOT OLD.id OR NEW.learner_id IS NOT OLD.learner_id OR NEW.kind IS NOT OLD.kind
 OR NEW.input_json IS NOT OLD.input_json OR NEW.result_json IS NOT OLD.result_json)
BEGIN SELECT RAISE(ABORT, 'FROZEN_VARIANT_JOB'); END;
CREATE TRIGGER immutable_variant_review_delete BEFORE DELETE ON variant_reviews
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_VARIANT_REVIEW'); END;
CREATE TRIGGER immutable_variant_revocation_delete BEFORE DELETE ON variant_revocations
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_VARIANT_REVOCATION'); END;
