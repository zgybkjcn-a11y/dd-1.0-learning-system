"""Consistent backup and isolated restore for the DD-1.0 data set."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .db import Database


CONSISTENCY = 'operator_stopped_sqlite_write_lock_verified_files'


def _plain_path(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('backup/restore paths must not contain symlinks')
    return path


def _relative_name(name: str) -> str:
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('invalid archive path')
    path = Path(name)
    if path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')) or path.as_posix() != name:
        raise ValueError('invalid archive path')
    return name


def _files(root: Path) -> dict[str, Path]:
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob('*')):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError('backup source must not contain symlinks or special files')
        if stat.S_ISREG(mode):
            result[path.relative_to(root).as_posix()] = path
    return result


def _sync_tree(root: Path) -> None:
    for path in _files(root).values():
        with path.open('rb') as stream:
            os.fsync(stream.fileno())
    for path in [p for p in root.rglob('*') if p.is_dir()] + [root]:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def _publish_directory(staging: Path, target: Path) -> None:
    """Linux atomic no-replace rename: never replace a concurrent target."""
    rename = getattr(ctypes.CDLL(None, use_errno=True), 'renameat2', None)
    if rename is None:
        raise RuntimeError('atomic no-replace directory publication unavailable')
    if rename(-100, os.fsencode(staging), -100, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))
    fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_receipt(path: Path, value: dict) -> None:
    """Publish an immutable private receipt atomically without replacing history."""
    path = _plain_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.receipt-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.link(temp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(temp).unlink(missing_ok=True)


def _reference_check(conn, root: Path) -> dict:
    """Verify active database references, not merely the copied file list."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assets = exports = 0
    for key, expected, size in conn.execute('SELECT object_key,sha256,byte_size FROM assets WHERE deleted_at IS NULL'):
        target = root / 'attachments' / _relative_name(key)
        if not target.is_file() or target.stat().st_size != size or _sha256(target) != expected:
            raise ValueError('active attachment missing or content hash differs')
        assets += 1
    if 'export_jobs' in tables:
        for key, expected, size in conn.execute("SELECT artifact_key,artifact_sha256,artifact_byte_size FROM export_jobs WHERE status='completed'"):
            target = root / 'exports' / _relative_name(key)
            if not target.is_file() or target.stat().st_size != size or _sha256(target) != expected:
                raise ValueError('completed export missing or content hash differs')
            exports += 1
    if 'source_pages' in tables:
        rows = conn.execute("SELECT p.object_key,p.asset_id,a.object_key,a.deleted_at FROM source_pages p "
            "JOIN source_documents d ON d.id=p.document_id LEFT JOIN assets a ON a.id=p.asset_id "
            "WHERE d.status<>'deleted' AND p.status<>'deleted' AND p.object_key IS NOT NULL").fetchall()
        if any(not r[1] or r[0] != r[2] or r[3] is not None for r in rows):
            raise ValueError('source page asset reference mismatch')
    return {'active_assets': assets, 'completed_exports': exports}


def _database_check(path: Path, *, references_root: Path | None = None) -> dict:
    # Only sealed backup/staging files use immutable mode, never a live source.
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or conn.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('backup database integrity check failed')
        revision = conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
        current = max(int(p.name.split('_')[0]) for p in (Path(__file__).parent / 'migrations').glob('*.sql'))
        if type(revision) is not int or revision > current:
            raise ValueError('unsupported backup schema revision')
        refs = _reference_check(conn, references_root) if references_root else {}
    return {'schema_revision': revision, 'integrity': 'ok', 'foreign_key_errors': 0, **refs}


