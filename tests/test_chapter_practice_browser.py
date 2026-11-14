"""Real family UI selection, answer recovery and grading across subject batches."""
from dataclasses import replace
from urllib.parse import urlsplit
import json
import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from learning_service.app import create_app, run_worker_once
from learning_service.browser_auth import SESSION_COOKIE
from learning_service import chapter_practice as chapter
from learning_service.practice import install
from test_browser_auth import assertion
from test_family_math import family

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width', [1280, 390])
def test_chapter_batches_in_family_browser(family, textbook_sources, playwright, launch_browser, tmp_path, monkeypatch, width):
    _, db, original, _ = family
    from learning_service.textbooks import PDF_SHA256
    synthetic = tmp_path / 'banks'
    synthetic.mkdir()
    digests = {}
    for name in chapter.BATCHES:
        filename = 'family_chapter_' + name + '_v1.json'
        data = json.loads((chapter.DATA / filename).read_bytes())
        for q in data['questions']:
            q['source']['textbook_sha256'] = PDF_SHA256[q['book_id']]
        raw = json.dumps(data, ensure_ascii=False).encode()
        (synthetic / filename).write_bytes(raw)
        digests[name] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(chapter, 'DATA', synthetic)
    monkeypatch.setattr(chapter, 'BATCHES', digests)
    from learning_service import practice_coverage, subject_coverage
    from learning_service.practice import bank as original_bank
    from learning_service.reserve_practice import bank as reserve_bank
    all_questions = original_bank() | reserve_bank() | chapter.bank()
    for coverage in (practice_coverage, subject_coverage):
        plan = json.loads(coverage.PATH.read_bytes())
        plan['pdf_sha256'] = {key: PDF_SHA256[key] for key in plan['pdf_sha256']}
        for row in plan['rows']:
            for mapping in row['mappings']:
                raw = json.dumps(all_questions[mapping['question_version_id']], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                mapping['question_sha256'] = hashlib.sha256(raw).hexdigest()
        plan_raw = json.dumps(plan).encode(); plan_path = tmp_path/(coverage.__name__+'.json'); plan_path.write_bytes(plan_raw)
        monkeypatch.setattr(coverage, 'PATH', plan_path)
        monkeypatch.setattr(coverage, 'SHA256', hashlib.sha256(plan_raw).hexdigest())
    install(db)
    for batch in chapter.BATCHES:
        chapter.install(db, batch)
    origin = 'https://chapters.example.invalid'
    settings = replace(original.app.state.settings, browser_auth_enabled=True,
                       browser_auth_secret='synthetic-gateway-key-0123456789abcdef',
                       browser_auth_issuer='synthetic-gateway', browser_identity_issuer='family-pilot-webui',
                       browser_origin=origin, public_base_path='/learning', shared_learner_context_enabled=True,
                       family_setup_code='synthetic-family-code-0123456789abcdef',
                       textbook_dir=textbook_sources)
    api = TestClient(create_app(settings, db), base_url=origin)
    assert api.post('/api/v1/auth/session', headers={'Origin': origin,
                    'Authorization': 'Bearer ' + assertion(settings, changes={'sub': 'synthetic-parent'})}).status_code == 201
    with playwright.sync_playwright() as runtime:
        browser = launch_browser(runtime)
        context = browser.new_context(viewport={'width': width, 'height': 960}, service_workers='block')
        context.add_cookies([{'name': k, 'value': v, 'url': origin, 'secure': True,
                             'httpOnly': k == SESSION_COOKIE, 'sameSite': 'Strict'} for k, v in api.cookies.items()])
        errors = []

        def handle(route):
            url = urlsplit(route.request.url)
            assert url.scheme + '://' + url.netloc == origin
            path = url.path.removeprefix('/learning')
            if '/api/v1/attempts/' in path and route.request.method == 'GET':
                run_worker_once(db, settings)
            response = api.request(route.request.method, path, headers=route.request.all_headers(),
                                   content=route.request.post_data_buffer, follow_redirects=False)
            route.fulfill(status=response.status_code, body=response.content,
                          headers={k: v for k, v in response.headers.items() if k not in ('content-length', 'set-cookie')})

        context.route('**/*', handle)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(origin + '/learning/ui')
        expect = playwright.expect
        varieties = {k:q for batch in ('math_g7_multistep','upper_variety','remaining_variety') for k,q in chapter.bank(batch).items()}
        books = sorted({q['book_id'] for q in varieties.values()}, key=lambda b:(int(b.split('-g')[1][0]),b))
        if os.environ.get('OTHER_VARIETY_BOOKS'):
            books = [b for b in books if b in os.environ['OTHER_VARIETY_BOOKS'].split(',')]
        for book in books:
            q = next(q for q in varieties.values() if q['book_id']==book)
            grade = q['grade']; ch = q['chapter_id']
            page.locator(f'.profile-card[data-grade="{grade}"]').click()
            page.locator('#textbookSubject').select_option(book.split('-')[0])
            page.locator('#textbookBook').select_option(book)
            page.locator('#textbookChapter').select_option(ch)
            from learning_service.practice import bank as word_bank
            count = sum(v['book_id']==book and v['chapter_id']==ch for v in (chapter.bank()|word_bank()).values())
            expect(page.locator('#practiceChoices button')).to_have_count(count)
            expect(page.locator('#scopeChallenge')).to_be_enabled()
            if book == 'math-g7-upper':
                expect(page.locator('#coveragePlan')).to_be_visible()
                page.locator('#coveragePlan').evaluate('(node) => node.open = true')
                expect(page.locator('#coverageSummary')).to_contain_text('项达到两种题型目标')
                expect(page.locator('#coverageSummary')).to_contain_text('项需人工表达或操作核对')
                expect(page.locator('#coverageRows')).to_contain_text('辅助练习')
                expect(page.locator('#coverageRows')).to_contain_text('独立表达与操作任务')
            else:
                expect(page.locator('#coveragePlan')).to_be_visible()
                page.locator('#coveragePlan').evaluate('(node) => node.open = true')
                expect(page.locator('#coverageRows')).to_contain_text('待人工练习与核对')
                expect(page.locator('#coverageRows')).to_contain_text('独立表达与操作任务')
            page.locator('#homeDifficulty').select_option('auto')
            page.locator('#practicePicker').evaluate('(node) => node.open = true')
            page.locator('#practiceChoices button').filter(has_text=q['title']).click()
            expect(page.locator('#questionVersion')).to_have_value(q['id'])
            expect(page.locator('#testPrompt')).to_have_text(q['prompt'])
            expect(page.locator('#questionCredit')).to_contain_text('自编章节练习')
            expect(page.locator('#singleAnswerLabel')).to_be_hidden()
            first=q['responses'][0]
            field=page.locator('#practiceResponse-'+first['id'])
            if first['options']: field.select_option(first['answer'])
            else: field.fill(first['answer'])
            page.reload()
            expect(page.locator('#testPrompt')).to_have_text(q['prompt'], timeout=12000)
            expect(page.locator('#practiceResponse-'+first['id'])).to_have_value(first['answer'])
            page.locator('#submitAnswer').click()
            expect(page.locator('#testStatus')).to_contain_text('请完成每一项')
            for f in q['responses']:
                field=page.locator('#practiceResponse-'+f['id'])
                if f['options']: field.select_option(f['answer'])
                else: field.fill(f['answer'])
            overflow=page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1 && e.getBoundingClientRect().width>0).map(e=>({tag:e.tagName,id:e.id,right:e.getBoundingClientRect().right,text:e.textContent.slice(0,80)})).slice(0,10)""")
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), (book,overflow)
            if os.environ.get('OTHER_VARIETY_ARTIFACTS'):
                path=Path(os.environ['OTHER_VARIETY_ARTIFACTS']);path.mkdir(parents=True,exist_ok=True)
                page.locator('#testSection').screenshot(path=str(path/f'{book}-{width}.png'))
            page.locator('#submitAnswer').click()
            expect(page.locator('#feedbackTitle')).to_contain_text('答对', timeout=15000)
            page.locator('#changeChapter').click()
        page.locator('.profile-card[data-grade="2"]').click()
        page.locator('#textbookSubject').select_option('math')
        page.locator('#textbookBook').select_option('math-g2-upper')
        page.locator('#textbookChapter').select_option('4')
        expect(page.locator('#practiceChoices button')).to_have_count(34)
        page.locator('#coveragePlan').evaluate('(node) => node.open = true')
        expect(page.locator('#coverageRows')).to_contain_text('辅助练习')
        expect(page.locator('#coverageRows')).to_contain_text('画指定长度线段并测量验证 · 待人工练习与核对')
        manual=page.locator('#coverageRows details').filter(has_text='自己画4厘米线段')
        manual.locator('summary').click()
        expect(manual).to_contain_text('实际测量记录不得用理论4替换')
        page.locator('#textbookChapter').select_option('activity2')
        expect(page.locator('#coverageRows')).to_contain_text('用校准后的身体尺测量 · 待人工练习与核对')
        expect(page.locator('#coverageSummary')).to_contain_text('在线配题 1/1 项')
        page.locator('#textbookChapter').select_option('4')
        expect(page.locator('#textbookChapter')).to_be_enabled()
        expect(page.locator('#practiceChoices button')).to_have_count(34)
        page.locator('#practicePicker').evaluate('(node) => node.open = true')
        page.locator('#practiceChoices button').filter(has_text='右端刻度不等于长度').click()
        qid = page.locator('#questionVersion').input_value()
        q = chapter.bank('math_g2_depth')[qid]
        expect(page.locator('#testPrompt')).to_have_text(q['prompt'])
        page.locator('#answer').fill(q['answer'])
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对', timeout=15000)
        page.locator('#changeChapter').click()
        page.locator('#homeDifficulty').select_option('normal')
        page.locator('#practicePicker').evaluate('(node) => node.open = true')
        page.locator('#practiceChoices button').filter(has_text='起点不同也能比').click()
        qid = page.locator('#questionVersion').input_value()
        q = chapter.bank('math_g2_challenge')[qid]
        assert q['title'] == '起点不同也能比'
        expect(page.locator('#practiceVisual')).to_be_visible()
        expect(page.locator('#practiceVisual svg')).to_have_count(1)
        expect(page.locator('#questionBadge')).to_contain_text('看图测量')
        page.reload()
        expect(page.locator('#practiceVisual svg')).to_have_count(1)
        expect(page.locator('#testPrompt')).to_have_text(q['prompt'])
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        if os.environ.get('G2_REVIEW_ARTIFACTS'):
            path = Path(os.environ['G2_REVIEW_ARTIFACTS']); path.mkdir(parents=True, exist_ok=True)
            page.locator('#practiceVisual').screenshot(path=str(path/f'ruler-{width}.png'))
        page.locator('#answer').fill(q['answer'])
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对', timeout=15000)
        page.locator('#changeChapter').click()
        page.locator('#textbookChapter').select_option('1')
        page.locator('#homeDifficulty').select_option('normal')
        page.locator('#practicePicker').evaluate('(node) => node.open = true')
        page.locator('#practiceChoices button').filter(has_text='分类表缺了一格').click()
        expect(page.locator('#practiceVisual table')).to_be_visible()
        expect(page.locator('#practiceVisual')).to_contain_text('红色')
        q = chapter.bank('math_g2_challenge')[page.locator('#questionVersion').input_value()]
        page.locator('#answer').fill(q['answer'])
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对', timeout=15000)
        page.locator('#changeChapter').click()
        page.locator('#textbookChapter').select_option('activity1')
        page.locator('#homeDifficulty').select_option('hard')
        page.locator('#practicePicker').evaluate('(node) => node.open = true')
        page.locator('#practiceChoices button').filter(has_text='避开中间的道路').click()
        expect(page.locator('#practiceVisual')).to_contain_text('体育馆')
        if os.environ.get('G2_REVIEW_ARTIFACTS'):
            page.locator('#practiceVisual').screenshot(path=str(Path(os.environ['G2_REVIEW_ARTIFACTS'])/f'campus-{width}.png'))
        q = chapter.bank('math_g2_challenge')[page.locator('#questionVersion').input_value()]
        assert q['title'] == '避开中间的道路'
        page.locator('#answer').fill(q['answer'])
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对', timeout=15000)
        page.locator('#changeChapter').click()
        plain=next(v for v in chapter.bank('math_g2_challenge').values() if v['chapter_id']=='activity1' and 'visual' not in v)
        page.locator('#practicePicker').evaluate('(node) => node.open = true')
        page.locator('#practiceChoices button').filter(has_text=plain['title']).click()
        expect(page.locator('#practiceVisual')).to_be_hidden()
        assert page.locator('#questionVersion').input_value() != q['id']
        page.locator('#answer').fill(plain['answer'])
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对',timeout=15000)
        # Same-family numeric variants cannot monopolize the next task. Use
        # synthetic choices to isolate the scheduler from authored ordering.
        chosen = page.evaluate("""() => {
          const old = {gameBook,gameChoices,gameDifficulty,gameCompletedChoices};
          try {
            gameBook='english-g7-upper'; gameDifficulty='normal';
            gameChoices=[{question_version_id:'done',practice:{difficulty:'normal',task_family:'same'}},
              {question_version_id:'variant',practice:{difficulty:'normal',task_family:'same',selection_priority:1}},
              {question_version_id:'fresh',practice:{difficulty:'normal',task_family:'different'}}];
            gameCompletedChoices=new Set(['done']); return gameNextChoice().question_version_id;
          } finally { ({gameBook,gameChoices,gameDifficulty,gameCompletedChoices}=old); }
        }""")
        assert chosen == 'fresh'
        # Recommendations never send a learner into an unavailable tier.
        fallback=page.evaluate("""() => {
          const old={gameBook,gameChapter,gameChoices,gameDifficulty,gameGuidance,gameCompletedChoices};
          try {
            gameBook='chinese-g7-lower';gameChapter='1';gameDifficulty='auto';gameCompletedChoices=new Set();
            gameGuidance={'chinese-g7-lower|1':{difficulty:'hard',streak:0,reason:'synthetic promotion'}};
            gameChoices=[{question_version_id:'normal-task',practice:{difficulty:'normal',task_family:'reading'}}];
            return {guide:difficultyGuidance(),next:gameNextChoice().question_version_id};
          } finally { ({gameBook,gameChapter,gameChoices,gameDifficulty,gameGuidance,gameCompletedChoices}=old); }
        }""")
        assert fallback['guide']['difficulty']=='normal' and fallback['next']=='normal-task'
        assert '暂未配置困难题' in fallback['guide']['reason']
        # Structured fields survive draft reload/hints, grade together, and clear on scope changes.
        page.locator('#changeChapter').click()
        page.locator('#textbookChapter').select_option('4')
        page.locator('#homeDifficulty').select_option('normal')
        page.locator('#practicePicker').evaluate('(node) => node.open = true')
        page.locator('#practiceChoices button').filter(has_text='分别测量再比较').click()
        expect(page.locator('#questionVersion')).to_have_value('family-chapter-math-g2-upper-4-multistep-two-lengths-v1')
        q = chapter.bank('math_g2_multistep')[page.locator('#questionVersion').input_value()]
        assert q['title'] == '分别测量再比较'
        expect(page.locator('#singleAnswerLabel')).to_be_hidden()
        expect(page.locator('#practiceResponses input')).to_have_count(3)
        page.locator('#practiceResponse-a').fill('5')
        page.reload()
        expect(page.locator('#practiceResponse-a')).to_have_value('5')
        expect(page.locator('#practiceResponse-b')).to_have_value('')
        page.locator('#submitAnswer').click()
        expect(page.locator('#testStatus')).to_contain_text('请完成每一项')
        page.locator('#requestHint').click()
        expect(page.locator('#gameHint')).to_be_visible()
        expect(page.locator('#practiceResponse-a')).to_have_value('5')
        page.locator('#practiceResponse-b').fill('6')
        page.locator('#practiceResponse-c').fill('1')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        if os.environ.get('G2_MULTISTEP_ARTIFACTS'):
            path=Path(os.environ['G2_MULTISTEP_ARTIFACTS']);path.mkdir(parents=True,exist_ok=True)
            page.locator('#testSection').screenshot(path=str(path/f'fields-{width}.png'))
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对',timeout=15000)
        page.reload()
        expect(page.locator('#savedPracticeAnswer')).to_contain_text('甲长几厘米：5', timeout=15000)
        expect(page.locator('#practiceResponse-a')).to_have_value('5')
        expect(page.locator('#practiceResponse-a')).to_be_disabled()
        page.locator('#changeChapter').click()
        page.locator('#textbookChapter').select_option('activity1')
        page.locator('#homeDifficulty').select_option('normal')
        page.locator('#scopeChallenge').click()
        expect(page.locator('#practiceResponses select')).to_have_count(2)
        page.locator('#practiceResponse-a').select_option('1')
        page.locator('#practiceResponse-b').select_option('4')
        page.reload()
        expect(page.locator('#practiceResponse-b')).to_have_value('4')
        page.locator('#submitAnswer').click()
        expect(page.locator('#feedbackTitle')).to_contain_text('答对',timeout=15000)
        page.locator('#changeChapter').click()
        page.locator('#textbookChapter').select_option('1')
        page.locator('#homeDifficulty').select_option('hard')
        page.locator('#scopeChallenge').click()
        expect(page.locator('#questionVersion')).to_have_value('family-chapter-math-g2-upper-1-multistep-changed-cards-v1')
        q = chapter.bank('math_g2_multistep')[page.locator('#questionVersion').input_value()]
        for f in q['responses']:
            page.locator('#practiceResponse-'+f['id']).fill('999' if f['id']=='a' else f['answer'])
        page.locator('#submitAnswer').click()
        expect(page.locator('#gameFeedback')).to_have_attribute('data-outcome','incorrect',timeout=15000)
        expect(page.locator('#solutionText')).to_contain_text('请重看：红色共几张')
        page.locator('#previewCollection').click()
        expect(page.locator('#collectionAnswer')).to_contain_text('红色共几张：999')
        page.locator('#cancelCollection').click()
        page.locator('#changeChapter').click()
        page.locator('.profile-card[data-grade="7"]').click()
        expect(page.locator('#practiceResponses')).to_be_hidden()
        expect(page.locator('#singleAnswerLabel')).not_to_have_attribute('hidden','')
        # New text/number/choice protocol in every book, including private
        # feedback, restoration, human tasks and mobile input modes.
        short_tasks=chapter.bank('subject_knowledge')
        for book in sorted({q['book_id'] for q in short_tasks.values()}):
            q=next(q for q in short_tasks.values() if q['book_id']==book)
            if book=='english-g7-upper':q=next(q for q in short_tasks.values() if q['book_id']==book and q['chapter_id']=='2')
            page.locator(f'.profile-card[data-grade="{q["grade"]}"]').click()
            page.locator('#textbookSubject').select_option(q['subject'])
            page.locator('#textbookBook').select_option(book)
            page.locator('#textbookChapter').select_option(q['chapter_id'])
            page.locator('#homeDifficulty').select_option('auto')
            page.locator('#practicePicker').evaluate('(node) => node.open = true')
            page.locator('#practiceChoices button').filter(has_text=q['title']).click()
            expect(page.locator('#questionVersion')).to_have_value(q['id'])
            expect(page.locator('#testPrompt')).to_have_text(q['prompt'])
            first=q['responses'][0]
            for f in q['responses']:
                field=page.locator('#practiceResponse-'+f['id'])
                if f['kind']=='choice':field.select_option(f['answer'])
                else:
                    expect(field).to_have_attribute('inputmode','text' if f['kind']=='text' else 'decimal')
                    field.fill('is' if book=='english-g7-upper' and f==first else ' '+f['answer'].upper()+' ' if f['kind']=='text' and not f['case_sensitive'] else f['answer'])
            if book=='english-g7-upper':
                page.reload()
                expect(page.locator('#testPrompt')).to_have_text(q['prompt'],timeout=12000)
                expect(page.locator('#practiceResponse-a')).to_have_value('is')
                page.locator('#requestHint').click()
                expect(page.locator('#gameHint')).to_be_visible()
                expect(page.locator('#practiceResponse-a')).to_have_value('is')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
            if os.environ.get('SUBJECT_KNOWLEDGE_ARTIFACTS'):
                path=Path(os.environ['SUBJECT_KNOWLEDGE_ARTIFACTS']);path.mkdir(parents=True,exist_ok=True)
                page.locator('#testSection').screenshot(path=str(path/f'{book}-{width}.png'))
            page.locator('#submitAnswer').click()
            if book=='english-g7-upper':
                expect(page.locator('#gameFeedback')).to_have_attribute('data-outcome','incorrect',timeout=15000)
                expect(page.locator('#solutionText')).to_contain_text('复数主语')
                expect(page.locator('#solutionText')).to_contain_text('下一步')
                page.locator('#previewCollection').click()
                expect(page.locator('#collectionAnswer')).to_contain_text('keys ____：is')
                page.locator('#cancelCollection').click()
            else:expect(page.locator('#feedbackTitle')).to_contain_text('答对',timeout=15000)
            page.locator('#changeChapter').click()
        assert not errors
        browser.close()
