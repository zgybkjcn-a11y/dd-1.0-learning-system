"""Bounded, frozen multi-field responses; never infer or grade free-form reasoning."""
from copy import deepcopy
import json
import re
import unicodedata

from .practice import numeric_answer


def validate_fields(fields):
    if not isinstance(fields, list) or not 2 <= len(fields) <= 4:
        raise ValueError('invalid response fields')
    seen = set()
    for field in fields:
        if (not isinstance(field, dict) or set(field) not in ({'id', 'label', 'units', 'options'}, {'id', 'label', 'units', 'options', 'kind'})
                or not isinstance(field['id'], str) or not re.fullmatch('[a-z][a-z0-9_]{0,19}', field['id'])
                or field['id'] in seen or not isinstance(field['label'], str) or not 1 <= len(field['label']) <= 100
                or not isinstance(field['units'], list) or len(field['units']) > 4
                or any(not isinstance(s, str) or not 1 <= len(s) <= 10 for s in field['units'])
                or not isinstance(field['options'], list) or len(field['options']) not in ((2,3,4,5,6) if field.get('kind') in ('multi','order') else (0,2,3,4))
                or any(not isinstance(s, str) or not 1 <= len(s) <= 80 for s in field['options'])
                or len(set(field['options'])) != len(field['options'])
                or (field['options'] and field['units'])):
            raise ValueError('invalid response field')
        if 'kind' in field and (field['kind'] not in ('number','choice','text','multi','order')
                or (field['kind'] in ('choice','multi','order')) != bool(field['options'])
                or (field['kind']=='text' and field['units'])):
            raise ValueError('invalid response kind')
        seen.add(field['id'])
    return deepcopy(fields)


def response_fields(content):
    return {'response_fields': validate_fields(content['response_fields'])} if 'response_fields' in content else {}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate response')
        result[key] = value
    return result


def grade_fields(raw, key):
    fields = key.get('field_answers', [])
    if (not isinstance(fields, list) or not 2 <= len(fields) <= 4
            or any(numeric_answer(str(f.get('numeric_answer', '')), []) is None for f in fields)
            or len({f['id'] for f in fields}) != len(fields)):
        return 'undetermined', '题目答案配置待复核。'
    try:
        answers = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, TypeError, RecursionError):
        answers = None
    valid = (isinstance(answers, dict) and set(answers) == {f['id'] for f in fields}
             and all(isinstance(v, str) and len(v) <= 80 for v in answers.values()))
    wrong = [f['label'] for f in fields if not valid or
             numeric_answer(answers[f['id']], f['units']) != numeric_answer(f['numeric_answer'], [])]
    prefix = (f'全部{len(fields)}项核对正确。' if not wrong else
              f'共{len(fields)}项，{len(fields)-len(wrong)}项正确。请重看：' + '、'.join(wrong) + '。')
    return ('incorrect' if wrong else 'correct'), prefix + '\n' + key.get('explanation', '')


def normalize_short(value, case_sensitive=True):
    """Bounded literal text: normalize full width and whitespace, not meaning."""
    value = ' '.join(unicodedata.normalize('NFKC', value).strip().split())
    return value if case_sensitive else value.casefold()


def validate_short_key(fields, answers):
    validate_fields(fields)
    if not isinstance(answers,list) or len(answers)!=len(fields):
        raise ValueError('invalid short answer key')
    for field,key in zip(fields,answers,strict=True):
        if (not isinstance(key,dict) or field.get('kind') not in ('number','choice','text','multi','order') or key.get('id')!=field['id'] or key.get('kind')!=field.get('kind')
                or key.get('label')!=field['label'] or key.get('units')!=field['units']):
            raise ValueError('short answer field mismatch')
        if key['kind']=='text':
            accepted=key.get('accepted')
            if (not isinstance(accepted,list) or not 1<=len(accepted)<=8
                    or type(key.get('case_sensitive')) is not bool
                    or any(not isinstance(v,str) or not 1<=len(v)<=80 or not v.strip() for v in accepted)
                    or len({normalize_short(v,key['case_sensitive']) for v in accepted})!=len(accepted)):
                raise ValueError('invalid short text answers')
        elif key['kind'] in ('multi','order'):
            if (key.get('options')!=field['options'] or
                    selection_values(key.get('selection',''),len(field['options']),key['kind']) is None):
                raise ValueError('invalid structured selection key')
        elif numeric_answer(str(key.get('numeric_answer','')),[]) is None:
            raise ValueError('invalid short numeric answer')
        elif key['kind']=='choice' and key['numeric_answer'] not in {str(i+1) for i in range(len(field['options']))}:
            raise ValueError('invalid short choice answer')
        errors=key.get('errors',[])
        if (not isinstance(errors,list) or len(errors)>8
                or any(not isinstance(e,dict) or set(e)!={'answer','message','action'}
                       or any(not isinstance(e[k],str) or not 1<=len(e[k])<=160 for k in e)
                       for e in errors)):
            raise ValueError('invalid short answer feedback')
        values=[normalize_short(e['answer'],key.get('case_sensitive',True)) for e in errors]
        if len(values)!=len(set(values)):
            raise ValueError('duplicate short answer feedback')
        for e in errors:
            if short_field_correct(e['answer'],key):raise ValueError('correct answer marked as error')


