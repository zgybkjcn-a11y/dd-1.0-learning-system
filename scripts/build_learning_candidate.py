#!/usr/bin/env python3
"""Build only a sealed named source set; retain separate immutable build evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

from prepare_learning_release import ROOT, REUSE_PROFILE, verify


def build(candidate: Path, output: Path, tag: str, wheels: Path, base_archive: Path) -> dict:
    manifest = verify(candidate)
    if manifest.get("source_profile") != REUSE_PROFILE:
        raise ValueError("a new runtime profile is required; do not build a historical candidate")
    if not re.fullmatch(r"dd-learning:reuse-[a-z0-9-]{1,80}", tag):
        raise ValueError("dedicated new image tag required")
    output = output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise ValueError("new project-local build directory required")
    env = {"PATH":os.environ.get("PATH", "")}
    if subprocess.run(["docker", "image", "inspect", tag], env=env, capture_output=True).returncode == 0:
        raise ValueError("existing image tags are preserved")
    output.mkdir(parents=True, mode=0o700)
    context=output/'context'; context.mkdir()
    with tarfile.open(candidate/'source.tar.gz') as source:
        for member in source:
            # verify() already rejects other types and any non-whitelist member.
            target=context/member.name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.extractfile(member).read())
    locked=set(re.findall(r'--hash=sha256:([a-f0-9]{64})', (context/'deploy/open-webui-reuse/requirements.lock').read_text()))
    dependencies={}
    wheel_target=context/'dependency-wheels';wheel_target.mkdir()
    for file in wheels.iterdir():
        if file.is_symlink() or not file.is_file() or not file.name.endswith('.whl'):
            raise ValueError('only regular locked wheels are allowed')
        content=file.read_bytes();digest=hashlib.sha256(content).hexdigest()
        if digest not in locked:raise ValueError('dependency checksum is outside the lock')
        dependencies[file.name]=digest;(wheel_target/file.name).write_bytes(content)
    if set(dependencies.values())!=locked:raise ValueError('locked dependency wheels are missing')
    # Docker's OCI export fixes the recorded multiarch base digest locally and
    # avoids a fresh registry resolver request. Every exported blob is checked.
    base=output/'base-oci';base.mkdir()
    with tarfile.open(base_archive) as archive:
        index=json.loads(archive.extractfile('index.json').read())
        if {m['digest'] for m in index['manifests']} != {'sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30'}:
            raise ValueError('unexpected base OCI digest')
        for member in archive:
            if not member.isfile():continue
            if member.name in {'index.json','oci-layout'} or re.fullmatch(r'blobs/sha256/[a-f0-9]{64}',member.name):
                data=archive.extractfile(member).read()
                if member.name.startswith('blobs/') and hashlib.sha256(data).hexdigest()!=member.name.rsplit('/',1)[1]:
                    raise ValueError('base blob checksum mismatch')
                target=base/member.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    with (output/'build.log').open('w') as log:
        p=subprocess.run(['docker','buildx','build','--load','--no-cache','--progress=plain','--network=none',
                          '--build-context','dd-runtime-base=oci-layout://'+str(base),
                          '--build-arg','RUNTIME_BASE=dd-runtime-base',
                          '--iidfile',str(output/'image.id'),'-t',tag,'-f','deploy/open-webui-reuse/Dockerfile',str(context)],
                         env=env,cwd=context,stdout=log,stderr=subprocess.STDOUT)
    if p.returncode:
        raise ValueError('no-cache candidate build failed; bounded evidence retained in build.log')
    image=(output/'image.id').read_text().strip()
    result={'source_set_sha256':manifest['source_set_sha256'],'archive_sha256':manifest['archive_sha256'],
            'image_id':image,'image_tag':tag,'registry_image_digest':None,'no_cache':True,
            'dependency_hashes_required':True,'base_image':'python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30',
            'source_files':len(manifest['source_sha256']),'published':False,'deployed_to_production':False}
    result['dependency_wheel_sha256']=dependencies
    result['build_network']='none'
    result['base_archive_sha256']=hashlib.sha256(base_archive.read_bytes()).hexdigest()
    result['base_source']='local_OCI_export_checked_against_recorded_registry_digest'
    (output/'build.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--tag',required=True)
    p.add_argument('--wheels',type=Path,required=True)
    p.add_argument('--base-archive',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.candidate,a.output,a.tag,a.wheels,a.base_archive)))
