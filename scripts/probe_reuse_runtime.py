#!/usr/bin/env python3
"""New mock-only project: fixed images, private test CA, real internal HTTP/TLS."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path

from check_reuse_compose import ROOT, compose_config, validate

ENV={"PATH":os.environ.get("PATH", "")}
WEBUI="ghcr.io/open-webui/open-webui@sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd"


def call(args, *, stdin=None, timeout=60):
    p=subprocess.run(args,input=stdin,env=ENV,capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError(f'isolated {args[0]} operation failed (exit {p.returncode}); private output withheld')
    return p.stdout.strip()


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n');path.chmod(0o600)


def prepare(run: Path, project: str, image: str):
    run=run.resolve()
    if run.exists() or not run.is_relative_to(ROOT/'learning_data') or not re.fullmatch(r'dd-learning-reuse-[a-z0-9-]{1,60}',project):
        raise ValueError('new isolated project and directory required')
    for args in (['ps','-aq'],['volume','ls','-q'],['network','ls','-q']):
        if call(['docker',*args,'--filter','label=com.docker.compose.project='+project]):
            raise ValueError('existing project resources are preserved')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',image):raise ValueError('fixed local learning image ID required')
    run.mkdir(parents=True,mode=0o700);directory=run/'secrets';directory.mkdir(mode=0o700)
    for name in ('learning_admin_secret','learning_adapter_secret','learning_browser_auth_secret'):
        (directory/name).write_text(secrets.token_urlsafe(32));(directory/name).chmod(0o444)
    call(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=DD isolated synthetic CA',
          '-addext','subjectAltName=IP:172.19.116.53,DNS:learning-proxy',
          '-keyout',str(directory/'tls_private_key.pem'),'-out',str(directory/'tls_certificate.pem')])
    (directory/'tls_private_key.pem').chmod(0o444)
    credentials={'email':'dd-reuse-synthetic@example.invalid','password':secrets.token_urlsafe(32)}
    save(directory/'login.json',credentials);(directory/'login.json').chmod(0o444)
    config=compose_config(image,directory);config['name']=project
    for name in ('learning-internal','webui-upstream'):
        config['networks'][name]={'name':project+'_'+name,'internal':True}
    config['volumes']['dd_learning_data']={'name':project+'_dd_learning_data'}
    config['volumes']['dd_webui_data']={'name':project+'_dd_webui_data'}
    config['services']['learning-proxy'].pop('ports',None)
    for name in ('learning-api','learning-worker'):
        config['services'][name]['environment'].update(LEARNING_BROWSER_AUTH_ENABLED='1',DD_ISOLATED_PROBE='1',
            LEARNING_BROWSER_AUTH_ISSUER='synthetic-reuse-gateway',LEARNING_BROWSER_IDENTITY_ISSUER='synthetic-webui-installation')
    config['services']['learning-gateway']['environment'].update(DD_GATEWAY_ENABLED='1',
        LEARNING_BROWSER_AUTH_ISSUER='synthetic-reuse-gateway',LEARNING_BROWSER_IDENTITY_ISSUER='synthetic-webui-installation')
    config['configs']['isolated_ca']={'file':str(directory/'tls_certificate.pem')}
    config['configs']['isolated_login']={'file':str(directory/'login.json')}
    config['services']['learning-api']['configs']=[{'source':'isolated_ca','target':'/run/isolated-ca.pem'},
                                                   {'source':'isolated_login','target':'/run/isolated-login.json'}]
    web_env={k:'false' for k in ('ENABLE_OPENAI_API','ENABLE_OLLAMA_API','ENABLE_PERSISTENT_CONFIG',
        'ENABLE_VERSION_UPDATE_CHECK','ENABLE_COMMUNITY_SHARING','ENABLE_EVALUATION_ARENA_MODELS',
        'RAG_EMBEDDING_MODEL_AUTO_UPDATE','RAG_RERANKING_MODEL_AUTO_UPDATE','WHISPER_MODEL_AUTO_UPDATE','ANONYMIZED_TELEMETRY','ENABLE_SIGNUP')}
    web_env.update(OFFLINE_MODE='true',HF_HUB_OFFLINE='1',DO_NOT_TRACK='true',SCARF_NO_ANALYTICS='true',WEBUI_AUTH='true',
        WEBUI_SECRET_KEY=secrets.token_urlsafe(32),WEBUI_ADMIN_EMAIL=credentials['email'],WEBUI_ADMIN_PASSWORD=credentials['password'],
        WEBUI_ADMIN_NAME='DD Synthetic Reuse Admin')
    config['services']['open-webui']={'image':WEBUI,'pull_policy':'never','restart':'no',
        'networks':{'learning-internal':None,'webui-upstream':None},'environment':web_env,
        'volumes':[{'type':'volume','source':'dd_webui_data','target':'/app/backend/data'}]}
    errors=validate(config,isolated=True)
    if errors:raise ValueError('isolated configuration rejected: '+', '.join(errors))
    save(run/'compose.private.json',config)
    save(run/'manifest.json',{'project':project,'image_id':image,'webui_image':WEBUI,
        'compose_sha256':hashlib.sha256((run/'compose.private.json').read_bytes()).hexdigest(),
        'secret_directory_private':True,'test_CA_only':True,'production_change':False})
    return {'prepared':True,'project':project,'host_ports':False,'all_networks_internal':True}


def compose(run,*args,restored=False,timeout=120):
    manifest=json.loads((run/'manifest.json').read_text())
    if not re.fullmatch(r'dd-learning-reuse-[a-z0-9-]{1,60}',manifest['project']):raise ValueError('invalid project')
    if hashlib.sha256((run/'compose.private.json').read_bytes()).hexdigest()!=manifest['compose_sha256']:raise ValueError('private source configuration changed')
    file=run/('compose.restore.json' if restored else 'compose.private.json')
    return call(['docker','compose','--env-file','/dev/null','-p',manifest['project'],'-f',str(file),*args],timeout=timeout)


def execute(run,source,*,restored=False):
    m=json.loads((run/'manifest.json').read_text())
    file=run/('compose.restore.json' if restored else 'compose.private.json')
    return call(['docker','compose','--env-file','/dev/null','-p',m['project'],'-f',str(file),
                 'exec','-T','learning-api','python','-'],stdin=source,timeout=180)


def stop(run: Path, grace_seconds: int = 60) -> dict:
    """Stop only verified isolated container IDs and record forced exits as failures."""
    if type(grace_seconds) is not int or not 1 <= grace_seconds <= 60:
        raise ValueError('shutdown grace must be between 1 and 60 seconds')
    manifest=json.loads((run/'manifest.json').read_text())
    project=manifest['project']
    restored=(run/'compose.restore.json').exists()
    ids=compose(run,'ps','-aq',restored=restored).splitlines()
    allowed={'learning-api','learning-worker','learning-gateway','learning-proxy','open-webui'}
    # Do not inspect environment variables, data or full container configuration.
    template='{"id":{{json .Id}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"running":{{json .State.Running}},"status":{{json .State.Status}},"exit_code":{{json .State.ExitCode}},"oom_killed":{{json .State.OOMKilled}},"pid":{{json .State.Pid}}}'

    def inspect(cid):
        result=json.loads(call(['docker','inspect','--format',template,cid]))
        if result['project'] != project or result['service'] not in allowed:
            raise ValueError('shutdown target is outside the named isolated project')
        return result

    before=[inspect(cid) for cid in ids]
    running=[c['id'] for c in before if c['running']]
    started=time.monotonic()
    if running:
        # IDs prevent a same-name replacement from becoming a new stop target.
        call(['docker','stop','--time',str(grace_seconds),*running],timeout=grace_seconds+30)
    after=[inspect(c['id']) for c in before]
    current_ids=compose(run,'ps','-aq',restored=restored).splitlines()
    current=[inspect(cid) for cid in current_ids]
    failures=[]
    if {c['id'] for c in before} != {c['id'] for c in current}:
        failures.append('ISOLATED_CONTAINER_SET_CHANGED')
    for c in after:
        if c['running'] or c['pid'] != 0:
            failures.append(c['service']+':STILL_RUNNING')
        elif c['oom_killed'] or c['exit_code'] != 0:
            failures.append(c['service']+':NONZERO_OR_OOM_EXIT')
    if any(c['running'] for c in current):
        failures.append('ISOLATED_PROJECT_STILL_RUNNING')
    result={'status':'passed' if not failures else 'failed','project':project,
            'grace_seconds':grace_seconds,'elapsed_seconds':round(time.monotonic()-started,3),
            'stopped_now':len(running),'already_stopped':len(before)-len(running),
            'containers':after,'errors':failures,'volumes_preserved':True,
            'production_change':False}
    # Each attempt is immutable; retain a previous forced-stop finding on retry.
    save(run/('shutdown-'+secrets.token_hex(8)+'.json'),result)
    return result


def start_and_probe(run):
    compose(run,'up','-d','--no-build','--pull','never',timeout=180)
    report=json.loads(execute(run,(ROOT/'scripts/reuse_runtime_http_probe.py').read_text()))
    manifest=json.loads((run/'manifest.json').read_text())
    networks={name:json.loads(call(['docker','network','inspect','--format','{{json .Internal}}',manifest['project']+'_'+name])) for name in ('learning-internal','webui-upstream')}
    assert all(networks.values())
    report['runtime_networks_internal']=networks
    save(run/'runtime-report.json',report)
    return report


RECOVER = '''
import json,shutil,hashlib
from pathlib import Path
from learning_service.backup import backup_data,restore_data
from learning_service.operations import recovery_inventory,verify_recovery
source=Path('/source');working=Path('/var/lib/dd-learning/inspection-source')
original_hashes={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
shutil.copytree(source,working)
assert all(hashlib.sha256((working/name).read_bytes()).hexdigest()==digest for name,digest in original_hashes.items())
# A read-only WAL source cannot always create its SQLite shared-memory file.
# Replay only in the byte-checked working copy; the stopped source stays read-only.
before=recovery_inventory(working)
backup_data(working,Path('/var/lib/dd-learning/backup'),writers_stopped=True)
restore_data(Path('/var/lib/dd-learning/backup'),Path('/var/lib/dd-learning/restored'))
after=recovery_inventory(Path('/var/lib/dd-learning/restored'))
result=verify_recovery(before,after)
assert result['status']=='passed',result
assert all(hashlib.sha256((source/name).read_bytes()).hexdigest()==digest for name,digest in original_hashes.items())
print(json.dumps({'verification':result,'before':before,'after':after,'readonly_source_hashes_unchanged':True,'WAL_replayed_in_verified_copy':True}))
'''


def recover(run):
    m=json.loads((run/'manifest.json').read_text());project=m['project']
    # Capture only synthetic probe state; never inspect the original WebUI data.
    api=compose(run,'ps','-q','learning-api')
    for name in ('synthetic-cookies.private.json','synthetic-session.private.json'):
        call(['docker','cp',api+':/var/lib/dd-learning/'+name,str(run/name)])
        (run/name).chmod(0o600)
    compose(run,'stop','learning-api','learning-worker')
    for service in ('learning-api','learning-worker'):
        cid=compose(run,'ps','-aq',service)
        assert call(['docker','inspect','--format','{{.State.Running}}',cid])=='false'
    original=project+'_dd_learning_data';restored=project+'_dd_learning_restored'
    if call(['docker','volume','ls','-q','--filter','name=^'+restored+'$']):raise ValueError('restore target already exists')
    call(['docker','volume','create','--label','com.docker.compose.project='+project,
          '--label','com.docker.compose.volume=dd_learning_data',restored])
    report=json.loads(call(['docker','run','--rm','--name',project+'-restore-check','--network','none',
        '--mount','type=volume,source='+original+',target=/source,readonly',
        '--mount','type=volume,source='+restored+',target=/var/lib/dd-learning',m['image_id'],'python','-c',RECOVER]))
    config=json.loads((run/'compose.private.json').read_text());config['volumes']['dd_learning_data']['name']=restored
    for name in ('learning-api','learning-worker'):
        config['services'][name]['environment'].update(LEARNING_DATA_DIR='/var/lib/dd-learning/restored',
            LEARNING_DB_PATH='/var/lib/dd-learning/restored/learning.db',LEARNING_ATTACHMENT_DIR='/var/lib/dd-learning/restored/attachments',
            LEARNING_EXPORT_DIR='/var/lib/dd-learning/restored/exports')
    save(run/'compose.restore.json',config)
    compose(run,'up','-d','--no-build','--pull','never',restored=True,timeout=180)
    # Verify the OLD cookie is rejected by the running restored API over TLS.
    saved_cookies=json.loads((run/'synthetic-cookies.private.json').read_text())
    saved_session=json.loads((run/'synthetic-session.private.json').read_text())
    source='''
import http.client,ssl,json,re
from http.cookies import SimpleCookie
from pathlib import Path
from learning_service.browser_auth import CSRF_COOKIE
cookies=SAVED_COOKIES
tls=ssl.create_default_context(cafile='/run/isolated-ca.pem')
def req(method,path,body=None):
 h={'Host':'172.19.116.53','Origin':'https://172.19.116.53','Cookie':'; '.join(k+'='+v for k,v in cookies.items())}
 if CSRF_COOKIE in cookies:h['X-CSRF-Token']=cookies[CSRF_COOKIE]
 if isinstance(body,dict):body=json.dumps(body);h['Content-Type']='application/json'
 elif body is not None:h['Content-Type']='application/x-www-form-urlencoded'
 c=http.client.HTTPSConnection('learning-proxy',443,context=tls,timeout=35);c.request(method,path,body,h);r=c.getresponse();raw=r.read()
 for k,v in r.getheaders():
  if k.lower()=='set-cookie':
   p=SimpleCookie();p.load(v)
   for key,val in p.items():
    if val.value:cookies[key]=val.value
    else:cookies.pop(key,None)
 status=r.status;c.close();return status,raw
assert req('GET','/learning/api/v1/learner-context')[0]==401
status,raw=req('GET','/learning/auth/login');assert status==200
nonce=re.search(r'name="csrf" value="([^"]+)"',raw.decode()).group(1)
assert req('POST','/learning/auth/session','csrf='+nonce)[0]==303
status,raw=req('GET','/learning/api/v1/learner-context');assert status==200 and json.loads(raw)['learner_id'] is None
context=json.loads(raw)
status,raw=req('POST','/learning/api/v1/learner-context',{'learner_id':'synthetic-learner','expected_revision':context['context_version']});assert status==200
version=json.loads(raw)['context_version']
# Read through fresh context; retain the server's frozen grade and revoked version.
c=http.client.HTTPSConnection('learning-proxy',443,context=tls,timeout=35)
h={'Host':'172.19.116.53','Cookie':'; '.join(k+'='+v for k,v in cookies.items()),'X-Learner-Context-Version':str(version)}
c.request('GET','/learning/api/v1/test-sessions/'+SAVED_SESSION['session_id'],headers=h);r=c.getresponse();data=json.loads(r.read());assert r.status==200 and data['items'][0]['attempt_status']=='graded';c.close()
print(json.dumps({'old_cookie_rejected':True,'fresh_login_and_selection':True,'frozen_grade_read_after_restore':True}))
'''.replace('SAVED_COOKIES',repr(saved_cookies)).replace('SAVED_SESSION',repr(saved_session))
    report['running_restored_api']=json.loads(execute(run,source,restored=True))
    report['writers_stopped_metadata_checked']=True
    report['source_volume_preserved']=True
    save(run/'recovery-report.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run','recover','stop'])
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--project');p.add_argument('--image')
    p.add_argument('--stop-grace-seconds',type=int,default=60)
    a=p.parse_args();run=a.directory.resolve()
    if a.action=='prepare':result=prepare(run,a.project,a.image)
    elif a.action=='run':result=start_and_probe(run)
    elif a.action=='recover':result=recover(run)
    else:result=stop(run,a.stop_grace_seconds)
    print(json.dumps(result))
    if a.action=='stop' and result['status']!='passed':
        raise SystemExit(1)
