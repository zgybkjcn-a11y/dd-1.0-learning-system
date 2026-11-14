"""Build only the new original challenge batch; frozen prior banks are untouched."""
from challenge_task_authoring import ChallengeTasks
import challenge_math_tasks,challenge_language_tasks,challenge_english_tasks,challenge_society_tasks
from learning_service.textbooks import BOOKS
b=ChallengeTasks('challenge_variety')
for module in (challenge_math_tasks,challenge_language_tasks,challenge_english_tasks,challenge_society_tasks):module.build(b)
assert len(b.questions)==98
scopes={(x['id'],c['id']) for x in BOOKS for c in x['chapters']}
assert {(q['book_id'],q['chapter_id']) for q in b.questions}==scopes
assert len({q['id'] for q in b.questions})==98
b.write()
