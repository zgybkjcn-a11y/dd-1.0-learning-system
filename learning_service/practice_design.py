"""Presentation and editorial tiers; immutable question/attempt bytes stay intact."""
from copy import deepcopy


def presentation(q):
    level = q['difficulty']
    # The first non-math bank used "hard" for every third single-choice item.
    # Direct lookup and one inference are not hard merely because of position.
    if q.get('subject') != 'math' and q.get('batch') in {
        'upper', 'remaining', 'upper_variety', 'remaining_variety',
    } and level == 'hard':
        direct_lookup = {
            'english-g7-upper': {'1','2','3','4','6','7','12','17'},
            'chinese-g2-upper': {'2','9'}, 'chinese-g2-lower': {'1'},
            'geography-g7-upper': {'2','6','9'}, 'biology-g7-upper': {'2'},
        }
        level = ('easy' if q['batch'] in {'upper','remaining'} and
                 q['chapter_id'] in direct_lookup.get(q['book_id'], set()) else 'normal')
    if q.get('batch') == 'math_g2_depth' and level == 'hard':
        level = 'easy' if q['title'] in {
            '先问清所求量', '检查整理有没有漏掉', '转身不会移动建筑',
            '估计值不是实测值', '整理表里的单位错误',
        } else 'normal'
    if q.get('book_id') == 'math-g2-upper' and q.get('batch') == 'math' and q['title'] in {
        '同一物品两种分法', '转身后辨方向', '两次截取', '身体尺要先校准',
    }:
        level = 'normal'
    design = q.get('design', {})
    return {'difficulty': level, 'extension': level in ('hard','challenge'),
            'task_form': design.get('form', '辨析选择' if '请填正确选项' in q['prompt'] else '计算应用'),
            'task_family': design.get('family', q.get('coverage', {}).get('family', q['title'])),
            'selection_priority': design.get('priority', 0), 'selection_order': design.get('order', 0)}


def validate_visual(visual):
    """Only bounded text tables/grids and number-line geometry, never HTML/URLs."""
    if not isinstance(visual, dict) or not isinstance(visual.get('caption'), str) or len(visual['caption']) > 180:
        raise ValueError('invalid practice visual')
    kind = visual.get('kind')
    if kind in ('table', 'grid'):
        if set(visual) != {'kind', 'caption', 'rows'}:
            raise ValueError('invalid practice visual fields')
        rows = visual['rows']
        if (not isinstance(rows, list) or not 1 <= len(rows) <= 10
                or any(not isinstance(r, list) or not 1 <= len(r) <= 8 for r in rows)
                or len({len(r) for r in rows}) != 1
                or any(not isinstance(c, str) or len(c) > 80 for r in rows for c in r)):
            raise ValueError('invalid practice visual cells')
    elif kind == 'ruler':
        if set(visual) != {'kind', 'caption', 'maximum', 'segments'}:
            raise ValueError('invalid practice visual fields')
        maximum, segments = visual['maximum'], visual['segments']
        if type(maximum) is not int or not 1 <= maximum <= 30 or not isinstance(segments, list) or not 1 <= len(segments) <= 4:
            raise ValueError('invalid practice ruler')
        for segment in segments:
            if (not isinstance(segment, dict) or set(segment) != {'label', 'start', 'end'}
                    or not isinstance(segment['label'], str) or len(segment['label']) > 20
                    or type(segment['start']) is not int or type(segment['end']) is not int
                    or not 0 <= segment['start'] < segment['end'] <= maximum):
                raise ValueError('invalid practice ruler segment')
    else:
        raise ValueError('invalid practice visual kind')
    return deepcopy(visual)


def visual_fields(content):
    return {'visual': validate_visual(content['visual'])} if 'visual' in content else {}
