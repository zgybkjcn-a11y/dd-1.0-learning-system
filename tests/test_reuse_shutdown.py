"""Stop outcomes and target isolation; Docker is replaced with metadata fixtures."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import probe_reuse_runtime as runtime


@pytest.fixture
def shutdown(tmp_path,monkeypatch):
    project='dd-learning-reuse-synthetic-stop'
    (tmp_path/'manifest.json').write_text(json.dumps({'project':project}))
    row={'id':'fixed-container-id','project':project,'service':'open-webui','running':True,
         'status':'running','exit_code':0,'oom_killed':False,'pid':120}
    calls=[];outcome={'exit_code':0,'oom_killed':False,'running':False,'pid':0,'status':'exited'}
    monkeypatch.setattr(runtime,'compose',lambda *a,**k:'fixed-container-id')
    def call(args,**kwargs):
        calls.append((args,kwargs))
        if args[:2]==['docker','inspect']:return json.dumps(row)
        assert args[:2]==['docker','stop']
        row.update(outcome)
        return row['id']
    monkeypatch.setattr(runtime,'call',call)
    return tmp_path,row,outcome,calls


def test_success_requires_zero_exit_and_persists_each_attempt(shutdown):
    path,row,outcome,calls=shutdown
    first=runtime.stop(path)
    assert first['status']=='passed' and first['stopped_now']==1 and first['grace_seconds']==60
    command=next(c for c in calls if c[0][1]=='stop')
    assert command[0]==['docker','stop','--time','60','fixed-container-id']
    assert command[1]['timeout']==90
    calls.clear();second=runtime.stop(path)
    assert second['status']=='passed' and second['already_stopped']==1
    assert all(c[0][1]!='stop' for c in calls)
    assert len(list(path.glob('shutdown-*.json')))==2


@pytest.mark.parametrize('failure',[{'exit_code':137},{'exit_code':143},{'oom_killed':True},{'running':True,'pid':120}])
def test_docker_stop_success_is_not_enough(shutdown,failure):
    path,row,outcome,calls=shutdown;outcome.update(failure)
    result=runtime.stop(path)
    assert result['status']=='failed' and result['errors']
    saved=json.loads(next(path.glob('shutdown-*.json')).read_text())
    assert saved['status']=='failed'


def test_old_failed_exit_is_not_overwritten_as_a_successful_retry(shutdown):
    path,row,outcome,calls=shutdown;row.update(running=False,pid=0,status='exited',exit_code=137)
    assert runtime.stop(path)['status']=='failed'
    assert all(c[0][1]!='stop' for c in calls)


@pytest.mark.parametrize('change',[{'project':'open-webui'},{'service':'unknown'}])
def test_foreign_targets_fail_before_any_stop(shutdown,change):
    path,row,outcome,calls=shutdown;row.update(change)
    with pytest.raises(ValueError,match='outside'):runtime.stop(path)
    assert all(c[0][1]!='stop' for c in calls)


def test_recreated_container_set_is_rejected(shutdown,monkeypatch):
    path,row,outcome,calls=shutdown
    responses=iter(['fixed-container-id','replacement-container-id'])
    monkeypatch.setattr(runtime,'compose',lambda *a,**k:next(responses))
    original=runtime.call
    def call(args,**kwargs):
        if args[1]=='inspect' and args[-1]=='replacement-container-id':
            return json.dumps({**row,'id':'replacement-container-id','running':True,'pid':121})
        return original(args,**kwargs)
    monkeypatch.setattr(runtime,'call',call)
    result=runtime.stop(path)
    assert result['status']=='failed' and 'ISOLATED_CONTAINER_SET_CHANGED' in result['errors']
    assert len([c for c in calls if c[0][1]=='stop'])==1
