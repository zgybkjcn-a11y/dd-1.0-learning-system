ALTER TABLE source_pages ADD COLUMN extracted_text TEXT;
ALTER TABLE source_pages ADD COLUMN extraction_format TEXT;
ALTER TABLE mistake_entries ADD COLUMN content_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE mistake_sources RENAME TO mistake_sources_legacy;

CREATE TABLE mistake_sources (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES mistake_entries(id),
    learner_id TEXT NOT NULL REFERENCES learners(id),
    source_kind TEXT NOT NULL CHECK(source_kind IN ('uploaded_work','test_attempt','manual')),
    occurrence_id TEXT NOT NULL,
    item_locator TEXT NOT NULL,
    item_id TEXT REFERENCES import_items(id),
    import_judgment_id TEXT REFERENCES import_judgments(id),
    attempt_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(learner_id, source_kind, occurrence_id, item_locator)
);

INSERT INTO mistake_sources(
    id,entry_id,learner_id,source_kind,occurrence_id,item_locator,item_id,
    import_judgment_id,attempt_id,active,created_at
)
SELECT
    id,entry_id,learner_id,source_kind,occurrence_id,item_locator,item_id,
    import_judgment_id,attempt_id,active,created_at
FROM mistake_sources_legacy;

DROP TABLE mistake_sources_legacy;
