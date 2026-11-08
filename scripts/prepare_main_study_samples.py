"""Prepare/verify the pinned static samples; never deploy or overwrite a packet.

The historical UI evidence belongs to SOURCE_COMMIT, including its old bridge.
Use explicit inputs and a new samples-* namespace. A07's working tree is not read.
"""
import argparse
import base64
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = 'deef3199f558ba72bbe3f2ff0c704586674a2232'
SOURCE_PATH = 'deploy/open-webui-reuse/main-study'
PREVIOUS = 'chat-20261107'
BASE_CONFIG_SHA256 = 'fcb3e8131090dbc5f89ad2b07186b0d17b897658a1c8cf9e18562bd3b7d0676a'
SOURCE_HASHES = {
    'study.js': 'fe26d4d4ae6834944fd093d9954808b118b7706daeb1aa42df459090cf75518d',
    'study.css': '952fddccb9e5366d350b0bd9bebf88fe76ebeea6861bed9b6d9fa7e697af292a',
    'family-bridge.js': '8bfe564373befe4d3bb64cfc4d91b67880545217f00d293da415938cce4f0347',
    'SOURCES.md': '821e16cbb26f44b01675dd6e8211c1f77c0380b43771734df3bc9d1b2cf2ca7f',
    'vendor/THIRD-PARTY-LICENSES.txt': '6dff51accc52d7ed3798a27626a2b0d7c3a7bca7766bb61240b11eda3894858b',
    'vendor/manifest.json': '687970b592578c81d984ab0502a1250c6c2f057740d1b347c74244221b2ef20b',
    'vendor/mermaid-11.12.1-LICENSE.txt': 'ec9fb67dcb25eccc416ed56e1aab819222c805a2a4bfe4cb19e7556bf2ffde80',
    'vendor/mermaid-11.12.1-NOTICES.txt': '5dda3fe2b170fbca6f2514f493daec2d624f7061d1c1276f9c9fbed6503d7828',
    'vendor/mermaid-11.12.1.min.js': '198b19442f86f0b46a17e56d3abf744c3a28a3427e66fa8dada3b589a77babcc',
}
PREVIOUS_HASHES = {
    'study.js': '6e2325ad44c246351e00f4f8bc480dbcdcef4912f90085696793b208524db7e4',
    'study.css': 'b7ea956e897b0bf12a26f55e0213b794a924ff8c10e02647e83de8027514627a',
    'family-bridge.js': SOURCE_HASHES['family-bridge.js'],
    'SOURCES.md': '9457b5d5ea7beba03c9d91f86cae3beaf606c18f704c328f117bf412366563d3',
}
ROUTES = {'/static/loader.js': 'study.js', '/static/custom.css': 'study.css',
          '/static/dd-family-bridge.js': 'family-bridge.js'}
MERMAID_ROUTE = '/static/dd-study-mermaid.min.js'
MERMAID_FILE = 'vendor/mermaid-11.12.1.min.js'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plain_path(path):
    path = Path(path).absolute()
    require('..' not in path.parts, 'Parent traversal is not allowed')
    require(not any(p.is_symlink() for p in (path, *path.parents)), f'Symlink not allowed: {path}')
    return path


def read_file(path):
    path = plain_path(path)
    require(path.is_file(), f'Missing regular file: {path}')
    return path.read_bytes()


def validate_snapshot(snapshot):
    require(isinstance(snapshot, str) and re.fullmatch(r'samples-[a-zA-Z0-9][a-zA-Z0-9_-]{0,70}', snapshot),
            'Snapshot must be a new samples-* basename')


