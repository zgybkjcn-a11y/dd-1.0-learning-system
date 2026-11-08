"""Static packet boundaries with synthetic assets; no deployment/private data."""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import prepare_main_study_samples as prep
from scripts import probe_main_study_samples_nginx as nginx


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    baseline = (Path(__file__).parent / 'fixtures/static_samples_nginx.conf').read_bytes()
    active = tmp_path / 'active.conf'; active.write_bytes(baseline)
    old = tmp_path / prep.PREVIOUS; old.mkdir()
    previous = {n: ('previous ' + n + '\n').encode() for n in prep.PREVIOUS_HASHES}
    source = {n: ('candidate ' + n + '\n').encode() for n in prep.SOURCE_HASHES}
    for name, data in previous.items():
        (old / name).write_bytes(data)
    monkeypatch.setattr(prep, 'PREVIOUS_HASHES', {n: prep.sha(b) for n, b in previous.items()})
    monkeypatch.setattr(prep, 'SOURCE_HASHES', {n: prep.sha(b) for n, b in source.items()})
    monkeypatch.setattr(prep, 'committed_assets', lambda: source)
    return SimpleNamespace(active=active, old=old, source=source, previous=previous,
                           output=tmp_path / 'packet', snapshot='samples-test', baseline=baseline)


def prepare(i):
    return prep.prepare(i.output, i.snapshot, i.active, i.old)


def test_packet_can_move_and_recover_exact_previous_bytes(inputs, tmp_path):
    i = inputs
    digest = prepare(i)
    moved = tmp_path / 'moved'; i.output.rename(moved)
    manifest = prep.verify(moved, digest, i.active, i.old)
    assert manifest['source_commit'] == prep.SOURCE_COMMIT
    assert (moved / 'rollback/nginx.conf').read_bytes() == i.baseline
    for name, data in i.previous.items():
        assert (moved / 'rollback' / prep.PREVIOUS / name).read_bytes() == data
    # Apply both real patches to an unrelated local target, verifying the round trip.
    patch_dir = tmp_path / 'replay'; patch_dir.mkdir()
    target = patch_dir / 'nginx.conf'; target.write_bytes(i.baseline)
    for patch in ['nginx.forward.patch', 'nginx.reverse.patch']:
        subprocess.run(['patch', '--batch', '-p0', '-i', str(moved / patch)], cwd=patch_dir,
                       check=True, capture_output=True)
        expected = 'nginx.candidate.conf' if 'forward' in patch else 'nginx.before.conf'
        assert target.read_bytes() == (moved / expected).read_bytes()
    assert i.active.read_bytes() == i.baseline
    assert {n: (i.old / n).read_bytes() for n in i.previous} == i.previous


def test_existing_output_is_never_overwritten(inputs):
    digest = prepare(inputs)
    with pytest.raises(ValueError, match='already exists'):
        prepare(inputs)
    prep.verify(inputs.output, digest)


@pytest.mark.parametrize('snapshot', ['../outside', 'samples-../x', '/tmp/foo', 'chat-20261107', 'samples-x;reload', 'samples-'])
def test_invalid_snapshot_fails_without_output(inputs, snapshot):
    inputs.snapshot = snapshot
    with pytest.raises(ValueError):
        prepare(inputs)
    assert not inputs.output.exists()


def test_existing_deployment_namespace_is_not_reused(inputs):
    (inputs.old.parent / inputs.snapshot).mkdir()
    with pytest.raises(ValueError, match='already exists in deployment'):
        prepare(inputs)
    assert not inputs.output.exists()


@pytest.mark.parametrize('change', ['alias', 'unrelated_config', 'previous_asset', 'missing_asset'])
def test_changed_baseline_never_produces_packet(inputs, change):
    i = inputs
    if change == 'alias':
        i.active.write_bytes(i.baseline.replace(b'chat-20261107', b'chat-20261108'))
    elif change == 'unrelated_config':
        i.active.write_bytes(i.baseline.replace(b'open-webui:8080', b'other:8080'))
    elif change == 'previous_asset':
        (i.old / 'study.js').write_text('changed')
    else:
        (i.old / 'study.css').unlink()
    with pytest.raises(ValueError):
        prepare(i)
    assert not i.output.exists()


def test_input_changed_during_extraction_is_rejected(inputs, monkeypatch):
    def extract():
        inputs.active.write_bytes(inputs.baseline + b'\n')
        return inputs.source
    monkeypatch.setattr(prep, 'committed_assets', extract)
    with pytest.raises(ValueError):
        prepare(inputs)
    assert not inputs.output.exists()


