CREATE TABLE browser_sessions (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_hash TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    learner_id TEXT REFERENCES learners(id),
    provider TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE gateway_assertions (
    jti_hash TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);