def transform(baseline, snapshot):
    validate_snapshot(snapshot)
    require(sha(baseline) == BASE_CONFIG_SHA256, 'Active config differs from reviewed baseline')
    text = baseline.decode('utf-8')
    old = f'/opt/dd-main-study/{PREVIOUS}/'
    new = f'/opt/dd-main-study/{snapshot}/'
    require(text.count(old) == 3 and MERMAID_ROUTE not in text, 'Unexpected static alias baseline')
    for route, file in ROUTES.items():
        pattern = rf'location = {re.escape(route)} \{{\s+alias {re.escape(old + file)};'
        require(len(re.findall(pattern, text)) == 1, 'Static route/alias mismatch')
    extra = f'''        location = {MERMAID_ROUTE} {{
            alias {new}{MERMAID_FILE};
            default_type application/javascript;
            add_header Cache-Control "no-store" always;
            add_header X-Content-Type-Options nosniff always;
        }}
'''
    marker = '        location = /static/loader.js {'
    require(text.count(marker) == 1, 'Missing unique loader route')
    candidate = text.replace(old, new).replace(marker, extra + marker)
    require(candidate.replace(extra, '').replace(new, old) == text, 'Non-static config change')
    return candidate.encode()


def previous_inputs(active_config, previous_assets):
    baseline = read_file(active_config)
    require(sha(baseline) == BASE_CONFIG_SHA256, 'Active config differs from reviewed baseline')
    previous_assets = plain_path(previous_assets)
    require(previous_assets.name == PREVIOUS, 'Previous assets must be the recorded alias directory')
    files = {name: read_file(previous_assets / name) for name in PREVIOUS_HASHES}
    require({n: sha(b) for n, b in files.items()} == PREVIOUS_HASHES, 'Previous assets changed')
    return baseline, files


def committed_assets():
    files = {}
    for name, digest in SOURCE_HASHES.items():
        data = subprocess.run(['git', 'show', f'{SOURCE_COMMIT}:{SOURCE_PATH}/{name}'],
                              cwd=ROOT, check=True, capture_output=True, timeout=30).stdout
        require(sha(data) == digest, f'Committed source mismatch: {name}')
        files[name] = data
    vendor = json.loads(files['vendor/manifest.json'])
    require(vendor['bundle_sha256'] == sha(files[MERMAID_FILE]), 'Vendor bundle mismatch')
    sri = 'sha384-' + base64.b64encode(hashlib.sha384(files[MERMAID_FILE]).digest()).decode()
    require(vendor['bundle_sri'] == sri and sri.encode() in files['study.js'], 'Vendor SRI mismatch')
    return files


def diff(before, after, left, right):
    return ''.join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
                                        fromfile=left, tofile=right)).encode()


def packet_files(baseline, previous, source, snapshot):
    candidate = transform(baseline, snapshot)
    files = {'nginx.before.conf': baseline, 'nginx.candidate.conf': candidate,
             'rollback/nginx.conf': baseline,
             'nginx.forward.patch': diff(baseline, candidate, 'nginx.conf', 'nginx.conf'),
             'nginx.reverse.patch': diff(candidate, baseline, 'nginx.conf', 'nginx.conf')}
    files.update({f'{snapshot}/{n}': b for n, b in source.items()})
    files.update({f'rollback/{PREVIOUS}/{n}': b for n, b in previous.items()})
    files['static-changes.patch'] = b''.join(diff(previous[n], source[n], f'{PREVIOUS}/{n}', f'{snapshot}/{n}')
                                            for n in PREVIOUS_HASHES)
    return files


