"""Pinned Tool lifecycle on disposable SQLite; no production reads or writes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading

import pytest

from scripts import upgrade_readonly_study_tool as upgrade
from scripts.register_main_study_tools import PROGRAM as REGISTER

ROOT = Path(__file__).parents[1]
OLD_SOURCE = ROOT / 'tests/fixtures/readonly_study_tools_v1_0_0.py'
SOURCE = ROOT / 'deploy/open-webui-reuse/readonly_study_tools.py'
NATIVE = ROOT / 'tests/fixtures/readonly_study_tool_120_native.json'
OWNER = 'synthetic-owner'
OLD_PIN = '733ad01dc38ed6b09fcae69047ff731e0eb83d59b0a2dd2432595a3508c6a650'

SCHEMA = '''
CREATE TABLE user(id TEXT PRIMARY KEY, role TEXT, settings TEXT, email TEXT);
CREATE TABLE tool(id TEXT PRIMARY KEY, version_id TEXT, user_id TEXT, name TEXT, content TEXT, specs TEXT, meta TEXT, valves TEXT, created_at INTEGER, updated_at INTEGER);
CREATE TABLE tool_history(id TEXT PRIMARY KEY, tool_id TEXT, parent_id TEXT, snapshot TEXT, user_id TEXT, commit_message TEXT, created_at INTEGER);
CREATE TABLE access_grant(id TEXT PRIMARY KEY, resource_type TEXT, resource_id TEXT, principal_type TEXT, principal_id TEXT, permission TEXT, created_at INTEGER);
CREATE TABLE chat(id TEXT PRIMARY KEY, body TEXT);
CREATE TABLE model(id TEXT PRIMARY KEY, body TEXT);
'''


def sql(db, query, values=()):
    with sqlite3.connect(db) as conn:
        return conn.execute(query, values).fetchall()


def dump(db):
    with sqlite3.connect(db) as conn:
        return '\n'.join(conn.iterdump())


def untouched(db):
    with sqlite3.connect(db) as conn:
        return {name: conn.execute(query).fetchall() for name,query in {
            'tools': "SELECT * FROM tool WHERE id!='dd_family_study_readonly_v1'",
            'history': "SELECT * FROM tool_history WHERE tool_id!='dd_family_study_readonly_v1'",
            'users': 'SELECT * FROM user', 'grants': 'SELECT * FROM access_grant',
            'chat': 'SELECT * FROM chat', 'model': 'SELECT * FROM model'}.items()}


@pytest.fixture
def store(tmp_path):
    db = tmp_path / 'webui ?#.db'
    with sqlite3.connect(db) as conn:
        conn.executescript(SCHEMA)
        conn.execute('INSERT INTO user VALUES (?,?,?,?)', (OWNER,'user','PRIVATE_USER_VALVES_DO_NOT_READ','private@example.invalid'))
        conn.execute('INSERT INTO user VALUES (?,?,?,?)', ('unrelated-owner','admin','UNRELATED_SETTINGS','unrelated@example.invalid'))
        row = {'id': upgrade.TOOL_ID, 'version_id': 'old-version', 'user_id': OWNER, 'name': '合成私有课本工具',
               'content': OLD_SOURCE.read_text(), 'specs': '[]',
               'meta': json.dumps({'description':'保留描述','custom':{'unchanged':True},'manifest':{'version':'1.0.0'},'has_user_valves':False,'i18n':{}}, ensure_ascii=False),
               'valves':'{"encrypted":"OPAQUE_VALVE_SECRET"}', 'created_at': 1, 'updated_at': 2}
        conn.execute('INSERT INTO tool VALUES (?,?,?,?,?,?,?,?,?,?)', tuple(row[k] for k in upgrade.COLUMNS['tool']))
        conn.execute('INSERT INTO tool_history VALUES (?,?,?,?,?,?,?)', ('old-version',upgrade.TOOL_ID,None,json.dumps(upgrade.snapshot(row)),OWNER,'原始注册',2))
        conn.execute('INSERT INTO tool VALUES (?,?,?,?,?,?,?,?,?,?)', ('other','other-version','unrelated-owner','unrelated','PRIVATE_OTHER_SOURCE','[]','{}','{"secret":"other"}',1,2))
        conn.execute('INSERT INTO tool_history VALUES (?,?,?,?,?,?,?)', ('other-version','other',None,'{}','unrelated-owner','other',2))
        conn.execute('INSERT INTO access_grant VALUES (?,?,?,?,?,?,?)', ('other-grant','tool','other','user','*','read',1))
        conn.execute('INSERT INTO chat VALUES (?,?)', ('keep','PRIVATE_CHAT_CONTENT'))
        conn.execute('INSERT INTO model VALUES (?,?)', ('keep','PRIVATE_MODEL_CONFIG'))
    return db


@pytest.fixture
def package(store, tmp_path):
    dest = tmp_path / 'review-packet'
    result = upgrade.prepare(store, ROOT, SOURCE, NATIVE, OLD_PIN, upgrade.digest(OWNER.encode()), dest)
    return dest / 'package.json', result['package_sha256']


def run(mode, store, package, root=ROOT):
    return upgrade.transition(mode, store, root, *package)


def test_full_lifecycle_preserves_permissions_config_and_legal_history(store, package):
    before = dump(store); others = untouched(store); plan = upgrade.load_plan(*package)
    assert run('dry-run',store,package)['state']=='prepared' and dump(store)==before
    first = run('apply',store,package); assert first['row_changes']==2 and first['state']=='applied'
    with upgrade.connect(store) as conn: state = upgrade.target_state(conn)
    assert state['tool']['valves']==plan['before']['tool']['valves']
    assert state['tool']['name']==plan['before']['tool']['name']
    assert state['tool']['created_at']==1 and state['tool']['user_id']==OWNER
    meta=json.loads(state['tool']['meta']); assert meta['description']=='保留描述' and meta['custom']=={'unchanged':True}
    assert meta['manifest']['version']=='1.2.0'
    assert untouched(store)==others
    after=dump(store)
    assert run('apply',store,package)['row_changes']==0 and dump(store)==after
    assert run('verify',store,package)['state']=='applied' and dump(store)==after
    result=run('rollback',store,package); assert result['state']=='rolled_back' and result['row_changes']==2
    with upgrade.connect(store) as conn: restored=upgrade.target_state(conn)
    for k,v in plan['before']['tool'].items():
        if k not in ('version_id','updated_at'): assert restored['tool'][k]==v
    assert len(restored['history'])==3 and untouched(store)==others
    rolled=dump(store)
    assert run('rollback',store,package)['row_changes']==0 and dump(store)==rolled
    assert run('verify',store,package)['state']=='rolled_back'
    with pytest.raises(upgrade.LifecycleError,match='ALREADY_ROLLED_BACK'):run('apply',store,package)
    assert dump(store)==rolled


@pytest.mark.parametrize('grant', [('user','specific-reader'),('group','specific-group')])
def test_explicit_existing_shares_preserved_exactly(store,tmp_path,grant):
    sql(store,'INSERT INTO access_grant VALUES (?,?,?,?,?,?,?)',('target-grant','tool',upgrade.TOOL_ID,*grant,'read',1))
    dest=tmp_path/'packet';p=upgrade.prepare(store,ROOT,SOURCE,NATIVE,OLD_PIN,upgrade.digest(OWNER.encode()),dest)
    packet=(dest/'package.json',p['package_sha256']);before=untouched(store)
    run('apply',store,packet);run('rollback',store,packet)
    assert untouched(store)==before


@pytest.mark.parametrize('mutation,code', [
    ('missing','TARGET_MISSING'),('old_hash','OLD_HASH_MISMATCH'),('owner','OWNER_MISMATCH'),
    ('role','OWNER_UNAVAILABLE'),('history_missing','HISTORY_INVALID'),('public','PUBLIC_TOOL_REJECTED'),
    ('schema','SCHEMA_UNSUPPORTED'),('trigger','SCHEMA_UNSUPPORTED'),('candidate','CANDIDATE_UNVALIDATED'),
    ('native','NATIVE_EVIDENCE_INVALID')])
def test_prepare_preconditions_are_readonly(store,tmp_path,mutation,code):
    old_pin=OLD_PIN;owner=upgrade.digest(OWNER.encode());source=SOURCE;native=NATIVE
    if mutation=='missing':sql(store,'DELETE FROM tool WHERE id=?',(upgrade.TOOL_ID,))
    if mutation=='old_hash':old_pin='0'*64
    if mutation=='owner':owner='0'*64
    if mutation=='role':sql(store,'UPDATE user SET role=? WHERE id=?',('pending',OWNER))
    if mutation=='history_missing':sql(store,'DELETE FROM tool_history WHERE tool_id=?',(upgrade.TOOL_ID,))
    if mutation=='public':sql(store,'INSERT INTO access_grant VALUES (?,?,?,?,?,?,?)',('public','tool',upgrade.TOOL_ID,'user','*','read',1))
    if mutation=='schema':sql(store,'ALTER TABLE tool ADD COLUMN unexpected TEXT')
    if mutation=='trigger':sql(store,"CREATE TRIGGER danger AFTER UPDATE ON tool BEGIN DELETE FROM chat; END")
    if mutation=='candidate':source=tmp_path/'candidate.py';source.write_text('print("never execute")')
    if mutation=='native':
        native=tmp_path/'native.json';data=json.loads(NATIVE.read_text());data['specs']=[];native.write_text(json.dumps(data))
    before=dump(store);raw=upgrade.digest(store.read_bytes())
    with pytest.raises(upgrade.LifecycleError,match=code):upgrade.prepare(store,ROOT,source,native,old_pin,owner,tmp_path/'packet')
    assert dump(store)==before and upgrade.digest(store.read_bytes())==raw and not (tmp_path/'packet').exists()


@pytest.mark.parametrize('phase', ['prepared','applied'])
@pytest.mark.parametrize('field', ['content','specs','meta','valves','name','user_id','created_at','updated_at','grant','history','role'])
def test_concurrent_changes_reject_without_writes(store,package,phase,field):
    if phase=='applied':run('apply',store,package)
    if field in ('grant','history','role'):
        if field=='grant':sql(store,'INSERT INTO access_grant VALUES (?,?,?,?,?,?,?)',('new','tool',upgrade.TOOL_ID,'user','new-reader','read',9))
        if field=='history':sql(store,'UPDATE tool_history SET commit_message=? WHERE id=?',('concurrent edit','old-version'))
        if field=='role':sql(store,'UPDATE user SET role=? WHERE id=?',('admin',OWNER))
    else:
        value={'content':'changed','specs':'[{}]','meta':'{}','valves':'{"changed":true}','name':'changed','user_id':'unrelated-owner','created_at':99,'updated_at':99}[field]
        sql(store,'UPDATE tool SET '+field+'=? WHERE id=?',(value,upgrade.TOOL_ID))
    before=dump(store)
    for mode in ('dry-run','verify','rollback' if phase=='applied' else 'apply'):
        with pytest.raises(upgrade.LifecycleError):run(mode,store,package)
        assert dump(store)==before


@pytest.mark.parametrize('mode', ['dry-run','apply','verify','rollback'])
def test_backend_change_denies_every_stage(store,package,tmp_path,mode):
    before=dump(store)
    with pytest.raises(upgrade.LifecycleError,match='BACKEND_INCOMPATIBLE'):run(mode,store,package,tmp_path)
    assert dump(store)==before


def test_candidate_package_tamper_and_wrong_database_are_rejected(store,package,tmp_path):
    copied=tmp_path/'copy.db';shutil.copy2(store,copied)
    with pytest.raises(upgrade.LifecycleError,match='DATABASE_REPLACED'):run('apply',copied,package)
    before=dump(store);package[0].write_bytes(package[0].read_bytes()+b' ')
    with pytest.raises(upgrade.LifecycleError,match='PACKAGE_CHANGED'):run('apply',store,package)
    assert dump(store)==before


def test_missing_or_symlink_database_never_created_or_followed(tmp_path,store,package):
    missing=tmp_path/'absent.db'
    with pytest.raises(upgrade.LifecycleError,match='PATH_INVALID'):run('apply',missing,package)
    assert not missing.exists()
    symlink=tmp_path/'link.db';symlink.symlink_to(store)
    with pytest.raises(upgrade.LifecycleError,match='PATH_INVALID'):run('apply',symlink,package)


def test_transaction_rolls_back_if_history_insert_fails(store,package):
    plan=upgrade.load_plan(*package)
    sql(store,'INSERT INTO tool_history VALUES (?,?,?,?,?,?,?)',(plan['upgrade_id'],'other',None,'{}','unrelated-owner','collision',1))
    before=dump(store)
    with pytest.raises(sqlite3.IntegrityError):run('apply',store,package)
    assert dump(store)==before


def test_backend_changes_after_update_roll_back_entire_transaction(store,package,monkeypatch):
    before=dump(store);original=upgrade.backend_check;calls=[]
    def changed(root):
        calls.append(1)
        if len(calls)>1:raise upgrade.LifecycleError('BACKEND_INCOMPATIBLE')
        return original(root)
    monkeypatch.setattr(upgrade,'backend_check',changed)
    with pytest.raises(upgrade.LifecycleError,match='BACKEND_INCOMPATIBLE'):run('apply',store,package)
    assert dump(store)==before


@pytest.mark.parametrize('mode',['apply','rollback'])
def test_concurrent_same_package_is_idempotent(store,package,mode):
    if mode=='rollback':run('apply',store,package)
    barrier=threading.Barrier(2)
    def go(_):barrier.wait();return run(mode,store,package)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(go,range(2)))
    assert sorted(r['row_changes'] for r in results)==[0,2]
    assert sql(store,'SELECT count(*) FROM tool_history WHERE tool_id=?',(upgrade.TOOL_ID,))[0][0]==(3 if mode=='rollback' else 2)


def test_competing_packages_cannot_overwrite_first_upgrade(store,package,tmp_path):
    dest=tmp_path/'second';r=upgrade.prepare(store,ROOT,SOURCE,NATIVE,OLD_PIN,upgrade.digest(OWNER.encode()),dest)
    run('apply',store,package);before=dump(store)
    with pytest.raises(upgrade.LifecycleError,match='STATE_CONFLICT'):run('apply',store,(dest/'package.json',r['package_sha256']))
    assert dump(store)==before


def test_prepare_packet_private_no_overwrite_and_redacted_cli(store,package,tmp_path):
    assert package[0].stat().st_mode & 0o777==0o600
    assert package[0].parent.stat().st_mode & 0o777==0o700
    before=dump(store)
    with pytest.raises(upgrade.LifecycleError,match='DESTINATION_EXISTS'):upgrade.prepare(store,ROOT,SOURCE,NATIVE,OLD_PIN,upgrade.digest(OWNER.encode()),package[0].parent)
    command=[sys.executable,str(ROOT/'scripts/upgrade_readonly_study_tool.py'),'dry-run','--db',str(store),'--backend-root',str(ROOT),'--package',str(package[0]),'--package-sha256',package[1]]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==0 and json.loads(result.stdout)['row_changes']==0
    assert all(secret not in result.stdout+result.stderr for secret in (OWNER,'OPAQUE_VALVE_SECRET','PRIVATE_CHAT_CONTENT','PRIVATE_USER_VALVES','private@example.invalid',str(store)))
    assert dump(store)==before
    command[-1]='0'*64;result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==2 and json.loads(result.stdout)['error']=='PACKAGE_CHANGED' and not result.stderr


def test_existing_registration_still_refuses_different_source(store,package):
    before=dump(store)
    payload={'mode':'apply','id':upgrade.TOOL_ID,'owner':OWNER,'source':SOURCE.read_text(),
             'source_sha256':upgrade.CANDIDATE_SHA256,'specs':json.loads(NATIVE.read_text())['specs'],'metadata':{}}
    result=subprocess.run([sys.executable,'-c',REGISTER,str(store)],input=json.dumps(payload),text=True,capture_output=True)
    assert result.returncode!=0 and dump(store)==before


def test_verify_and_rollback_before_apply_are_readonly(store,package):
    before=dump(store)
    for mode in ('verify','rollback'):
        with pytest.raises(upgrade.LifecycleError,match='NOT_APPLIED'):run(mode,store,package)
    assert dump(store)==before


def test_wal_mode_and_post_rollback_fresh_package(store,package,tmp_path):
    sql(store,'PRAGMA journal_mode=WAL')
    first=run('apply',store,package);run('rollback',store,package)
    dest=tmp_path/'next-package';r=upgrade.prepare(store,ROOT,SOURCE,NATIVE,OLD_PIN,upgrade.digest(OWNER.encode()),dest)
    assert r['operation_id']!=first['operation_id']
    new=(dest/'package.json',r['package_sha256']);assert run('apply',store,new)['row_changes']==2
    with pytest.raises(upgrade.LifecycleError):run('rollback',store,package)
    assert run('rollback',store,new)['row_changes']==2
    assert sql(store,'SELECT count(*) FROM tool_history WHERE tool_id=?',(upgrade.TOOL_ID,))[0][0]==5


def test_read_scope_queries_only_target_rows(store,package,monkeypatch):
    from contextlib import contextmanager
    statements=[];original=upgrade.connect
    @contextmanager
    def traced(path,write=False):
        with original(path,write) as conn:
            conn.set_trace_callback(statements.append)
            yield conn
    monkeypatch.setattr(upgrade,'connect',traced)
    run('apply',store,package);run('rollback',store,package)
    selects=[s for s in statements if s.startswith('SELECT') and 'sqlite_schema' not in s]
    assert selects and all(upgrade.TOOL_ID in s or (s.startswith('SELECT role FROM user WHERE id=') and OWNER in s) for s in selects)
    assert all('settings' not in s and 'chat' not in s and 'email' not in s for s in statements)


def test_schema_trigger_added_after_prepare_denies_all_writes(store,package):
    sql(store,"CREATE TRIGGER danger AFTER UPDATE ON tool BEGIN DELETE FROM chat; END")
    before=dump(store)
    with pytest.raises(upgrade.LifecycleError,match='SCHEMA_UNSUPPORTED'):run('apply',store,package)
    assert dump(store)==before


def test_duplicate_json_keys_and_error_messages_do_not_leak(store,package,tmp_path):
    duplicate=tmp_path/'duplicate.json';duplicate.write_text('{"tool_id":"private","tool_id":"secret"}')
    with pytest.raises(upgrade.LifecycleError,match='JSON_INVALID'):upgrade.load_plan(duplicate,upgrade.digest(duplicate.read_bytes()))
    args=['apply','--db',str(store),'--backend-root',str(ROOT),'--package',str(duplicate),'--package-sha256',upgrade.digest(duplicate.read_bytes())]
    result=subprocess.run([sys.executable,str(ROOT/'scripts/upgrade_readonly_study_tool.py'),*args],capture_output=True,text=True)
    assert result.returncode==2 and json.loads(result.stdout)['error']=='JSON_INVALID'
    assert 'secret' not in result.stdout+result.stderr and str(duplicate) not in result.stdout+result.stderr
