-- Preserve every workspace, round id and test-item reference while adding a tier.
CREATE TABLE practice_workspaces_v14 (
    learner_id TEXT PRIMARY KEY REFERENCES learners(id),
    book_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL CHECK(difficulty IN ('auto','easy','normal','hard','challenge')),
    pool TEXT NOT NULL CHECK(pool IN ('initial','reserve')),
    current_session_id TEXT REFERENCES test_sessions(id),
    revision INTEGER NOT NULL CHECK(revision >= 1),
    updated_at TEXT NOT NULL
);
INSERT INTO practice_workspaces_v14 SELECT * FROM practice_workspaces;
DROP TABLE practice_workspaces;
ALTER TABLE practice_workspaces_v14 RENAME TO practice_workspaces;
CREATE TABLE practice_rounds_v14 (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES learners(id),
    book_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL DEFAULT '',
    pool TEXT NOT NULL CHECK(pool IN ('initial','reserve')),
    difficulty TEXT NOT NULL CHECK(difficulty IN ('easy','normal','hard','challenge','starter')),
    generation INTEGER NOT NULL DEFAULT 1 CHECK(generation >= 1),
    UNIQUE(learner_id,book_id,chapter_id,pool,difficulty)
);
INSERT INTO practice_rounds_v14 SELECT * FROM practice_rounds;
DROP TABLE practice_rounds;
ALTER TABLE practice_rounds_v14 RENAME TO practice_rounds;