def selection_values(raw, count, kind):
    if not isinstance(raw,str) or len(raw)>80:
        return None
    value=unicodedata.normalize('NFKC',raw).strip()
    if not re.fullmatch(r'[1-6](?:\s*,\s*[1-6])*',value):
        return None
    values=tuple(int(v.strip()) for v in value.split(','))
    if (len(set(values))!=len(values) or any(v>count for v in values)
            or (kind=='order' and set(values)!=set(range(1,count+1)))):
        return None
    return tuple(sorted(values)) if kind=='multi' else values


def short_field_correct(value,key):
    if key['kind'] in ('multi','order'):
        values=selection_values(value,len(key['options']),key['kind'])
        return values is not None and values==selection_values(key['selection'],len(key['options']),key['kind'])
    if key['kind']=='text':
        normalized=normalize_short(value,key['case_sensitive'])
        return normalized in {normalize_short(a,key['case_sensitive']) for a in key['accepted']}
    return numeric_answer(value,key['units'])==numeric_answer(key['numeric_answer'],[])


def grade_short_fields(raw,key):
    fields=key.get('field_answers',[])
    try:
        validate_short_key(key.get('response_fields',[]),fields)
    except (ValueError,TypeError,KeyError):
        return 'undetermined','题目答案配置待复核。'
    try:answers=json.loads(raw,object_pairs_hook=_unique_object)
    except (ValueError,TypeError,RecursionError):answers=None
    if (not isinstance(answers,dict) or set(answers)!={f['id'] for f in fields}
            or any(not isinstance(v,str) or not v.strip() or len(v)>80 for v in answers.values())):
        return 'incorrect','请按每项要求填写完整答案。\n'+key.get('explanation','')
    wrong=[f for f in fields if not short_field_correct(answers[f['id']],f)]
    lines=[f'全部{len(fields)}项核对正确。' if not wrong else f'共{len(fields)}项，{len(fields)-len(wrong)}项正确。请重看：'+'、'.join(f['label'] for f in wrong)+'。']
    for f in wrong:
        raw_value=answers[f['id']]
        matched=None
        for e in f.get('errors',[]):
            same=(normalize_short(raw_value,f.get('case_sensitive',True))==normalize_short(e['answer'],f.get('case_sensitive',True)) if f['kind']=='text' else numeric_answer(raw_value,f['units']) is not None and numeric_answer(raw_value,f['units'])==numeric_answer(e['answer'],[]))
            if same:matched=e;break
        if matched:
            lines.append(f['label']+'：这个答案与“'+matched['message']+'”相符，请对照自己的步骤检查。下一步：'+matched['action'])
        elif f['kind']=='number' and numeric_answer(raw_value,f['units']) is None:
            lines.append(f['label']+'：请检查是否填了算式或不符合要求的单位，按本项要求填写数值。')
        elif f['kind'] in ('multi','order'):
            lines.append(f['label']+'：'+('请逐条核对，漏选和多选都会影响结果。' if f['kind']=='multi' else '请核对每张卡片的位置，区分事件先后和材料排列顺序。'))
        elif f['kind']=='text':
            lines.append(f['label']+'：请核对题目要求的词形、拼写或指定术语。')
    lines.append(key.get('explanation',''))
    return ('incorrect' if wrong else 'correct'),'\n'.join(lines)
