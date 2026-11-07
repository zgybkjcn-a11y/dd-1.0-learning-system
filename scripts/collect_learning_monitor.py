#!/usr/bin/env python3
"""Local-only monitoring: read-only SQL, writable SQLite side files, no delivery."""
from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import os
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service.gateway_http import GatewayHTTP
from learning_service.operations import monitor

FORMAT = 'dd-learning-monitor-v1'
ALERTS = frozenset({
    'METRICS_UNAVAILABLE', 'DATABASE_SCHEMA_UNSUPPORTED', 'QUEUE_AGE_EXCEEDED',
    'WORKER_LEASE_EXPIRED', 'IMPORT_PAGE_FAILURE', 'DELETION_PENDING',
    'PROVIDER_DISPATCH_PAUSED', 'PROVIDER_INVOICE_PENDING', 'PROVIDER_USAGE_UNKNOWN',
    'REVIEW_BACKLOG_EXCEEDED', 'API_UNAVAILABLE', 'STORAGE_UNAVAILABLE',
    'STORAGE_BYTES_LOW', 'STORAGE_INODES_LOW', 'STORAGE_INODES_UNKNOWN',
    'BACKUP_UNOBSERVED', 'BACKUP_FAILED', 'BACKUP_STALE', 'BACKUP_RECEIPT_INVALID',
    'MONITOR_STATE_INVALID', 'MONITOR_CLOCK_REVERSED',
})


def read_json(path: Path, limit=16384):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError('regular file required')
        data = f.read(limit + 1)
    if len(data) > limit:
        raise ValueError('bounded JSON required')
    return json.loads(data)


def db_alerts(path: Path, now: int, queue_age: int, review_limit: int) -> list[str]:
    conn = None
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError('named database required')
        conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
        conn.execute('PRAGMA query_only=ON')
        deadline = time.monotonic() + 2
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        conn.execute('BEGIN')
        def one(sql, args=()):
            row = conn.execute(sql, args).fetchone()
            if row is None:
                raise ValueError('required aggregate missing')
            return row[0]
        if one('SELECT MAX(version) FROM schema_migrations') != 11:
            return ['DATABASE_SCHEMA_UNSUPPORTED', 'METRICS_UNAVAILABLE']
        age = one("SELECT MAX(0,CAST((julianday(?,'unixepoch')-julianday(MIN(created_at)))*86400 AS INTEGER)) FROM jobs WHERE status='queued'", (now,))
        if age is None and one("SELECT COUNT(*) FROM jobs WHERE status='queued'"):
            raise ValueError('queue timestamp unavailable')
        leases = one("SELECT COUNT(*) FROM jobs WHERE status='running' AND julianday(lease_until)<julianday(?,'unixepoch')", (now,))
        metrics = {'status': 'ok', 'jobs': {'oldest_queued_age_seconds': age, 'expired_running_leases': leases},
                   'pages': {'failed': one("SELECT COUNT(*) FROM source_pages WHERE status='failed' OR failure_code IS NOT NULL")},
                   'lifecycle': {'pending_deletions': one("SELECT COUNT(*) FROM deletion_records WHERE cleanup_state IN ('pending','failed')")},
                   'external_calls': {'paused': bool(one('SELECT paused FROM provider_control WHERE id=1')),
                                      'invoice_pending_calls': one("SELECT COUNT(*) FROM provider_calls WHERE reconciled_cost_micros IS NULL AND evidence_mode='live_http'"),
                                      'by_state': {'unknown': one("SELECT COUNT(*) FROM provider_calls WHERE state='unknown'")}}}
        result = monitor(metrics, queue_age_seconds=queue_age)['alerts']
        pending = one("SELECT COUNT(*) FROM import_items WHERE status IN ('extracted','needs_review','ready') AND verification_status='needs_review'")
        if pending > review_limit:
            result.append('REVIEW_BACKLOG_EXCEEDED')
        return result
    except (OSError, ValueError, sqlite3.Error):
        return ['METRICS_UNAVAILABLE']
    finally:
        if conn is not None:
            conn.close()


