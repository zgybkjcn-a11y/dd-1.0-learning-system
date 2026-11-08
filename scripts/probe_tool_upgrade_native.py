"""Fixed offline WebUI image, migrated temporary DB, native cache/history checks."""
import asyncio
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

assert os.environ['DATA_DIR'] == '/tmp/dd-a08-native'
assert os.environ['OFFLINE_MODE'] == 'true'
Path(os.environ['DATA_DIR']).mkdir()
sys.path.insert(0, '/candidate')
import upgrade_readonly_study_tool as u
faulthandler.dump_traceback_later(90)
from fastapi import Request
from open_webui.models.tools import Tools
from open_webui.models.tool_history import tool_snapshot
from open_webui.utils import tools as native
from open_webui.utils.plugin import load_tool_module_by_id


def unrelated(db):
    with sqlite3.connect(db) as c:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        result = {}
        for table in tables:
            if table == 'tool': query = 'SELECT * FROM tool WHERE id != ?'; params = (u.TOOL_ID,)
            elif table == 'tool_history': query = 'SELECT * FROM tool_history WHERE tool_id != ?'; params = (u.TOOL_ID,)
            else: query = 'SELECT * FROM "' + table.replace('"', '""') + '"'; params = ()
            result[table] = c.execute(query, params).fetchall()
        return result


async def main():
    root = Path('/candidate'); db = Path(os.environ['DATA_DIR']) / 'webui.db'
    old = (root / 'old.py').read_text()
    old_tool, old_meta, _ = await load_tool_module_by_id(u.TOOL_ID, content=old)
    old_specs = native.get_tool_specs(old_tool)
    row = {'id':u.TOOL_ID, 'version_id':'old-version', 'user_id':'native-owner', 'name':'合成私有课本工具',
           'content':old, 'specs':json.dumps(old_specs),
           'meta':json.dumps({'description':'synthetic preserved','custom':{'keep':True},'manifest':old_meta,'has_user_valves':False}),
           'valves':'{"opaque":"kept"}', 'created_at':1, 'updated_at':2}
    assert u.snapshot(row) == tool_snapshot({**row, 'meta': json.loads(row['meta'])})
    with sqlite3.connect(db) as c:
        c.execute('INSERT INTO user(id,email,role,name,settings,created_at,updated_at,last_active_at) VALUES(?,?,?,?,?,?,?,?)',
                  ('native-owner','native@example.invalid','user','Synthetic','{"tools":{"valves":{"keep":"private"}}}',1,1,1))
        c.execute('INSERT INTO tool ('+','.join(u.COLUMNS['tool'])+') VALUES (?,?,?,?,?,?,?,?,?,?)',tuple(row[k] for k in u.COLUMNS['tool']))
        c.execute('INSERT INTO tool_history VALUES (?,?,?,?,?,?,?)',('old-version',u.TOOL_ID,None,json.dumps(u.snapshot(row)),'native-owner','initial',2))
        c.execute('INSERT INTO access_grant VALUES (?,?,?,?,?,?,?)',('grant','tool',u.TOOL_ID,'user','native-reader','read',1))
        other={**row,'id':'other-tool','version_id':None,'content':'PRIVATE_UNRELATED_SOURCE','valves':'{"private":"unrelated"}'}
        c.execute('INSERT INTO tool ('+','.join(u.COLUMNS['tool'])+') VALUES (?,?,?,?,?,?,?,?,?,?)',tuple(other[k] for k in u.COLUMNS['tool']))
    untouched = unrelated(db)
    request = Request({'type':'http','app':SimpleNamespace(state=SimpleNamespace()),'headers':[]})
    user = SimpleNamespace(id='native-owner',role='user')
    async def loaded():
        result = await native.get_tools(request,[u.TOOL_ID],user,{'__user__':{'id':user.id},'__request__':request})
        assert len(result)==6
        return result
    first = await loaded()
    result = u.prepare(db,root/'backend',root/'candidate.py',root/'native.json',hashlib.sha256(old.encode()).hexdigest(),hashlib.sha256(user.id.encode()).hexdigest(),Path('/tmp/a08-packet'))
    package = Path('/tmp/a08-packet/package.json'); pin = result['package_sha256']
    reports = [u.transition('dry-run',db,root/'backend',package,pin), u.transition('apply',db,root/'backend',package,pin)]
    upgraded = await Tools.get_tool_by_id(u.TOOL_ID)
    assert upgraded.content == (root/'candidate.py').read_text()
    assert upgraded.meta.manifest['version']=='1.2.0' and len(upgraded.access_grants)==1
    second = await loaded()
    assert first['search_textbook']['callable'] is not second['search_textbook']['callable']
    reports += [u.transition('verify',db,root/'backend',package,pin),u.transition('apply',db,root/'backend',package,pin),u.transition('rollback',db,root/'backend',package,pin)]
    restored = await Tools.get_tool_by_id(u.TOOL_ID)
    assert restored.content==old and restored.meta.manifest==old_meta
    third = await loaded()
    assert second['search_textbook']['callable'] is not third['search_textbook']['callable']
    reports += [u.transition('verify',db,root/'backend',package,pin),u.transition('rollback',db,root/'backend',package,pin)]
    with sqlite3.connect(db) as c:
        history = c.execute('SELECT id,parent_id,snapshot FROM tool_history WHERE tool_id=?',(u.TOOL_ID,)).fetchall()
        current = next(r for r in history if r[0]==restored.version_id)
        assert json.loads(current[2])==tool_snapshot(restored)
        assert len(history)==3
    assert unrelated(db)==untouched
    faulthandler.cancel_dump_traceback_later()
    print('DD_TOOL_UPGRADE_NATIVE='+json.dumps({'passed':True,'results':reports,'history_entries':len(history),
          'methods_each_version':6,'cache_reloaded_after_upgrade_and_rollback':True,
          'native_snapshot_matches':True,'unrelated_tables_unchanged':True,'model_calls':0,
          'network':'none','formal_data_mounted':False,'upgrader_sha256':hashlib.sha256(Path(u.__file__).read_bytes()).hexdigest()},ensure_ascii=False))

asyncio.run(main())
