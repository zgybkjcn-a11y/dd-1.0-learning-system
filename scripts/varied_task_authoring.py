"""Offline, original tasks using the existing frozen multi-field protocol."""
import json
import hashlib
from chapter_practice_authoring import Batch
from learning_service.textbooks import learning_scope


def number(label, answer, check, unit=''):
    return dict(label=label, answer=str(answer), independent_check=check,
                units=[unit] if unit else [], options=[])


def choose(label, correct, *options):
    assert correct in options and len(set(options)) == len(options)
    answer = str(options.index(correct)+1)
    return dict(label=label, answer=answer, independent_check=answer, units=[], options=list(options))


def table(caption, rows):
    return dict(kind='table', caption=caption, rows=rows)


class Tasks(Batch):
    def task(self, book, ch, key, level, form, title, stem, fields, explanation,
             *, hint='逐项回到材料找条件，注意区分事实、推断和所求量。', visual=None,
             page=None, coverage=None, skills=()):
        ch = str(ch)
        self.add(book, ch, level, title, stem+'\n请分别完成下面各项。', 0, '0', hint, explanation)
        q = self.questions[-1]
        q['id'] = f'family-chapter-{book}-{ch}-{self.name}-{key}-v1'
        for i, field in enumerate(fields):
            field['id'] = chr(97+i)
            if field['options']:
                correct = field['options'][int(field['answer'])-1]
                shift = hashlib.sha256((q['id']+field['id']).encode()).digest()[0] % len(field['options'])
                field['options'] = field['options'][shift:] + field['options'][:shift]
                field['answer'] = field['independent_check'] = str(field['options'].index(correct)+1)
        q['responses'] = fields
        q['answer'] = json.dumps({f['id']:f['answer'] for f in fields},ensure_ascii=False,separators=(',',':'))
        del q['independent_check']
        _, chapter = learning_scope(f'math-g{q["grade"]}-v1',book,ch)
        q['source'].update(basis='本地固定教材目录与主题核对；材料、情境及题目为自编，非教材原题',
                           topic_printed_pages=[page or chapter['printed_page']],
                           reference_scope='topic_location_not_verbatim_question')
        q['design'] = dict(form=form, family=(coverage or {}).get('family',f'{book}:{ch}:{key}'),
                           priority=2,order=len(self.questions),skills=list(skills),
                           demand='联合材料完成多个结果或判断，全部正确才记本题答对',
                           assessment_limit='只核对指定结果或判断，不代替自由写作、口述、听说或实际操作。')
        if visual: q['visual'] = visual
        if coverage: q['coverage'] = coverage


def mapping(ch, point, task, role, family):
    return dict(point_id=f'math-g7-upper:{ch}:{point}',task=task,role=role,family=family,
                rationale='按完整能力要求判断对应或辅助；多个输入项不单独计题型，不替代独立表达或作图。')
