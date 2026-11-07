"""Execute inside the NEW isolated learning API; emit aggregate synthetic evidence."""
import base64
import http.client
import io
import json
import os
import re
import ssl
import time
from http.cookies import SimpleCookie
from pathlib import Path

from PIL import Image

from learning_service.app import _variant_snapshot
from learning_service.browser_auth import CSRF_COOKIE
from learning_service.config import Settings
from learning_service.db import Database, json_dumps, utc_now
from learning_service.operations import monitor

assert os.environ.get('DD_ISOLATED_PROBE') == '1', 'isolated fixture opt-in required'
origin='https://172.19.116.53'
settings=Settings.from_env(); db=Database(settings.db_path)
assert not settings.dev_mode and not settings.model_external_calls_enabled and not settings.tencent_ocr_external_calls_enabled
cookies={}; version=None
tls=ssl.create_default_context(cafile='/run/isolated-ca.pem')


def request(method,path,body=None,headers=None,expected=200):
    h={'Host':'172.19.116.53','Origin':origin,'Cookie':'; '.join(k+'='+v for k,v in cookies.items())}
    if CSRF_COOKIE in cookies: h['X-CSRF-Token']=cookies[CSRF_COOKIE]
    if version is not None: h['X-Learner-Context-Version']=str(version)
    if isinstance(body,dict): body=json.dumps(body).encode();h['Content-Type']='application/json'
    h.update(headers or {})
    c=http.client.HTTPSConnection('learning-proxy',443,context=tls,timeout=35)
    try:
        c.request(method,path,body=body,headers=h);r=c.getresponse();raw=r.read();hs=r.getheaders()
        for name,value in hs:
            if name.lower()=='set-cookie':
                p=SimpleCookie();p.load(value)
                for k,v in p.items():
                    if v.value:cookies[k]=v.value
                    else:cookies.pop(k,None)
        assert r.status==expected,(method,path,r.status)
        return raw,hs
    finally:c.close()


def api(method,path,body=None,headers=None,expected=200):
    return json.loads(request(method,'/learning'+path,body,headers,expected)[0])


credentials=json.loads(Path('/run/isolated-login.json').read_text())
for attempt in range(90):
    try:
        raw,_=request('POST','/api/v1/auths/signin',{'email':credentials['email'],'password':credentials['password']})
        user=json.loads(raw);assert 'token' in cookies;break
    except (OSError,AssertionError):
        if attempt==89:raise
        time.sleep(1)
assert user['role']=='admin'
with db.session(write=True) as conn:
    assert conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]==0
    now=utc_now()
    conn.execute("INSERT INTO accounts(id,created_at) VALUES ('synthetic-account',?)",(now,))
    conn.execute("INSERT INTO identity_bindings(id,account_id,provider,issuer,subject,created_at) VALUES ('synthetic-binding','synthetic-account','open-webui',?,?,?)",(settings.browser_identity_issuer,user['id'],now))
    conn.execute("INSERT INTO learners(id,display_name,timezone,curriculum_id,created_at) VALUES ('synthetic-learner','Synthetic','Asia/Shanghai','math-g7-v1',?)",(now,))
    conn.execute("INSERT INTO learner_access(account_id,learner_id,role,created_at) VALUES ('synthetic-account','synthetic-learner','admin',?)",(now,))
    conn.execute("INSERT INTO knowledge_points(id,curriculum_id,code,title,created_at) VALUES ('synthetic-kp','math-g7-v1','signed','Synthetic',?)",(now,))
    conn.execute("INSERT INTO review_objectives(id,knowledge_point_id,code,title,created_at) VALUES ('synthetic-objective','synthetic-kp','subtract','Synthetic',?)",(now,))
    conn.execute("INSERT INTO questions(id,visibility,approval,objective_id,created_at) VALUES ('synthetic-source','shared','approved','synthetic-objective',?)",(now,))
    content={'template_id':'signed_number_subtraction','prompt':'-3 - (-5) = ?', 'parameters':{'start':-3,'subtrahend':-5},'domain':'integers','unit':None}
    conn.execute("INSERT INTO question_versions(id,question_id,version,content_json,answer_key_json,validator_version,approval,created_at) VALUES ('synthetic-source-v1','synthetic-source',1,?,?,'exact-text-v1','approved',?)",(json_dumps(content),json_dumps({'accepted':['2']}),now))
    source=_variant_snapshot(conn,'synthetic-learner',{'objective_id':'synthetic-objective','source_question_version_id':'synthetic-source-v1'})
    draft={'objective_id':'synthetic-objective','source_question_version_id':'synthetic-source-v1','content':{**content,'prompt':'-4 - (-7) = ?','parameters':{'start':-4,'subtrahend':-7}},'answer_key':{'accepted':['3']},'validator_version':'exact-text-v1','approval':'draft'}
    result={'status':'needs_review','approval_required':True,'payload':{'draft':draft,'approval_required':True},'source_snapshot_hash':source['snapshot_hash'],'evidence':{'mode':'synthetic_fixture','external_call':False}}
    conn.execute("INSERT INTO jobs(id,learner_id,kind,input_json,idempotency_key,status,result_json,created_at,updated_at) VALUES ('synthetic-variant','synthetic-learner','variant_generation',?,'synthetic-fixture','succeeded',?,?,?)",(json_dumps(source),json_dumps(result),now,now))