def verify_backup(backup_dir: Path, *, require_consistent: bool = True) -> dict:
    """Read-only archive verification; does not restore or certify storage custody."""
    started = time.monotonic()
    backup_dir = _plain_path(backup_dir)
    files = _files(backup_dir)
    manifest_path = backup_dir / 'manifest.json'
    if 'manifest.json' not in files or 'learning.db' not in files:
        raise FileNotFoundError('backup manifest or database missing')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('format') not in ('dd-learning-backup-v1', 'dd-learning-backup-v2'):
        raise ValueError('unsupported backup format')
    manifest_files = manifest.get('files')
    if not isinstance(manifest_files, dict) or 'learning.db' not in manifest_files:
        raise ValueError('backup manifest has no database entry')
    for name, expected in manifest_files.items():
        _relative_name(name)
        if name != 'learning.db' and name.split('/')[0] not in ('attachments', 'exports', 'materials', 'versions'):
            raise ValueError('unsupported archive component')
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('invalid archive checksum')
    if set(manifest_files) != set(files) - {'manifest.json'}:
        raise ValueError('backup manifest file list mismatch')
    for name, expected in manifest_files.items():
        if _sha256(files[name]) != expected:
            raise ValueError(f'backup checksum mismatch: {name}')
    strict = manifest.get('format') == 'dd-learning-backup-v2' and manifest.get('consistency') == CONSISTENCY
    if manifest.get('format') == 'dd-learning-backup-v2' and not strict:
        raise ValueError('invalid joint backup consistency metadata')
    if require_consistent and not strict:
        raise ValueError('joint consistency is not verified for this legacy backup')
    checked = _database_check(backup_dir / 'learning.db', references_root=backup_dir if strict else None)
    return {'format': 'dd-learning-backup-verification-v1', 'status': 'passed', 'verified': True,
            'finished_at': int(time.time()), 'duration_seconds': round(time.monotonic() - started, 6),
            'manifest_sha256': _sha256(manifest_path), 'file_count': len(manifest_files),
            'archive_bytes': sum(files[n].stat().st_size for n in manifest_files), 'database': checked,
            'joint_consistency_checked': strict, 'process_stop_independently_verified': False,
            'recovery_performed': False, 'independent_fault_domain_verified': False}


def _sha256(path: Path) -> str:
    path = _plain_path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_data(source_dir: Path, destination: Path, *, writers_stopped: bool = False,
                include_files: dict[str, Path] | None = None, lock_timeout: float = 5.0) -> dict[str, object]:
    """Preserve legacy snapshots; stopped-writer mode seals a checked joint bundle.

    The flag is an operator assertion, not a process-stop command. The database
    lock and before/after file checks supplement it; they cannot stop arbitrary
    external writers modifying files outside SQLite transactions.
    """
    source_dir, destination = _plain_path(source_dir), _plain_path(destination)
    if (destination == source_dir or source_dir.is_relative_to(destination)
            or any(destination.is_relative_to(source_dir / name) for name in ('attachments', 'exports'))):
        raise ValueError('backup destination must be outside copied asset directories')
    db_path = _plain_path(source_dir / 'learning.db')
    if not db_path.is_file(): raise FileNotFoundError(db_path)
    if destination.exists(): raise FileExistsError('backup destination already exists')
    if include_files and not writers_stopped:
        raise ValueError('named materials require stopped-writer backup mode')
    if not 0 <= lock_timeout <= 60: raise ValueError('invalid lock timeout')
    extras = {}
    for name, path in (include_files or {}).items():
        _relative_name(name)
        if name.split('/')[0] not in ('materials', 'versions') or len(Path(name).parts) < 2:
            raise ValueError('named files must be under materials/ or versions/')
        path = _plain_path(path)
        if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError('named source file is not a regular file')
        if path.is_relative_to(destination): raise ValueError('source file overlaps destination')
        extras[name] = path
    def inventory():
        paths = dict(extras)
        for name in ('attachments', 'exports'):
            folder = _plain_path(source_dir / name)
            if folder.exists() and not folder.is_dir(): raise ValueError('asset root must be a directory')
            paths.update({name + '/' + n: p for n, p in _files(folder).items()})
        return paths
    inventory()  # Validate paths before creating output or acquiring locks.
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.backup-', dir=destination.parent))
    guard = None
    try:
        identity = (db_path.stat().st_dev, db_path.stat().st_ino)
        if writers_stopped:
            guard = sqlite3.connect(db_path.as_uri() + '?mode=rw', uri=True, timeout=lock_timeout, isolation_level=None)
            guard.execute('BEGIN IMMEDIATE')
        paths = inventory()
        before_hashes = {n: _sha256(p) for n, p in paths.items()}
        if writers_stopped: _reference_check(guard, source_dir)
        with closing(sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(staging / 'learning.db')) as target:
                source.backup(target)
        for name, path in paths.items():
            target = staging / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        if writers_stopped:
            after_paths = inventory()
            if set(after_paths) != set(paths) or {n: _sha256(p) for n, p in after_paths.items()} != before_hashes:
                raise ValueError('source files changed during backup')
            if (db_path.stat().st_dev, db_path.stat().st_ino) != identity:
                raise ValueError('source database identity changed during backup')
            if any(_sha256(staging / n) != h for n, h in before_hashes.items()):
                raise ValueError('copied file checksum mismatch')
        files = _files(staging)
        manifest = {
            'format': 'dd-learning-backup-v2' if writers_stopped else 'dd-learning-backup-v1',
            'created_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            'source_dir': str(source_dir),
            'consistency': CONSISTENCY if writers_stopped else 'online_database_snapshot_with_sequential_asset_copy',
            'process_stop': 'operator_assertion' if writers_stopped else 'not_asserted',
            'files': {n: _sha256(p) for n, p in files.items()},
            'named_components': sorted(extras), 'independent_fault_domain_verified': False,
        }
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        verify_backup(staging, require_consistent=writers_stopped)
        _sync_tree(staging)
        _publish_directory(staging, destination)
        return manifest
    finally:
        if guard is not None: guard.rollback(); guard.close()
        if staging.exists(): shutil.rmtree(staging)


