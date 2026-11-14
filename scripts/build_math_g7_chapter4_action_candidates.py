"""Author a local candidate for error analysis in grade-seven chapter four."""
from chapter_practice_authoring import Batch


batch = Batch('math_g7_chapter4_action_candidates')
batch.choice(
    'math-g7-upper', '4', 'normal', '减去整式的符号错误辨析',
    '小周把(5x+2)−(2x−3)化简为3x−1。哪项指出错误并给出正确结果？',
    '括号前的减号要使括号内两项都变号，结果是3x+5。',
    [
        '只需改变x项的符号，结果仍是3x−1。',
        '应把第一个括号也变号，结果是−7x+1。',
        '把括号前的减号当成加号，结果是7x−1。',
    ],
    '把减号看作乘以−1，再逐项检查第二个括号中的两项。',
    '5x+2−(2x−3)=5x+2−2x+3=3x+5；原解漏掉了常数项变号。',
)
batch.questions[-1]['id'] = 'family-chapter-math-g7-upper-4-action-subtract-expression-v1'
batch.questions[-1]['coverage'] = {
    'point_id': 'math-g7-upper:4:application',
    'task': 'distinguish',
    'family': 'g7:polynomial:subtract-whole-expression-sign-error',
    'role': 'direct',
    'rationale': '要求定位减去整式时漏变号的具体错误，并给出逐项变号后的正确结果。',
}
batch.write()