raw,_=request('GET','/learning/auth/login')
nonce=re.search(r'name="csrf" value="([^"]+)"',raw.decode()).group(1)
raw,hs=request('POST','/learning/auth/session','csrf='+nonce,{'Content-Type':'application/x-www-form-urlencoded'},303)
assert dict(hs).get('location')=='/learning/ui'
learning_cookies=[v for k,v in hs if k.lower()=='set-cookie']
assert len(learning_cookies)==2 and all('Secure' in c and 'Path=/' in c and 'SameSite=strict' in c for c in learning_cookies)
context=api('GET','/api/v1/learner-context')
version=api('POST','/api/v1/learner-context',{'learner_id':'synthetic-learner','expected_revision':context['context_version']})['context_version']
request('GET','/learning/ui')
request('GET','/learning/internal/bootstrap',expected=404)
request('POST','/learning/api/v1/auth/session',expected=404)
manual={'question_text':'Synthetic runtime exercise -3 - (-5)','objective_id':'synthetic-objective'}
a=api('POST','/api/v1/mistakes/manual',manual,{'Idempotency-Key':'synthetic-runtime-manual'},201)
assert api('POST','/api/v1/mistakes/manual',manual,{'Idempotency-Key':'synthetic-runtime-manual'},201)==a
png=io.BytesIO();Image.new('RGB',(8,8),'white').save(png,format='PNG')
boundary='ddsyntheticboundary'
payload=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="synthetic.png"\r\nContent-Type: image/png\r\n\r\n').encode()+png.getvalue()+('\r\n--'+boundary+'--\r\n').encode()
asset=api('POST','/api/v1/documents',payload,{'Content-Type':'multipart/form-data; boundary='+boundary},201)
detail=api('GET','/api/v1/admin/variant-jobs/synthetic-variant')
assert detail['source_current']
body={'decision':'approve','result_fingerprint':detail['result_fingerprint'],'note':'Synthetic human fixture checked integer program answer.'}
approved=api('POST','/api/v1/admin/variant-jobs/synthetic-variant/review',body,{'Idempotency-Key':'synthetic-runtime-review'})
assert api('POST','/api/v1/admin/variant-jobs/synthetic-variant/review',body,{'Idempotency-Key':'synthetic-runtime-review'})==approved
session=api('POST','/api/v1/test-sessions',{'question_version_id':approved['question_version_id']},expected=201)
item=session['items'][0]['test_item_id']
api('GET','/api/v1/test-items/'+item)
ch=api('POST','/api/v1/test-items/'+item+'/submission-challenges')
api('POST','/api/v1/test-items/'+item+'/answers',{'challenge_id':ch['challenge_id'],'nonce':ch['nonce'],'raw_answer':'3'},{'Idempotency-Key':'synthetic-runtime-answer'},202)
for attempt in range(30):
    grade=api('GET','/api/v1/test-sessions/'+session['session_id'])
    if grade['items'][0].get('attempt_status')=='graded':break
    time.sleep(1)
else:raise AssertionError('mock grade worker did not finish')
api('POST','/api/v1/admin/variant-reviews/'+approved['review_id']+'/revoke',{'note':'Synthetic rollback exercise'},{'Idempotency-Key':'synthetic-runtime-revoke'})
assert api('GET','/api/v1/test-sessions/'+session['session_id'])['items'][0]['attempt_status']=='graded'
metrics=api('GET','/api/v1/admin/metrics')
assert metrics['external_calls']['budget_charge_micros']==0 and not metrics['external_calls']['by_evidence_mode']
api('GET','/api/v1/mistakes',headers={'X-Learner-Context-Version':str(version-1)},expected=409)
Path('/var/lib/dd-learning/synthetic-cookies.private.json').write_text(json.dumps(cookies))
Path('/var/lib/dd-learning/synthetic-session.private.json').write_text(json.dumps({'session_id':session['session_id'],'asset_id':asset['asset_id']}))
with db.session(write=True) as conn:
    conn.execute("INSERT INTO provider_calls(id,provider_id,operation,model_id,evidence_mode,currency,pricing_reference,reserved_cost_micros,state,created_at) VALUES ('synthetic-interrupted-call','synthetic','diagnosis','synthetic','synthetic_http','USD','synthetic-price',17,'reserved',datetime('now'))")
pending=api('POST','/api/v1/test-sessions',{'question_version_id':'synthetic-source-v1'},expected=201)
api('POST','/api/v1/test-items/'+pending['items'][0]['test_item_id']+'/submission-challenges')
print(json.dumps({'passed':True,'schema_revision':11,'real_model_ocr_calls':0,'http_mode':'actual_TLS_proxy_gateway_API_and_isolated_WebUI_cookie_with_synthetic_account','formal_IP_certificate_trust':False,'native_model_callback':False,'manual_idempotency':True,'representative_PNG_uploaded':True,'review_freeze_grade_revoke':True,'monitor':monitor(metrics)}))
