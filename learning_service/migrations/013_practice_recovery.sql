-- Server-owned family workspace; legacy sessions/attempts are not rewritten.
CREATE TABLE practice_workspaces (
    learner_id TEXT PRIMARY KEY REFERENCES learners(id),
    book_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL CHECK(difficulty IN ('auto','easy','normal','hard')),
    pool TEXT NOT NULL CHECK(pool IN ('initial','reserve')),
    current_session_id TEXT REFERENCES test_sessions(id),
    revision INTEGER NOT NULL CHECK(revision >= 1),
    updated_at TEXT NOT NULL
);
CREATE TABLE practice_rounds (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    book_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL DEFAULT '',
    pool TEXT NOT NULL CHECK(pool IN ('initial','reserve')),
    difficulty TEXT NOT NULL CHECK(difficulty IN ('easy','normal','hard','starter')),
    generation INTEGER NOT NULL DEFAULT 1 CHECK(generation >= 1),
    UNIQUE(learner_id,book_id,chapter_id,pool,difficulty)
);
ALTER TABLE test_items ADD COLUMN practice_round_id TEXT REFERENCES practice_rounds(id);
ALTER TABLE test_items ADD COLUMN practice_round_generation INTEGER;
CREATE INDEX practice_round_items ON test_items(practice_round_id,practice_round_generation,status);
