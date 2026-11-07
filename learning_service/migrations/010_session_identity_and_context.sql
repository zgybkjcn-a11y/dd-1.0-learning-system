ALTER TABLE browser_sessions ADD COLUMN issuer TEXT;
ALTER TABLE browser_sessions ADD COLUMN subject TEXT;
-- Earlier sessions have no verifiable source identity and cannot be reused.
UPDATE browser_sessions SET revoked_at=COALESCE(revoked_at,datetime('now'));
CREATE TABLE account_contexts (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id),
    learner_id TEXT REFERENCES learners(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    updated_at TEXT NOT NULL
);
