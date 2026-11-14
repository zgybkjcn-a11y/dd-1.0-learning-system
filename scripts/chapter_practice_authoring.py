"""Offline authoring helpers; output is reviewed and frozen before runtime use."""
import hashlib
import json
from pathlib import Path
from fractions import Fraction
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_service.textbooks import learning_scope, PDF_SHA256

ROOT = Path(__file__).resolve().parents[1]


class Batch:
    def __init__(self, name):
        self.name, self.questions = name, []

    def add(self, book, chapter, level, title, prompt, answer, check, hint, explanation, units=(), relation=None):
        grade = int(book.split('-g')[1].split('-')[0])
        b, c = learning_scope(f'math-g{grade}-v1', book, chapter)
        n = 1 + sum(q['book_id'] == book and q['chapter_id'] == chapter for q in self.questions)
        self.questions.append({
            'id': f'family-chapter-{book}-{chapter}-{n:02}-v1', 'batch': self.name,
            'grade': grade, 'subject': b['subject'], 'book_id': book, 'chapter_id': chapter,
            'difficulty': level, 'title': title, 'prompt': prompt,
            'answer': str(Fraction(answer)), 'independent_check': check, 'units': list(units),
            'hint': hint, 'explanation': explanation, 'extension': level == 'hard',
            'source': {'kind': 'authored', 'attribution': 'DD 家庭学习版 · 助手编写与核对',
                       'license': 'project-authored', 'basis': '本地教材目录主题；题干与情境为自编',
                       'chapter_title': c['title'], 'textbook_sha256': PDF_SHA256[book],
                       'textbook_original_question': False, 'template_relation': relation},
            'review': {'status': 'assistant_checked', 'teacher_reviewed': False,
                       'method': 'semantic_conditions_answer_and_explanation_check',
                       'difficulty_calibration': 'author_trial_not_student_calibrated'}})

    def number(self, book, chapter, level, title, prompt, answer, check, hint, explanation, unit='', relation=None):
        self.add(book, chapter, level, title, prompt + '\n请只填最后所求的数值' + (f'（单位：{unit}）' if unit else '') + '。',
                 answer, check, hint, explanation, [unit] if unit else [], relation)

    def choice(self, book, chapter, level, title, prompt, correct, others, hint, explanation):
        # Deterministic position rotation. The answer is the displayed option number.
        options = list(others)
        index = len(self.questions) % 4
        options.insert(index, correct)
        if len(options) != 4 or len(set(options)) != 4:
            raise ValueError('four distinct choices required')
        self.add(book, chapter, level, title, prompt + '\n' + '\n'.join(f'{i}. {text}' for i, text in enumerate(options, 1))
                 + '\n请填正确选项的序号（1～4）。', index + 1, str(index + 1), hint, explanation)

    def choices(self, book, chapter, rows):
        """One entry per difficulty: stem, correct, three distractors, rationale."""
        for level, row in zip(('easy', 'normal', 'hard'), rows, strict=True):
            prompt, correct, a, c, d, explanation = row
            self.choice(book, str(chapter), level, {'easy': '基础辨认', 'normal': '理解应用', 'hard': '综合判断'}[level],
                        prompt, correct, [a, c, d], '先读清题中条件，再比较四个选项。', explanation)

    def write(self):
        prompts = [q['prompt'] for q in self.questions]
        if len(prompts) != len(set(prompts)):
            raise ValueError('duplicate questions')
        path = ROOT / 'learning_service/data' / f'family_chapter_{self.name}_v1.json'
        raw = (json.dumps({'format': 'dd-family-chapter-practice-v1', 'batch': self.name,
                           'questions': self.questions}, ensure_ascii=False, indent=2) + '\n').encode()
        path.write_bytes(raw)
        print(self.name, len(self.questions), hashlib.sha256(raw).hexdigest())

