"""B08 compatibility and separate observer checks with synthetic data only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import collect_learning_monitor as monitor
from learning_service.backup import backup_data, verify_backup, write_receipt
from learning_service.db import Database

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('revision', [11, 12, 13])
def test_real_historical_migrations_remain_readable_without_schema_writes(tmp_path, revision):
    migrations = tmp_path / 'migrations'; migrations.mkdir()
    for p in (ROOT / 'learning_service/migrations').glob('*.sql'):
        if int(p.name.split('_')[0]) <= revision: shutil.copy2(p, migrations / p.name)
    db = Database(tmp_path / 'source/learning.db', migration_dir=migrations)
    before = db.path.read_bytes()
    assert monitor.db_alerts(db.path, int(time.time()), 300, 100) == []
    assert db.path.read_bytes() == before
    with db.session() as conn:
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] == revision


@pytest.mark.parametrize('status,created,lease', [
    ('queued','invalid',None), ('queued','2099-01-01',None),
    ('running','2020-01-01',None), ('running','2020-01-01','invalid'),
])
def test_invalid_job_time_cannot_hide_beside_valid_row(tmp_path, status, created, lease):
    db = Database(tmp_path / 'learning.db')
    with db.session(write=True) as conn:
        for identifier, state, timestamp, expiry in [('good','queued','2020-01-01',None),('PRIVATE',status,created,lease)]:
            conn.execute('INSERT INTO jobs(id,kind,input_json,idempotency_key,status,created_at,updated_at,lease_until) VALUES (?,\'diagnosis\',\'PRIVATE\',?,?,?,\'2020-01-01\',?)',
                         (identifier, identifier, state, timestamp, expiry))
    assert monitor.db_alerts(db.path, int(time.time()), 300, 100) == ['METRICS_UNAVAILABLE']


@pytest.mark.parametrize('revision,expected', [(11,True),(12,True),(13,True),(14,False),(10,False),('13',False),(True,False),(None,False)])
def test_health_revision_is_explicit_and_typed(monkeypatch, revision, expected):
    payload = {'status':'ok','service':'learning-api','schema_revision':revision,'private':'PRIVATE'}
    monkeypatch.setattr(monitor.GatewayHTTP, 'send', lambda *a,**k: SimpleNamespace(status=200,body=json.dumps(payload).encode()))
    assert monitor.health_child('http://127.0.0.1:1') is expected


@pytest.mark.parametrize('payload', [[],None,'PRIVATE'])
def test_wrong_health_shape_is_unavailable(monkeypatch, payload):
    monkeypatch.setattr(monitor.GatewayHTTP, 'send', lambda *a,**k: SimpleNamespace(status=200,body=json.dumps(payload).encode()))
    assert not monitor.health_child('http://127.0.0.1:1')


@pytest.mark.parametrize('field,value', [('checked_at',-1),('last_event_at',-1),('last_event_at',101),('checked_at',True)])
def test_corrupt_heartbeat_times_never_report_green(tmp_path, field, value):
    monitor.publish(tmp_path, [],100,30)
    path = tmp_path / 'latest.json'; state=json.loads(path.read_text()); state[field]=value
    path.write_text(json.dumps(state)); before=path.read_bytes()
    assert monitor.status(tmp_path,100,180)['alerts'] == ['MONITOR_STATE_INVALID']
    assert path.read_bytes() == before


@pytest.fixture
def cli_monitor(tmp_path):
    source = tmp_path / 'source'; db = Database(source / 'learning.db')
    archive = tmp_path / 'archive'; backup_data(source,archive,writers_stopped=True)
    verified = verify_backup(archive)
    receipt = tmp_path / 'backup-observation.json'
    write_receipt(receipt, {'format':'dd-learning-backup-observation-v1','scope':'learning_only',
        'status':'passed','verified':True,'finished_at':verified['finished_at'],
        'manifest_sha256':verified['manifest_sha256'],'private':'PRIVATE'})
    class Handler(BaseHTTPRequestHandler):
        healthy = True
        def do_GET(self):
            assert self.path == '/health'
            self.send_response(200 if self.healthy else 503); self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"learning-api","schema_revision":13,"private":"PRIVATE"}')
        def log_message(self,*args): pass
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    state = tmp_path / 'monitor-state'
    base = [sys.executable,str(ROOT / 'scripts/collect_learning_monitor.py')]
    args = ['collect','--db',str(db.path),'--storage',str(source),'--state-dir',str(state),
            '--backup-receipt',str(receipt),'--upstream',f'http://127.0.0.1:{server.server_port}',
            '--min-free-bytes','0','--min-free-percent','0','--min-free-inodes','0']
    env = {'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'}
    def command(*options):
        result = subprocess.run(base + list(options),env=env,text=True,capture_output=True,timeout=10)
        assert 'PRIVATE' not in result.stdout + result.stderr
        return result
    yield SimpleNamespace(db=db,receipt=receipt,state=state,handler=Handler,base=base,args=args,env=env,command=command)
    server.shutdown(); server.server_close(); thread.join()


def test_collector_cli_fault_recovery_and_readonly_observer(cli_monitor):
    c=cli_monitor
    original=c.db.path.read_bytes()
    healthy=c.command(*c.args)
    assert healthy.returncode == 0 and json.loads(healthy.stdout)['alerts'] == []
    assert c.db.path.read_bytes() == original
    c.handler.healthy=False
    with c.db.session(write=True) as conn:
        conn.execute("INSERT INTO jobs(id,kind,input_json,idempotency_key,status,created_at,updated_at,lease_until) VALUES ('PRIVATE','diagnosis','PRIVATE','PRIVATE','running','2020-01-01','2020-01-01','2020-01-01')")
    receipt=json.loads(c.receipt.read_text());receipt['finished_at']=int(time.time())-86401
    c.receipt.write_text(json.dumps(receipt))
    failed=c.command(*c.args);payload=json.loads(failed.stdout)
    assert failed.returncode == 2 and set(payload['alerts']) == {'API_UNAVAILABLE','WORKER_LEASE_EXPIRED','BACKUP_STALE'}
    assert json.loads(c.command(*c.args).stdout)['event'] == 'none'
    c.handler.healthy=True
    with c.db.session(write=True) as conn: conn.execute("UPDATE jobs SET status='succeeded'")
    receipt['finished_at']=int(time.time());c.receipt.write_text(json.dumps(receipt))
    recovered=c.command(*c.args);payload=json.loads(recovered.stdout)
    assert recovered.returncode == 0 and set(payload['resolved']) == {'API_UNAVAILABLE','WORKER_LEASE_EXPIRED','BACKUP_STALE'}
    before=(c.state/'latest.json').read_bytes()
    observed=c.command('status','--state-dir',str(c.state))
    assert observed.returncode == 0 and (c.state/'latest.json').read_bytes() == before


def test_stopped_collector_detected_by_separate_cli_without_source_access(cli_monitor):
    c=cli_monitor
    collector=subprocess.Popen(c.base+c.args+['--cycles','100','--interval','1'],env=c.env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not (c.state/'latest.json').exists() and time.monotonic()<deadline: time.sleep(.02)
        assert (c.state/'latest.json').exists()
        collector.terminate(); collector.communicate(timeout=5)
        before=(c.state/'latest.json').read_bytes()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            result=c.command('status','--state-dir',str(c.state),'--stale-seconds','1')
            if result.returncode == 2: break
            time.sleep(.05)
        assert result.returncode == 2 and json.loads(result.stdout)['alerts'] == ['MONITOR_STALE']
        assert (c.state/'latest.json').read_bytes() == before
    finally:
        if collector.poll() is None: collector.kill();collector.communicate(timeout=5)


def test_second_collector_refuses_same_state_lock(cli_monitor):
    import fcntl
    c=cli_monitor;c.state.mkdir(mode=0o700)
    with (c.state/'monitor.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=c.command(*c.args)
    assert result.returncode == 3 and json.loads(result.stdout)['error_code'] == 'MONITOR_ALREADY_RUNNING'
    assert not (c.state/'latest.json').exists()
