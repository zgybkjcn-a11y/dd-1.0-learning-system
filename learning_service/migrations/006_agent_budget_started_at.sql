ALTER TABLE agent_runs ADD COLUMN budget_started_at TEXT;
UPDATE agent_runs SET budget_started_at=created_at WHERE budget_started_at IS NULL;
