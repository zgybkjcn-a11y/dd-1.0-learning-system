"""Validate prepared static routes in a disposable, network-disabled nginx.

Uses a generated temporary test certificate, never deployment secrets/data.
No host ports, production networks, volumes, reloads or container mutations.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'learning_data/verification/main-study-samples-20261107/candidate'
IMAGE = 'nginx@sha256:1d13701a5f9f3fb01aaa88cef2344d65b6b5bf6b7d9fa4cf0dca557a8d7702ba'


def run(args):
    return subprocess.run(args, check=True, capture_output=True).stdout


def main():
    report = {'network': 'none', 'production_mounts': False, 'host_ports': False, 'assets': []}
    with tempfile.TemporaryDirectory(prefix='synthetic-tls-', dir=OUT) as directory:
        cert, key = Path(directory) / 'cert.pem', Path(directory) / 'key.pem'
        run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
             '-subj', '/CN=study-sample.invalid', '-keyout', str(key), '-out', str(cert)])
        name = 'dd-study-samples-probe-' + uuid.uuid4().hex[:10]
        mounts = [('nginx.candidate.conf', '/candidate.conf'), ('samples-20261107', '/opt/dd-main-study/samples-20261107')]
        args = ['docker', 'run', '--rm', '-d', '--name', name, '--network', 'none', '--read-only',
                '--tmpfs', '/tmp', '--security-opt', 'no-new-privileges', '--pids-limit', '64', '--entrypoint', 'nginx']
        for source, target in mounts:
            args += ['--mount', f'type=bind,source={OUT / source},target={target},readonly']
        for source, target in [(cert, '/run/secrets/tls_certificate'), (key, '/run/secrets/tls_private_key')]:
            args += ['--mount', f'type=bind,source={source},target={target},readonly']
        try:
            run(args + [IMAGE, '-c', '/candidate.conf', '-g', 'daemon off;'])
            check = subprocess.run(['docker', 'exec', name, 'nginx', '-t', '-c', '/candidate.conf'], check=True, capture_output=True)
            report['syntax_check'] = check.stderr.decode()
            for path, file in [('/static/loader.js', 'study.js'), ('/static/custom.css', 'study.css'),
                               ('/static/dd-family-bridge.js', 'family-bridge.js'),
                               ('/static/dd-study-mermaid.min.js', 'vendor/mermaid-11.12.1.min.js')]:
                # curl runs inside the disconnected namespace, only loopback.
                response = subprocess.run(['docker', 'exec', name, 'curl', '-kfsS', '--max-time', '10',
                    '--noproxy', '*', '-D', '-', 'https://127.0.0.1' + path], check=True, capture_output=True, timeout=20)
                header_bytes, body = response.stdout.split(b'\r\n\r\n', 1)
                expected = (OUT / 'samples-20261107' / file).read_bytes()
                assert body == expected
                headers = header_bytes.decode()
                assert '200 OK' in headers and 'no-store' in headers
                mime = 'text/css' if path.endswith('.css') else 'application/javascript'
                assert mime in headers
                report['assets'].append({'path': path, 'sha256': hashlib.sha256(body).hexdigest(), 'content_type': mime, 'status': 200, 'cache_control': 'no-store'})
        finally:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    (OUT / 'nginx-isolated.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Disconnected nginx: syntax and all four static routes passed; temporary container removed.')


if __name__ == '__main__':
    main()
