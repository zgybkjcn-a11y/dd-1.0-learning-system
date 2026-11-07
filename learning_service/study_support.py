"""Local subject reading scaffolds and source-bound study-card exports.

SCENARIOS.md informs the presentation, not the facts of a textbook. All prompts
here are locally authored reflection aids, with no grades or mastery claims.
"""
import re

from .math_references import ReferenceError, query_reference
from .textbooks import catalogue

VERSION = '2026-11-06-study-support-v1'
SCENARIOS_COMMIT = '508748a2c8dddc1253100b2d10d91c9526903f67'

PROMPTS = {
    'math': [('先看关系', '题目给了哪些量？它们怎样联系？先用图或自己的话说明，再计算。'),
             ('核对每一步', '每一步用了什么规则？所求量与最后得到的量是否相同？'),
             ('换个例子', '用较小的数举一个例子，解释为什么这个方法仍然成立。')],
    'chinese': [('整体理解', '这一篇主要写什么？用自己的话说出一条主线。'),
                ('找到依据', '哪些句子支持你的理解？回到原文核对语境和说话人。'),
                ('比较表达', '作者为什么这样用词或安排顺序？换一种表达会有什么变化？')],
    'english': [('先理解情境', '这一单元的人物在什么场景交流？他们想表达什么？'),
                ('观察表达', '找出本单元的一种表达，比较它在不同句子中的用法。'),
                ('尝试迁移', '换成自己的日常情境写一句话，再用教材示例核对。')],
    'ethics': [('辨认情境', '这一章讨论谁在什么情况下作选择？先说清事实。'),
               ('说明理由', '教材怎样解释责任或规则？区分事实、观点与自己的感受。'),
               ('联系生活', '找一个日常例子，说明你的选择和理由，再回到教材核对。')],
    'history': [('定位时空', '本章涉及什么时间和地点？用时间线排列关键事件。'),
                ('区分因果', '背景、原因、过程和影响分别是什么？哪些材料支持这些解释？'),
                ('比较证据', '比较两项事件或制度时，先确定同一个比较维度。')],
    'geography': [('先看地图', '地图的方向、图例和比例尺表示什么？先定位再解释。'),
                  ('连接条件', '本章讨论的自然或人文现象受哪些条件影响？回到图和文字找依据。'),
                  ('比较地区', '比较两地时使用相同指标，说明相似处与差异。')],
    'biology': [('观察结构', '本章讨论什么结构或过程？画出主要部分并标注。'),
                ('联系功能', '结构、功能和发生条件怎样联系？用教材图文核对。'),
                ('区分推断', '哪些是直接观察，哪些是解释？若有实验，比较变量与对照。')],
}


def _label(text):
    # Mermaid labels are locally authored catalogue titles, never student text.
    return str(text).replace('"', '＂').replace('<', '＜').replace('>', '＞').replace('\n', ' ')[:100]


