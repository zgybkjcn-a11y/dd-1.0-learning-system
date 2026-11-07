import hashlib
import json

import pytest

from scripts.import_family_textbooks import verified_ocr_pages


def artifact(tmp_path):
    pages = ['13=4×3+1', '11盒酸奶，每4盒装一袋。']
    check = {'status':'verified','method':'independent_review','reviewer':'synthetic',
             'evidence':'synthetic independent review, not actual textbook approval'}
    report = {'pdf_sha256':'a'*64, 'usage':'reference_only', 'pages':[
        {'page_number':i, 'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
         'transcription_review':dict(check), 'content_review':dict(check), 'unresolved_issues':[]}
        for i,text in enumerate(pages,1)]}
    record = {'sha256':'a'*64,'ocr_review_status':'all_pages_verified','ocr_review_report':'review.json'}
    return record, pages, report


def save(tmp_path, record, report):
    raw = json.dumps(report).encode()
    (tmp_path/'review.json').write_bytes(raw)
    record['ocr_review_report_sha256'] = hashlib.sha256(raw).hexdigest()


def test_flag_alone_cannot_import_ocr(tmp_path):
    record,pages,_ = artifact(tmp_path)
    assert not verified_ocr_pages(record,pages,tmp_path)


@pytest.mark.parametrize('change', ['none','content_unchecked','one_missing','reordered','edited',
                                  'source_changed','open_issue','ocr_self_check','report_changed'])
def test_every_page_requires_bound_transcription_and_independent_content_review(tmp_path,change):
    record,pages,report = artifact(tmp_path)
    if change == 'content_unchecked': report['pages'][1]['content_review']['status']='needs_review'
    if change == 'one_missing': report['pages'].pop()
    if change == 'reordered': pages.reverse()
    if change == 'edited': pages[0]='13=4×3+2'
    if change == 'source_changed': record['sha256']='b'*64
    if change == 'open_issue': report['pages'][0]['unresolved_issues']=['lost diagram']
    if change == 'ocr_self_check': report['pages'][0]['content_review']['method']='repeat_ocr'
    save(tmp_path,record,report)
    if change == 'report_changed': (tmp_path/'review.json').write_text('{}')
    assert verified_ocr_pages(record,pages,tmp_path) is (change=='none')
