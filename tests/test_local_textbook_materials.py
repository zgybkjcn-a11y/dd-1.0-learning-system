"""Opt-in checks of supplied PDFs; never required by the synthetic test suite."""
import hashlib
from pathlib import Path

import fitz
import pytest

from learning_service.math_references import load_reference
from learning_service.textbooks import PDF_SHA256

pytestmark = pytest.mark.local_materials


@pytest.mark.parametrize('book_id', ['math-g2-upper', 'math-g7-upper'])
def test_local_reference_pdf_identity_and_page_extent(pytestconfig, book_id):
    directory = pytestconfig.getoption('--textbook-dir')
    if not directory:
        pytest.fail('Local material checks require --textbook-dir; no default private directory is read', pytrace=False)
    path = Path(directory) / (book_id + '.pdf')
    assert path.is_file() and not path.is_symlink(), 'Supply the actual version-bound PDF'
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == PDF_SHA256[book_id]
    reference = load_reference()
    with fitz.open(stream=data, filetype='pdf') as doc:
        pages = {p['pdf_page'] for c in reference['concepts'].values() if c['book_id'] == book_id for p in c['textbook_pages']}
        assert pages and max(pages) <= doc.page_count
        for number in pages:
            pix = doc[number - 1].get_pixmap()
            assert pix.width > 0 and pix.height > 0
