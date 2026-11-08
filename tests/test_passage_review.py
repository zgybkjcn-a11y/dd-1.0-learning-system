"""B03 local journal and source/review gates, using original synthetic PDFs."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from learning_service import passage_review as review
from learning_service.passage_evidence import canonical, digest, text_digest, load_bundle
from learning_service.textbooks import learning_scope, page_evidence, render_page
from learning_service.passage_review_web import create_app

ACTOR = {'type': 'assistant', 'label': 'synthetic assistant'}
ORIGIN = 'http://127.0.0.1:8765'
VISUAL = {'notes': '逐字核对合成原页上的数字与运算符号', 'scope_notes': '仅选择完整等式，保留合成上下文说明',
          'layout_notes': '等式在同一行，没有上下标或跨列拼接'}
SEMANTIC = {'derivation': '独立用加法定义复算：三个单位加两个单位得到五个单位。',
            'conditions': '所用对象为整数，等式两边条件完整，无隐含变量。',
            'units': '纯整数计算不带物理单位，核对的是等式是否成立。',
            'diagram': 'none_for_selected_excerpt',
            'checks': [{'claim': '3+2=5', 'purpose': '直接独立计算所选等式的两边，确认结果一致。'}]}


@pytest.fixture
def review_workspace(tmp_path, textbook_sources, monkeypatch):
    monkeypatch.setattr(review, 'now', lambda: datetime(2026, 11, 8, 12, tzinfo=ZoneInfo('Asia/Shanghai')))
    bundle = tmp_path / 'bundle'; (bundle / 'source').mkdir(parents=True)
    book, _ = learning_scope('math-g7-v1', 'math-g7-upper', '2')
    page = page_evidence(book, 47)
    image = render_page(textbook_sources, book['id'], 47)
    (bundle / 'source/page.png').write_bytes(image)
    text, context = '3+2=5', '完整合成等式，仅用于工作台流程测试；不是出版社教材内容。'
    binding = {k: page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')}
    binding.update(text_sha256=text_digest(text), context_sha256=text_digest(context), image_sha256=digest(image))
    checks = canonical({'checks': {'synthetic-review': {'passed': True, 'case_count': 1, 'method': 'exact_rational_checks'}}})
    verifier = b'# synthetic evidence, not executable input\n'
    (bundle / 'semantic-checks.json').write_bytes(checks); (bundle / 'verify_semantics.py').write_bytes(verifier)
    entry = {'id': 'synthetic-review', 'curriculum_id': 'math-g7-v1', 'book_id': book['id'],
             **{k: page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page', 'printed_page', 'chapter_id')},
             'text': text, 'context': context, 'text_policy': 'layout_normalized_transcription',
             'image_path': 'source/page.png', 'retrieval_terms': ['合成等式'], 'enabled': True, 'binding': binding,
             'review': {'revision': 1, 'scope': 'selected_excerpt', 'binding': deepcopy(binding),
                        'teacher_reviewed': False, 'reviewed_on': '2026-11-07', 'valid_until': '2026-12-07', 'unresolved_issues': [],
                        'transcription': {'status': 'checked', 'reviewer_type': 'assistant', 'method': 'visual_original_comparison',
                                          'layout_checked': True, 'notes': 'synthetic source comparison'},
                        'semantic': {'status': 'checked', 'reviewer_type': 'assistant', 'method': 'independent_mathematical_reasoning_and_exact_checks',
                                     'conditions_complete': True, 'derivation': 'synthetic arithmetic', 'diagram_dependency': 'none_for_selected_excerpt',
                                     'checks_sha256': digest(checks), 'verifier_sha256': digest(verifier)}}}
    raw = canonical({'format': 'dd-textbook-excerpt-pilot-v1', 'passages': [entry]})
    (bundle / 'passages.json').write_bytes(raw)
    workspace = tmp_path / 'review-workspace'
    review.prepare(workspace, bundle, digest(raw), textbook_sources, entry['id'])
    return review.ReviewStore(workspace), bundle, textbook_sources, digest(raw)


def act(store, action, values):
    return store.mutate(store.history()[-1]['seq'], action, values, ACTOR)


def approved(store):
    act(store, 'transcription', VISUAL)
    act(store, 'semantic', SEMANTIC)
    act(store, 'enable', {'reason': '双步骤核验完成，仅启用本地候选'})
    return store.view()['evidence_id']


def test_import_is_pending_and_does_not_change_original_bundle(review_workspace):
    store, bundle, textbooks, pin = review_workspace
    original = {str(p.relative_to(bundle)): digest(p.read_bytes()) for p in bundle.rglob('*') if p.is_file()}
    state = store.view()
    assert state['revision'] == state['seq'] == 1
    assert state['transcription'] is state['semantic'] is state['evidence_id'] is None
    assert not state['available'] and len(state['blockers']) == 2
    assert state['native_text'].startswith('SYNTHETIC')
    assert state['content']['source']['printed_page'] == 40
    assert load_bundle(bundle, pin, textbooks, as_of=review.now().date())
    approved(store)
    assert original == {str(p.relative_to(bundle)): digest(p.read_bytes()) for p in bundle.rglob('*') if p.is_file()}
    with pytest.raises(review.ReviewError): review.prepare(store.directory, bundle, pin, textbooks, 'synthetic-review')
    with pytest.raises(review.ReviewError): review.prepare(bundle/'nested', bundle, pin, textbooks, 'synthetic-review')


@pytest.mark.parametrize('values', [{}, {'checked': True}, {**VISUAL, 'notes': '已看'}])
def test_checkbox_or_generic_acknowledgment_cannot_record_review(review_workspace, values):
    store = review_workspace[0]
    with pytest.raises(review.ReviewError): act(store, 'transcription', values)
    with pytest.raises(review.ReviewError): act(store, 'enable', {'reason': '尝试缺审核启用'})
    assert len(store.history()) == 1


@pytest.mark.parametrize('change', ['missing', 'false_equality', 'layout', 'no_relation', 'no_conditions', 'diagram', 'code'])
def test_missing_or_invalid_independent_evidence_blocks_approval(review_workspace, change):
    store = review_workspace[0]; act(store, 'transcription', VISUAL)
    values = deepcopy(SEMANTIC)
    if change == 'missing': values['checks'] = []
    if change == 'false_equality': values['checks'][0]['claim'] = '3+2=6'
    if change == 'layout': values['checks'][0]['claim'] = '1 2=12'
    if change == 'no_relation': values['checks'][0]['purpose'] = ''
    if change == 'no_conditions': values['conditions'] = ''
    if change == 'diagram': values['diagram'] = 'requires_diagram'
    if change == 'code': values['checks'][0]['claim'] = '__import__("os")=0'
    with pytest.raises(review.ReviewError): act(store, 'semantic', values)
    assert store.view()['semantic'] is None
    with pytest.raises(review.ReviewError): act(store, 'enable', {'reason': '缺少第二种核验依据'})


@pytest.mark.parametrize('field', ['text', 'context', 'pdf_page'])
def test_any_content_or_source_revision_invalidates_prior_evidence(review_workspace, field):
    store = review_workspace[0]; old = approved(store); first = store.view()
    values = {'text': first['content']['text'], 'context': first['content']['context'],
              'pdf_page': first['content']['source']['pdf_page'], 'reason': '合成修订测试'}
    values[field] = {'text': '3+3=6', 'context': '修改后的合成上下文，仍须重新逐字复核', 'pdf_page': 48}[field]
    act(store, 'revise', values)
    state = store.view()
    assert state['revision'] == 2 and not state['available']
    assert state['transcription'] is state['semantic'] is None
    with pytest.raises(review.ReviewError, match='失效'): store.evidence(old)
    assert store.history()[3]['state']['evidence_id'] == old


def test_issues_resolution_withdrawal_and_reenable_keep_history(review_workspace):
    store = review_workspace[0]; first = approved(store)
    act(store, 'disable', {'reason': '暂时停用本地候选'})
    with pytest.raises(review.ReviewError): store.evidence(first)
    act(store, 'enable', {'reason': '原审核未变，恢复本地使用'})
    second = store.view()['evidence_id']; assert second != first
    act(store, 'issue', {'description': '需再次核对数字的版面位置'})
    act(store, 'transcription', VISUAL); act(store, 'semantic', SEMANTIC)
    with pytest.raises(review.ReviewError, match='未解决'): act(store, 'enable', {'reason': '尝试带问题启用'})
    issue = store.view()['issues'][0]['id']
    act(store, 'resolve', {'issue_id': issue, 'resolution': '重新对照合成原页确认数字位置，保存本次处理依据'})
    assert store.view()['transcription'] is store.view()['semantic'] is None
    approved(store)
    act(store, 'withdraw', {'reason': '撤回后需重新审核'})
    with pytest.raises(review.ReviewError): act(store, 'enable', {'reason': '不能直接重新启用'})
    with pytest.raises(review.ReviewError): act(store, 'transcription', VISUAL)
    s = store.view(); act(store, 'revise', {**{k:s['content'][k] for k in ('text','context')}, 'pdf_page':47, 'reason':'建立重审修订'})
    assert approved(store) not in (first, second)
    assert store.view()['revision'] == 2


def test_faithful_but_false_original_cannot_use_an_unrelated_true_check(review_workspace):
    store=review_workspace[0];s=store.view()
    act(store,'revise',{'text':'3+2=6','context':s['content']['context'],'pdf_page':47,'reason':'保留原文错例待核'})
    act(store,'transcription',VISUAL)
    with pytest.raises(review.ReviewError,match='原文等式不成立'):
        act(store,'semantic',SEMANTIC)
    assert not store.view()['available']


def test_concurrent_review_does_not_overwrite_and_actor_is_recorded(review_workspace):
    store = review_workspace[0]
    def attempt(label):
        try:
            store.mutate(1, 'transcription', VISUAL, {'type':'human','label':label})
            return 200
        except review.ReviewError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(attempt, ['reviewer-a', 'reviewer-b']))
    assert sorted(statuses) == [200, 409]
    assert len(store.history()) == 2
    assert store.view()['transcription']['actor']['type'] == 'human'
    assert store.view()['teacher_reviewed'] is False


@pytest.mark.parametrize('target', ['pdf', 'image', 'native', 'config', 'journal'])
def test_changed_material_or_journal_fails_closed(review_workspace, target):
    store, _, textbooks, _ = review_workspace; old = approved(store)
    source = store.view()['content']['source']
    paths = {'pdf':textbooks/'math-g7-upper.pdf', 'image':store.directory/'assets'/(source['image_sha256']+'.png'),
             'native':store.directory/'assets'/(source['native_text_sha256']+'.txt'), 'config':store.directory/'workspace.json'}
    if target == 'journal':
        with sqlite3.connect(store.directory/'review.sqlite') as conn:
            conn.execute("UPDATE events SET hash='changed' WHERE seq=1")
    elif target == 'config':
        config = json.loads(paths[target].read_text()); config['valid_until']='2099-01-01'; paths[target].write_bytes(canonical(config))
    else: paths[target].write_bytes(paths[target].read_bytes()+b'changed')
    with pytest.raises(review.ReviewError): store.evidence(old)
    if target in ('pdf','image','native'):
        act(store, 'withdraw', {'reason':'材料损坏后仍可撤回'})
        assert store.history()[-1]['state']['withdrawn']


def test_expiry_and_wrong_page_cannot_be_bypassed(review_workspace, monkeypatch):
    store = review_workspace[0]; old=approved(store)
    s=store.view()
    with pytest.raises(review.ReviewError): act(store,'revise',{'text':s['content']['text'],'context':s['content']['context'],'pdf_page':150,'reason':'越界来源'})
    monkeypatch.setattr(review,'now',lambda:datetime(2026,12,8,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert not store.view()['available']
    with pytest.raises(review.ReviewError): store.evidence(old)
    with pytest.raises(review.ReviewError): act(store,'enable',{'reason':'不能绕过真实日期'})


def test_local_export_is_versioned_historical_snapshot_not_runtime_manifest(review_workspace, tmp_path):
    store=review_workspace[0]
    with pytest.raises(review.ReviewError): store.export(tmp_path/'pending',1)
    assert not (tmp_path/'pending').exists()
    old=approved(store); state=store.view()
    result=store.export(tmp_path/'packet',state['seq'])
    assert not result['runtime_publish_performed']
    record=json.loads((tmp_path/'packet/review.json').read_text())
    assert record['historical_snapshot_only'] and not record['runtime_manifest']
    assert record['state']['fully_reviewed_page'] is record['state']['eligible_as_grading_basis'] is False
    assert record['state']['evidence_id']==old
    with pytest.raises(review.ReviewError):store.export(tmp_path/'packet',state['seq'])
    act(store,'disable',{'reason':'导出后停用当前证据'})
    with pytest.raises(review.ReviewError):store.export(tmp_path/'stale',state['seq'])
    assert not (tmp_path/'stale').exists()


def client(store):
    api=TestClient(create_app(store.directory,actor=ACTOR,origin=ORIGIN),base_url=ORIGIN)
    page=api.get('/')
    token=re.search(r'name="review-token" content="([^"]+)"',page.text).group(1)
    return api,{'X-Review-Token':token,'Origin':ORIGIN}


def test_local_api_requires_host_token_origin_and_rejects_identity_in_body(review_workspace):
    store=review_workspace[0];api,headers=client(store)
    assert api.get('/api/state').status_code==403
    assert api.get('/api/state',headers={**headers,'Host':'evil.invalid'}).status_code==403
    assert api.get('/',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    assert api.get('/api/state',headers=headers).json()['operator']==ACTOR
    body={'expected_seq':1,'action':'transcription','values':VISUAL}
    assert api.post('/api/commands',json=body,headers={'X-Review-Token':headers['X-Review-Token']}).status_code==403
    assert api.post('/api/commands',json={**body,'reviewer_type':'teacher'},headers=headers).status_code==422
    assert api.post('/api/commands',json=body,headers=headers).status_code==200
    assert api.post('/api/commands',json=body,headers=headers).status_code==409
    assert api.get('/api/image?seq=1',headers=headers).status_code==409
    response=api.get('/api/image?seq=2',headers=headers)
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert 'frame-ancestors' in response.headers['content-security-policy']
    with pytest.raises(ValueError):create_app(store.directory,actor=ACTOR,origin='http://0.0.0.0:8765')


def test_pure_import_and_no_automatic_database_creation():
    code="import sqlite3; sqlite3.connect=lambda *a, **k: (_ for _ in ()).throw(AssertionError('DB opened on import')); import learning_service.passage_review; import learning_service.passage_review_web; import scripts.passage_review_workbench"
    subprocess.run([sys.executable,'-c',code],check=True,capture_output=True)
