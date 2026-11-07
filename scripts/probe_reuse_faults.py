#!/usr/bin/env python3
"""Bounded fault phases for a prepared, synthetic-only isolated reuse project.

Requires a resident reuse_fault_client.py peer, a synthetic login and binding.
Never provisions production, recreates a container, or removes a volume.
Each phase refuses to overwrite evidence. Run phases individually for review.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import re
import time
from pathlib import Path

from probe_reuse_runtime import ROOT, call, compose, save, stop

SERVICES = {'learning-api', 'learning-worker', 'learning-gateway', 'learning-proxy', 'open-webui'}
STATE_FORMAT = ('{"id":{{json .Id}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
                '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
                '"observer_project":{{json (index .Config.Labels "dd.verification.project")}},'
                '"running":{{json .State.Running}},"exit_code":{{json .State.ExitCode}},'
                '"oom_killed":{{json .State.OOMKilled}},"pid":{{json .State.Pid}},'
                '"ports":{{json .HostConfig.PortBindings}},"networks":{{json .NetworkSettings.Networks}}}')


class Probe:
    def __init__(self, run: Path, phase: str, evidence_suffix: str = ''):
        self.run = run.resolve()
        if not self.run.is_relative_to(ROOT / 'learning_data'):
            raise ValueError('isolated learning_data runtime required')
        self.project = json.loads((self.run / 'manifest.json').read_text())['project']
        # compose() validates project syntax and private configuration hash.
        ids = compose(self.run, 'ps', '-aq').splitlines()
        self.targets = {}
        for cid in ids:
            row = self.inspect(cid)
            service = row['service']
            if row['project'] != self.project or service not in SERVICES or service in self.targets:
                raise ValueError('foreign or duplicate isolated service')
            self.isolated(row)
            self.targets[service] = row['id']
        if set(self.targets) != SERVICES:
            raise ValueError('exactly five isolated services required')
        peer = self.inspect(self.project + '-client')
        if peer['observer_project'] != self.project or peer['project'] is not None:
            raise ValueError('isolated observer label required')
        self.isolated(peer)
        self.peer = peer['id']
        if evidence_suffix and not re.fullmatch(r'[a-z0-9-]{1,40}', evidence_suffix):
            raise ValueError('invalid evidence suffix')
        self.output = self.run.parent / (phase + ('-' + evidence_suffix if evidence_suffix else '') + '.json')
        self.lock = (self.run / 'fault-probe.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise ValueError('another fault phase is still running') from None
        if self.output.exists():
            self.lock.close()
            raise ValueError('phase evidence already exists; preserve it')
        self.report = {'project': self.project, 'phase': phase, 'status': 'running',
                       'production_change': False, 'steps': {}}

    @staticmethod
    def inspect(cid):
        return json.loads(call(['docker', 'inspect', '--format', STATE_FORMAT, cid]))

    def isolated(self, row):
        if row['ports']:
            raise ValueError('host ports are forbidden')
        if not row['networks']:
            raise ValueError('isolated networks required')
        for name, net in row['networks'].items():
            internal = call(['docker', 'network', 'inspect', '--format', '{{json .Internal}}', net['NetworkID']])
            if not name.startswith(self.project + '_') or internal != 'true':
                raise ValueError('only project internal networks allowed')

    def record(self, key, value):
        self.report['steps'][key] = value
        save(self.output, self.report)
        print(json.dumps({'phase': self.report['phase'], 'checkpoint': key}), flush=True)
        return value

    def client(self, action):
        return json.loads(call(['docker', 'exec', self.peer, 'python', '/probe.py', action], timeout=50))

    def healthy(self):
        deadline = time.monotonic() + 90
        while True:
            result = self.client('check')
            if all(row['status'] == 200 for row in result.values()):
                assert result['webui']['same_subject'] and result['learning']['same_account']
                return result
            if time.monotonic() >= deadline:
                raise RuntimeError('isolated session recovery deadline exceeded')
            time.sleep(1)

    def change(self, service, action):
        cid = self.targets[service]
        before = self.inspect(cid)
        assert before['project'] == self.project and before['service'] == service
        since = time.time()
        started = time.monotonic()
        if action == 'stop':
            call(['docker', 'stop', '--time', '60', cid], timeout=90)
        elif action == 'kill':
            call(['docker', 'kill', '--signal', 'KILL', cid])
        elif action == 'start':
            call(['docker', 'start', cid])
        else:
            raise ValueError('unsupported operation')
        elapsed = round(time.monotonic() - started, 3)
        row = self.inspect(cid)
        events = []
        raw = call(['docker', 'events', '--since', str(since), '--until', str(time.time()),
                    '--filter', 'container=' + cid, '--format', '{{json .}}'], timeout=10)
        for line in raw.splitlines():
            event = json.loads(line)
            attrs = event.get('Actor', {}).get('Attributes', {})
            if event.get('Action') in {'kill', 'die', 'stop', 'start'}:
                events.append({'action': event['Action'], 'signal': attrs.get('signal'),
                               'exit_code': attrs.get('exitCode')})
        result = {k: row[k] for k in ('id', 'service', 'running', 'exit_code', 'oom_killed', 'pid')}
        result.update(operation=action, seconds=elapsed, events=events)
        self.record(service + '-' + action, result)
        if action != 'start':
            assert not row['running'] and row['pid'] == 0 and not row['oom_killed']
            assert row['exit_code'] == (137 if action == 'kill' else 0)
        else:
            assert row['running']
        return result

    def websocket(self):
        path = self.run / 'client-state/websocket-report.json'
        if path.exists():
            previous = json.loads(path.read_text())
            if previous['currently_connected']:
                if not previous['authenticated_join'] or time.time() - path.stat().st_mtime > 3:
                    raise ValueError('existing websocket observer is stale or unauthenticated')
                return self.record('websocket-connected', previous)
            destination = path.with_name('websocket-history-' + str(time.time_ns()) + '.json')
            path.rename(destination)
        call(['docker', 'exec', '-d', self.peer, 'python', '/probe.py', 'websocket'])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if path.exists():
                report = json.loads(path.read_text())
                if report['currently_connected'] and report['authenticated_join']:
                    return self.record('websocket-connected', report)
            time.sleep(0.25)
        raise RuntimeError('authenticated isolated websocket unavailable')

    def run_phase(self, phase):
        if phase == 'finish':
            call(['docker', 'stop', '--time', '10', self.peer], timeout=20)
            row = self.inspect(self.peer)
            self.record('observer-stopped', {k: row[k] for k in ('running', 'exit_code', 'oom_killed', 'pid')})
            assert not row['running'] and row['exit_code'] == 0 and not row['oom_killed'] and row['pid'] == 0
            result = self.record('compose-stopped', stop(self.run))
            assert result['status'] == 'passed'
            return
        self.record('before', self.healthy())
        if phase == 'gateway-outage':
            self.websocket()
            self.record('nonce-issued', self.client('nonce'))
            self.change('learning-gateway', 'stop')
            observations = []
            for attempt in range(3):
                result = self.client('check')
                observations.append(result)
                self.record('outage-observations', observations)
                if result['learning']['status'] in {502, 504}:
                    break
                time.sleep(1)
            assert result['webui']['status'] == 200 and result['learning']['status'] in {502, 504}
            assert observations[0]['learning']['status'] in {502, 504} and observations[0]['learning']['seconds'] < 8
            assert result['learning_health']['status'] == 200
            report = self.record('websocket-during-outage', json.loads((self.run / 'client-state/websocket-report.json').read_text()))
            assert report['currently_connected'] and not report['server_disconnect_observed'] and not report['self_timeout']
            self.change('learning-gateway', 'start')
            time.sleep(2)
            self.record('old-nonce-rejected', self.client('stale-nonce'))
            self.record('new-session', self.client('learning-login'))
        elif phase == 'api-outage':
            self.change('learning-worker', 'stop')
            self.change('learning-api', 'stop')
            result = self.record('outage', self.client('check'))
            assert result['webui']['status'] == 200
            assert result['learning']['status'] == 503 and result['learning']['error_code'] == 'LEARNING_UPSTREAM_UNAVAILABLE'
            assert result['learning_health']['status'] is None
            self.change('learning-api', 'start')
            self.change('learning-worker', 'start')
        elif phase in {'webui-stop', 'webui-kill'}:
            self.websocket()
            self.change('open-webui', 'stop' if phase == 'webui-stop' else 'kill')
            deadline = time.monotonic() + 15
            while True:
                report = json.loads((self.run / 'client-state/websocket-report.json').read_text())
                if report['server_disconnect_observed']:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError('peer did not observe server disconnect')
                time.sleep(0.25)
            self.record('websocket-disconnected', report)
            assert not report['self_timeout'] and not report['currently_connected']
            result = self.record('outage', self.client('check'))
            assert result['webui']['status'] in {502, 504} and result['webui']['seconds'] < 8
            assert result['learning_health']['status'] == 200
            assert result['learning']['status'] == 503 and result['learning']['error_code'] == 'AUTH_UPSTREAM_UNAVAILABLE'
            self.change('open-webui', 'start')
        self.record('recovered-existing-cookies', self.healthy())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['gateway-outage', 'api-outage', 'webui-stop', 'webui-kill', 'finish'])
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--evidence-suffix', default='')
    args = parser.parse_args()
    probe = Probe(args.runtime, args.phase, args.evidence_suffix)
    try:
        probe.run_phase(args.phase)
        probe.report['status'] = 'passed'
    except Exception:
        probe.report['status'] = 'failed'
        raise
    finally:
        save(probe.output, probe.report)
        probe.lock.close()
    print(json.dumps({'phase': args.phase, 'status': probe.report['status']}))


if __name__ == '__main__':
    main()
