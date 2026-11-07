"""Fault injection must stay in internal disposable resources and retain failures."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import probe_reuse_faults as faults


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(faults, 'ROOT', tmp_path)
    run = tmp_path / 'learning_data' / 'run'
    run.mkdir(parents=True)
    project = 'dd-learning-reuse-test-faults'
    (run / 'manifest.json').write_text(json.dumps({'project': project}))
    rows = {}
    for service in sorted(faults.SERVICES):
        cid = service + '-fixed-id'
        rows[cid] = {'id': cid, 'project': project, 'service': service, 'observer_project': None,
                     'running': True, 'exit_code': 0, 'oom_killed': False, 'pid': 12, 'ports': {},
                     'networks': {project + '_learning-internal': {'NetworkID': 'fixed-network'}}}
    rows[project + '-client'] = {**rows['open-webui-fixed-id'], 'id': 'observer-fixed-id',
                                'project': None, 'service': None, 'observer_project': project}
    monkeypatch.setattr(faults, 'compose', lambda *a: '\n'.join(k for k in rows if k.endswith('-fixed-id')))
    calls = []
    outcome = {'exit_code': 0, 'oom_killed': False, 'running': False, 'pid': 0}

    def call(args, **kwargs):
        calls.append(args)
        if args[1] == 'inspect':
            return json.dumps(rows[args[-1]])
        if args[1:3] == ['network', 'inspect']:
            return 'true'
        if args[1] in {'stop', 'kill'}:
            rows[args[-1]].update(outcome)
            return args[-1]
        if args[1] == 'events':
            return ''
        raise AssertionError('unexpected Docker operation')

    monkeypatch.setattr(faults, 'call', call)
    return run, rows, calls, outcome


@pytest.mark.parametrize('change', [
    {'project': 'open-webui'}, {'service': 'foreign-service'},
    {'ports': {'443/tcp': [{'HostPort': '443'}]}},
    {'networks': {'open-webui_default': {'NetworkID': 'production-network'}}},
])
def test_foreign_or_exposed_resources_rejected_before_mutation(environment, change):
    run, rows, calls, _ = environment
    rows['open-webui-fixed-id'].update(change)
    with pytest.raises(ValueError):
        faults.Probe(run, 'webui-kill')
    assert all(c[1] in {'inspect', 'network'} for c in calls)


def test_existing_evidence_preserved(environment):
    run, _, calls, _ = environment
    evidence = run.parent / 'webui-stop.json'
    evidence.write_text('old evidence')
    with pytest.raises(ValueError, match='already exists'):
        faults.Probe(run, 'webui-stop')
    assert evidence.read_text() == 'old evidence'
    assert all(c[1] in {'inspect', 'network'} for c in calls)


def test_overlapping_fault_phases_rejected(environment):
    run, _, calls, _ = environment
    first = faults.Probe(run, 'gateway-outage')
    with pytest.raises(ValueError, match='still running'):
        faults.Probe(run, 'api-outage')
    assert all(c[1] in {'inspect', 'network'} for c in calls)
    first.lock.close()


@pytest.mark.parametrize('outcome', [{'exit_code': 137}, {'oom_killed': True}, {'running': True, 'pid': 12}])
def test_failed_graceful_stop_is_recorded_before_assertion(environment, outcome):
    run, _, calls, result = environment
    result.update(outcome)
    probe = faults.Probe(run, 'webui-stop')
    with pytest.raises(AssertionError):
        probe.change('open-webui', 'stop')
    report = json.loads(probe.output.read_text())
    assert all(report['steps']['open-webui-stop'][k] == v for k, v in outcome.items())
    assert ['docker', 'stop', '--time', '60', 'open-webui-fixed-id'] in calls


def test_intentional_kill_retains_137_as_fault_evidence(environment):
    run, _, calls, outcome = environment
    outcome['exit_code'] = 137
    probe = faults.Probe(run, 'webui-kill')
    result = probe.change('open-webui', 'kill')
    assert result['operation'] == 'kill' and result['exit_code'] == 137
    assert ['docker', 'kill', '--signal', 'KILL', 'open-webui-fixed-id'] in calls
