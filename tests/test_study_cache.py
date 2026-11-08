"""Cache correctness uses synthetic bytes and actual current filesystem metadata."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import os
import threading
import time

import fitz
import pytest

from learning_service import textbooks, textbook_cache
from test_family_math import family
from test_math_references import reference_family
from test_readonly_study_tools import chat_tools
from test_runtime_passages import stack, runtime_bundle, search, detail, reseal


@pytest.fixture
def pdf(tmp_path, monkeypatch):
    path=tmp_path/'math-g7-upper.pdf'
    with fitz.open() as doc:
        for n in range(2):
            page=doc.new_page(width=200,height=200);page.insert_text((20,40),f'Synthetic page {n}')
        path.write_bytes(doc.tobytes(no_new_id=True)+b'\n%AAAA\n')
    monkeypatch.setitem(textbooks.PDF_SHA256,path.stem,hashlib.sha256(path.read_bytes()).hexdigest())
    textbooks.clear_page_cache()
    yield path
    textbooks.clear_page_cache()


def render(pdf, page=1):
    return textbooks.render_page(pdf.parent,pdf.stem,page)


def test_warm_page_skips_hash_and_render_but_checks_current_file(pdf,monkeypatch):
    first=render(pdf)
    def forbidden(*a,**kw):raise AssertionError('cached page rehashed or rerendered')
    monkeypatch.setattr(textbook_cache.hashlib,'sha256',forbidden)
    monkeypatch.setattr(textbooks,'_render_pdf',forbidden)
    assert render(pdf)==first
    pdf.unlink()
    with pytest.raises((OSError,ValueError)):render(pdf)


@pytest.mark.parametrize('change',['same_size_same_mtime','replace_inode','pin','symlink','parent_symlink'])
def test_warm_cache_cannot_hide_source_changes(pdf,change,monkeypatch,tmp_path):
    render(pdf); raw=pdf.read_bytes(); before=pdf.stat()
    if change=='same_size_same_mtime':
        pdf.write_bytes(raw[:-5]+b'BBBB\n');os.utime(pdf,ns=(before.st_atime_ns,before.st_mtime_ns))
        assert pdf.stat().st_size==before.st_size and pdf.stat().st_mtime_ns==before.st_mtime_ns
    elif change=='replace_inode':
        other=tmp_path/'replacement.pdf';other.write_bytes(raw+b'changed');other.replace(pdf)
    elif change=='pin':monkeypatch.setitem(textbooks.PDF_SHA256,pdf.stem,'0'*64)
    elif change=='symlink':
        other=tmp_path/'outside.pdf';pdf.rename(other);pdf.symlink_to(other)
    else:
        linked=tmp_path/'linked';linked.symlink_to(tmp_path,target_is_directory=True)
        pdf=linked/pdf.name
    with pytest.raises((OSError,ValueError)):render(pdf)


def test_new_valid_source_and_pin_get_new_pixels(pdf,monkeypatch):
    before=render(pdf)
    with fitz.open() as doc:
        p=doc.new_page(width=220,height=220);p.insert_text((20,40),'New synthetic version')
        pdf.write_bytes(doc.tobytes())
    monkeypatch.setitem(textbooks.PDF_SHA256,pdf.stem,hashlib.sha256(pdf.read_bytes()).hexdigest())
    assert render(pdf)!=before


def test_concurrent_identical_misses_render_once_and_hits_avoid_native_lock(pdf,monkeypatch):
    calls=[];original=textbooks._render_pdf
    def measured(*args):calls.append(1);time.sleep(.02);return original(*args)
    monkeypatch.setattr(textbooks,'_render_pdf',measured)
    with ThreadPoolExecutor(max_workers=4) as pool: images=list(pool.map(lambda _:render(pdf),range(4)))
    assert len(calls)==1 and len(set(images))==1
    with textbooks._RENDER_LOCK:
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(render,pdf).result(timeout=1)==images[0]


def test_source_change_during_render_is_rejected_and_not_cached(pdf,monkeypatch):
    original=textbooks._render_pdf
    def changed(*args):
        result=original(*args);pdf.write_bytes(pdf.read_bytes()+b'changed');return result
    monkeypatch.setattr(textbooks,'_render_pdf',changed)
    with pytest.raises(ValueError):render(pdf)
    with pytest.raises(ValueError):render(pdf)


def test_cache_byte_and_entry_limits_evict_oldest():
    cache=textbook_cache.ByteCache(max_bytes=5,max_entries=2)
    cache.put('a',b'aa',2);cache.put('b',b'bb',2)
    assert cache.get('a')==b'aa'
    cache.put('c',b'cc',2)
    assert cache.get('b') is None and cache.byte_size==4
    cache.put('large',b'123456',6)
    assert cache.get('large') is None and cache.byte_size<=5
    cache.clear();assert cache.byte_size==0


def test_cached_source_never_caches_withdrawal_or_access(stack):
    response=search(stack);old=response.json()['passage_result']['items'][0]
    assert detail(stack,old).status_code==200
    stack['manifest']['passages'][1]['enabled']=False;reseal(stack)
    assert detail(stack,old).status_code==404
    assert not search(stack).json()['passage_result']['items']
    path='/learning/api/v1/textbooks/math-g7-upper/pages/31/image'
    assert stack['gateway'].get(path,headers=stack['headers']).status_code==200
    with stack['db'].session(write=True) as conn:
        conn.execute("DELETE FROM learner_access WHERE learner_id='family-g7'")
    assert stack['gateway'].get(path,headers=stack['headers']).status_code!=200


def test_cached_page_rechecks_context_after_material_read(stack,monkeypatch):
    from learning_service import study_routes
    path='/learning/api/v1/textbooks/math-g7-upper/pages/31/image'
    assert stack['gateway'].get(path,headers=stack['headers']).status_code==200
    original=study_routes.render_textbook_page
    def changed(*args):
        result=original(*args)
        with stack['db'].session(write=True) as conn:conn.execute('UPDATE account_contexts SET revision=revision+1')
        return result
    monkeypatch.setattr(study_routes,'render_textbook_page',changed)
    assert stack['gateway'].get(path,headers=stack['headers']).status_code==409
