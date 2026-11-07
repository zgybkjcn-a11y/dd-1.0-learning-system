"""Prepare/apply static family bridge through the current proxy; no service rebuild.

No environment/secret/data inspection. Immutable static revision is added under
the existing readonly mount; only the mounted nginx config is rewritten in place.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'learning_data/deployments/family-math-20261105/compose-main-study-20261106.json'
OUT = ROOT / 'learning_data/verification/main-study-bridge-20261107/deployment'
ASSETS = ROOT / 'deploy/open-webui-reuse/main-study'
PROXY = 'dd-family-math-learning-proxy-1'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def container_state():
    result = []
    for name in ('open-webui', 'dd-family-math-learning-api-1', 'dd-family-math-learning-worker-1',
                 'dd-family-math-learning-gateway-1', PROXY):
        raw = subprocess.check_output(['docker', 'inspect', '--format',
            '{{json .Id}}|{{json .Image}}|{{json .State.StartedAt}}', name], text=True)
        result.append({'name': name, 'state': [json.loads(x) for x in raw.strip().split('|')]})
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true'); args = parser.parse_args()
    config = json.loads(BASE.read_text())
    live = Path(config['configs']['learning_proxy']['file'])
    mounted = next(Path(v['source']) for v in config['services']['learning-proxy']['volumes'] if v['target'] == '/opt/dd-main-study')
    release = mounted / 'bridge-20261107'
    if not args.apply:
        assert not OUT.exists() and not release.exists(), 'Preserve previous revisions'
        OUT.mkdir(parents=True); shutil.copytree(ASSETS, release)
        before = live.read_text()
        assert 'dd_family_bridge' not in before
        candidate = before.replace('/opt/dd-main-study/study.', '/opt/dd-main-study/bridge-20261107/study.')
        candidate = candidate.replace('    server {', '''    map $uri $dd_family_bridge {
        default "";
        /learning/ui '<script src="/static/dd-family-bridge.js" defer></script>';
    }
    server {''', 1)
        candidate = candidate.replace('        location ^~ /learning/ {', '''        location ^~ /learning/ {
            proxy_set_header Accept-Encoding "";
            sub_filter_once on;
            sub_filter '</body>' '$dd_family_bridge</body>';''', 1)
        candidate = candidate.replace('        location = /static/loader.js {', '''        location = /static/dd-family-bridge.js {
            alias /opt/dd-main-study/bridge-20261107/family-bridge.js;
            default_type application/javascript;
            add_header Cache-Control "no-store" always;
            add_header X-Content-Type-Options nosniff always;
        }
        location = /static/loader.js {''', 1)
        assert candidate != before
        (OUT / 'nginx.before.conf').write_text(before)
        (OUT / 'nginx.candidate.conf').write_text(candidate)
        (OUT / 'prepared.json').write_text(json.dumps({'compose': str(BASE.relative_to(ROOT)),
            'live_config': str(live.relative_to(ROOT)), 'base_sha256': digest(live),
            'candidate_sha256': digest(OUT / 'nginx.candidate.conf'), 'containers_before': container_state(),
            'static_files': {p.name: digest(p) for p in release.iterdir()}, 'applied': False}, indent=2) + '\n')
        subprocess.run(['docker', 'exec', '-i', PROXY, 'sh', '-c', 'cat > /tmp/dd-bridge-candidate.conf'],
                       input=candidate.encode(), check=True)
        subprocess.run(['docker', 'exec', PROXY, 'nginx', '-t', '-c', '/tmp/dd-bridge-candidate.conf'], check=True)
        print('Candidate static revision and nginx syntax verified; not applied.')
    else:
        evidence = json.loads((OUT / 'prepared.json').read_text())
        assert digest(live) == evidence['base_sha256'], 'Proxy config changed since preparation'
        assert digest(OUT / 'nginx.candidate.conf') == evidence['candidate_sha256']
        assert container_state() == evidence['containers_before'], 'Deployment changed since preparation'
        assert {p.name: digest(p) for p in release.iterdir()} == evidence['static_files']
        try:
            live.write_bytes((OUT / 'nginx.candidate.conf').read_bytes())  # Preserve bind-mount inode.
            subprocess.run(['docker', 'exec', PROXY, 'nginx', '-t', '-c', '/etc/nginx/dd-learning.conf'], check=True)
            subprocess.run(['docker', 'exec', PROXY, 'nginx', '-s', 'reload', '-c', '/etc/nginx/dd-learning.conf'], check=True)
        except Exception:
            live.write_bytes((OUT / 'nginx.before.conf').read_bytes())
            subprocess.run(['docker', 'exec', PROXY, 'nginx', '-s', 'reload', '-c', '/etc/nginx/dd-learning.conf'], check=True)
            raise
        evidence.update(applied=True, containers_after=container_state(), live_sha256=digest(live))
        assert evidence['containers_before'] == evidence['containers_after']
        (OUT / 'applied.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print('Proxy reloaded; all five container IDs/images/start times unchanged.')


if __name__ == '__main__': main()
