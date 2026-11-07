from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location("learning_release", Path(__file__).parents[1]/"scripts/prepare_learning_release.py")
release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release)


def _root(tmp_path):
    root = tmp_path/"source"
    root.mkdir()
    for name in release.PATHS:
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source fixture: " + name)
    # Disposable synthetic fixtures, never the actual protected project files.
    (root/"docker-compose.yml").write_text("DO-NOT-PACK-DEPLOYMENT")
    (root/"batch_ingest.py").write_text("DO-NOT-PACK-INGEST")
    (root/".env").write_text("DO-NOT-PACK-SECRET")
    return root


def test_release_is_reproducible_and_only_contains_named_sources(tmp_path):
    root = _root(tmp_path)
    a = release.prepare(root/"candidate-a", root)
    b = release.prepare(root/"candidate-b", root)
    assert a["archive_sha256"] == b["archive_sha256"] and a["source_set_sha256"] == b["source_set_sha256"]
    assert a["image_digest"] is None and a["state"] == "local_source_candidate_not_built_not_deployed"
    assert set(a["source_sha256"]) == set(release.PATHS) and release.verify(root/"candidate-a") == a
    assert all(name not in a["source_sha256"] for name in (".env", "docker-compose.yml", "batch_ingest.py"))


def test_release_refuses_overwrite_and_corrupted_archive(tmp_path):
    root = _root(tmp_path); destination = root/"candidate"
    release.prepare(destination, root)
    with pytest.raises(ValueError, match="existing files"):
        release.prepare(destination, root)
    path = destination/"source.tar.gz"; path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        release.verify(destination)


def test_release_refuses_source_symlink_and_outside_destination(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(ValueError):
        release.prepare(tmp_path/"outside", root)
    target = root/"learning_service/config.py"
    target.unlink(); target.symlink_to(root/".env")
    with pytest.raises(ValueError, match="symlink"):
        release.prepare(root/"candidate", root)


def test_old_schema9_profile_still_verifies_after_whitelist_expansion(tmp_path):
    root = _root(tmp_path)
    old = root/"legacy"
    manifest = release.prepare(old, root)
    payload = io.BytesIO()
    with tarfile.open(old/"source.tar.gz") as source, tarfile.open(fileobj=payload, mode="w:gz") as target:
        for member in source:
            if member.name in release.LEGACY_PATHS:
                target.addfile(member, source.extractfile(member))
    assert len(release.LEGACY_PATHS) == 29 and len(release.SCHEMA10_PATHS) == 35 and len(release.SCHEMA11_PATHS) == 38
    manifest["schema_revision"] = 9
    manifest.pop("source_profile", None)
    manifest["source_sha256"] = {k:v for k,v in manifest["source_sha256"].items() if k in release.LEGACY_PATHS}
    manifest["source_set_sha256"] = release.sha256(release._json(manifest["source_sha256"]))
    manifest["archive_sha256"] = release.sha256(payload.getvalue())
    (old/"source.tar.gz").write_bytes(payload.getvalue())
    (old/"manifest.json").write_text(json.dumps(manifest))
    assert release.verify(old)["schema_revision"] == 9


def test_old_schema10_profile_still_verifies_after_review_expansion(tmp_path):
    root = _root(tmp_path); old = root/'schema10'
    manifest = release.prepare(old, root)
    payload = io.BytesIO()
    with tarfile.open(old/'source.tar.gz') as source, tarfile.open(fileobj=payload, mode='w:gz') as target:
        for member in source:
            if member.name in release.SCHEMA10_PATHS:
                target.addfile(member, source.extractfile(member))
    manifest['schema_revision'] = 10
    manifest.pop('source_profile', None)
    manifest['source_sha256'] = {k:v for k,v in manifest['source_sha256'].items() if k in release.SCHEMA10_PATHS}
    manifest['source_set_sha256'] = release.sha256(release._json(manifest['source_sha256']))
    manifest['archive_sha256'] = release.sha256(payload.getvalue())
    (old/'source.tar.gz').write_bytes(payload.getvalue()); (old/'manifest.json').write_text(json.dumps(manifest))
    assert release.verify(old)['schema_revision'] == 10


def test_old_schema11_candidate_verifies_after_runtime_profile_expansion(tmp_path):
    root = _root(tmp_path); old = root/'schema11'
    manifest = release.prepare(old, root)
    payload = io.BytesIO()
    with tarfile.open(old/'source.tar.gz') as source, tarfile.open(fileobj=payload, mode='w:gz') as target:
        for member in source:
            if member.name in release.SCHEMA11_PATHS: target.addfile(member,source.extractfile(member))
    manifest.pop('source_profile')
    manifest['source_sha256']={k:v for k,v in manifest['source_sha256'].items() if k in release.SCHEMA11_PATHS}
    manifest['source_set_sha256']=release.sha256(release._json(manifest['source_sha256']))
    manifest['archive_sha256']=release.sha256(payload.getvalue())
    (old/'source.tar.gz').write_bytes(payload.getvalue());(old/'manifest.json').write_text(json.dumps(manifest))
    assert len(release.verify(old)['source_sha256'])==38


def test_previous_runtime_candidate_still_verifies_after_textbook_expansion(tmp_path):
    root = _root(tmp_path); old = root/'previous-runtime'
    manifest = release.prepare(old, root)
    payload = io.BytesIO()
    with tarfile.open(old/'source.tar.gz') as source, tarfile.open(fileobj=payload, mode='w:gz') as target:
        for member in source:
            if member.name in release.PRE_TEXTBOOK_PATHS:
                target.addfile(member, source.extractfile(member))
    manifest['source_profile'] = release.PRE_TEXTBOOK_PROFILE
    manifest['source_sha256'] = {k:v for k,v in manifest['source_sha256'].items() if k in release.PRE_TEXTBOOK_PATHS}
    manifest['source_set_sha256'] = release.sha256(release._json(manifest['source_sha256']))
    manifest['archive_sha256'] = release.sha256(payload.getvalue())
    (old/'source.tar.gz').write_bytes(payload.getvalue())
    (old/'manifest.json').write_text(json.dumps(manifest))
    assert len(release.verify(old)['source_sha256']) == 50


@pytest.mark.parametrize('profile,paths', [('textbook','TEXTBOOK_PATHS'),('practice','PRACTICE_PATHS'),
                                          ('math_reference','MATH_REFERENCE_PATHS')])
def test_prior_content_profiles_verify_after_reference_expansion(tmp_path, profile, paths):
    root = _root(tmp_path); old = root / ('previous-' + profile)
    manifest = release.prepare(old, root)
    names = getattr(release, paths)
    payload = io.BytesIO()
    with tarfile.open(old/'source.tar.gz') as source, tarfile.open(fileobj=payload, mode='w:gz') as target:
        for member in source:
            if member.name in names:
                target.addfile(member, source.extractfile(member))
    manifest['source_profile'] = getattr(release, profile.upper() + '_PROFILE')
    manifest['source_sha256'] = {k:v for k,v in manifest['source_sha256'].items() if k in names}
    manifest['source_set_sha256'] = release.sha256(release._json(manifest['source_sha256']))
    manifest['archive_sha256'] = release.sha256(payload.getvalue())
    (old/'source.tar.gz').write_bytes(payload.getvalue())
    (old/'manifest.json').write_text(json.dumps(manifest))
    assert set(release.verify(old)['source_sha256']) == set(names)
