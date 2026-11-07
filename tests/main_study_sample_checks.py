"""Checks for the three bounded public samples, called in the real API bridge test."""
import json
from pathlib import Path

import fitz


def check_chapter_five_samples(main, browser, out, width, errors):
    from playwright.sync_api import expect

    graph = main.locator('#dd-study-route-graph')
    expect(graph.locator('svg g.node')).to_have_count(2)
    expect(graph).to_contain_text('基础回顾')
    expect(graph).to_contain_text('等式的基本性质')
    expect(graph).to_contain_text('解一元一次方程')
    # Click/keyboard graph nodes navigate to the existing source cards, not chat.
    graph.get_by_role('button', name='查看参考：等式的基本性质').focus()
    main.keyboard.press('Enter')
    assert '等式的基本性质' in main.evaluate('document.activeElement.textContent')
    graph.screenshot(path=str(out / f'route-sample-{width}.png'))
    main.locator('#dd-study-classroom-open').click()
    main.locator('#dd-lesson-concept').select_option('g7-equality')
    main.locator('#dd-lesson-next').click()
    expect(main.locator('#dd-lesson-sources')).to_contain_text('116')
    expect(main.locator('#dd-equality-apply')).to_be_disabled()
    cases = []
    for mode in ('both', 'left'):
        main.locator('#dd-equality-mode').select_option(mode)
        for delta in range(-6, 7):
            main.locator('#dd-equality-amount').evaluate('(e,n)=>{e.value=n;e.dispatchEvent(new Event("input"))}', delta)
            expect(main.locator('#dd-equality-apply')).to_be_disabled()
            # Always predict equality so the mismatch explanation is tested too.
            main.locator('#dd-equality-prediction').select_option('equal')
            main.locator('#dd-equality-apply').click()
            result = main.locator('#dd-equality-result').inner_text()
            left, right = 6 + delta, 6 + delta if mode == 'both' else 6
            assert f'左边：6 + ({delta}) = {left}' in result
            assert ('两边仍然相等' if left == right else '两边不再相等') in result
            assert ('与预测一致' if left == right else '与预测不同') in result
            if delta == 0:
                assert '加 0 没有改变数值' in result
            cases.append({'mode': mode, 'delta': delta, 'left': left, 'right': right})
    main.locator('#dd-study-classroom').screenshot(path=str(out / f'equality-{width}.png'))
    assert not main.locator('#dd-study-classroom').evaluate('(e)=>e.scrollWidth>e.clientWidth')
    main.locator('#dd-study-classroom').get_by_role('button', name='关闭课堂').click()
    main.locator('#dd-study-material').fill('PRIVATE_SAMPLE_INPUT <script>alert(1)</script>')
    main.locator('#dd-study-topic').fill('PRIVATE_SAMPLE_TOPIC')
    with main.expect_download() as download:
        main.locator('#dd-study-classroom-download').click()
    offline_file = out / f'equality-classroom-{width}.html'
    download.value.save_as(offline_file)
    # Both downloads must exclude hand-entered fields and every identity field.
    forbidden = ('PRIVATE_SAMPLE', 'family-g7', 'synthetic-parent', 'account_id', 'learner_id', 'context_version')
    assert all(s not in offline_file.read_text() for s in forbidden)
    offline_context = browser.new_context(viewport={'width': width, 'height': 1000}, offline=True)
    page = offline_context.new_page(); requests = []
    page.on('request', lambda r: requests.append(r.url))
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(offline_file.resolve().as_uri())
    page.locator('#dd-lesson-concept').select_option('g7-equality')
    page.locator('#dd-lesson-next').click()
    page.locator('#dd-equality-amount').evaluate('(e)=>{e.value=-6;e.dispatchEvent(new Event("input"))}')
    page.locator('#dd-equality-prediction').select_option('equal')
    page.locator('#dd-equality-apply').click()
    expect(page.locator('#dd-equality-result')).to_contain_text('两边仍然相等')
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    main.locator('#dd-study-review-open').click()
    expect(main.locator('#dd-study-review')).to_contain_text('等式性质与解方程')
    expect(main.locator('#dd-study-review .dd-review-sheet')).to_have_count(3)
    # Test the print path with the browser print dialog stubbed, inspect only
    # the isolated frame sent to print. No hidden chat/profile content may leak.
    main.evaluate("""() => {
        window.__samplePrintCalls=0;
        const create=Document.prototype.createElement;
        Document.prototype.createElement=function(...args) {
            const e=create.apply(this,args);
            if(args[0]==='iframe') e.addEventListener('load',()=>{e.contentWindow.print=()=>window.__samplePrintCalls++},true);
            return e;
        };
        window.__restorePrintProbe=()=>{Document.prototype.createElement=create};
    }""")
    main.locator('#dd-review-print').click()
    main.wait_for_function('window.__samplePrintCalls === 1')
    main.evaluate('window.__restorePrintProbe()')
    frame = main.frame_locator('iframe[title="仅公开复习卡的打印页面"]')
    expect(frame.locator('.dd-review-sheet')).to_have_count(3)
    print_text = frame.locator('body').inner_text()
    assert all(s not in print_text for s in forbidden)
    with main.expect_download() as download:
        main.locator('#dd-review-download').click()
    review_file = out / f'chapter-review-{width}.html'; download.value.save_as(review_file)
    assert all(s not in review_file.read_text() for s in forbidden)
    page.goto(review_file.resolve().as_uri())
    expect(page.locator('.dd-review-sheet')).to_have_count(3)
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    page.screenshot(path=str(out / f'review-{width}.png'), full_page=True)
    page.pdf(path=str(out / f'chapter-review-{width}.pdf'), prefer_css_page_size=True, print_background=True)
    pdf = fitz.open(out / f'chapter-review-{width}.pdf')
    assert len(pdf) == 3
    text = '\n'.join(p.get_text() for p in pdf).replace(' ', '')
    for phrase in ('等式性质与解方程', 'x+3−3=9−3', 'x=6', '116', '128', '回到出处'):
        assert phrase in text, phrase
    assert all(s not in text for s in forbidden)
    links = [link.get('uri', '') for p in pdf for link in p.get_links()]
    assert any(u.startswith('https://book.pep.com.cn/') for u in links)
    assert any('508748a2c8dddc1253100b2d10d91c9526903f67' in u for u in links)
    for index, p in enumerate(pdf):
        # The entire printed text bounding box must stay inside A4 margins.
        for block in p.get_text('blocks'):
            assert block[0] >= 35 and block[1] >= 35 and block[2] <= p.rect.width - 35 and block[3] <= p.rect.height - 35
        if width == 1280:
            p.get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(out / f'review-page-{index+1}.png')
    assert not any(u.startswith(('https:', 'http:')) for u in requests)
    offline_context.close()
    main.locator('#dd-study-review').get_by_role('button', name='关闭复习').click()
    # A soft relationship is explicitly drawn differently from a hard one.
    main.locator('#dd-study-route-concept').select_option('g7-model')
    expect(graph.locator('svg g.node')).to_have_count(2)
    expect(graph.locator('.edgeLabel')).to_contain_text('辅助联系')
    main.locator('#dd-study-route-concept').select_option('g7-solve')
    (out / f'samples-{width}.json').write_text(json.dumps({
        'equation_cases': cases, 'prediction_required': True, 'pdf_pages': len(pdf),
        'pdf_links': links, 'offline_http_requests': 0, 'public_only_exports': True,
        'isolated_print_frame': True, 'graph_keyboard_navigation': True,
        'hard_soft_edges_distinguished': True}, ensure_ascii=False, indent=2))