def validate_upstream(value: str):
    p = urlsplit(value)
    if p.scheme != 'http' or p.username or p.password or p.path or p.query or p.fragment:
        raise ValueError('internal health origin required')
    if not p.port or not 1 <= p.port <= 65535:
        raise ValueError('explicit health port required')
    if p.hostname != 'learning-api':
        try:
            if not ipaddress.ip_address(p.hostname).is_loopback:
                raise ValueError('loopback or learning-api required')
        except (ValueError, TypeError):
            raise ValueError('loopback or learning-api required') from None


def health_child(upstream: str) -> bool:
    validate_upstream(upstream)
    response = GatewayHTTP().send(upstream, 'GET', '/health', {}, timeout=2, limit=4096)
    data = json.loads(response.body)
    return response.status == 200 and data.get('status') == 'ok' and data.get('service') == 'learning-api' and data.get('schema_revision') == 11


def health_ok(upstream: str) -> bool:
    # A separate process bounds DNS as well as HTTP; no proxy env or credentials.
    try:
        child = subprocess.run([sys.executable, str(Path(__file__).resolve()), '_health', '--upstream', upstream],
                               env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': os.pathsep.join(sys.path)},
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        return child.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def storage_alerts(path: Path, min_bytes: int, min_percent: int, min_inodes: int) -> list[str]:
    try:
        s = os.statvfs(path)
        if s.f_blocks <= 0 or s.f_frsize <= 0:
            raise ValueError('unknown filesystem capacity')
        result = []
        available = s.f_bavail * s.f_frsize
        if available < min_bytes or 100 * s.f_bavail < min_percent * s.f_blocks:
            result.append('STORAGE_BYTES_LOW')
        if s.f_files <= 0:
            result.append('STORAGE_INODES_UNKNOWN')
        elif s.f_favail < min_inodes:
            result.append('STORAGE_INODES_LOW')
        return result
    except (OSError, ValueError):
        return ['STORAGE_UNAVAILABLE']


def backup_alerts(path: Path, now: int, max_age: int) -> list[str]:
    try:
        r = read_json(path, 4096)
        if (not isinstance(r, dict) or r.get('format') != 'dd-learning-backup-observation-v1'
                or r.get('scope') != 'learning_only' or r.get('status') not in {'passed', 'failed'}
                or type(r.get('finished_at')) is not int or not 0 < r['finished_at'] <= now + 60):
            return ['BACKUP_RECEIPT_INVALID']
        if r['status'] == 'failed':
            return ['BACKUP_FAILED']
        if r.get('verified') is not True:
            return ['BACKUP_RECEIPT_INVALID']
        return ['BACKUP_STALE'] if now - r['finished_at'] > max_age else []
    except FileNotFoundError:
        return ['BACKUP_UNOBSERVED']
    except (OSError, ValueError, TypeError):
        return ['BACKUP_RECEIPT_INVALID']


def atomic_json(directory: Path, value: dict):
    fd, filename = tempfile.mkstemp(prefix='.monitor-', dir=directory)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(filename, directory / 'latest.json')
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def previous_state(directory: Path):
    try:
        r = read_json(directory / 'latest.json')
    except FileNotFoundError:
        return None
    if (not isinstance(r, dict) or r.get('format') != FORMAT
            or type(r.get('checked_at')) is not int or type(r.get('last_event_at')) is not int
            or type(r.get('sequence')) is not int or r['sequence'] < 1
            or not isinstance(r.get('alerts'), list) or len(r['alerts']) > len(ALERTS)
            or any(not isinstance(a, str) or a not in ALERTS for a in r['alerts'])):
        raise ValueError('invalid monitor state')
    return r


def publish(directory: Path, alerts: list[str], now: int, reminder_seconds: int) -> dict:
    # The caller owns the directory lock for the entire collection + publication.
    alerts = set(alerts)
    if not alerts <= ALERTS:
        raise ValueError('unknown monitor alert')
    try:
        old = previous_state(directory)
    except (OSError, ValueError, TypeError):
        alerts.add('MONITOR_STATE_INVALID')
        old = None
    previous = set(old['alerts']) if old else set()
    if old and now < max(old['checked_at'], old['last_event_at']):
        alerts.add('MONITOR_CLOCK_REVERSED')
    opened, resolved = sorted(alerts - previous), sorted(previous - alerts)
    event = 'initial' if old is None else ('changed' if opened or resolved else 'none')
    if event == 'none' and alerts and now - old['last_event_at'] >= reminder_seconds:
        event = 'reminder'
    value = {'format': FORMAT, 'checked_at': now, 'alerts': sorted(alerts),
             'status': 'attention' if alerts else 'ok', 'sequence': old['sequence'] + 1 if old else 1,
             'event': event, 'opened': opened, 'resolved': resolved,
             'last_event_at': now if event != 'none' else old['last_event_at'],
             'delivery': 'local_file_only', 'student_payload_included': False,
             'chat_costs_covered': False, 'full_architecture_backup_covered': False}
    atomic_json(directory, value)
    return value


def status(directory: Path, now: int, max_age: int) -> dict:
    try:
        r = previous_state(directory)
        if r is None or not 0 <= now - r['checked_at'] <= max_age:
            return {'status': 'attention', 'alerts': ['MONITOR_STALE']}
        return {'status': 'attention' if r['alerts'] else 'ok', 'alerts': r['alerts'],
                'age_seconds': now - r['checked_at']}
    except (OSError, ValueError, TypeError):
        return {'status': 'attention', 'alerts': ['MONITOR_STATE_INVALID']}


def bounded(low, high):
    def parse(value):
        number = int(value)
        if not low <= number <= high:
            raise argparse.ArgumentTypeError('value outside supported bounds')
        return number
    return parse


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['collect', 'status', '_health'])
    p.add_argument('--state-dir', type=Path)
    p.add_argument('--db', type=Path)
    p.add_argument('--storage', type=Path)
    p.add_argument('--backup-receipt', type=Path)
    p.add_argument('--upstream', default='http://learning-api:31010')
    p.add_argument('--cycles', type=bounded(1, 1000000), default=1)
    p.add_argument('--interval', type=bounded(1, 3600), default=60)
    p.add_argument('--queue-age', type=bounded(1, 86400), default=300)
    p.add_argument('--review-limit', type=bounded(0, 1000000), default=100)
    p.add_argument('--min-free-bytes', type=bounded(0, 2**63-1), default=1024**3)
    p.add_argument('--min-free-percent', type=bounded(0, 99), default=10)
    p.add_argument('--min-free-inodes', type=bounded(0, 2**63-1), default=10000)
    p.add_argument('--backup-max-age', type=bounded(1, 604800), default=86400)
    p.add_argument('--reminder-seconds', type=bounded(1, 604800), default=3600)
    p.add_argument('--stale-seconds', type=bounded(1, 86400), default=180)
    a = p.parse_args()
    if a.action == '_health':
        try:
            return 0 if health_child(a.upstream) else 1
        except Exception:
            return 1
    if a.state_dir is None:
        p.error('--state-dir required')
    if a.action == 'status':
        result = status(a.state_dir, int(time.time()), a.stale_seconds)
        print(json.dumps(result))
        return 0 if result['status'] == 'ok' else 2
    if any(v is None for v in (a.db, a.storage, a.backup_receipt)):
        p.error('--db, --storage and --backup-receipt required')
    validate_upstream(a.upstream)
    if a.state_dir.is_symlink():
        raise ValueError('private state directory required')
    a.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = a.state_dir.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('state directory must be owned by this user with mode 0700')
    fd = os.open(a.state_dir / 'monitor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'w') as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError('regular lock file required')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'status': 'busy', 'error_code': 'MONITOR_ALREADY_RUNNING'}))
            return 3
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        for cycle in range(a.cycles):
            now = int(time.time())
            alerts = db_alerts(a.db, now, a.queue_age, a.review_limit)
            if not health_ok(a.upstream):
                alerts.append('API_UNAVAILABLE')
            alerts.extend(storage_alerts(a.storage, a.min_free_bytes, a.min_free_percent, a.min_free_inodes))
            alerts.extend(backup_alerts(a.backup_receipt, now, a.backup_max_age))
            result = publish(a.state_dir, alerts, int(time.time()), a.reminder_seconds)
            print(json.dumps(result), flush=True)
            if cycle + 1 < a.cycles:
                time.sleep(a.interval)
    return 0 if result['status'] == 'ok' else 2


if __name__ == '__main__':
    try:
        code = main()
    except (OSError, ValueError, sqlite3.Error):
        # Suppress file paths, responses and arbitrary exception strings.
        print(json.dumps({'status': 'error', 'error_code': 'MONITOR_EXECUTION_FAILED'}))
        code = 1
    raise SystemExit(code)
