-- Existing sessions retain their legacy behavior; only newly frozen sessions
-- can be explicitly collected from a trusted presentation snapshot.
ALTER TABLE test_items ADD COLUMN question_snapshot_json TEXT;

CREATE TRIGGER test_item_question_snapshot_immutable
BEFORE UPDATE OF question_snapshot_json ON test_items
WHEN OLD.question_snapshot_json IS NOT NEW.question_snapshot_json
BEGIN
    SELECT RAISE(ABORT, 'test presentation snapshot is immutable');
END;
