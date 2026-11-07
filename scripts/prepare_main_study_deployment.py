"""Prepare proxy-only navigation release from the current family Compose.

Does not start services; does not inspect environments, secrets or WebUI data.
Config file references are retained without opening their secret targets.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'learning_data/deployments/family-math-20261105'
OUT = ROOT / 'learning_data/verification/main-study-20261106'
SOURCE = ROOT / 'deploy/open-webui-reuse/main-study'
BASE = DEPLOY / 'compose-study-workbench-20261106.json'
TARGET = DEPLOY / 'compose-main-study-20261106.json'
RELEASE = DEPLOY / 'main-study-20261106'
EXPECTED_IMAGE = 'sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0'


def main():
    assert not TARGET.exists() and not RELEASE.exists(), 'Keep existing release; choose a new version'
    config = json.loads(BASE.read_text())
    updated = copy.deepcopy(config)
    before = []
    for name in ('open-webui', 'dd-family-math-learning-api-1', 'dd-family-math-learning-worker-1',
                 'dd-family-math-learning-gateway-1', 'dd-family-math-learning-proxy-1'):
        raw = subprocess.check_output(['docker', 'inspect', '--format',
            '{{json .Id}}|{{json .Image}}|{{json .State.StartedAt}}', name], text=True)
        cid, image, started = [json.loads(x) for x in raw.strip().split('|')]
        if name in ('dd-family-math-learning-api-1', 'dd-family-math-learning-worker-1', 'dd-family-math-learning-gateway-1'):
            assert image == EXPECTED_IMAGE, 'Current deployment changed; reassess'
        before.append({'name': name, 'id': cid, 'image': image, 'started_at': started})
    old_nginx = Path(config['configs']['learning_proxy']['file'])
    nginx = old_nginx.read_text()
    assert 'dd-study' not in nginx and nginx.count('        location / {') == 1
    assert all(config['services'][name]['image'] == EXPECTED_IMAGE
               for name in ('learning-api', 'learning-worker', 'learning-gateway'))
    # Use Open WebUI's existing custom loader/stylesheet slots. Public upstream
    # assets were checked to be empty at this deployment version.
    locations = '''        # DD main study: original local assets; see mounted SOURCES.md.
        location = /static/loader.js {
            alias /opt/dd-main-study/study.js;
            default_type application/javascript;
            add_header Cache-Control "no-store" always;
            add_header X-Content-Type-Options nosniff always;
        }
        location = /static/custom.css {
            alias /opt/dd-main-study/study.css;
            default_type text/css;
            add_header Cache-Control "no-store" always;
            add_header X-Content-Type-Options nosniff always;
        }
'''
    nginx = nginx.replace('        location / {', locations + '        location / {')
    RELEASE.mkdir()
    assets = RELEASE / 'assets'
    shutil.copytree(SOURCE, assets)
    (RELEASE / 'nginx.conf').write_text(nginx)
    (RELEASE / 'nginx.before.conf').write_bytes(old_nginx.read_bytes())
    updated['configs']['learning_proxy']['file'] = str(RELEASE / 'nginx.conf')
    assert 'volumes' not in updated['services']['learning-proxy']
    updated['services']['learning-proxy']['volumes'] = [
        {'type': 'bind', 'source': str(assets), 'target': '/opt/dd-main-study', 'read_only': True,
         'bind': {'create_host_path': False}}
    ]
    comparison = copy.deepcopy(updated)
    comparison['configs']['learning_proxy'] = config['configs']['learning_proxy']
    del comparison['services']['learning-proxy']['volumes']
    assert comparison == config, 'Only proxy config and readonly static mount may change'
    TARGET.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'base_compose': str(BASE.relative_to(ROOT)), 'candidate_compose': str(TARGET.relative_to(ROOT)),
              'containers_before': before, 'only_proxy_config_and_static_mount_changed': True,
              'formal_webui_data_accessed': False, 'model_calls': 0,
              'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets.iterdir()},
              'nginx_sha256': hashlib.sha256(nginx.encode()).hexdigest(), 'deployed': False}
    (OUT / 'prepared.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'candidate_compose': str(TARGET.relative_to(ROOT)), 'deployed': False, 'only_proxy_changed': True}))


if __name__ == '__main__':
    main()
