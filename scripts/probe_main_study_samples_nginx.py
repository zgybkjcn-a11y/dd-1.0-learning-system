"""Probe a verified packet and its rollback in disposable, disconnected nginx.

No host ports, production mounts, real certificates, reloads or deployment.
The output directory must not exist; failed probes never emit a passed report.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

try:
    from .prepare_main_study_samples import (MERMAID_FILE, MERMAID_ROUTE, PREVIOUS,
                                            ROUTES, plain_path, read_file, require, sha, verify)
except ImportError:
    from prepare_main_study_samples import (MERMAID_FILE, MERMAID_ROUTE, PREVIOUS,
                                           ROUTES, plain_path, read_file, require, sha, verify)

IMAGE = 'nginx@sha256:1d13701a5f9f3fb01aaa88cef2344d65b6b5bf6b7d9fa4cf0dca557a8d7702ba'


def run(args, timeout=40):
    return subprocess.run(args, check=True, capture_output=True, timeout=timeout)


def probe_mode(packet, manifest, mode, cert, key):
    name = 'dd-study-samples-probe-' + uuid.uuid4().hex[:10]
    snapshot = manifest['snapshot'] if mode == 'candidate' else PREVIOUS
    config = packet / ('nginx.candidate.conf' if mode == 'candidate' else 'rollback/nginx.conf')
    assets = packet / snapshot if mode == 'candidate' else packet / 'rollback' / PREVIOUS
    mounts = [(config, '/candidate.conf'), (assets, f'/opt/dd-main-study/{snapshot}'),
              (cert, '/run/secrets/tls_certificate'), (key, '/run/secrets/tls_private_key')]
    args = ['docker', 'run', '--pull', 'never', '--rm', '-d', '--name', name,
            '--network', 'none', '--read-only', '--tmpfs', '/tmp',
            '--security-opt', 'no-new-privileges', '--pids-limit', '64', '--entrypoint', 'nginx']
    for source, target in mounts:
        source = plain_path(source)
        require(source.exists() and ',' not in str(source), 'Invalid or missing bind source')
        args += ['--mount', f'type=bind,source={source},target={target},readonly']
    report = {'mode': mode, 'config_sha256': sha(read_file(config)), 'assets': []}
    try:
        run(args + [IMAGE, '-c', '/candidate.conf', '-g', 'daemon off;'])
        report['syntax_check'] = run(['docker', 'exec', name, 'nginx', '-t', '-c', '/candidate.conf']).stderr.decode()
        routes = dict(ROUTES)
        if mode == 'candidate':
            routes[MERMAID_ROUTE] = MERMAID_FILE
        for path, file in routes.items():
            response = run(['docker', 'exec', name, 'curl', '-kfsS', '--max-time', '10',
                            '--noproxy', '*', '-D', '-', 'https://127.0.0.1' + path], timeout=20)
            headers, body = response.stdout.split(b'\r\n\r\n', 1)
            require(body == read_file(assets / file), f'Wrong static response: {path}')
            headers = headers.decode().lower()
            mime = 'text/css' if path.endswith('.css') else 'application/javascript'
            require('200 ok' in headers and 'cache-control: no-store' in headers and
                    f'content-type: {mime}' in headers, f'Wrong response headers: {path}')
            report['assets'].append({'path': path, 'sha256': sha(body), 'content_type': mime,
                                     'status': 200, 'cache_control': 'no-store'})
    finally:
        # Remove only the unique temporary container, including after a failed syntax check.
        removed = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30)
        require(removed.returncode == 0 or b'No such container' in removed.stderr,
                f'Temporary container cleanup failed: {name}')
    report['container_removed'] = True
    return report


def probe(packet, expected_manifest_sha256, output):
    packet, output = plain_path(packet), plain_path(output)
    manifest = verify(packet, expected_manifest_sha256)
    require(not output.exists(), 'Probe output already exists')
    require(output.parent.is_dir(), 'Create the probe output parent first')
    require(not output.is_relative_to(packet), 'Probe output must be outside the immutable packet')
    output.mkdir()
    report = {'status': 'running', 'image': IMAGE, 'network': 'none', 'production_mounts': False,
              'host_ports': False, 'manifest_sha256': expected_manifest_sha256,
              'started_at': datetime.now(timezone.utc).isoformat(), 'modes': []}
    try:
        with tempfile.TemporaryDirectory(prefix='synthetic-tls-', dir=output) as directory:
            cert, key = Path(directory) / 'cert.pem', Path(directory) / 'key.pem'
            run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                 '-subj', '/CN=study-sample.invalid', '-keyout', str(key), '-out', str(cert)])
            for mode in ('candidate', 'rollback'):
                report['modes'].append(probe_mode(packet, manifest, mode, cert, key))
        verify(packet, expected_manifest_sha256)
        report['status'] = 'passed'
    except BaseException as exc:
        report['status'] = 'failed'
        report['error_type'] = type(exc).__name__
        if isinstance(exc, subprocess.CalledProcessError):
            report['stderr'] = (exc.stderr or b'').decode(errors='replace')[-4000:]
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        (output / 'nginx-isolated.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    probe(args.packet, args.expected_manifest_sha256, args.output)
    print('Disconnected nginx: candidate (4 routes) and rollback (3 routes) passed; containers removed.')


if __name__ == '__main__':
    main()
