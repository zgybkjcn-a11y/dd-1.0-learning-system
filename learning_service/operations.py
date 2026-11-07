"""Small privacy-preserving monitoring and isolated recovery checks."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


def monitor(metrics: dict, *, queue_age_seconds: int = 300) -> dict:
    """Never copy unknown fields, resource IDs or provider payloads to alerts."""
    jobs, calls = metrics.get("jobs", {}), metrics.get("external_calls", {})
    alerts = []
    if metrics.get("status") != "ok": alerts.append("METRICS_UNAVAILABLE")
    age = jobs.get("oldest_queued_age_seconds")
    if type(age) is int and age > queue_age_seconds: alerts.append("QUEUE_AGE_EXCEEDED")
    if jobs.get("expired_running_leases", 0): alerts.append("WORKER_LEASE_EXPIRED")
    if metrics.get("pages", {}).get("failed", 0): alerts.append("IMPORT_PAGE_FAILURE")
    if metrics.get("lifecycle", {}).get("pending_deletions", 0): alerts.append("DELETION_PENDING")
    if calls.get("paused"): alerts.append("PROVIDER_DISPATCH_PAUSED")
    if calls.get("invoice_pending_calls", 0): alerts.append("PROVIDER_INVOICE_PENDING")
    if calls.get("by_state", {}).get("unknown", 0): alerts.append("PROVIDER_USAGE_UNKNOWN")
    return {"status": "attention" if alerts else "ok", "alerts": alerts,
            "chat_costs_covered": False, "student_payload_included": False}


FROZEN_TABLES = ("variant_reviews", "variant_revocations", "attempts", "grade_versions",
                 "review_events", "test_sessions", "test_items", "learning_events",
                 "identity_bindings", "learner_access", "accounts", "learners",
                 "source_documents", "source_pages", "import_items", "import_judgments",
                 "mistake_entries", "mistake_sources", "review_requests", "idempotency_records")


def recovery_inventory(data_dir: Path) -> dict:
    """Read a named isolated copy; report hashes/counts rather than private rows."""
    data_dir = data_dir.resolve()
    with sqlite3.connect((data_dir / "learning.db").as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        fingerprints = {}
        for name in FROZEN_TABLES:
            if name not in tables: continue
            rows = [dict(r) for r in conn.execute('SELECT * FROM "' + name + '"')]
            rows.sort(key=lambda r: json.dumps(r, sort_keys=True))
            fingerprints[name] = {"count":len(rows), "sha256":hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
        versions = [dict(r) for r in conn.execute("SELECT v.* FROM question_versions v JOIN variant_reviews r ON r.question_version_id=v.id ORDER BY v.id")]
        fingerprints["published_versions"] = {"count":len(versions), "sha256":hashlib.sha256(json.dumps(versions, sort_keys=True).encode()).hexdigest()}
        missing_assets = 0
        for row in conn.execute("SELECT object_key FROM assets WHERE deleted_at IS NULL"):
            target = (data_dir / "attachments" / row[0]).resolve()
            if not target.is_relative_to(data_dir / "attachments") or not target.is_file(): missing_assets += 1
        calls = conn.execute("SELECT COUNT(*),COALESCE(SUM(reserved_cost_micros),0),COALESCE(SUM(reconciled_cost_micros),0) FROM provider_calls").fetchone()
        return {"integrity":integrity, "foreign_key_errors":foreign_keys, "missing_assets":missing_assets,
                "schema_revision":conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0],
                "business_fingerprints":fingerprints,
                "provider_call_count":calls[0], "provider_reserved_cost_micros":calls[1], "provider_reconciled_cost_micros":calls[2],
                "active_browser_sessions":conn.execute("SELECT COUNT(*) FROM browser_sessions WHERE revoked_at IS NULL").fetchone()[0],
                "selected_contexts":conn.execute("SELECT COUNT(*) FROM account_contexts WHERE learner_id IS NOT NULL").fetchone()[0],
                "unconsumed_challenges":conn.execute("SELECT COUNT(*) FROM interaction_challenges WHERE consumed_at IS NULL").fetchone()[0],
                "reserved_calls":conn.execute("SELECT COUNT(*) FROM provider_calls WHERE state='reserved'").fetchone()[0],
                "unknown_calls":conn.execute("SELECT COUNT(*) FROM provider_calls WHERE state='unknown'").fetchone()[0],
                "provider_paused":bool(conn.execute("SELECT paused FROM provider_control WHERE id=1").fetchone()[0])}


def verify_recovery(before: dict, after: dict) -> dict:
    errors = []
    for k in ("business_fingerprints", "provider_call_count", "provider_reserved_cost_micros", "provider_reconciled_cost_micros"):
        if before[k] != after[k]: errors.append(k + "_changed")
    if after["integrity"] != "ok" or after["foreign_key_errors"] or after["missing_assets"]:
        errors.append("database_or_asset_integrity")
    if any(after[k] for k in ("active_browser_sessions", "selected_contexts", "unconsumed_challenges", "reserved_calls")) or not after["provider_paused"]:
        errors.append("restored_runtime_not_invalidated")
    if after["unknown_calls"] != before["unknown_calls"] + before["reserved_calls"]:
        errors.append("pending_usage_hold_changed")
    return {"status":"passed" if not errors else "failed", "errors":errors,
            "scope":"isolated_learning_database_and_assets", "webui_database_backed_up":False,
            "formal_RPO_RTO_verified":False}
