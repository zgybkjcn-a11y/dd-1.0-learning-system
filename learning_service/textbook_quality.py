"""Independent transcription and mathematical correctness gates for textbook items.

This does not approve whole OCR pages. Automatic verification is deliberately
limited to a complete, plain arithmetic equality; word problems and diagrams
need a separate review with evidence. No eval, external model, or OCR call.
"""
from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import re


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _number(expression: str) -> Fraction:
    tree = ast.parse(expression, mode='eval')
    if len(list(ast.walk(tree))) > 64:
        raise ValueError('too complex')

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) < 10**9:
            return Fraction(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            return left / right
        raise ValueError('unsupported expression')

    return visit(tree.body)


def check_arithmetic_claim(text: str) -> dict:
    """Check only a full arithmetic equality, never infer missing conditions."""
    # Joining OCR columns/rows or separated digits can invent a valid equation.
    if re.search(r'[\r\n]|[0-9]\s+[0-9]', text):
        return {'status':'needs_review', 'reason':'ambiguous_layout_or_separated_digits'}
    expression = re.sub(r'\s+', '', text.translate(str.maketrans('×÷−＝（）', '*/-=()')))
    if len(expression) > 200 or not re.fullmatch(r'[0-9()+*/\-]+=[0-9()+*/\-]+', expression):
        return {'status':'needs_review', 'reason':'not_a_complete_plain_arithmetic_equality'}
    left, right = expression.split('=')
    try:
        lhs, rhs = _number(left), _number(right)
    except (ValueError, SyntaxError, ZeroDivisionError, RecursionError):
        return {'status':'needs_review', 'reason':'invalid_or_unsupported_arithmetic'}
    return {'status':'verified' if lhs == rhs else 'rejected',
            'method':'independent_exact_rational_arithmetic',
            'left_value':str(lhs), 'right_value':str(rhs), 'content_sha256':content_hash(text)}


def check_remainder(dividend: int, divisor: int, quotient: int, remainder: int) -> dict:
    """Independently check both the reconstruction and the remainder bound."""
    values = (dividend, divisor, quotient, remainder)
    if any(type(value) is not int or abs(value) >= 10**9 for value in values):
        return {'status':'needs_review', 'reason':'unsupported_remainder_values'}
    valid = (dividend >= 0 and divisor > 0 and quotient >= 0
             and 0 <= remainder < divisor and dividend == divisor * quotient + remainder)
    return {'status':'verified' if valid else 'rejected', 'method':'integer_division_invariants',
            'dividend':dividend, 'divisor':divisor, 'quotient':quotient, 'remainder':remainder}


def assess_item(text: str, image_sha256: str, transcription_review: dict,
                semantic_review: dict | None = None, *, answer: str | None = None) -> dict:
    """A matching image and correct mathematics are independent requirements."""
    digest = content_hash(text)
    transcription_ok = bool(re.fullmatch(r'[0-9a-f]{64}', image_sha256 or '')
        and transcription_review.get('status') == 'verified'
        and transcription_review.get('content_sha256') == digest
        and transcription_review.get('image_sha256') == image_sha256
        and transcription_review.get('scope') == 'complete_item'
        and transcription_review.get('layout_checked') is True
        and transcription_review.get('evidence'))
    mathematics = (check_arithmetic_claim(text) if answer is None else
                   {'status':'needs_review', 'reason':'question_and_answer_need_joint_review'})
    if mathematics['status'] == 'needs_review' and semantic_review:
        if (semantic_review.get('status') == 'verified'
                and semantic_review.get('content_sha256') == digest
                and semantic_review.get('image_sha256') == image_sha256
                and semantic_review.get('answer_sha256') == content_hash(answer or '')
                and semantic_review.get('method') == 'independent_review'
                and semantic_review.get('conditions_complete') is True
                and semantic_review.get('units_checked') is True
                and semantic_review.get('diagram_checked') is True
                and semantic_review.get('derivation') and semantic_review.get('evidence')):
            mathematics = {**semantic_review}
    approved = transcription_ok and mathematics['status'] == 'verified'
    return {'content_sha256':digest, 'image_sha256':image_sha256,
            'answer_sha256':content_hash(answer or ''),
            'transcription_status':'verified' if transcription_ok else 'needs_review',
            'mathematical_review':mathematics,
            'eligible_for_question_or_answer':approved,
            'status':'verified' if approved else 'quarantined'}