def restore_data(backup_dir: Path, target_dir: Path, *, require_consistent: bool = False) -> dict[str, object]:
    """Verify, stage, migrate and invalidate sessions before no-replace publication."""
    started = time.monotonic()
    backup_dir, target_dir = _plain_path(backup_dir), _plain_path(target_dir)
    if target_dir.is_relative_to(backup_dir) or backup_dir.is_relative_to(target_dir):
        raise ValueError('restore target must be outside the backup directory')
    if target_dir.exists() and (not target_dir.is_dir() or any(target_dir.iterdir())):
        raise FileExistsError(f'restore target is not empty: {target_dir}')
    verification = verify_backup(backup_dir, require_consistent=require_consistent)
    manifest_bytes = (backup_dir / 'manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != verification['manifest_sha256']:
        raise ValueError('backup manifest changed while restoring')
    manifest = json.loads(manifest_bytes)
    manifest_files = manifest['files']
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.restore-', dir=target_dir.parent))
    try:
        for name, expected in manifest_files.items():
            source = _plain_path(backup_dir / name)
            target = staging / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if _sha256(target) != expected:
                raise ValueError('backup changed while restoring')
        if _sha256(backup_dir / 'manifest.json') != verification['manifest_sha256']:
            raise ValueError('backup manifest changed while restoring')
        restored_db = Database(staging / 'learning.db')
        with restored_db.session(write=True) as conn:
            conn.execute("UPDATE browser_sessions SET revoked_at=COALESCE(revoked_at,datetime('now'))")
            conn.execute("UPDATE account_contexts SET learner_id=NULL,revision=revision+1,updated_at=datetime('now')")
            conn.execute("UPDATE interaction_challenges SET consumed_at=COALESCE(consumed_at,datetime('now'))")
            conn.execute("UPDATE provider_control SET paused=1,updated_at=datetime('now') WHERE id=1")
            conn.execute("UPDATE provider_calls SET state='unknown',error_code='RESTORED_PENDING_CALL' WHERE state='reserved'")
        _replay_deletions(staging)
        # Close/checkpoint before immutable validation and final publication.
        with closing(restored_db.connect()) as conn:
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        checked = _database_check(staging / 'learning.db', references_root=staging if verification['joint_consistency_checked'] else None)
        with closing(sqlite3.connect((staging / 'learning.db').as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
            assert conn.execute('SELECT COUNT(*) FROM browser_sessions WHERE revoked_at IS NULL').fetchone()[0] == 0
            assert conn.execute('SELECT COUNT(*) FROM account_contexts WHERE learner_id IS NOT NULL').fetchone()[0] == 0
            assert conn.execute('SELECT COUNT(*) FROM interaction_challenges WHERE consumed_at IS NULL').fetchone()[0] == 0
            assert conn.execute('SELECT paused FROM provider_control WHERE id=1').fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM provider_calls WHERE state='reserved'").fetchone()[0] == 0
        _sync_tree(staging)
        if target_dir.exists():
            _plain_path(target_dir)
            target_dir.rmdir()  # Fails if concurrent work made the empty target nonempty.
        _publish_directory(staging, target_dir)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return {'format': manifest['format'], 'restored_to': str(target_dir), 'files': manifest_files,
            'receipt_format': 'dd-learning-restore-receipt-v1', 'status': 'passed',
            'manifest_sha256': verification['manifest_sha256'], 'finished_at': int(time.time()),
            'duration_seconds': round(time.monotonic() - started, 6), 'database': checked,
            'runtime_sessions_invalidated': True, 'provider_paused': True,
            'joint_consistency_checked': verification['joint_consistency_checked'],
            'scope': 'isolated_learning_bundle', 'full_architecture_recovered': False,
            'business_equivalence_checked': False,
            'post_snapshot_deletions_or_billing_replayed': False, 'independent_fault_domain_verified': False}


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
                elif resource_type == 'practice_workspace':
                    conn.execute('DELETE FROM practice_workspaces WHERE learner_id=?', (resource_id,))
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
    backup_parser.add_argument('--include', action='append', default=[], metavar='NAME=PATH', help='Explicit file under materials/ or versions/; never scans configuration')
    backup_parser.add_argument('--receipt', type=Path)
    verify_parser = subparsers.add_parser('verify')
    verify_parser.add_argument('backup_dir', type=Path)
    verify_parser.add_argument('--receipt', type=Path)
    verify_parser.add_argument('--observation', type=Path, help='Write learning-only backup verification observation for the monitor')
    verify_parser.add_argument('--allow-legacy-sequential', action='store_true')
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup_dir", type=Path)
    restore_parser.add_argument("target_dir", type=Path)
    restore_parser.add_argument('--receipt', type=Path)
    restore_parser.add_argument('--allow-legacy-sequential', action='store_true')
    args = parser.parse_args()
    if args.command == 'backup' and not args.writers_stopped:
        parser.error('backup requires --writers-stopped after independently stopping all writers')
    roots = [getattr(args, name, None) for name in ('source_dir', 'destination', 'backup_dir', 'target_dir')]
    if args.receipt and getattr(args, 'observation', None) and _plain_path(args.receipt) == _plain_path(args.observation):
        parser.error('verification receipt and monitor observation must be separate files')
    for receipt in (args.receipt, getattr(args, 'observation', None)):
        if receipt is not None:
            receipt = _plain_path(receipt)
            if receipt.exists() or any(receipt.is_relative_to(_plain_path(root)) for root in roots if root is not None):
                parser.error('receipt must be a new file outside source, archive and restore directories')
    started = time.monotonic()
    if args.command == 'backup':
        include = {}
        for value in args.include:
            name, separator, path = value.partition('=')
            if not separator or name in include: parser.error('invalid or duplicate --include')
            include[name] = Path(path)
        manifest = backup_data(args.source_dir, args.destination, writers_stopped=True, include_files=include)
        result = {'format': 'dd-learning-backup-receipt-v1', 'status': 'passed', 'finished_at': int(time.time()),
                  'duration_seconds': round(time.monotonic() - started, 6), 'manifest_sha256': _sha256(args.destination / 'manifest.json'),
                  'file_count': len(manifest['files']), 'consistency': manifest['consistency'],
                  'process_stop_independently_verified': False, 'recovery_performed': False, 'independent_fault_domain_verified': False}
    elif args.command == 'verify':
        result = verify_backup(args.backup_dir, require_consistent=not args.allow_legacy_sequential)
        if args.observation:
            if not result['joint_consistency_checked']: parser.error('legacy sequential backup cannot produce verified monitor observation')
            write_receipt(args.observation, {'format': 'dd-learning-backup-observation-v1', 'scope': 'learning_only',
                'status': 'passed', 'verified': True, 'finished_at': result['finished_at'],
                'manifest_sha256': result['manifest_sha256'], 'recovery_performed': False,
                'independent_fault_domain_verified': False})
    else:
        result = restore_data(args.backup_dir, args.target_dir, require_consistent=not args.allow_legacy_sequential)
    if args.receipt: write_receipt(args.receipt, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
