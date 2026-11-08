"""B03 UI uses synthetic material and intercepted requests only."""
from copy import deepcopy
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from test_passage_review import review_workspace, client, VISUAL, SEMANTIC, ORIGIN

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [390, 1280])
def test_review_revision_evidence_issue_and_concurrent_editor(
        review_workspace, tmp_path, width, playwright, launch_browser):
    store = review_workspace[0]
    api, headers = client(store)
    destination = Path(os.getenv('DD_PASSAGE_REVIEW_EVIDENCE_DIR', str(tmp_path)))
    destination.mkdir(parents=True, exist_ok=True)
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(viewport={'width':width, 'height':1000}, service_workers='block')
        errors=[]
        def handle(route):
            url=urlsplit(route.request.url)
            assert url.scheme+'://'+url.netloc==ORIGIN
            response=api.request(route.request.method,url.path+('?' + url.query if url.query else ''),
                                 headers=route.request.all_headers(),content=route.request.post_data_buffer)
            route.fulfill(status=response.status_code,body=response.content,
                          headers={k:v for k,v in response.headers.items() if k not in ('content-length','set-cookie')})
        context.route('**/*',handle)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(ORIGIN+'/');expect=playwright.expect
        expect(page.locator('#state')).to_contain_text('审核记录 1')
        expect(page.locator('#enable')).to_be_disabled()
        expect(page.locator('#location')).to_contain_text('书内第 40 页 / PDF 第 47 页')
        assert page.locator('#original').evaluate('(e)=>e.complete && e.naturalWidth>0')
        page.locator('#text').fill('3+3=6')
        for key,field in [('notes','visualNotes'),('scope_notes','scopeNotes'),('layout_notes','layoutNotes')]:
            page.locator('#'+field).fill(VISUAL[key])
        page.locator('#transcription').click()
        expect(page.locator('#message')).to_contain_text('先保存新修订')
        assert store.view()['seq']==1
        # Hostile-looking source text stays text; no execution or external request.
        page.locator('#context').fill('原创合成上下文 <img src=x onerror="throw 1">，保留片段边界。')
        page.locator('#revisionReason').fill('更正合成例子的第二个加数，重新逐字审核。')
        page.locator('#revise').click()
        expect(page.locator('#state')).to_contain_text('内容修订 2')
        expect(page.locator('#semanticStatus')).to_contain_text('尚无')

        def visual():
            for key,field in [('notes','visualNotes'),('scope_notes','scopeNotes'),('layout_notes','layoutNotes')]:
                page.locator('#'+field).fill(VISUAL[key])
            page.locator('#transcription').click()
            expect(page.locator('#visualStatus')).to_contain_text('已记录')

        def semantic(wrong=False):
            for field in ('derivation','conditions','units'):
                page.locator('#'+field).fill(SEMANTIC[field] if field!='derivation' else '三个单位再加三个单位，总计六个单位；独立用加法定义核算。')
            page.locator('#diagram').select_option('none_for_selected_excerpt')
            page.locator('#checks').fill(('3+3=7' if wrong else '3+3=6')+' | 独立核对当前完整等式两边数值相同。')
            page.locator('#semantic').click()
            if wrong:expect(page.locator('#message')).to_contain_text('未通过')
            else:expect(page.locator('#semanticStatus')).to_contain_text('已记录')

        visual();semantic(wrong=True)
        expect(page.locator('#checks')).to_have_value('3+3=7 | 独立核对当前完整等式两边数值相同。')
        semantic()
        page.locator('#reason').fill('两种独立核验完成，仅启用本地候选。')
        page.locator('#enable').click()
        expect(page.locator('#state')).to_contain_text('本地候选已启用')
        old=store.view()['evidence_id']
        assert api.get('/api/evidence/'+old,headers=headers).status_code==200
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(destination/f'review-enabled-{width}.png'),full_page=True)
        saved_context=page.locator('#context').input_value()
        page.locator('#context').fill(saved_context+'未保存修改')
        page.locator('#export').click()
        expect(page.locator('#message')).to_contain_text('存在未保存修订')
        assert not (store.directory.parent/(store.directory.name+'-exports')).exists()
        page.locator('#context').fill(saved_context)
        page.locator('#export').click()
        expect(page.locator('#exportStatus')).to_contain_text('已保存历史审核快照')
        packet=next((store.directory.parent/(store.directory.name+'-exports')).glob('*/review.json'))
        assert json.loads(packet.read_text())['state']['evidence_id']==old

        other=context.new_page();other.goto(ORIGIN+'/')
        expect(other.locator('#state')).to_contain_text('本地候选已启用')
        other.locator('#reason').fill('另一审核者的未提交内容需要保留。')
        page.locator('#issueText').fill('需再次核对上下文中的数字条件。')
        page.locator('#addIssue').click()
        expect(page.locator('#blockers')).to_contain_text('未解决问题')
        other.locator('#disable').click()
        expect(other.locator('#message')).to_contain_text('其他复核已更新')
        expect(other.locator('#reason')).to_have_value('另一审核者的未提交内容需要保留。')
        assert api.get('/api/evidence/'+old,headers=headers).status_code==404
        other.close()
        expect(page.locator('#enable')).to_be_disabled()
        page.locator('#issues textarea').fill('逐字核对合成原页与上下文，已保存本次处理依据。')
        page.locator('#issues button').click()
        expect(page.locator('#issues')).to_contain_text('处理依据')
        expect(page.locator('#visualStatus')).to_contain_text('尚无')
        expect(page.locator('#semanticStatus')).to_contain_text('尚无')
        visual();semantic()
        page.locator('#reason').fill('问题解决且两种依据重新核对完成。')
        page.locator('#enable').click()
        expect(page.locator('#state')).to_contain_text('本地候选已启用')
        assert store.view()['evidence_id']!=old
        page.locator('#reason').fill('本片段暂撤回，保留版本与审核依据。')
        page.locator('#withdraw').click()
        expect(page.locator('#state')).to_contain_text('已撤回')
        expect(page.locator('#export')).to_be_disabled()
        page.reload();expect(page.locator('#state')).to_contain_text('已撤回')
        expect(page.locator('#history li')).to_have_count(11)
        page.locator('#revisionReason').fill('以新修订重新开始独立复核。')
        page.locator('#revise').click()
        expect(page.locator('#state')).to_contain_text('内容修订 3')
        expect(page.locator('#enable')).to_be_disabled()
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(destination/f'review-rereview-{width}.png'),full_page=True)
        s=store.view();asset=store.directory/'assets'/(s['content']['source']['image_sha256']+'.png')
        asset.write_bytes(asset.read_bytes()+b'changed')
        page.reload();expect(page.locator('#state')).to_contain_text('材料不可用')
        expect(page.locator('#enable')).to_be_disabled()
        page.locator('#reason').fill('原页素材损坏，立即撤回本地片段。')
        page.locator('#withdraw').click()
        expect(page.locator('#state')).to_contain_text('已撤回')
        assert store.history()[-1]['state']['withdrawn']
        assert not errors,errors
        context.close();browser.close()
