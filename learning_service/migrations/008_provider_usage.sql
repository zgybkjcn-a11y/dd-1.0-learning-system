CREATE TABLE provider_control (
    id INTEGER PRIMARY KEY CHECK(id=1),
    paused INTEGER NOT NULL DEFAULT 0 CHECK(paused IN (0,1)),
    updated_at TEXT NOT NULL
);
INSERT INTO provider_control(id,paused,updated_at) VALUES (1,0,strftime('%Y-%m-%dT%H:%M:%S+00:00','now'));

-- No student, account, prompt, answer, image, endpoint credential or payload.
-- An interrupted/unknown attempt keeps its entire reservation until invoice
-- reconciliation. Worker lease expiry must never release a monetary hold.
CREATE TABLE provider_calls (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    model_id TEXT NOT NULL,
    evidence_mode TEXT NOT NULL CHECK(evidence_mode IN ('live_http','synthetic_http')),
    currency TEXT NOT NULL,
    pricing_reference TEXT NOT NULL,
    input_rate INTEGER NOT NULL DEFAULT 0 CHECK(input_rate>=0),
    output_rate INTEGER NOT NULL DEFAULT 0 CHECK(output_rate>=0),
    reserved_cost_micros INTEGER NOT NULL CHECK(reserved_cost_micros>0),
    estimated_cost_micros INTEGER CHECK(estimated_cost_micros>=0),
    reconciled_cost_micros INTEGER CHECK(reconciled_cost_micros>=0),
    billing_reference TEXT,
    prompt_tokens INTEGER CHECK(prompt_tokens>=0),
    completion_tokens INTEGER CHECK(completion_tokens>=0),
    state TEXT NOT NULL CHECK(state IN ('reserved','returned','failed','unknown','reconciled')),
    error_code TEXT,
    request_id TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX provider_calls_created ON provider_calls(created_at);
CREATE TABLE provider_denials (
    reason TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
);
