ALTER TABLE source_pages ADD COLUMN asset_id TEXT REFERENCES assets(id);
ALTER TABLE import_batches ADD COLUMN answer_document_id TEXT REFERENCES source_documents(id);

CREATE INDEX IF NOT EXISTS source_pages_asset_id_idx ON source_pages(asset_id);
CREATE INDEX IF NOT EXISTS import_batches_answer_document_idx ON import_batches(answer_document_id);
