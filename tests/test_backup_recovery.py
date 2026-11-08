"""Stopped-writer bundle integrity and isolated recovery; synthetic data only."""
from contextlib import closing
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

from PIL import Image
import pytest
from fastapi.testclient import TestClient

from learning_service import backup
from learning_service.app import create_app
from learning_service.db import Database, utc_now
from learning_service.operations import recovery_inventory, verify_recovery
from learning_service.practice import install, bank
from test_family_math import family
from test_practice_collection import collect
from test_practice_recovery import configure, start, submit


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_bundle_fixture(directory, db, api, headers):
    """Reusable synthetic drill fixture; no external requests or model jobs."""
    install(db)
    headers = {**headers, 'X-Learner-Id':'family-g7'}
    question = next(q for q in bank().values() if q['grade'] == 7 and q['chapter_id'] == '2')
    env = db, api, headers, question
    configure(env, difficulty='easy')
    _, _, attempt = submit(env, start(env), raw='99999')
    saved = collect(env, attempt['attempt_id']).json()
    configure(env, difficulty='hard')
    hard = next(q for q in bank().values() if q['grade'] == 7 and q['chapter_id'] == '2' and q['difficulty'] == 'hard')
    session = start(env, hard).json()
    pending = session['items'][0]['test_item_id']
    assert api.post(f'/api/v1/test-items/{pending}/hints', headers=headers).status_code == 200
    assert api.post(f'/api/v1/test-items/{pending}/submission-challenges', headers=headers).status_code == 200
    image = io.BytesIO(); Image.new('RGB', (12, 10), '#2b7a68').save(image, format='PNG')
    response = api.post('/api/v1/documents', headers=headers, files={'file':('synthetic-page.png', image.getvalue(), 'image/png')})
    assert response.status_code == 201, response.text
    exports = directory / 'exports'; exports.mkdir(exist_ok=True)
    artifact = exports / 'synthetic.json'; artifact.write_text('{"synthetic_export": true}\n')
    now = utc_now()
    with db.session(write=True) as conn:
        account = conn.execute('SELECT id FROM accounts').fetchone()[0]
        conn.execute("INSERT INTO export_jobs(id,learner_id,requested_by_account_id,status,artifact_key,artifact_sha256,artifact_byte_size,created_at,completed_at) VALUES ('synthetic-export','family-g7',?,'completed','synthetic.json',?,?,?,?)",
                     (account, digest(artifact), artifact.stat().st_size, now, now))
        conn.execute("INSERT INTO browser_sessions(id,token_hash,csrf_hash,account_id,learner_id,provider,issuer,subject,expires_at,created_at) VALUES ('synthetic-session','synthetic-token','synthetic-csrf',?,'family-g7','open-webui','family-pilot-webui','synthetic-parent','2099-01-01',?)", (account, now))
        conn.execute("INSERT INTO account_contexts(account_id,learner_id,revision,updated_at) VALUES (?,'family-g7',1,?)", (account, now))
        conn.execute("INSERT INTO provider_calls(id,provider_id,operation,model_id,evidence_mode,currency,pricing_reference,reserved_cost_micros,state,created_at) VALUES ('synthetic-hold','synthetic','diagnosis','synthetic','synthetic_http','USD','synthetic-price',17,'reserved',?)", (now,))
    return {'directory':directory, 'db':db, 'api':api, 'headers':headers, 'question':question,
            'attempt_id':attempt['attempt_id'], 'saved':saved, 'session':session}


@pytest.fixture
def bundle(family, tmp_path):
    result = build_bundle_fixture(*family)
    extras = tmp_path / 'named-inputs'; extras.mkdir()
    (extras / 'textbook.txt').write_text('SYNTHETIC textbook page: 2 + 2 = 4.\n')
    (extras / 'versions.json').write_text('{"schema_revision":13,"source":"synthetic","provider_enabled":false}\n')
    result['include_files'] = {'materials/textbook.txt':extras / 'textbook.txt', 'versions/runtime.json':extras / 'versions.json'}
    return result


def capture(bundle, path):
    return backup.backup_data(bundle['directory'], path, writers_stopped=True, include_files=bundle['include_files'])


