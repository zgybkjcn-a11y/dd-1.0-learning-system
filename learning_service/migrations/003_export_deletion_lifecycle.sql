CREATE TABLE IF NOT EXISTS export_jobs (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    requested_by_account_id TEXT NOT NULL REFERENCES accounts(id),
    scope_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('queued','completed','failed','cancelled')),
    artifact_key TEXT,
    artifact_sha256 TEXT,
    artifact_byte_size INTEGER,
    error_code TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS export_jobs_learner_idx ON export_jobs(learner_id, created_at);

ALTER TABLE deletion_records ADD COLUMN cleanup_state TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE deletion_records ADD COLUMN object_key TEXT;
ALTER TABLE deletion_records ADD COLUMN deleted_at TEXT;
ALTER TABLE deletion_records ADD COLUMN error_code TEXT;
CREATE INDEX IF NOT EXISTS deletion_records_learner_idx ON deletion_records(learner_id, cleanup_state);
