ALTER TABLE question_versions ADD COLUMN variant_kind TEXT NOT NULL DEFAULT 'base';
ALTER TABLE question_versions ADD COLUMN variant_group TEXT;
CREATE INDEX IF NOT EXISTS question_versions_variant_idx
  ON question_versions(variant_kind, variant_group, approval);
