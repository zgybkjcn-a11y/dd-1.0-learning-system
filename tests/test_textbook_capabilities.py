"""Per-book capability status must follow installed facts, never a claim."""
import pytest

from learning_service import chapter_practice as chapter, practice, reserve_practice
from learning_service.textbook_capabilities import book_capabilities
from test_family_math import family


def installed_ids(conn):
    return {row[0] for row in conn.execute(
        "SELECT v.id FROM question_versions v JOIN questions q ON q.id=v.question_id "
        "WHERE v.approval='approved' AND q.approval='approved'")}


@pytest.fixture
def catalogued(family):
    _, db, api, headers = family
    practice.install(db)
    return db, api, headers


def test_capabilities_only_report_installed_books_and_real_counts(catalogued):
    db, _, _ = catalogued
    with db.session() as conn:
        counts = {book: value for book, value in book_capabilities(conn, 'math-g2-v1').items()}
        installed = installed_ids(conn)
        authored = {**chapter.bank(), **practice.bank(), **reserve_practice.bank()}
    # The starter bank only installs here, so those books carry counts and the
    # added lower books have none; no book may borrow another's capability.
    assert counts['math-g2-upper']['installed_questions'] == sum(
        1 for version_id, item in authored.items()
        if item['book_id'] == 'math-g2-upper' and version_id in installed)
    assert counts['math-g2-lower']['installed_questions'] == 0
    assert counts['math-g2-lower']['keyword_search'] is False
    assert '仅原页阅读' in counts['math-g2-lower']['note']
    for book in counts.values():
        assert book['page_reading'] is True
        assert (book['knowledge_mapping'] == 'local_sample') == bool(book['mapped_questions'])


@pytest.mark.parametrize('book', ['math-g2-lower', 'ethics-g2-lower'])
def test_reading_only_books_never_claim_search_or_practice(catalogued, book):
    db, _, _ = catalogued
    with db.session() as conn:
        status = book_capabilities(conn, 'math-g2-v1')[book]
    assert status['keyword_search'] is False and status['installed_questions'] == 0
    assert status['mapped_questions'] == 0 and status['knowledge_mapping'] == 'none'


@pytest.mark.parametrize('questions,mappings,searchable,expected', [
    (11, 0, False, '原页可读；本册暂不支持关键词检索；有已安装练习，但没有已核对的逐题知识映射。'),
    (0, 0, False, '仅原页阅读：目录与页码可读，暂不支持关键词检索，没有已安装的练习。'),
    (0, 0, True, '原文可读、可检索；当前没有已安装的练习。'),
    (264, 12, True, '原文可读、可检索；有已安装练习与局部已核对知识映射（不是整册覆盖）。'),
])
def test_note_never_contradicts_the_facts(questions, mappings, searchable, expected):
    from learning_service.textbook_capabilities import _note
    note = _note(questions, mappings, searchable)
    assert note == expected
    # A read-only book must never be described as searchable.
    if not searchable:
        assert '可检索' not in note.replace('本册暂不支持关键词检索', '')


def test_catalogue_exposes_capabilities_for_every_book_of_the_grade(catalogued):
    _, api, headers = catalogued
    for grade in (2, 7):
        response = api.get('/api/v1/textbooks', headers={**headers, 'X-Learner-Id': f'family-g{grade}'})
        assert response.status_code == 200, response.text
        items = response.json()['items']
        assert items and all(set(book['capabilities']) == {
            'page_reading', 'keyword_search', 'installed_questions',
            'mapped_questions', 'knowledge_mapping', 'note'} for book in items)
        # Searchability must agree with the catalogue flag it is derived from.
        assert all(book['capabilities']['keyword_search'] == book.get('search_available', True)
                   for book in items)


def test_mapping_count_only_counts_installed_mapped_questions(catalogued):
    db, _, _ = catalogued
    from learning_service.math_references import load_reference
    mapping = load_reference()['question_mappings']
    with db.session() as conn:
        installed = installed_ids(conn)
        counts = book_capabilities(conn, 'math-g2-v1')
    expected = sum(1 for version_id, item in mapping.items()
                   if item['book_id'] == 'math-g2-upper' and version_id in installed)
    assert counts['math-g2-upper']['mapped_questions'] == expected
    assert counts['math-g2-upper']['knowledge_mapping'] == (
        'local_sample' if expected else 'none')
