"""Consistent backup and isolated restore for the DD-1.0 data set."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import Database


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_data(source_dir: Path, destination: Path, *, writers_stopped: bool = False) -> dict[str, object]:
    """Back up the database through SQLite's online backup API and copy assets."""
    source_dir = source_dir.resolve()
    destination = destination.resolve()
    db_path = source_dir / "learning.db"
    attachments = source_dir / "attachments"
    if destination == source_dir or any(destination.is_relative_to(source_dir / name) for name in ("attachments", "exports")):
        raise ValueError("backup destination must be outside copied asset directories")
    if db_path.is_symlink() or any(p.is_symlink() for name in ("attachments", "exports") for p in [source_dir/name, *(source_dir/name).rglob("*")]):
        raise ValueError("backup source must not contain symlinks")
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    destination.mkdir(parents=True, exist_ok=False)
    backup_db = destination / "learning.db"
    source = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(backup_db)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    if attachments.is_dir():
        shutil.copytree(attachments, destination / "attachments")
    exports = source_dir / "exports"
    if exports.is_dir():
        shutil.copytree(exports, destination / "exports")
    files = [path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()]
    manifest = {
        "format": "dd-learning-backup-v1",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_dir": str(source_dir),
        "consistency": "caller_asserted_writers_stopped" if writers_stopped else "online_database_snapshot_with_sequential_asset_copy",
        "files": {name: _sha256(destination / name) for name in sorted(files)},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def restore_data(backup_dir: Path, target_dir: Path) -> dict[str, object]:
    """Restore a backup into a new directory, refusing accidental overwrite."""
    backup_dir = backup_dir.resolve()
    target_dir = target_dir.resolve()
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file() or not (backup_dir / "learning.db").is_file():
        raise FileNotFoundError("backup manifest or database missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "dd-learning-backup-v1":
        raise ValueError("unsupported backup format")
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict) or "learning.db" not in manifest_files:
        raise ValueError("backup manifest has no database entry")
    actual_files = {
        path.relative_to(backup_dir).as_posix()
        for path in backup_dir.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(manifest_files) != actual_files:
        raise ValueError("backup manifest file list mismatch")
    for name, expected in manifest_files.items():
        path = (backup_dir / name).resolve()
        if backup_dir not in path.parents or not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"backup checksum mismatch: {name}")
    if target_dir.exists() and any(target_dir.iterdir()):
        raise FileExistsError(f"restore target is not empty: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(backup_dir / "learning.db", target_dir / "learning.db")
        if (backup_dir / "attachments").is_dir():
            shutil.copytree(backup_dir / "attachments", target_dir / "attachments")
        if (backup_dir / "exports").is_dir():
            shutil.copytree(backup_dir / "exports", target_dir / "exports")
        # A backup may come from a previous schema revision. Apply the current
        # migrations before replaying lifecycle tombstones so newly introduced
        # cleanup columns and tables are available during recovery.
        restored_db = Database(target_dir / "learning.db")
        # A restored snapshot must not revive previously logged-out browser
        # sessions. The gateway performs a fresh login after recovery.
        with restored_db.session(write=True) as conn:
            conn.execute("UPDATE browser_sessions SET revoked_at=COALESCE(revoked_at,datetime('now'))")
            conn.execute("UPDATE account_contexts SET learner_id=NULL,revision=revision+1,updated_at=datetime('now')")
            conn.execute("UPDATE interaction_challenges SET consumed_at=COALESCE(consumed_at,datetime('now'))")
            conn.execute("UPDATE provider_control SET paused=1,updated_at=datetime('now') WHERE id=1")
            conn.execute("UPDATE provider_calls SET state='unknown',error_code='RESTORED_PENDING_CALL' WHERE state='reserved'")
        integrity = sqlite3.connect(target_dir / "learning.db")
        try:
            result = integrity.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            integrity.close()
        if result != "ok":
            raise ValueError("restored database integrity check failed")
        _replay_deletions(target_dir)
    except Exception:
        # A failed restore must not leave a directory that looks usable to a
        # later retry. The target was required to be empty above.
        shutil.rmtree(target_dir, ignore_errors=True)
        raise
    return {"format": manifest["format"], "restored_to": str(target_dir), "files": manifest_files}


def _replay_deletions(data_dir: Path) -> None:
    """Reapply tombstones after restore so a stale backup cannot re-expose data."""
    db_path = data_dir / "learning.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            records = conn.execute("SELECT learner_id,resource_type,resource_id,object_key FROM deletion_records").fetchall()
        except sqlite3.OperationalError:
            records = conn.execute("SELECT learner_id,resource_type,resource_id FROM deletion_records").fetchall()
        for record in records:
            object_key = record["object_key"] if "object_key" in record.keys() else None
            resource_type = record["resource_type"]
            if not object_key and resource_type == "asset":
                asset = conn.execute("SELECT object_key FROM assets WHERE id=?", (record["resource_id"],)).fetchone()
                object_key = asset["object_key"] if asset else None
            if object_key:
                root = data_dir / "exports" if resource_type == "export_artifact" else data_dir / "attachments"
                target = (root / object_key).resolve()
                if root.resolve() in target.parents:
                    target.unlink(missing_ok=True)
            try:
                resource_id = record["resource_id"]
                if resource_type == "asset":
                    conn.execute("UPDATE assets SET deleted_at=COALESCE(deleted_at, datetime('now')) WHERE id=?", (resource_id,))
                elif resource_type == "diagnosis":
                    conn.execute("UPDATE diagnoses SET status='deleted' WHERE id=?", (resource_id,))
                elif resource_type == "learning_draft":
                    conn.execute("UPDATE learning_drafts SET status='deleted' WHERE id=?", (resource_id,))
                elif resource_type == "visual_asset":
                    conn.execute("UPDATE visual_assets SET approval='retracted' WHERE id=?", (resource_id,))
                elif resource_type == "mistake":
                    conn.execute("UPDATE mistake_entries SET status='deleted',archived_at=COALESCE(archived_at, datetime('now')) WHERE id=?", (resource_id,))
                elif resource_type == "review_card":
                    conn.execute("UPDATE review_cards SET active=0,updated_at=datetime('now') WHERE id=?", (resource_id,))
                elif resource_type == "test_session":
                    conn.execute("UPDATE test_sessions SET status='deleted',completed_at=COALESCE(completed_at, datetime('now')) WHERE id=?", (resource_id,))
                elif resource_type == "attempt":
                    conn.execute("UPDATE attempts SET status='deleted' WHERE id=?", (resource_id,))
                elif resource_type == "review_request":
                    conn.execute("UPDATE review_requests SET status='cancelled',updated_at=datetime('now') WHERE id=?", (resource_id,))
                elif resource_type == "private_question":
                    conn.execute("UPDATE questions SET approval='retracted' WHERE id=?", (resource_id,))
                    conn.execute("UPDATE question_versions SET approval='retracted' WHERE question_id=?", (resource_id,))
                elif resource_type == "export_artifact":
                    conn.execute("UPDATE export_jobs SET status='cancelled',error_code='DATA_DELETED',completed_at=COALESCE(completed_at, datetime('now')) WHERE id=?", (resource_id,))
                conn.execute("UPDATE deletion_records SET cleanup_state='completed',deleted_at=COALESCE(deleted_at, datetime('now')) WHERE resource_type=? AND resource_id=?", (resource_type, resource_id))
                conn.execute("UPDATE learner_access SET active=0 WHERE learner_id=?", (record["learner_id"],))
                conn.execute("UPDATE learners SET active=0 WHERE id=?", (record["learner_id"],))
            except sqlite3.OperationalError:
                # Older backups may predate one of the optional lifecycle
                # tables. The tombstone still remains authoritative.
                conn.execute("UPDATE deletion_records SET cleanup_state='completed',deleted_at=COALESCE(deleted_at, datetime('now')) WHERE resource_type=? AND resource_id=?", (resource_type, record["resource_id"]))
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="DD-1.0 learning data backup/restore")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("source_dir", type=Path)
    backup_parser.add_argument("destination", type=Path)
    backup_parser.add_argument("--writers-stopped", action="store_true", help="Record the operator's maintenance assertion; does not stop processes")
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup_dir", type=Path)
    restore_parser.add_argument("target_dir", type=Path)
    args = parser.parse_args()
    result = backup_data(args.source_dir, args.destination, writers_stopped=args.writers_stopped) if args.command == "backup" else restore_data(args.backup_dir, args.target_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