def test_joint_bundle_restores_pages_mistakes_rounds_and_paused_runtime(bundle, tmp_path):
    before = recovery_inventory(bundle['directory'])
    original = tmp_path / 'archive'; manifest = capture(bundle, original)
    assert manifest['format'] == 'dd-learning-backup-v2'
    assert backup.verify_backup(original)['joint_consistency_checked']
    target = tmp_path / 'restored'; target.mkdir()
    receipt = backup.restore_data(original, target, require_consistent=True)
    after = recovery_inventory(target)
    assert verify_recovery(before, after)['status'] == 'passed'
    assert after['unknown_calls'] == 1 and after['provider_reserved_cost_micros'] == 17
    assert receipt['runtime_sessions_invalidated'] and receipt['provider_paused']
    assert not receipt['full_architecture_recovered'] and not receipt['independent_fault_domain_verified']
    for name, source in bundle['include_files'].items(): assert (target / name).read_bytes() == source.read_bytes()
    restored = Database(target / 'learning.db')
    settings = replace(bundle['api'].app.state.settings, data_dir=target, db_path=restored.path,
                       attachment_dir=target / 'attachments', export_dir=target / 'exports')
    client = TestClient(create_app(settings, restored)); headers = bundle['headers']
    assert client.get('/api/v1/practice-workspace', headers=headers).json()['current_session_id'] == bundle['session']['session_id']
    assert client.get('/api/v1/mistakes', headers=headers).json()['items'][0]['id'] == bundle['saved']['mistake_id']
    item = client.get('/api/v1/test-sessions/' + bundle['session']['session_id'], headers=headers).json()['items'][0]
    assert item['assistance'] == 'hint' and item['status'] == 'presented'
    assert client.get('/api/v1/attempts/' + bundle['attempt_id'], headers=headers).json()['outcome'] == 'incorrect'
    assert backup.verify_backup(original)['status'] == 'passed'


@pytest.mark.parametrize('change', ['missing_asset', 'wrong_asset_hash', 'wrong_export', 'missing_named'])
def test_missing_or_mismatched_inputs_fail_without_published_backup(bundle, tmp_path, change):
    with bundle['db'].session() as conn:
        key = conn.execute('SELECT object_key FROM assets WHERE deleted_at IS NULL LIMIT 1').fetchone()[0]
    if change == 'missing_asset': (bundle['directory'] / 'attachments' / key).unlink()
    elif change == 'wrong_asset_hash': (bundle['directory'] / 'attachments' / key).write_bytes(b'wrong')
    elif change == 'wrong_export': (bundle['directory'] / 'exports/synthetic.json').write_text('wrong')
    else: next(iter(bundle['include_files'].values())).unlink()
    with pytest.raises((ValueError, FileNotFoundError)): capture(bundle, tmp_path / 'rejected')
    assert not (tmp_path / 'rejected').exists()
    assert not list(tmp_path.glob('.backup-*'))