def query_support(conn, learner_id, curriculum_id, textbook_dir, *, subject='', book_id='', chapter_id=''):
    for value in (subject, book_id, chapter_id):
        if type(value) is not str or (value and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value)):
            raise ReferenceError(422, 'STUDY_SUPPORT_SCOPE_INVALID', '请选择当前档案的学科、课本和章节')
    books = catalogue(curriculum_id)
    if not book_id:
        subject = subject or 'math'
        book_id = next((b['id'] for b in books if b['subject'] == subject and b['semester'] == '上册'), '')
    book = next((b for b in books if b['id'] == book_id), None)
    chapter = next((c for c in book['chapters'] if c['id'] == chapter_id), None) if book else None
    if (not book or (subject and book['subject'] != subject) or (chapter_id and not chapter)
            or book['subject'] not in PROMPTS):
        raise ReferenceError(422, 'STUDY_SUPPORT_SCOPE_INVALID', '该学科、课本或章节不属于当前档案')
    subject = book['subject']
    scope = {key: book[key] for key in ('id','grade','subject','subject_title','title','semester','edition')}
    scope['book_id'] = scope.pop('id')
    scope.update(chapter_id=chapter_id, chapter_title=chapter['title'] if chapter else '整本书')
    steps = [{'title': title, 'prompt': prompt} for title,prompt in PROMPTS[subject]]
    math = query_reference(conn, learner_id, curriculum_id, textbook_dir, book_id=book_id, chapter_id=chapter_id) if subject == 'math' else None
    template = None
    if math and math['mapping_status'] == 'mapped':
        if book_id == 'math-g2-upper':
            template = 'multiplication_groups_v1' if chapter_id == '2' else 'equal_groups_v1'
        elif book_id == 'math-g7-upper' and chapter_id in {'', '2'}:
            template = 'signed_number_line_v1'
    lines = ['flowchart TD']
    if math and math['concepts']:
        lines += [f'  B["{_label(book["title"])}"]', f'  S["{_label(scope["chapter_title"])}"]', '  B -->|目录范围| S']
        for i,node in enumerate(math['concepts']):
            lines += [f'  C{i}["{_label(node["title"])}"]', f'  S -->|本地映射| C{i}']
        indices={n['id']:i for i,n in enumerate(math['concepts'])}
        for i,node in enumerate(math['prerequisites']):
            lines.append(f'  P{i}["{_label(node["title"])}"]')
            target=indices.get(node['from_concept'])
            if target is not None:
                lines.append(f'  C{target} -->|先修参考 {node["strength"]}| P{i}')
        diagram_role = 'catalogue_and_local_concept_mapping'
    else:
        for i,step in enumerate(steps):
            lines.append(f'  S{i}["{_label(step["title"])}"]')
            if i:
                lines.append(f'  S{i-1} -->|学习步骤| S{i}')
        diagram_role = 'reading_process_not_knowledge_dependencies'
    markdown = ['---', 'marp: true', 'paginate: true', '---',
                f'# {book["subject_title"]} · {scope["chapter_title"]}', '',
                f'{book["title"]}；{book["edition"]}', '',
                '学习参考，不判分、不宣称掌握；非数学学科目前提供阅读问题串，未建立精确概念/页码映射。']
    for step in steps:
        markdown += ['', '---', f'## {step["title"]}', '', step['prompt'], '', '回到当前课本图文找依据，再用自己的话解释。']
    if math:
        for node in math['concepts'] + math['prerequisites']:
            markdown += ['', '---', f'## {node["title"]}', '', node['explanation'], '', *['- '+s for s in node['checks']]]
            pages = '、'.join(str(p['printed_page']) for p in node['pages'])
            markdown += ['', f'本地核对点：{node["id"]}；'+(f'本册原页：{pages}。' if pages else '本地综合核对点，无教材原页声明。')]
        markdown += ['', '结构参考：dangjian/faststudy-knowledge；图谱相关元数据 CC BY-NC-SA 4.0。',
                     '局部原页核对不等于整页或教师审核；原教材版权归出版社。']
    else:
        markdown += ['', '以上问题串由本项目编写；不提供未经核对的学科答案。']
    return {'support_version': VERSION, 'scope': scope, 'study_steps': steps,
            'concepts': math['concepts'] if math else [], 'prerequisites': math['prerequisites'] if math else [],
            'interactive_template': template,
            'mapping_status': math['mapping_status'] if math else 'reading_scaffold_only',
            'mapped_question_count': math['mapped_question_count'] if math else 0,
            'diagram_role': diagram_role, 'diagram_mermaid': '\n'.join(lines),
            'lesson_markdown': '\n'.join(markdown)+'\n', 'artifact_formats': ['mermaid','marp_markdown'],
            'reference_only': True, 'eligible_as_grading_basis': False, 'teacher_reviewed': False, 'mastery_claim': None,
            'provenance': {'scenario_document': 'dangjian/faststudy-knowledge/docs/SCENARIOS.md',
                           'scenario_commit': SCENARIOS_COMMIT,
                           'presentation_reference': ['Mermaid','Marp','EduLab'],
                           'implementation': 'locally_authored_no_upstream_runtime'},
            'notice': '先观察，再解释，再回到课本核对。问题串与展示资料不作为判分依据。'}
