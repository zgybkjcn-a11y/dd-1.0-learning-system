"""Prepare only: a reviewable snapshot and nginx candidate for the three samples.

Does not write active configuration, call Docker, register tools or deploy files.
The live baseline must still be the recorded chat-20261107 snapshot.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'deploy/open-webui-reuse/main-study'
OUT = ROOT / 'learning_data/verification/main-study-samples-20261107/candidate'
ACTIVE = ROOT / 'learning_data/deployments/family-math-20261105/main-study-20261106/nginx.conf'


def main():
    baseline = ACTIVE.read_text()
    assert baseline.count('/opt/dd-main-study/chat-20261107/') == 3
    assert '/static/dd-study-mermaid.min.js' not in baseline
    assert hashlib.sha256((ASSETS / 'family-bridge.js').read_bytes()).hexdigest() == '8bfe564373befe4d3bb64cfc4d91b67880545217f00d293da415938cce4f0347'
    manifest = json.loads((ASSETS / 'vendor/manifest.json').read_text())
    bundle = ASSETS / 'vendor/mermaid-11.12.1.min.js'
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == manifest['bundle_sha256']
    assert manifest['bundle_sri'] in (ASSETS / 'study.js').read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot = OUT / 'samples-20261107'; snapshot.mkdir(exist_ok=True)
    files = [ASSETS / n for n in ('study.js', 'study.css', 'family-bridge.js', 'SOURCES.md')]
    files += sorted((ASSETS / 'vendor').iterdir())
    hashes = {}
    for path in files:
        relative = path.relative_to(ASSETS); target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
        hashes[str(relative)] = hashlib.sha256(target.read_bytes()).hexdigest()
    extra = '''        location = /static/dd-study-mermaid.min.js {
            alias /opt/dd-main-study/samples-20261107/vendor/mermaid-11.12.1.min.js;
            default_type application/javascript;
            add_header Cache-Control "no-store" always;
            add_header X-Content-Type-Options nosniff always;
        }
'''
    marker = '        location = /static/loader.js {'
    assert baseline.count(marker) == 1
    candidate = baseline.replace('/opt/dd-main-study/chat-20261107/', '/opt/dd-main-study/samples-20261107/').replace(marker, extra + marker)
    assert candidate.replace(extra, '').replace('/opt/dd-main-study/samples-20261107/', '/opt/dd-main-study/chat-20261107/') == baseline
    (OUT / 'nginx.before.conf').write_text(baseline)
    (OUT / 'nginx.candidate.conf').write_text(candidate)
    (OUT / 'manifest.json').write_text(json.dumps({'status': 'prepared_not_deployed',
        'active_config_sha256': hashlib.sha256(baseline.encode()).hexdigest(),
        'candidate_config_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
        'scope': 'three static alias substitutions plus one local renderer route',
        'snapshot': str(snapshot.relative_to(ROOT)), 'files': hashes,
        'compose_changed': False, 'tool_registration': False, 'container_actions': False}, indent=2) + '\n')
    print('Prepared isolated candidate; active config and deployment untouched.')


if __name__ == '__main__':
    main()
