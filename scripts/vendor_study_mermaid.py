"""Pin the browser renderer and preserve exact bundled dependencies' licenses.

Downloads only public npm packages. Never runs package scripts or uses npm install.
The source map identifies the versions actually included in the upstream bundle.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'learning_data/verification/main-study-samples-20261107'
VENDOR = ROOT / 'deploy/open-webui-reuse/main-study/vendor'
VERSION = '11.12.1'
INTEGRITY = 'sha512-UlIZrRariB11TY1RtTgUWp65tphtBv4CSq7vyS2ZZ2TgoMjs2nloq+wFqxiwcxlhHUvs7DPGgMjs2aeQxz5h9g=='


def fetch(url):
    with urlopen(url, timeout=30) as response:
        return response.read()


def verify(data, integrity):
    algorithm, value = integrity.split('-', 1)
    assert base64.b64encode(hashlib.new(algorithm, data).digest()).decode() == value


def dependency_license(package):
    name, version = package
    meta = json.loads(fetch('https://registry.npmjs.org/' + quote(name, safe='') + '/' + version))
    archive = fetch(meta['dist']['tarball']); verify(archive, meta['dist']['integrity'])
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        licenses = []
        for member in tar.getmembers():
            parts = member.name.split('/')
            if member.isfile() and len(parts) == 2 and re.match(r'^(licen[cs]e|copying|notice)(\.|$)', parts[-1], re.I):
                licenses.append((member.name, tar.extractfile(member).read().decode('utf-8', errors='replace')))
    if not licenses:
        raise ValueError(f'No license text in {name}@{version}')
    text = '\n\n'.join(path + '\n' + value for path, value in licenses)
    license_id = meta.get('license')
    if not license_id and 'The MIT License (MIT)' in text:
        license_id = 'MIT'
    if not license_id:
        raise ValueError(f'License needs review: {name}@{version}')
    return {'name': name, 'version': version, 'license': license_id, 'license_from_text': not bool(meta.get('license')),
            'tarball': meta['dist']['tarball'], 'integrity': meta['dist']['integrity'],
            'license_sha256': hashlib.sha256(text.encode()).hexdigest()}, text


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True); VENDOR.mkdir(parents=True, exist_ok=True)
    archive_path = EVIDENCE / f'mermaid-{VERSION}.tgz'
    archive = archive_path.read_bytes() if archive_path.exists() else fetch(f'https://registry.npmjs.org/mermaid/-/mermaid-{VERSION}.tgz')
    verify(archive, INTEGRITY); archive_path.write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        bundle = tar.extractfile('package/dist/mermaid.min.js').read()
        license_text = tar.extractfile('package/LICENSE').read()
        source_map = json.load(tar.extractfile('package/dist/mermaid.min.js.map'))
    packages = set()
    for source in source_map['sources']:
        found = re.search(r'/\.pnpm/([^/]+)/node_modules/', source)
        if found:
            identifier = found[1].split('_', 1)[0]
            name, version = identifier.rsplit('@', 1)
            packages.add((name.replace('+', '/'), version))
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(dependency_license, sorted(packages)))
    manifest = {'name': 'mermaid', 'version': VERSION, 'license': 'MIT',
        'source': f'https://registry.npmjs.org/mermaid/-/mermaid-{VERSION}.tgz', 'integrity': INTEGRITY,
        'bundle_sha256': hashlib.sha256(bundle).hexdigest(),
        'bundle_sri': 'sha384-' + base64.b64encode(hashlib.sha384(bundle).digest()).decode(),
        'dependencies': [entry for entry, _ in results]}
    (VENDOR / f'mermaid-{VERSION}.min.js').write_bytes(bundle)
    (VENDOR / f'mermaid-{VERSION}-LICENSE.txt').write_bytes(license_text)
    (VENDOR / 'THIRD-PARTY-LICENSES.txt').write_text('\n\n'.join(
        entry['name'] + '@' + entry['version'] + '\n' + text for entry, text in results))
    (VENDOR / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Pinned Mermaid {VERSION}, preserved licenses for {len(results)} bundled dependency versions.')


if __name__ == '__main__':
    main()
