"""Bounded, deterministic five-concept retrieval for reviewed excerpts.

Inputs must come from the reviewed bundle loader. Concept profiles are trusted
caller configuration, never model arguments. This grammar locates rule/definition
quotes; it does not solve expressions, prove claims or assess student answers.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import re
import unicodedata

from .textbooks import learning_scope


VERSION = 'bounded-rules-v1'
PILOT_CONCEPTS = {
    'g7-ch2-addition-rule': 'addition',
    'g7-ch2-subtraction-rule': 'subtraction',
    'g7-ch2-reciprocal-definition': 'reciprocal',
    'g7-ch2-distributive-law': 'distribution',
    'g7-ch2-product-sign': 'product_sign',
}
CONCEPTS = frozenset(PILOT_CONCEPTS.values())
# These tasks need content absent from the five approved excerpts. Matching a
# rule name alone cannot satisfy a request for a proof, figure or worked answer.
UNSUPPORTED = re.compile(
    r'证明|论证|推导|公理|交换律|结合律|除法|相除|除以|'
    r'函数|导数|积分|矩阵|向量|复数|平方根|幂|乘方|指数|不等式|'
    r'数轴|图上|图中|原图|图示|画图|画出|图像|几何|三角|内角|'
    r'练习|例题|标准答案|标准解答|第.{0,12}题|解题步骤|笔算|竖式|进位|'
    r'补码|二进制|计算机|发明|最早|历史|谁提出|谁发现|'
    r'(?:算出|计算出|求出|给出|直接算).{0,12}(?:结果|答案|数值)|数值结果')
ADDITION = re.compile(r'加法|相加|求和|加运算|加在一起|加起来|合起来|合在一起|加数|和的符号')
SUBTRACTION = re.compile(r'减法|相减|减去|减掉|扣去|减号|减数|减一个数')
MULTIPLY = re.compile(r'相乘|连乘|乘法|乘数|因子|乘积|积的|积为|积也|积该|乘起来|乘得')
SIGN = re.compile(r'符号|正负|负号|正号|负数|正数|负的|负因子|非零|不为0|为0|含0|出现零|混进了0|奇数|偶数|奇偶')


def normalize(query):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', query).casefold()).translate(
        str.maketrans({'−': '-', '–': '-', '×': '*', '·': '*', '∙': '*', '÷': '/', '［': '(',
                       '］': ')', '[': '(', ']': ')', '【': '(', '】': ')'}))


def expression_features(query):
    """Recognize arithmetic structure without evaluating any expression."""
    operations, distributed = set(), False
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult,
               ast.Div, ast.UAdd, ast.USub, ast.Name, ast.Load, ast.Constant)
    for fragment in re.findall(r'[a-z0-9().+*/=-]+', query):
        for expression in fragment.split('='):
            # Restricted implicit multiplication: a(b+c), (a+b)c, (a+b)(c+d).
            expression = re.sub(r'([a-z0-9)])\(', r'\1*(', expression)
            expression = re.sub(r'\)([a-z0-9])', r')*\1', expression)
            try:
                tree = ast.parse(expression, mode='eval')
            except (SyntaxError, ValueError):
                continue
            nodes = list(ast.walk(tree))
            if any(not isinstance(n, allowed) or isinstance(n, ast.Name) and len(n.id) != 1 for n in nodes):
                continue
            for node in nodes:
                if not isinstance(node, ast.BinOp):
                    continue
                operations.add(type(node.op))
                if isinstance(node.op, ast.Mult):
                    distributed |= any(isinstance(side, ast.BinOp) and isinstance(side.op, ast.Add)
                                       for side in (node.left, node.right))
                if isinstance(node.op, ast.Add) and all(isinstance(side, ast.BinOp) and isinstance(side.op, ast.Mult)
                                                       for side in (node.left, node.right)):
                    left = {ast.dump(n) for n in (node.left.left, node.left.right)}
                    right = {ast.dump(n) for n in (node.right.left, node.right.right)}
                    distributed |= bool(left & right)
    return operations, distributed


def classify(query):
    q = normalize(query)
    if UNSUPPORTED.search(q):
        return {}, 'unsupported_task'
    operations, distributed = expression_features(q)
    reciprocal = bool('倒数' in q or re.search(r'(?:乘积|积|相乘|乘起来).{0,12}(?:等于|是|为|得到|得|=).{0,4}(?:1|一|单位数)', q)
                      or re.search(r'(?:[a-z]\*?[a-z]|[a-z0-9()./]+\*[a-z0-9()./]+)=1(?:[^0-9.]|$)', q))
    distribution = bool(distributed or '分配律' in q or re.search(r'乘.{0,6}(?:一个和|两数之和|两个数的和)', q)
                        or re.search(r'乘法.{0,8}加法.{0,6}展开', q))
    subtraction = bool(SUBTRACTION.search(q) or ast.Sub in operations)
    addition = bool(ADDITION.search(q) or ast.Add in operations)
    product_sign = bool((MULTIPLY.search(q) or ast.Mult in operations) and SIGN.search(q))
    scores = {}
    if reciprocal:
        scores['reciprocal'] = 10
    if distribution:
        scores['distribution'] = 10 if distributed else 8
    if subtraction:
        scores['subtraction'] = 8
    # Embedded addition is not an independent request when converting subtraction
    # or distributing a product. Explicitly named addition/subtraction rules may
    # both be retrieved, as may a comparison of sum and product signs.
    if addition and not distribution and (not subtraction or '加法' in q):
        scores['addition'] = 8
    if product_sign and not distribution and not reciprocal:
        scores['product_sign'] = 8
    if reciprocal and not any(word in q for word in ('分别', '各用', '两处', '比较')):
        scores = {'reciprocal': scores['reciprocal']}
    return scores, None


def retrieve(passages, curriculum_id, book_id, chapter_id, query, *, concept_by_id=None):
    """Authorize and scope the entire reviewed corpus before scoring or limiting."""
    book, chapter = learning_scope(curriculum_id, book_id, chapter_id)
    if (type(query) is not str or not query.strip() or len(query) > 120
            or any(ord(c) < 32 for c in query)):
        raise ValueError('invalid query')
    profiles = PILOT_CONCEPTS if concept_by_id is None else concept_by_id
    if not isinstance(profiles, dict) or any(v not in CONCEPTS for v in profiles.values()):
        raise ValueError('invalid trusted concept profiles')
    scoped = []
    seen, identities = {}, {}
    for passage in passages:
        evidence = passage['evidence']
        if evidence['book_id'] != book['id'] or chapter['id'] and evidence['chapter_id'] != chapter['id']:
            continue
        key, eid = passage['id'], evidence['evidence_id']
        if key in identities and identities[key] != eid or eid in seen and seen[eid] != passage:
            raise ValueError('conflicting excerpt identity')
        identities[key] = eid
        if eid not in seen:
            seen[eid] = passage
            scoped.append(passage)
    scores, unsupported = classify(query)
    ranked = [(scores[profiles[p['id']]], p) for p in scoped
              if p['id'] in profiles and profiles[p['id']] in scores]
    ranked.sort(key=lambda pair: (-pair[0], pair[1]['evidence']['evidence_id']))
    covered = {profiles[p['id']] for _, p in ranked[:4]}
    if not scoped:
        status, reason = 'no_evidence', 'no_reviewed_excerpts_in_scope'
    elif unsupported:
        status, reason = 'no_evidence', unsupported
    elif not scores:
        status, reason = 'low_relevance', 'no_supported_rule_intent'
    elif set(scores) - covered:
        status, reason = 'insufficient_evidence', 'required_rule_not_available'
    else:
        status, reason = 'reviewed_excerpts_only', 'matched_supported_rule_intent'
    selected = ranked[:4] if status == 'reviewed_excerpts_only' else []
    items = [{k: deepcopy(v) for k, v in p.items() if k != 'retrieval_terms'} for _, p in selected]
    messages = {
        'reviewed_excerpts_only': '以下仅引用已核对的规则或定义，请打开原页；不生成解题答案，不作为判分依据。',
        'no_evidence': '本次已核对的片段不能提供所需依据，可打开原页继续查阅；这不表示整本教材没有相关内容。',
        'low_relevance': '暂不能把问题可靠对应到已有规则，请明确要查的运算规则或定义，或打开原页查阅。',
        'insufficient_evidence': '当前片段未覆盖所需的全部规则，请打开原页查阅；不拼出不完整的依据。',
    }
    return {'scope': {'book_id': book['id'], 'chapter_id': chapter['id'], 'grade': book['grade']},
            'items': items,
            'retrieval': {'schema': 'dd-retrieval-coverage-v1', 'method': VERSION,
                          'coverage_complete': True, 'coverage_scope': 'loaded_reviewed_excerpts_only',
                          'scoped_count': len(scoped), 'candidate_count': len(ranked), 'limit': 4,
                          'status': status, 'reason': reason,
                          'ranking': [{'evidence_id': p['evidence']['evidence_id'], 'score': score} for score, p in selected],
                          'display_order': [p['evidence']['evidence_id'] for p in sorted(items, key=lambda p: (p['evidence']['pdf_page'], p['evidence']['evidence_id']))]},
            'grounding': {'status': status, 'can_quote_textbook': bool(items), 'can_answer_from_textbook': False,
                          'eligible_as_grading_basis': False, 'message': messages[status]}}
