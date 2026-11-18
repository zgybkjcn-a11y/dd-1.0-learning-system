"""Knowledge-point inventory for the seven newly added lower textbooks.

Built from the local reviewed inventory, the catalogue section titles and the
registered question bank. It lists what exists and which sections are not yet
expanded; it never invents points for unexpanded sections.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from learning_service import chapter_practice as chapter
from learning_service.textbooks import catalogue

INVENTORY = ROOT / 'docs/quality/lower-knowledge-inventory-2026-11-13.json'
OUTPUT = ROOT / 'docs/quality/new-books-knowledge-inventory-2026-11-18.json'
NEW_BOOKS = {'math-g2-lower', 'ethics-g2-lower', 'english-g7-lower', 'ethics-g7-lower',
             'history-g7-lower', 'geography-g7-lower', 'biology-g7-lower'}


def main():
    inventory = json.loads(INVENTORY.read_text())
    bank = chapter.bank()
    questions = {}
    for question_id, item in bank.items():
        knowledge = item.get('knowledge') or {}
        if knowledge.get('point_id'):
            questions.setdefault(knowledge['point_id'], []).append(question_id)
    books = {}
    for grade, curriculum in ((2, 'math-g2-v1'), (7, 'math-g7-v1')):
        for book in catalogue(curriculum):
            if book['id'] in NEW_BOOKS:
                books[book['id']] = book
    scopes, missing_books = [], sorted(NEW_BOOKS - set(books))
    for scope in inventory['scopes']:
        if scope['book_id'] not in NEW_BOOKS:
            continue
        book = books[scope['book_id']]
        chapter_meta = next(c for c in book['chapters'] if c['id'] == scope['chapter_id'])
        points, reviewed_pages = [], set()
        for point in scope.get('new_initial_points', []):
            pages = point.get('source_printed_pages', [])
            reviewed_pages.update(pages)
            ids = sorted(questions.get(point['id'], []))
            points.append({
                'id': point['id'],
                'title': point['title'],
                'printed_pages': pages,
                'requirement': point.get('bounded_candidate_action'),
                'manual_task': point.get('manual_task'),
                'question_version_ids': ids,
                'question_count': len(ids),
                'levels': sorted({bank[qid]['difficulty'] for qid in ids}),
                'formal_status': 'available_in_local_bank' if ids else 'manual_only_no_question',
            })
        starts = scope.get('textbook_section_starts', [])
        uncovered = [section for section in starts if section['printed_page'] not in reviewed_pages]
        scopes.append({
            'id': scope['id'], 'book_id': scope['book_id'], 'grade': scope['grade'],
            'chapter_id': scope['chapter_id'], 'title': scope['title'],
            'printed_range': scope.get('printed_range'),
            'chapter_title': chapter_meta['title'],
            'section_titles': [section['title'] for section in starts],
            'knowledge_points': points,
            'uncovered_sections': uncovered,
        })
    counts = Counter()
    for scope in scopes:
        for point in scope['knowledge_points']:
            counts[point['formal_status']] += 1
    record = {
        'format': 'dd-new-books-knowledge-inventory-v1',
        'recorded_at': '2026-11-18',
        'scope': sorted(NEW_BOOKS),
        'source_inventory': str(INVENTORY.relative_to(ROOT)),
        'source_inventory_sha256': __import__('hashlib').sha256(INVENTORY.read_bytes()).hexdigest(),
        'method': 'catalogue section titles + locally reviewed initial requirements + registered questions; '
                  'no OCR, no external model, no invented points',
        'question_source': 'learning_service chapter bank (local, sha256-pinned); production installation is '
                           'recorded separately in the release/deployment evidence',
        'teacher_reviewed': False,
        'curriculum_standard_crosscheck': 'assistant_crosscheck_passed_2026-11-18_against_local_plan_or_inventory',
        'summary': {
            'books': len(books), 'scopes': len(scopes),
            'knowledge_points': sum(len(scope['knowledge_points']) for scope in scopes),
            **counts,
            'questions_by_book': dict(Counter(
                bank[qid]['book_id'] for ids in
                ([p['question_version_ids'] for scope in scopes for p in scope['knowledge_points']])
                for qid in ids)),
            'catalogue_sections': sum(len(scope['section_titles']) for scope in scopes),
            'uncovered_sections': sum(len(scope['uncovered_sections']) for scope in scopes),
            'missing_books': missing_books,
        },
        'limitations': [
            '清单覆盖起始范围与已有初始要求，不宣称单元内知识点穷尽。',
            '未展开的节只记录教材目录标题，没有生成要求或题目。',
            '教师签署与真实难度校准仍为 false/pending。',
        ],
        'scopes': scopes,
    }
    if missing_books:
        raise SystemExit('missing catalogue books: %s' % missing_books)
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(record['summary'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
