"""The scoped Tool transaction never overwrites an existing different tool."""
import json
import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from register_main_study_tools import PROGRAM


def test_private_tool_and_native_history_are_created_atomically(tmp_path):
    path=tmp_path/'webui.db'
    with sqlite3.connect(path) as c:
        c.executescript('''CREATE TABLE user(id TEXT PRIMARY KEY,role TEXT);
        CREATE TABLE tool(id TEXT PRIMARY KEY,version_id TEXT,user_id TEXT,name TEXT,content TEXT,specs TEXT,meta TEXT,valves TEXT,created_at INTEGER,updated_at INTEGER);
        CREATE TABLE tool_history(id TEXT PRIMARY KEY,tool_id TEXT,parent_id TEXT,snapshot TEXT,user_id TEXT,commit_message TEXT,created_at INTEGER);
        INSERT INTO user VALUES ('synthetic-owner','user');
        INSERT INTO tool(id,content) VALUES('keep_existing','UNRELATED_PRIVATE_SOURCE');''')
    source='class Tools: pass\n'
    payload={'id':'dd_family_study_readonly_v1','owner':'synthetic-owner','source':source,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'specs':[],'metadata':{}}
    def run(mode):return subprocess.run([sys.executable,'-c',PROGRAM,str(path)],input=json.dumps({**payload,'mode':mode}),text=True,capture_output=True)
    result=run('prepare');assert result.returncode==0 and json.loads(result.stdout)['row_changes']==0
    result=run('apply');assert result.returncode==0 and json.loads(result.stdout)['row_changes']==2
    result=run('apply');assert result.returncode==0 and json.loads(result.stdout)['row_changes']==0
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT content FROM tool WHERE id='keep_existing'").fetchone()[0]=='UNRELATED_PRIVATE_SOURCE'
        assert c.execute('SELECT count(*) FROM tool_history').fetchone()[0]==1
        live=c.execute("SELECT version_id,content FROM tool WHERE id='dd_family_study_readonly_v1'").fetchone()
        history=c.execute('SELECT id,snapshot FROM tool_history').fetchone()
        assert live[0]==history[0] and json.loads(history[1])['content']==live[1]
    payload['source']='DIFFERENT';payload['source_sha256']=hashlib.sha256(b'DIFFERENT').hexdigest()
    assert run('apply').returncode!=0
    with sqlite3.connect(path) as c:assert c.execute("SELECT content FROM tool WHERE id='dd_family_study_readonly_v1'").fetchone()[0]==source
