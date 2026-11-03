CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS identity_bindings (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    provider TEXT NOT NULL,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(provider, issuer, subject)
);
CREATE TABLE IF NOT EXISTS learners (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    curriculum_id TEXT NOT NULL DEFAULT 'math-g7-v1',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learner_access (
    account_id TEXT NOT NULL REFERENCES accounts(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    role TEXT NOT NULL CHECK(role IN ('student','guardian','reviewer','admin')),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY(account_id, learner_id)
);
CREATE TABLE IF NOT EXISTS knowledge_points (
    id TEXT PRIMARY KEY,
    curriculum_id TEXT NOT NULL,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(curriculum_id, code)
);
CREATE TABLE IF NOT EXISTS review_objectives (
    id TEXT PRIMARY KEY,
    knowledge_point_id TEXT NOT NULL REFERENCES knowledge_points(id),
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(knowledge_point_id, code)
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    learner_id TEXT REFERENCES learners(id),
    visibility TEXT NOT NULL CHECK(visibility IN ('private','shared')),
    object_key TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS source_documents (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    kind TEXT NOT NULL CHECK(kind IN ('paper','homework','answer_key')),
    status TEXT NOT NULL DEFAULT 'stored',
    page_count INTEGER NOT NULL DEFAULT 0,
    completed_date TEXT,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_pages (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES source_documents(id),
    page_index INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    object_key TEXT,
    failure_code TEXT,
    width INTEGER,
    height INTEGER,
    transform_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, page_index)
);
CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    document_ids_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    revision INTEGER NOT NULL DEFAULT 1,
    total_pages INTEGER NOT NULL DEFAULT 0,
    processed_pages INTEGER NOT NULL DEFAULT 0,
    failed_pages INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS import_items (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    occurrence_id TEXT NOT NULL,
    locator TEXT NOT NULL,
    page_index INTEGER NOT NULL,
    source_page_id TEXT REFERENCES source_pages(id),
    content_json TEXT NOT NULL DEFAULT '{}',
    raw_answer TEXT,
    normalized_answer TEXT,
    teacher_evidence_json TEXT NOT NULL DEFAULT '{}',
    verdict TEXT NOT NULL DEFAULT 'undetermined' CHECK(verdict IN ('correct','incorrect','partial','unanswered','undetermined')),
    verification_status TEXT NOT NULL DEFAULT 'needs_review',
    status TEXT NOT NULL DEFAULT 'extracted',
    revision INTEGER NOT NULL DEFAULT 1,
    confirmed_at TEXT,
    UNIQUE(batch_id, occurrence_id)
);
CREATE TABLE IF NOT EXISTS source_regions (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES import_items(id),
    source_page_id TEXT NOT NULL REFERENCES source_pages(id),
    region_type TEXT NOT NULL,
    bbox_json TEXT NOT NULL,
    coordinate_space TEXT NOT NULL DEFAULT 'original'
);
CREATE TABLE IF NOT EXISTS import_judgments (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES import_items(id),
    revision INTEGER NOT NULL,
    verdict TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    basis_version TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(item_id, revision)
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    learner_id TEXT REFERENCES learners(id),
    visibility TEXT NOT NULL DEFAULT 'shared',
    approval TEXT NOT NULL DEFAULT 'draft',
    objective_id TEXT REFERENCES review_objectives(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS question_versions (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id),
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL,
    answer_key_json TEXT NOT NULL,
    validator_version TEXT NOT NULL,
    approval TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    UNIQUE(question_id, version)
);
CREATE TABLE IF NOT EXISTS mistake_entries (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    question_id TEXT,
    objective_id TEXT REFERENCES review_objectives(id),
    status TEXT NOT NULL DEFAULT 'active',
    diagnosis_status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS mistake_sources (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES mistake_entries(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    source_kind TEXT NOT NULL CHECK(source_kind IN ('uploaded_work','test_attempt')),
    occurrence_id TEXT NOT NULL,
    item_locator TEXT NOT NULL,
    item_id TEXT REFERENCES import_items(id),
    import_judgment_id TEXT REFERENCES import_judgments(id),
    attempt_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(learner_id, source_kind, occurrence_id, item_locator)
);

CREATE TABLE IF NOT EXISTS learning_drafts (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    objective_id TEXT REFERENCES review_objectives(id),
    content_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_events (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    objective_id TEXT REFERENCES review_objectives(id),
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    assistance TEXT NOT NULL DEFAULT 'none',
    observed_at TEXT,
    accepted_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS diagnoses (
    id TEXT PRIMARY KEY,
    mistake_id TEXT NOT NULL REFERENCES mistake_entries(id),
    question_version_id TEXT,
    source_attempt_id TEXT,
    evidence_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'needs_review',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_cards (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    knowledge_point_id TEXT NOT NULL REFERENCES knowledge_points(id),
    objective_id TEXT NOT NULL REFERENCES review_objectives(id),
    state TEXT NOT NULL CHECK(state IN ('review','relearning','maintenance')),
    stage INTEGER NOT NULL CHECK(stage BETWEEN 0 AND 5),
    due_at TEXT NOT NULL,
    timezone_snapshot TEXT NOT NULL,
    scheduler_version TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    last_exposure_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(learner_id, knowledge_point_id, objective_id)
);

CREATE TABLE IF NOT EXISTS test_sessions (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    mode TEXT NOT NULL CHECK(mode IN ('independent','practice')),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS test_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES test_sessions(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    question_version_id TEXT NOT NULL REFERENCES question_versions(id),
    card_id TEXT REFERENCES review_cards(id),
    cycle_id TEXT,
    reserved_revision INTEGER,
    status TEXT NOT NULL DEFAULT 'reserved',
    assistance TEXT NOT NULL DEFAULT 'none',
    presented_at TEXT,
    UNIQUE(card_id, cycle_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_card_item ON test_items(card_id) WHERE card_id IS NOT NULL AND status IN ('reserved','presented','grading_pending');
CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    test_item_id TEXT NOT NULL UNIQUE REFERENCES test_items(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    raw_answer TEXT NOT NULL,
    normalized_answer TEXT,
    source TEXT NOT NULL DEFAULT 'test',
    source_region_ids_json TEXT NOT NULL DEFAULT '[]',
    submitted_at TEXT NOT NULL,
    assistance TEXT NOT NULL DEFAULT 'none',
    assessment_eligibility INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'grading_pending',
    idempotency_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS grade_versions (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts(id),
    outcome TEXT NOT NULL CHECK(outcome IN ('correct','incorrect','partial','undetermined')),
    score REAL,
    feedback TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    validator_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    supersedes_id TEXT
);
CREATE TABLE IF NOT EXISTS review_events (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES review_cards(id),
    cycle_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL REFERENCES attempts(id),
    grade_version_id TEXT NOT NULL REFERENCES grade_versions(id),
    event_type TEXT NOT NULL DEFAULT 'initial',
    before_json TEXT NOT NULL,
    after_json TEXT NOT NULL,
    scheduler_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(card_id, cycle_id, event_type)
);

CREATE TABLE IF NOT EXISTS interaction_challenges (
    id TEXT PRIMARY KEY,
    actor_account_id TEXT NOT NULL REFERENCES accounts(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    operation TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    resource_versions_json TEXT NOT NULL,
    nonce_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_records (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    operation TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    idem_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(account_id, operation, resource_id, idem_key)
);
CREATE TABLE IF NOT EXISTS batch_operations (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES import_batches(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    status TEXT NOT NULL DEFAULT 'queued',
    selected_json TEXT NOT NULL,
    result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    learner_id TEXT REFERENCES learners(id),
    kind TEXT NOT NULL,
    input_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued',
    lease_token TEXT,
    lease_until TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    goal TEXT NOT NULL,
    allowed_actions_json TEXT NOT NULL,
    budget_steps INTEGER NOT NULL,
    budget_ms INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    stop_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES agent_runs(id),
    step_index INTEGER NOT NULL,
    action TEXT NOT NULL,
    input_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, step_index)
);
CREATE TABLE IF NOT EXISTS visual_templates (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    template_id TEXT NOT NULL,
    parameter_schema_json TEXT NOT NULL,
    approval TEXT NOT NULL DEFAULT 'approved',
    created_at TEXT NOT NULL,
    UNIQUE(template_id, version)
);
CREATE TABLE IF NOT EXISTS visual_assets (
    id TEXT PRIMARY KEY,
    learner_id TEXT REFERENCES learners(id),
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private',
    approval TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media_events (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    objective_id TEXT REFERENCES review_objectives(id),
    asset_id TEXT REFERENCES visual_assets(id),
    kind TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    observed_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    account_id TEXT,
    learner_id TEXT,
    operation TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    result TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deletion_records (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(resource_type, resource_id)
);
