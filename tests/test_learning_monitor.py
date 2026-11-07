"""Monitoring must not leak payloads, mutate business state or silently go stale."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import collect_learning_monitor as m
from learning_service.db import Database


def database(tmp_path):
    db = Database(tmp_path / 'learning.db')
    with db.session(write=True) as c:
        c.execute("INSERT INTO jobs(id,kind,input_json,idempotency_key,status,created_at,updated_at) VALUES ('PRIVATE','diagnosis','PRIVATE','PRIVATE','queued','2020-01-01','2020-01-01')")
        c.execute("INSERT INTO provider_calls(id,provider_id,operation,model_id,evidence_mode,currency,pricing_reference,reserved_cost_micros,state,created_at) VALUES ('PRIVATE','PRIVATE','diagnosis','PRIVATE','synthetic_http','USD','PRIVATE',17,'unknown','2020-01-01')")
        c.execute("UPDATE provider_control SET paused=1")
    return db


def test_readonly_aggregates_keep_unknown_hold_and_hide_private_fields(tmp_path):
    db = database(tmp_path)
    before = hashlib.sha256(db.path.read_bytes()).hexdigest()
    result = m.db_alerts(db.path, 1800000000, 300, 100)
    assert set(result) == {'QUEUE_AGE_EXCEEDED', 'PROVIDER_DISPATCH_PAUSED', 'PROVIDER_USAGE_UNKNOWN'}
    assert 'PRIVATE' not in json.dumps(result)
    with db.session() as c:
        assert tuple(c.execute('SELECT state,reserved_cost_micros FROM provider_calls').fetchone()) == ('unknown', 17)
    assert hashlib.sha256(db.path.read_bytes()).hexdigest() == before


def test_reserved_live_invoice_semantics_match_metrics_without_calling_provider(tmp_path):
    db = database(tmp_path)
    with db.session(write=True) as c:
        c.execute("UPDATE provider_calls SET state='reserved',evidence_mode='live_http'")
    assert 'PROVIDER_INVOICE_PENDING' in m.db_alerts(db.path, 1800000000, 300, 100)


def test_reads_committed_wal_state_without_immutable_or_mutating_hold(tmp_path):
    db = Database(tmp_path / 'learning.db')
    writer = db.connect()
    try:
        writer.execute("UPDATE provider_control SET paused=1")
        assert (tmp_path / 'learning.db-wal').exists()
        assert m.db_alerts(db.path, 1800000000, 300, 100) == ['PROVIDER_DISPATCH_PAUSED']
        writer.execute("UPDATE provider_control SET paused=0")
        assert m.db_alerts(db.path, 1800000000, 300, 100) == []
    finally:
        writer.close()


def test_missing_and_future_schema_fail_without_creating_or_migrating_database(tmp_path):
    missing = tmp_path / 'absent.db'
    assert m.db_alerts(missing, 1, 300, 100) == ['METRICS_UNAVAILABLE']
    assert not missing.exists()
    db = database(tmp_path)
    with db.session(write=True) as c:
        c.execute("INSERT INTO schema_migrations VALUES (12,'2020-01-01')")
    assert 'DATABASE_SCHEMA_UNSUPPORTED' in m.db_alerts(db.path, 1, 300, 100)


@pytest.mark.parametrize('mutation', ["DELETE FROM provider_control", "UPDATE jobs SET created_at='invalid'"])
def test_missing_control_or_invalid_queue_time_never_silently_reports_ok(tmp_path, mutation):
    db = database(tmp_path)
    with db.session(write=True) as c:
        c.execute(mutation)
    assert m.db_alerts(db.path, 1800000000, 300, 100) == ['METRICS_UNAVAILABLE']


def test_dedup_recovery_reminder_corrupt_state_and_private_output(tmp_path):
    a = m.publish(tmp_path, ['API_UNAVAILABLE'], 100, 30)
    assert a['event'] == 'initial'
    assert m.publish(tmp_path, ['API_UNAVAILABLE'], 101, 30)['event'] == 'none'
    assert m.publish(tmp_path, ['API_UNAVAILABLE'], 130, 30)['event'] == 'reminder'
    recovered = m.publish(tmp_path, [], 131, 30)
    assert recovered['resolved'] == ['API_UNAVAILABLE'] and recovered['status'] == 'ok'
    assert (tmp_path / 'latest.json').stat().st_mode & 0o777 == 0o600
    (tmp_path / 'latest.json').write_text('{PRIVATE invalid')
    result = m.publish(tmp_path, [], 132, 30)
    assert 'MONITOR_STATE_INVALID' in result['alerts'] and 'PRIVATE' not in json.dumps(result)
    assert set(p.name for p in tmp_path.iterdir()) == {'latest.json'}


def test_monitor_staleness_and_backwards_clock_do_not_report_green(tmp_path):
    m.publish(tmp_path, [], 100, 30)
    assert m.status(tmp_path, 111, 10)['alerts'] == ['MONITOR_STALE']
    assert m.status(tmp_path, 99, 10)['alerts'] == ['MONITOR_STALE']
    assert 'MONITOR_CLOCK_REVERSED' in m.publish(tmp_path, [], 90, 30)['alerts']


@pytest.mark.parametrize('change,expected', [
    ({'f_bavail': 9}, ['STORAGE_BYTES_LOW']),
    ({'f_favail': 9}, ['STORAGE_INODES_LOW']),
    ({'f_files': 0}, ['STORAGE_INODES_UNKNOWN']),
    ({'f_blocks': 0}, ['STORAGE_UNAVAILABLE']),
])
def test_capacity_uses_available_bytes_and_inodes_without_filling_disk(monkeypatch, change, expected):
    values = dict(f_blocks=100, f_frsize=4096, f_bavail=10, f_files=100, f_favail=10)
    values.update(change)
    monkeypatch.setattr(m.os, 'statvfs', lambda _: SimpleNamespace(**values))
    assert m.storage_alerts(Path('/unused'), 40960, 10, 10) == expected


def test_backup_missing_stale_failed_future_and_unverified_receipts(tmp_path):
    path = tmp_path / 'receipt.json'
    assert m.backup_alerts(path, 100, 10) == ['BACKUP_UNOBSERVED']
    r = {'format': 'dd-learning-backup-observation-v1', 'scope': 'learning_only', 'status': 'passed', 'verified': True, 'finished_at': 95, 'private': 'PRIVATE'}
    path.write_text(json.dumps(r))
    assert m.backup_alerts(path, 100, 10) == []
    assert m.backup_alerts(path, 106, 10) == ['BACKUP_STALE']
    for change, expected in [({'status':'failed'}, 'BACKUP_FAILED'), ({'verified':False}, 'BACKUP_RECEIPT_INVALID'), ({'finished_at':200}, 'BACKUP_RECEIPT_INVALID')]:
        path.write_text(json.dumps({**r, **change}))
        assert m.backup_alerts(path, 100, 10) == [expected]


def test_symbolic_receipt_or_state_not_followed(tmp_path):
    secret = tmp_path / 'private'
    secret.write_text('PRIVATE')
    receipt = tmp_path / 'receipt'
    receipt.symlink_to(secret)
    assert m.backup_alerts(receipt, 100, 10) == ['BACKUP_RECEIPT_INVALID']
    (tmp_path / 'latest.json').symlink_to(secret)
    result = m.publish(tmp_path, [], 100, 30)
    assert result['alerts'] == ['MONITOR_STATE_INVALID'] and secret.read_text() == 'PRIVATE'


def test_atomic_write_failure_keeps_previous_complete_state(tmp_path, monkeypatch):
    m.publish(tmp_path, [], 100, 30)
    old = (tmp_path / 'latest.json').read_bytes()
    def fail(*args):
        raise OSError('PRIVATE')
    monkeypatch.setattr(m.os, 'replace', fail)
    with pytest.raises(OSError):
        m.publish(tmp_path, ['API_UNAVAILABLE'], 101, 30)
    assert (tmp_path / 'latest.json').read_bytes() == old
    assert not list(tmp_path.glob('.monitor-*'))


@pytest.mark.parametrize('url', ['https://learning-api:31010', 'http://example.com:80', 'http://127.0.0.1:123/a', 'http://x:y@127.0.0.1:123'])
def test_health_target_rejects_external_urls_and_credentials(url):
    with pytest.raises(ValueError):
        m.validate_upstream(url)


def test_health_deadline_includes_dns(monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs['timeout'] == 4
        raise subprocess.TimeoutExpired('synthetic', 4)
    monkeypatch.setattr(m.subprocess, 'run', timeout)
    assert m.health_ok('http://learning-api:31010') is False


def test_actual_health_child_rejects_redirect_without_following(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        redirect = False
        hits = []
        def do_GET(self):
            self.hits.append(self.path)
            if self.redirect:
                self.send_response(302)
                self.send_header('Location', '/PRIVATE')
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok","service":"learning-api","schema_revision":11}')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:' + str(server.server_port)
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
    try:
        assert m.health_ok(url)
        Handler.redirect = True
        assert not m.health_ok(url)
        assert Handler.hits == ['/health', '/health']
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