def test_database_write_lock_blocks_competing_writer_and_busy_database_fails(bundle, tmp_path, monkeypatch):
    real_copy = backup.shutil.copy2
    writes_blocked = []
    def try_write(source, target):
        with closing(sqlite3.connect(bundle['db'].path, timeout=0.01)) as conn:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                conn.execute('UPDATE provider_control SET paused=1')
        writes_blocked.append(True)
        return real_copy(source, target)
    monkeypatch.setattr(backup.shutil, 'copy2', try_write)
    capture(bundle, tmp_path / 'locked-snapshot')
    assert writes_blocked
    with closing(sqlite3.connect(bundle['db'].path, isolation_level=None)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            backup.backup_data(bundle['directory'], tmp_path / 'busy', writers_stopped=True, lock_timeout=0.01)
        writer.rollback()
    assert not (tmp_path / 'busy').exists()


@pytest.mark.parametrize('change', ['content', 'add_file', 'replace_database'])
def test_external_file_changes_during_copy_abort_joint_backup(bundle, tmp_path, monkeypatch, change):
    real_copy = backup.shutil.copy2; changed = []
    def mutate(source, target):
        result = real_copy(source, target)
        if not changed:
            changed.append(True)
            if change == 'content': Path(source).write_bytes(Path(source).read_bytes() + b'changed')
            elif change == 'add_file': (bundle['directory'] / 'attachments/late.bin').write_bytes(b'late')
            else:
                alternate = tmp_path / 'alternate.db'; real_copy(bundle['db'].path, alternate)
                alternate.replace(bundle['db'].path)
        return result
    monkeypatch.setattr(backup.shutil, 'copy2', mutate)
    with pytest.raises(ValueError, match='changed'): capture(bundle, tmp_path / 'unstable')
    assert not (tmp_path / 'unstable').exists()


@pytest.mark.parametrize('change', ['extra', 'missing', 'corrupt', 'rehash_asset', 'traversal', 'symlink', 'special', 'bad_checksum', 'future_schema'])
def test_archive_verification_rejects_bad_members_before_creating_target(bundle, tmp_path, change):
    archive = tmp_path / 'bad-archive'; capture(bundle, archive)
    manifest = json.loads((archive / 'manifest.json').read_text())
    if change == 'extra': (archive / 'unexpected.bin').write_bytes(b'new')
    elif change == 'missing': (archive / 'materials/textbook.txt').unlink()
    elif change == 'corrupt': (archive / 'materials/textbook.txt').write_bytes(b'bad')
    elif change == 'rehash_asset':
        name = next(n for n in manifest['files'] if n.startswith('attachments/'))
        (archive / name).write_bytes(b'bad')
        manifest['files'][name] = digest(archive / name)
    elif change == 'traversal': manifest['files']['../escape'] = '0' * 64
    elif change == 'bad_checksum': manifest['files']['learning.db'] = 'not-a-hash'
    elif change == 'symlink':
        target = archive / 'materials/textbook.txt'; target.unlink(); target.symlink_to(bundle['include_files']['materials/textbook.txt'])
    elif change == 'special':
        import os
        os.mkfifo(archive / 'pipe')
    else:
        with sqlite3.connect(archive / 'learning.db') as conn: conn.execute("INSERT INTO schema_migrations VALUES (999,'synthetic')")
        manifest['files']['learning.db'] = digest(archive / 'learning.db')
    (archive / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises((ValueError, FileNotFoundError)):
        backup.restore_data(archive, tmp_path / 'never-created', require_consistent=True)
    assert not (tmp_path / 'never-created').exists()


def test_nonempty_symlink_overlap_and_concurrent_target_are_preserved(bundle, tmp_path, monkeypatch):
    archive = tmp_path / 'archive'; capture(bundle, archive)
    target = tmp_path / 'keep'; target.mkdir(); (target / 'keep.txt').write_text('keep')
    with pytest.raises(FileExistsError): backup.restore_data(archive, target, require_consistent=True)
    link = tmp_path / 'link'; link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'): backup.restore_data(archive, link)
    with pytest.raises(ValueError, match='outside'): backup.restore_data(archive, archive / 'nested')
    with pytest.raises(ValueError, match='outside'): capture(bundle, bundle['directory'] / 'attachments/nested')
    real_publish = backup._publish_directory
    def collision(staging, destination):
        destination.mkdir(); (destination / 'keep.txt').write_text('concurrent')
        real_publish(staging, destination)
    monkeypatch.setattr(backup, '_publish_directory', collision)
    with pytest.raises(FileExistsError): backup.restore_data(archive, tmp_path / 'racing')
    assert (target / 'keep.txt').read_text() == 'keep'
    assert (tmp_path / 'racing/keep.txt').read_text() == 'concurrent'
    assert not list(tmp_path.glob('.restore-*'))


def test_archive_mutation_during_restore_aborts_and_preserves_archive(bundle, tmp_path, monkeypatch):
    archive = tmp_path / 'archive'; capture(bundle, archive)
    real_copy = backup.shutil.copy2
    def corrupt(source, target):
        result = real_copy(source, target)
        if Path(source).name == 'learning.db': Path(target).write_bytes(Path(target).read_bytes() + b'bad')
        return result
    monkeypatch.setattr(backup.shutil, 'copy2', corrupt)
    with pytest.raises(ValueError, match='changed while restoring'): backup.restore_data(archive, tmp_path / 'failed')
    assert not (tmp_path / 'failed').exists()
    assert backup.verify_backup(archive)['status'] == 'passed'


def test_legacy_sequential_backup_is_compatible_but_not_joint_verified(bundle, tmp_path):
    archive = tmp_path / 'legacy'; manifest = backup.backup_data(bundle['directory'], archive)
    assert manifest['format'] == 'dd-learning-backup-v1'
    with pytest.raises(ValueError, match='joint consistency'): backup.verify_backup(archive)
    assert not backup.verify_backup(archive, require_consistent=False)['joint_consistency_checked']
    assert backup.restore_data(archive, tmp_path / 'legacy-restored')['status'] == 'passed'


def test_cli_receipts_are_separate_atomic_bound_and_monitor_compatible(bundle, tmp_path):
    archive = tmp_path / 'cli-backup'; target = tmp_path / 'cli-restore'
    def command(*args):
        return subprocess.run([sys.executable, '-m', 'learning_service.backup', *map(str, args)], text=True, capture_output=True)
    failed = command('backup', bundle['directory'], archive, '--receipt', tmp_path / 'not-written.json')
    assert failed.returncode != 0 and not archive.exists() and not (tmp_path / 'not-written.json').exists()
    receipt = tmp_path / 'backup.json'
    result = command('backup', bundle['directory'], archive, '--writers-stopped', '--receipt', receipt,
                     '--include', 'materials/textbook.txt=' + str(bundle['include_files']['materials/textbook.txt']))
    assert result.returncode == 0, result.stderr
    assert receipt.stat().st_mode & 0o777 == 0o600
    result = command('verify', archive, '--receipt', tmp_path / 'verify.json', '--observation', tmp_path / 'observation.json')
    assert result.returncode == 0, result.stderr
    result = command('restore', archive, target, '--receipt', tmp_path / 'restore.json')
    assert result.returncode == 0, result.stderr
    receipts = [json.loads((tmp_path / name).read_text()) for name in ('backup.json', 'verify.json', 'restore.json')]
    assert {r['manifest_sha256'] for r in receipts} == {digest(archive / 'manifest.json')}
    assert not receipts[0]['recovery_performed'] and not receipts[1]['recovery_performed']
    assert receipts[2]['runtime_sessions_invalidated']
    from collect_learning_monitor import backup_alerts
    assert backup_alerts(tmp_path / 'observation.json', int(time.time()), 86400) == []
    old = receipt.read_bytes()
    assert command('verify', archive, '--receipt', receipt).returncode != 0
    assert command('verify', archive, '--receipt', archive / 'receipt.json').returncode != 0
    assert receipt.read_bytes() == old
    (archive / 'learning.db').write_bytes(b'corrupt')
    assert command('verify', archive, '--receipt', tmp_path / 'failed-verify.json').returncode != 0
    assert not (tmp_path / 'failed-verify.json').exists()


def test_new_workspace_deletion_tombstone_replay_clears_stale_workspace(bundle, tmp_path):
    with bundle['db'].session(write=True) as conn:
        conn.execute("INSERT INTO deletion_records(id,learner_id,resource_type,resource_id,policy_version,created_at) VALUES ('workspace-delete','family-g7','practice_workspace','family-g7','synthetic',?)", (utc_now(),))
    archive = tmp_path / 'deleted'; capture(bundle, archive)
    target = tmp_path / 'deleted-restore'; backup.restore_data(archive, target, require_consistent=True)
    with Database(target / 'learning.db').session() as conn:
        assert conn.execute('SELECT count(*) FROM practice_workspaces').fetchone()[0] == 0
        assert conn.execute("SELECT active FROM learners WHERE id='family-g7'").fetchone()[0] == 0


def test_recovery_inventory_detects_asset_bytes_and_round_drift(bundle, tmp_path):
    before = recovery_inventory(bundle['directory']); archive = tmp_path / 'archive'; capture(bundle, archive)
    target = tmp_path / 'restore'; backup.restore_data(archive, target, require_consistent=True)
    assert verify_recovery(before, recovery_inventory(target))['status'] == 'passed'
    (target / 'exports/synthetic.json').write_text('changed')
    with Database(target / 'learning.db').session(write=True) as conn:
        conn.execute('UPDATE practice_rounds SET generation=generation+1')
    errors = verify_recovery(before, recovery_inventory(target))['errors']
    assert 'file_fingerprints_changed' in errors and 'business_fingerprints_changed' in errors
