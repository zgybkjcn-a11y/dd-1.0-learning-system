#!/usr/bin/env python3
"""Pinned 1.2.0 Tool lifecycle for an explicitly supplied, existing SQLite DB.

No Docker calls, environment/config imports, registration, global reads or code
execution. Packages contain private target configuration: keep them local.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

TOOL_ID = 'dd_family_study_readonly_v1'
WEBUI_IMAGE = 'sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd'
CANDIDATE_SHA256 = '23fc5c2558a0141750031acaee434f7b0abd81d884974e8d15ee781c1f2404d7'
SPECS_SHA256 = 'b2590ce999d95b330a2daab7e68330e45c3c3e53e1d4a01d377b953fae1a020e'
METADATA_SHA256 = 'db67e7837cf6927366baf99728c1d8a02b33a6c24fcad8c40a7186256d73ab93'
# A07 code identities, independent of documentation-only release rebuilds.
BACKEND = {
    'learning_service/app.py': '4252f9ee3f1fe9925196337c109bad3cb5bc37a005cfa6caa50750106fb72ffb',
    'learning_service/config.py': '54bfdc6afd44048da3f3fe0f9dfc305de3810bf46ce6c2169cf5f924c9c686eb',
    'learning_service/login_gateway.py': 'e12c4e0f6131a6424aa136f913160facdb37df0f61be3122b66b0f24cfee10ff',
    'learning_service/textbooks.py': '457c627e6d21943fd07caa414c36b34f23008f1056cde2d87680df745b38225a',
    'learning_service/passage_evidence.py': 'c29ab513580a162800158664b27eddfb340033e2ebfc303efb5a829ff9e24738',
    'learning_service/passage_retrieval.py': 'a10e1b4b995720c273db0ce8b09ed7edbd0fdc380a5a186650db30e631fdca96',
    'learning_service/textbook_passages.py': '08293a7a11c393af1564d2e347a7bfb5e1a7eaff9e2d51cd1e4957e659c2649e',
    'docs/contracts/openapi-v1.json': '57708794dc2b18bb5b762cffe45a6976cef714bd0ba55c1c757cb7aa95eb98aa',
    'deploy/open-webui-reuse/main-study/family-bridge.js': '876cb599ea7c1729bde5964138b4f22d5fdcd8ea6a580004c6b4807b4f3c7ab7',
}
COLUMNS = {
    'tool': ('id', 'version_id', 'user_id', 'name', 'content', 'specs', 'meta', 'valves', 'created_at', 'updated_at'),
    'tool_history': ('id', 'tool_id', 'parent_id', 'snapshot', 'user_id', 'commit_message', 'created_at'),
    'access_grant': ('id', 'resource_type', 'resource_id', 'principal_type', 'principal_id', 'permission', 'created_at'),
}
MUTABLE = ('version_id', 'content', 'specs', 'meta', 'updated_at')
SHA = re.compile(r'[a-f0-9]{64}')


class LifecycleError(Exception):
    """Only stable codes cross the CLI boundary; never raw DB/configuration."""


def require(condition, code):
    if not condition:
        raise LifecycleError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def fingerprint(value):
    return digest(canonical(value))


def strict_json(raw):
    def pairs(rows):
        result = {}
        for k, v in rows:
            require(k not in result, 'JSON_INVALID')
            result[k] = v
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(LifecycleError('JSON_INVALID')))
    except (ValueError, TypeError, RecursionError):
        raise LifecycleError('JSON_INVALID') from None


def regular(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(), 'PATH_INVALID')
    return path


def read_bytes(path, limit=16_000_000):
    path = regular(path)
    require(path.stat().st_size <= limit, 'INPUT_TOO_LARGE')
    return path.read_bytes()


def backend_check(root):
    try:
        actual = {name: digest(read_bytes(Path(root) / name)) for name in BACKEND}
    except (OSError, LifecycleError):
        raise LifecycleError('BACKEND_INCOMPATIBLE') from None
    require(actual == BACKEND, 'BACKEND_INCOMPATIBLE')
    return fingerprint(actual)


def native_candidate(source, native):
    require(digest(source.encode()) == CANDIDATE_SHA256, 'CANDIDATE_UNVALIDATED')
    require(isinstance(native, dict) and native.get('passed') is True
            and native.get('source_sha256') == CANDIDATE_SHA256
            and native.get('network') == 'none' and native.get('formal_data_mounted') is False
            and native.get('model_calls') == 0 and native.get('passage_fixture_checked') is True
            and native.get('citation_events') == 4
            and fingerprint(native.get('specs')) == SPECS_SHA256
            and fingerprint(native.get('metadata')) == METADATA_SHA256, 'NATIVE_EVIDENCE_INVALID')
    return {'content': source, 'specs': native['specs'], 'metadata': native['metadata']}


def db_identity(path):
    path = regular(path); stat = path.stat()
    return {'path_sha256': digest(str(path).encode()), 'device': stat.st_dev, 'inode': stat.st_ino}


@contextmanager
def connect(path, write=False):
    path = regular(path)
    # mode=rw never creates an absent database. URI quoting preserves ?/# names.
    conn = sqlite3.connect(path.as_uri() + ('?mode=rw' if write else '?mode=ro'), uri=True, timeout=2, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA trusted_schema=OFF')
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield conn
        if write:
            conn.commit()
        else:
            conn.rollback()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def schema_check(conn):
    for table, columns in COLUMNS.items():
        info = conn.execute('PRAGMA table_info(' + table + ')').fetchall()
        require({r['name'] for r in info} == set(columns) and
                [r['name'] for r in info if r['pk']] == ['id'], 'SCHEMA_UNSUPPORTED')
        require(not conn.execute('PRAGMA foreign_key_list(' + table + ')').fetchall(), 'SCHEMA_UNSUPPORTED')
    require({'id', 'role'} <= {r['name'] for r in conn.execute('PRAGMA table_info(user)')}, 'SCHEMA_UNSUPPORTED')
    require(not conn.execute("SELECT 1 FROM sqlite_schema WHERE type='trigger' AND tbl_name IN ('tool','tool_history','access_grant')").fetchone(), 'SCHEMA_UNSUPPORTED')


def snapshot(row):
    """WebUI 0.12.5 tool_snapshot semantics; valves/specs are not history fields."""
    meta = deepcopy(strict_json(row['meta']) if row['meta'] else {})
    require(isinstance(meta, dict), 'TARGET_INVALID')
    meta.setdefault('description', None)
    if not meta.get('i18n'):
        meta.pop('i18n', None)
    for key in ('manifest', 'has_user_valves'):
        meta.pop(key, None)
    return {'name': row['name'], 'content': row['content'] or '', 'meta': meta}


def target_state(conn):
    schema_check(conn)
    row = conn.execute('SELECT ' + ','.join(COLUMNS['tool']) + ' FROM tool WHERE id=?', (TOOL_ID,)).fetchone()
    require(row is not None, 'TARGET_MISSING')
    row = dict(row)
    require(type(row['user_id']) is str and row['user_id'] and type(row['content']) is str
            and len(row['content']) <= 1_000_000 and type(row['name']) is str, 'TARGET_INVALID')
    owner = conn.execute('SELECT role FROM user WHERE id=?', (row['user_id'],)).fetchone()
    require(owner is not None and owner['role'] in ('admin', 'user'), 'OWNER_UNAVAILABLE')
    require(isinstance(strict_json(row['specs']), list), 'TARGET_INVALID')
    snapshot(row)
    history = [dict(r) for r in conn.execute('SELECT ' + ','.join(COLUMNS['tool_history']) + ' FROM tool_history WHERE tool_id=? ORDER BY id LIMIT 501', (TOOL_ID,))]
    require(len(history) <= 500, 'HISTORY_TOO_LARGE')
    current = next((r for r in history if r['id'] == row['version_id']), None)
    require(current is not None and strict_json(current['snapshot']) == snapshot(row), 'HISTORY_INVALID')
    grants = [dict(r) for r in conn.execute('SELECT ' + ','.join(COLUMNS['access_grant']) + " FROM access_grant WHERE resource_type='tool' AND resource_id=? ORDER BY id LIMIT 501", (TOOL_ID,))]
    require(len(grants) <= 500, 'GRANTS_TOO_LARGE')
    # This migration targets the private family tool, never a public plugin.
    require(all(r['principal_type'] in ('user', 'group') and r['principal_id'] != '*'
                and r['permission'] in ('read', 'write') for r in grants), 'PUBLIC_TOOL_REJECTED')
    return {'tool': row, 'history': history, 'grants': grants, 'owner_role': owner['role']}


def private_write(path, value):
    raw = canonical(value) + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def upgrade_row(plan, timestamp):
    row = deepcopy(plan['before']['tool'])
    meta = strict_json(row['meta']) if row['meta'] else {}
    meta.update(manifest=plan['candidate']['metadata'], has_user_valves=False)
    row.update(content=plan['candidate']['content'], specs=canonical(plan['candidate']['specs']).decode(),
               meta=canonical(meta).decode(), version_id=plan['upgrade_id'], updated_at=timestamp)
    return row


def restored_row(plan, timestamp):
    return {**plan['before']['tool'], 'version_id': plan['rollback_id'], 'updated_at': timestamp}


def history_entry(plan, row, rollback=False):
    return {'id': row['version_id'], 'tool_id': TOOL_ID,
            'parent_id': plan['upgrade_id'] if rollback else plan['before']['tool']['version_id'],
            'snapshot': canonical(snapshot(row)).decode(), 'user_id': plan['before']['tool']['user_id'],
            'commit_message': 'DD A08 ' + plan['operation_id'] + (' rollback' if rollback else ' upgrade'),
            'created_at': row['updated_at']}


def expected_state(plan, phase, history):
    entries = {r['id']: r for r in history}
    result = deepcopy(plan['before'])
    if phase in ('applied', 'rolled_back'):
        require(plan['upgrade_id'] in entries, 'STATE_CONFLICT')
        row = upgrade_row(plan, entries[plan['upgrade_id']]['created_at'])
        result['tool'] = row; result['history'].append(history_entry(plan, row))
    if phase == 'rolled_back':
        require(plan['rollback_id'] in entries, 'STATE_CONFLICT')
        row = restored_row(plan, entries[plan['rollback_id']]['created_at'])
        result['tool'] = row; result['history'].append(history_entry(plan, row, True))
    result['history'].sort(key=lambda r: r['id'])
    return result


def phase_of(plan, state):
    if state == plan['before']:
        return 'prepared'
    for phase in ('applied', 'rolled_back'):
        try:
            if state == expected_state(plan, phase, state['history']):
                return phase
        except LifecycleError:
            pass
    raise LifecycleError('STATE_CONFLICT')


def summary(plan, phase, changes=0):
    return {'format': 'dd-tool-lifecycle-result-v1', 'tool_id': TOOL_ID, 'operation_id': plan['operation_id'],
            'state': phase, 'row_changes': changes, 'old_source_sha256': plan['old_source_sha256'],
            'candidate_source_sha256': CANDIDATE_SHA256, 'owner_sha256': plan['owner_sha256'],
            'before_fingerprint': fingerprint(plan['before']), 'backend_fingerprint': fingerprint(BACKEND),
            'grants_preserved': True, 'configuration_preserved': True, 'other_records_modified': False}


def prepare(db, backend_root, source, native, expected_old_sha256, expected_owner_sha256, destination):
    require(type(expected_old_sha256) is str and SHA.fullmatch(expected_old_sha256), 'OLD_HASH_INVALID')
    require(type(expected_owner_sha256) is str and SHA.fullmatch(expected_owner_sha256), 'OWNER_HASH_INVALID')
    backend_check(backend_root)
    candidate = native_candidate(read_bytes(source).decode(), strict_json(read_bytes(native)))
    identity = db_identity(db)
    with connect(db) as conn:
        before = target_state(conn)
        require(digest(before['tool']['content'].encode()) == expected_old_sha256, 'OLD_HASH_MISMATCH')
        require(expected_old_sha256 != CANDIDATE_SHA256, 'ALREADY_CANDIDATE_REQUIRES_ORIGINAL_PACKAGE')
        require(digest(before['tool']['user_id'].encode()) == expected_owner_sha256, 'OWNER_MISMATCH')
    require(db_identity(db) == identity, 'DATABASE_REPLACED')
    backend_check(backend_root)
    operation = str(uuid.uuid4())
    plan = {'format': 'dd-tool-upgrade-package-v1', 'tool_id': TOOL_ID, 'operation_id': operation,
            'upgrade_id': str(uuid.uuid5(uuid.UUID(operation), 'upgrade')),
            'rollback_id': str(uuid.uuid5(uuid.UUID(operation), 'rollback')),
            'created_at': int(time.time()), 'database': identity, 'backend': BACKEND, 'webui_image': WEBUI_IMAGE,
            'old_source_sha256': expected_old_sha256, 'owner_sha256': expected_owner_sha256,
            'before': before, 'candidate': candidate}
    destination = Path(destination).absolute()
    require(not destination.exists() and not any(p.is_symlink() for p in destination.parents), 'DESTINATION_EXISTS_OR_UNSAFE')
    destination.mkdir(mode=0o700, parents=False)
    private_write(destination / 'package.json', plan)
    pin = digest((destination / 'package.json').read_bytes())
    preview = {**summary(plan, 'prepared'), 'package_sha256': pin,
               'change_fields': list(MUTABLE), 'history_writes_per_transition': 1,
               'source_diff': ''.join(__import__('difflib').unified_diff(before['tool']['content'].splitlines(keepends=True), candidate['content'].splitlines(keepends=True), fromfile='old_tool.py', tofile='candidate_tool.py'))}
    private_write(destination / 'review.json', preview)
    return {**summary(plan, 'prepared'), 'package_sha256': pin}


def load_plan(package, pin):
    require(type(pin) is str and SHA.fullmatch(pin), 'PACKAGE_PIN_REQUIRED')
    raw = read_bytes(package)
    require(digest(raw) == pin, 'PACKAGE_CHANGED')
    plan = strict_json(raw)
    require(isinstance(plan, dict) and plan.get('format') == 'dd-tool-upgrade-package-v1'
            and plan.get('tool_id') == TOOL_ID and plan.get('backend') == BACKEND
            and plan.get('webui_image') == WEBUI_IMAGE, 'PACKAGE_INVALID')
    require(digest(plan['candidate']['content'].encode()) == CANDIDATE_SHA256
            and fingerprint(plan['candidate']['specs']) == SPECS_SHA256
            and fingerprint(plan['candidate']['metadata']) == METADATA_SHA256, 'PACKAGE_INVALID')
    require(plan['before']['tool']['id'] == TOOL_ID
            and digest(plan['before']['tool']['content'].encode()) == plan['old_source_sha256']
            and digest(plan['before']['tool']['user_id'].encode()) == plan['owner_sha256'], 'PACKAGE_INVALID')
    for key, suffix in [('upgrade_id', 'upgrade'), ('rollback_id', 'rollback')]:
        require(plan[key] == str(uuid.uuid5(uuid.UUID(plan['operation_id']), suffix)), 'PACKAGE_INVALID')
    return plan


def write_guard(action, table, column, database, trigger):
    if trigger:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        return sqlite3.SQLITE_OK if table == 'tool' and column in MUTABLE else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table == 'tool_history' else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def transition(mode, db, backend_root, package, package_sha256):
    require(mode in ('dry-run', 'apply', 'verify', 'rollback'), 'MODE_INVALID')
    plan = load_plan(package, package_sha256)
    backend_check(backend_root)
    require(db_identity(db) == plan['database'], 'DATABASE_REPLACED')
    write = mode in ('apply', 'rollback')
    with connect(db, write) as conn:
        state = target_state(conn)
        phase = phase_of(plan, state)
        require(not (mode == 'apply' and phase == 'rolled_back'), 'OPERATION_ALREADY_ROLLED_BACK')
        require(not (mode == 'rollback' and phase == 'prepared'), 'NOT_APPLIED')
        if mode == 'verify':
            require(phase in ('applied', 'rolled_back'), 'NOT_APPLIED')
        if (mode == 'apply' and phase == 'prepared') or (mode == 'rollback' and phase == 'applied'):
            rollback = mode == 'rollback'
            require(digest(state['tool']['content'].encode()) == (CANDIDATE_SHA256 if rollback else plan['old_source_sha256']), 'CURRENT_HASH_MISMATCH')
            stamp = max(int(time.time()), state['tool']['updated_at'] + 1)
            row = restored_row(plan, stamp) if rollback else upgrade_row(plan, stamp)
            entry = history_entry(plan, row, rollback)
            conn.set_authorizer(write_guard)
            cursor = conn.execute('UPDATE tool SET ' + ','.join(k+'=?' for k in MUTABLE) + ' WHERE id=? AND version_id=? AND content=?',
                                 tuple(row[k] for k in MUTABLE) + (TOOL_ID, state['tool']['version_id'], state['tool']['content']))
            require(cursor.rowcount == 1, 'STATE_CONFLICT')
            columns = COLUMNS['tool_history']
            conn.execute('INSERT INTO tool_history (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')', tuple(entry[k] for k in columns))
            require(conn.total_changes == 2, 'WRITE_SCOPE_INVALID')
            phase = 'rolled_back' if rollback else 'applied'
            # Check row, grants, owner and exact legal history before COMMIT.
            require(target_state(conn) == expected_state(plan, phase, state['history'] + [entry]), 'POST_WRITE_MISMATCH')
        require(db_identity(db) == plan['database'], 'DATABASE_REPLACED')
        backend_check(backend_root)
        result = summary(plan, phase, conn.total_changes)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'dry-run', 'apply', 'verify', 'rollback'])
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--backend-root', type=Path, required=True, help='Read-only A07 service/gateway/bridge source root; active deployment mapping must be established separately')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--native-report', type=Path)
    parser.add_argument('--expected-old-sha256')
    parser.add_argument('--expected-owner-sha256')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--package-sha256')
    args = parser.parse_args(argv)
    try:
        if args.mode == 'prepare':
            require(all(v is not None for v in (args.source, args.native_report, args.expected_old_sha256, args.expected_owner_sha256, args.destination))
                    and args.package is None and args.package_sha256 is None, 'ARGUMENTS_INVALID')
            result = prepare(args.db, args.backend_root, args.source, args.native_report,
                             args.expected_old_sha256, args.expected_owner_sha256, args.destination)
        else:
            require(args.package is not None and args.package_sha256 is not None
                    and all(v is None for v in (args.source, args.native_report, args.expected_old_sha256, args.expected_owner_sha256, args.destination)), 'ARGUMENTS_INVALID')
            result = transition(args.mode, args.db, args.backend_root, args.package, args.package_sha256)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except LifecycleError as exc:
        print(json.dumps({'error': str(exc), 'tool_id': TOOL_ID, 'committed': False}))
    except (OSError, sqlite3.Error, UnicodeError, KeyError, TypeError, ValueError, RecursionError):
        print(json.dumps({'error': 'INPUT_OR_DATABASE_REJECTED', 'tool_id': TOOL_ID, 'committed': False}))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
