"""Frozen practice scope; adding readable books does not create practice evidence."""
from learning_service.textbooks import BOOKS

PRACTICE_BOOK_IDS = frozenset({
    'math-g2-upper', 'math-g7-upper', 'math-g7-lower',
    'chinese-g2-upper', 'chinese-g2-lower', 'chinese-g7-upper', 'chinese-g7-lower',
    'ethics-g2-upper', 'ethics-g7-upper', 'english-g7-upper',
    'history-g7-upper', 'geography-g7-upper', 'biology-g7-upper',
})
READING_ONLY_BOOK_IDS = frozenset({
    'math-g2-lower', 'ethics-g2-lower', 'english-g7-lower', 'ethics-g7-lower',
    'history-g7-lower', 'geography-g7-lower', 'biology-g7-lower',
})
PRACTICE_BOOKS = [b for b in BOOKS if b['id'] in PRACTICE_BOOK_IDS]