@pytest.mark.parametrize('member', ['nginx.candidate.conf', 'rollback/nginx.conf',
                                    'rollback/chat-20261107/study.js', 'samples-test/study.js',
                                    'samples-test/vendor/THIRD-PARTY-LICENSES.txt', 'nginx.reverse.patch'])
def test_tamper_rejected_before_docker(inputs, member, monkeypatch):
    digest = prepare(inputs)
    (inputs.output / member).write_text('tampered')
    def forbidden(*args, **kwargs):
        pytest.fail('Docker/openssl must not run for a tampered packet')
    monkeypatch.setattr(nginx.subprocess, 'run', forbidden)
    out = inputs.output.parent / 'probe'
    with pytest.raises(ValueError):
        nginx.probe(inputs.output, digest, out)
    assert not out.exists()


def test_reviewed_manifest_hash_is_required(inputs):
    digest = prepare(inputs)
    file = inputs.output / 'manifest.json'
    file.write_text(file.read_text() + '\n')
    with pytest.raises(ValueError, match='Manifest hash'):
        prep.verify(inputs.output, digest)


def test_manifest_cannot_choose_arbitrary_mount_path(inputs):
    prepare(inputs)
    file = inputs.output / 'manifest.json'; m = json.loads(file.read_text())
    m['snapshot'] = '../outside'; file.write_text(json.dumps(m))
    with pytest.raises(ValueError, match='basename'):
        prep.verify(inputs.output, prep.sha(file.read_bytes()))


@pytest.mark.parametrize('where', ['output_parent', 'active', 'previous_asset', 'packet_member'])
def test_symlinks_rejected(inputs, where, tmp_path):
    i = inputs
    digest = prepare(i) if where == 'packet_member' else None
    if where == 'output_parent':
        link = tmp_path / 'link'; link.symlink_to(tmp_path, target_is_directory=True)
        i.output = link / 'packet'
    else:
        file = {'active': i.active, 'previous_asset': i.old / 'study.js',
                'packet_member': i.output / i.snapshot / 'study.js'}[where]
        saved = tmp_path / 'saved'; file.rename(saved); file.symlink_to(saved)
    with pytest.raises(ValueError, match='Symlink'):
        prep.verify(i.output, digest) if digest else prepare(i)


def test_unlisted_file_rejected(inputs):
    digest = prepare(inputs)
    (inputs.output / 'injected.js').write_text('extra')
    with pytest.raises(ValueError, match='Unexpected'):
        prep.verify(inputs.output, digest)


def test_preflight_catches_change_since_preparation(inputs):
    digest = prepare(inputs)
    inputs.active.write_bytes(inputs.baseline + b'\n')
    with pytest.raises(ValueError):
        prep.verify(inputs.output, digest, inputs.active, inputs.old)


def test_failed_nginx_syntax_cleans_up_and_records_failure(inputs, monkeypatch):
    digest = prepare(inputs)
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        if args[0] == 'openssl':
            Path(args[args.index('-out') + 1]).write_text('synthetic cert')
            Path(args[args.index('-keyout') + 1]).write_text('synthetic key')
        if args[:2] == ['docker', 'exec']:
            raise subprocess.CalledProcessError(1, args, stderr=b'syntax failed')
        return SimpleNamespace(stdout=b'container', stderr=b'', returncode=0)
    monkeypatch.setattr(nginx.subprocess, 'run', fake_run)
    output = inputs.output.parent / 'probe'
    with pytest.raises(subprocess.CalledProcessError):
        nginx.probe(inputs.output, digest, output)
    report = json.loads((output / 'nginx-isolated.json').read_text())
    assert report['status'] == 'failed' and report['modes'] == []
    assert any(args[:3] == ['docker', 'rm', '-f'] for args in calls)
    assert not any('curl' in args for args in calls)
    assert not list(output.glob('synthetic-tls-*'))


def test_probe_does_not_overwrite_old_evidence(inputs):
    digest = prepare(inputs)
    out = inputs.output.parent / 'probe'; out.mkdir()
    receipt = out / 'nginx-isolated.json'; receipt.write_text('previous evidence')
    with pytest.raises(ValueError, match='already exists'):
        nginx.probe(inputs.output, digest, out)
    assert receipt.read_text() == 'previous evidence'