def prepare(output, snapshot, active_config, previous_assets):
    output = plain_path(output)
    require(not output.exists(), 'Output already exists; choose a new independent directory')
    require(output.parent.is_dir(), 'Create the output parent first')
    baseline, previous = previous_inputs(active_config, previous_assets)
    validate_snapshot(snapshot)
    require(not (Path(previous_assets).parent / snapshot).exists(), 'Snapshot already exists in deployment assets')
    files = packet_files(baseline, previous, committed_assets(), snapshot)
    manifest = {
        'schema': 'dd-static-samples-packet-v2', 'status': 'prepared_not_deployed',
        'source_commit': SOURCE_COMMIT, 'snapshot': snapshot, 'previous_snapshot': PREVIOUS,
        'active_config_sha256': BASE_CONFIG_SHA256,
        'candidate_config_sha256': sha(files['nginx.candidate.conf']),
        'files': {name: sha(data) for name, data in sorted(files.items())},
        'scope': 'three static aliases plus local Mermaid route; rollback restores this baseline',
        'compose_changed': False, 'tool_registration': False, 'container_actions': False,
    }
    # Construct off to the side. Exclusive mkdir also rejects a concurrent creator.
    with tempfile.TemporaryDirectory(prefix='.static-prepare-', dir=output.parent) as temp:
        staging = Path(temp)
        for name, data in files.items():
            dest = staging / name; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        verify(staging, sha((staging / 'manifest.json').read_bytes()))
        # Recheck input consistency after extraction before publishing the local packet.
        require(previous_inputs(active_config, previous_assets) == (baseline, previous), 'Baseline changed during preparation')
        output.mkdir()
        try:
            shutil.copytree(staging, output, dirs_exist_ok=True)
        except BaseException:
            shutil.rmtree(output)
            raise
    return sha(read_file(output / 'manifest.json'))


def verify(packet, expected_manifest_sha256, active_config=None, previous_assets=None):
    packet = plain_path(packet)
    raw = read_file(packet / 'manifest.json')
    require(sha(raw) == expected_manifest_sha256, 'Manifest hash differs from reviewed packet')
    manifest = json.loads(raw)
    require(manifest['schema'] == 'dd-static-samples-packet-v2' and
            manifest['source_commit'] == SOURCE_COMMIT and manifest['previous_snapshot'] == PREVIOUS,
            'Unsupported packet provenance')
    snapshot = manifest['snapshot']; validate_snapshot(snapshot)
    baseline = read_file(packet / 'nginx.before.conf')
    previous = {n: read_file(packet / 'rollback' / PREVIOUS / n) for n in PREVIOUS_HASHES}
    source = {n: read_file(packet / snapshot / n) for n in SOURCE_HASHES}
    require({n: sha(b) for n, b in previous.items()} == PREVIOUS_HASHES, 'Rollback assets mismatch')
    require({n: sha(b) for n, b in source.items()} == SOURCE_HASHES, 'Static source mismatch')
    expected = packet_files(baseline, previous, source, snapshot)
    require(manifest['files'] == {n: sha(b) for n, b in expected.items()}, 'Packet inventory/hash mismatch')
    require(manifest['active_config_sha256'] == BASE_CONFIG_SHA256 and
            manifest['candidate_config_sha256'] == sha(expected['nginx.candidate.conf']), 'Config pin mismatch')
    actual = set()
    for file in packet.rglob('*'):
        plain_path(file)
        if file.is_dir():
            continue
        require(file.is_file(), 'Non-regular packet member')
        actual.add(file.relative_to(packet).as_posix())
    require(actual == set(expected) | {'manifest.json'}, 'Unexpected or missing packet member')
    for name, data in expected.items():
        require(read_file(packet / name) == data, f'Packet content mismatch: {name}')
    require((active_config is None) == (previous_assets is None), 'Both baseline paths are required')
    if active_config is not None:
        require(previous_inputs(active_config, previous_assets) == (baseline, previous), 'Current baseline changed')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--snapshot', required=True)
    p.add_argument('--active-config', type=Path, required=True)
    p.add_argument('--previous-assets', type=Path, required=True)
    v = commands.add_parser('verify')
    v.add_argument('--packet', type=Path, required=True)
    v.add_argument('--expected-manifest-sha256', required=True)
    v.add_argument('--active-config', type=Path)
    v.add_argument('--previous-assets', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            digest = prepare(args.output, args.snapshot, args.active_config, args.previous_assets)
            print(json.dumps({'status': 'prepared_not_deployed', 'manifest_sha256': digest}))
        else:
            verify(args.packet, args.expected_manifest_sha256, args.active_config, args.previous_assets)
            print('Packet verified; no deployment performed.')
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'Preparation/verification stopped: {exc}\n')


if __name__ == '__main__':
    main()
