CREATE TABLE IF NOT EXISTS review_requests (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    requested_by_account_id TEXT NOT NULL REFERENCES accounts(id),
    reason TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'requested'
        CHECK(status IN ('requested','in_review','resolved','dismissed','cancelled')),
    resolution_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS review_requests_learner_status_idx
    ON review_requests(learner_id, status, created_at);
