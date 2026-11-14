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
def test_challenge_interactions_in_family_browser(family, textbook_sources, playwright, launch_browser, tmp_path, monkeypatch, width):
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
        representatives={'math-g2-upper':'4','math-g7-upper':'2','math-g7-lower':'8','biology-g7-upper':'7','history-g7-upper':'5'}
        questions=chapter.bank('challenge_variety')
        def encoded(f):return ','.join(sorted(f['answer'].split(','),key=int)) if f['kind']=='multi' else f['answer']
        def fill(f):
            field=page.locator('#practiceResponse-'+f['id']);group=field.locator('..')
            if f['kind']=='multi':
                selected=set(f['answer'].split(','))
                for i in range(1,len(f['options'])+1):group.locator('input[type=checkbox][value="'+str(i)+'"]').set_checked(str(i) in selected)
            elif f['kind']=='order':
                expected=f['answer'].split(',')
                # Explicit identity confirmation records an answer but reveals none.
                group.locator('.confirm-order').click()
                for target,n in enumerate(expected):
                    current=field.input_value().split(',');position=current.index(n)
                    while position>target:
                        group.locator('.order-card').nth(position).locator('button').first.click();position-=1
            elif f['options']:field.select_option(f['answer'])
            else:field.fill(f['answer'])
        for book in sorted({q['book_id'] for q in questions.values()},key=lambda b:(int(b.split('-g')[1][0]),b)):
            q=next(q for q in questions.values() if q['book_id']==book and q['chapter_id']==representatives.get(book,'1'))
            grade=q['grade'];ch=q['chapter_id']
            page.locator(f'.profile-card[data-grade="{grade}"]').click()
            page.locator('#textbookSubject').select_option(book.split('-')[0])
            page.locator('#textbookBook').select_option(book)
            page.locator('#textbookChapter').select_option(ch)
            page.locator('#homeDifficulty').select_option('challenge')
            expect(page.locator('#practiceChoices button').filter(has_text=q['title'])).to_have_count(1)
            page.locator('#practicePicker').evaluate('(n)=>n.open=true')
            page.locator('#practiceChoices button').filter(has_text=q['title']).click()
            expect(page.locator('#questionVersion')).to_have_value(q['id'])
            expect(page.locator('#questionBadge')).to_contain_text('挑战')
            expect(page.locator('#practiceDifficulty')).to_have_value('challenge')
            for f in q['responses']:
                if f['kind']=='order':expect(page.locator('#practiceResponse-'+f['id'])).to_have_value('')
            deep=book in ('chinese-g2-lower','math-g2-upper')
            if deep:
                fill(q['responses'][0])
                page.reload()
                expect(page.locator('#testPrompt')).to_have_text(q['prompt'],timeout=12000)
                expect(page.locator('#practiceResponse-'+q['responses'][0]['id'])).to_have_value(encoded(q['responses'][0]))
                page.locator('#submitAnswer').click()
                expect(page.locator('#testStatus')).to_contain_text('请完成每一项')
            for f in q['responses']:fill(f)
            if deep:
                page.locator('#requestHint').click()
                expect(page.locator('#gameHint')).to_be_visible()
                page.reload()
                expect(page.locator('#gameHint')).to_be_visible(timeout=12000)
                for f in q['responses']:expect(page.locator('#practiceResponse-'+f['id'])).to_have_value(encoded(f))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),book
            folder=Path('learning_data/verification/challenge-tier-20261111/review/browser');folder.mkdir(parents=True,exist_ok=True)
            page.locator('#testSection').screenshot(path=str(folder/f'{book}-{width}.png'))
            incorrect=book=='chinese-g2-lower'
            if incorrect:
                f=next(f for f in q['responses'] if f['kind']=='multi')
                extra=next(str(i) for i in range(1,len(f['options'])+1) if str(i) not in f['answer'].split(','))
                page.locator('#practiceResponse-'+f['id']).locator('..').locator('input[type=checkbox][value="'+extra+'"]').check()
            title='值得再研究' if incorrect else '答对'
            page.locator('#submitAnswer').click()
            expect(page.locator('#feedbackTitle')).to_contain_text(title,timeout=15000)
            assert page.locator('#practiceResponses input:enabled:not([type=hidden]),#practiceResponses select:enabled,#practiceResponses button:enabled').count()==0
            if deep:
                page.reload()
                expect(page.locator('#feedbackTitle')).to_contain_text(title,timeout=12000)
            if incorrect:
                page.locator('#previewCollection').click()
                expect(page.locator('#collectionDialog')).to_be_visible()
                # Answers in collections use labels and arrows, not raw index strings.
                for f in q['responses']:
                    if f['options']:
                        for n in f['answer'].split(','):expect(page.locator('#collectionAnswer')).to_contain_text(f['options'][int(n)-1])
                page.locator('#confirmCollection').click()
                expect(page.locator('#collectionStatus')).to_contain_text('已保存')
            page.locator('#changeChapter').click()
        assert not errors,errors
        context.close();browser.close()
