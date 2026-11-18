"""Per-book capability status: what the deployed data actually supports.

Every value is derived from the database and the reviewed reference, never
asserted. Question counts come from the installed, approved versions; the
chapter bank is not loaded to describe a book, because reading it re-parses and
re-verifies every authored batch. A book without those facts is reported as
read-only instead of borrowing a neighbour's capability.
"""
from __future__ import annotations

READ_ONLY_NOTE = '仅原页阅读：目录与页码可读，暂不支持关键词检索，没有已安装的练习。'
NO_QUESTIONS_NOTE = '原文可读、可检索；当前没有已安装的练习。'
PARTIAL_NOTE = '原文可读、可检索；有已安装练习，但没有已核对的逐题知识映射。'
MAPPED_NOTE = '原文可读、可检索；有已安装练习与局部已核对知识映射（不是整册覆盖）。'
NO_SEARCH_NOTE = '原页可读；本册暂不支持关键词检索；'


def _note(questions, mappings, searchable):
    """Compose the note from the facts, so a read-only claim cannot contradict them."""
    if not searchable:
        if not questions:
            return READ_ONLY_NOTE
        return NO_SEARCH_NOTE + ('有已安装练习与局部已核对知识映射（不是整册覆盖）。' if mappings
                                 else '有已安装练习，但没有已核对的逐题知识映射。')
    return (MAPPED_NOTE if mappings else PARTIAL_NOTE) if questions else NO_QUESTIONS_NOTE


def _installed_by_book(conn, book_ids):
    """Installed approved versions per known book id.

    Chapter objectives are named `objective-family-chapter-<book>-<chapter>`; the
    starter and reserve banks are small, cheap to verify, and carry their own
    `book_id`, so they are read directly rather than through a naming rule.
    """
    from . import practice, reserve_practice

    starter = {version_id: item['book_id'] for version_id, item in
               {**practice.bank(), **reserve_practice.bank()}.items() if item.get('book_id')}
    counts = dict.fromkeys(book_ids, 0)
    prefix = 'objective-family-chapter-'
    for (version_id, objective) in conn.execute(
            "SELECT v.id, q.objective_id FROM question_versions v JOIN questions q ON q.id=v.question_id "
            "WHERE v.approval='approved' AND q.approval='approved'"):
        book = starter.get(version_id)
        if not book and objective and objective.startswith(prefix):
            rest = objective[len(prefix):]
            book = next((candidate for candidate in book_ids if rest.startswith(candidate + '-')), None)
        if book in counts:
            counts[book] += 1
    return counts


def _mapped(installed):
    from .math_references import load_reference

    try:
        reference = load_reference()
    except Exception:  # A withheld reference must not break the catalogue.
        return {}
    counts: dict[str, int] = {}
    for version_id, mapping in reference['question_mappings'].items():
        if version_id in installed:
            counts[mapping['book_id']] = counts.get(mapping['book_id'], 0) + 1
    return counts


def book_capabilities(conn, curriculum_id):
    """{book_id: {...}} for the books of one grade; every book gets an entry."""
    from .textbooks import catalogue

    books = catalogue(curriculum_id)
    if not books:
        return {}
    installed = {row[0] for row in conn.execute(
        "SELECT v.id FROM question_versions v JOIN questions q ON q.id=v.question_id "
        "WHERE v.approval='approved' AND q.approval='approved'")}
    questions = _installed_by_book(conn, [book['id'] for book in books])
    mapped = _mapped(installed)
    result = {}
    for book in books:
        count, mappings = questions.get(book['id'], 0), mapped.get(book['id'], 0)
        searchable = book.get('search_available', True)
        result[book['id']] = {'page_reading': True, 'keyword_search': searchable,
                              'installed_questions': count, 'mapped_questions': mappings,
                              'knowledge_mapping': 'local_sample' if mappings else 'none',
                              'note': _note(count, mappings, searchable)}
    return result
