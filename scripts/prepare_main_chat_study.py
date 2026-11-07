"""Release the chat study static revision; keep current family Compose and routes."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from prepare_main_study_bridge import ROOT, BASE, ASSETS, PROXY, digest, container_state

OUT = ROOT / 'learning_data/verification/main-chat-study-20261107/deployment'
REVISION = 'chat-20261107'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true'); args = parser.parse_args()
    config = json.loads(BASE.read_text())
    live = Path(config['configs']['learning_proxy']['file'])
    mounted = next(Path(v['source']) for v in config['services']['learning-proxy']['volumes'] if v['target'] == '/opt/dd-main-study')
    release = mounted / REVISION
    if not args.apply:
        assert not OUT.exists() and not release.exists(), 'Keep earlier release evidence'
        before = live.read_text()
        # Only the three established static aliases move. All auth/API/HTML
        # routing stays byte-for-byte identical, with an explicit diff proof.
        pattern = r'/opt/dd-main-study/knowledge-20261107/(study\.js|study\.css|family-bridge\.js)'
        candidate, count = re.subn(pattern, lambda m: '/opt/dd-main-study/' + REVISION + '/' + m[1], before)
        assert count == 3 and candidate.replace('/' + REVISION + '/', '/knowledge-20261107/') == before
        OUT.mkdir(parents=True); shutil.copytree(ASSETS, release)
        (OUT / 'nginx.before.conf').write_text(before); (OUT / 'nginx.candidate.conf').write_text(candidate)
        (OUT / 'prepared.json').write_text(json.dumps({'compose': str(BASE.relative_to(ROOT)),
            'live_config': str(live.relative_to(ROOT)), 'base_sha256': digest(live),
            'candidate_sha256': digest(OUT / 'nginx.candidate.conf'), 'containers_before': container_state(),
            'static_files': {p.name: digest(p) for p in release.iterdir()}, 'only_three_static_aliases_changed': True,
            'applied': False}, indent=2) + '\n')
        subprocess.run(['docker', 'exec', '-i', PROXY, 'sh', '-c', 'cat > /tmp/dd-chat-candidate.conf'], input=candidate.encode(), check=True)
        subprocess.run(['docker', 'exec', PROXY, 'nginx', '-t', '-c', '/tmp/dd-chat-candidate.conf'], check=True)
        print('Chat study candidate ready; current deployment still serving the previous revision.')
        return
    evidence = json.loads((OUT / 'prepared.json').read_text())
    assert digest(live) == evidence['base_sha256'] and container_state() == evidence['containers_before']
    assert digest(OUT / 'nginx.candidate.conf') == evidence['candidate_sha256']
    assert {p.name: digest(p) for p in release.iterdir()} == evidence['static_files']
    try:
        live.write_bytes((OUT / 'nginx.candidate.conf').read_bytes())
        subprocess.run(['docker', 'exec', PROXY, 'nginx', '-t', '-c', '/etc/nginx/dd-learning.conf'], check=True)
        subprocess.run(['docker', 'exec', PROXY, 'nginx', '-s', 'reload', '-c', '/etc/nginx/dd-learning.conf'], check=True)
    except Exception:
        live.write_bytes((OUT / 'nginx.before.conf').read_bytes())
        subprocess.run(['docker', 'exec', PROXY, 'nginx', '-s', 'reload', '-c', '/etc/nginx/dd-learning.conf'], check=True)
        raise
    evidence.update(applied=True, containers_after=container_state(), live_sha256=digest(live))
    assert evidence['containers_after'] == evidence['containers_before']
    (OUT / 'applied.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('Chat study published with proxy reload; no container restarted.')


if __name__ == '__main__': main()
