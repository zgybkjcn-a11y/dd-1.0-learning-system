"""Author two local candidates for uncovered chapter-two error analysis."""
from chapter_practice_authoring import Batch


batch = Batch('math_g7_action_candidates')

batch.choice(
    'math-g7-upper', '2', 'normal', '减去负数的错误辨析',
    '小明计算4−(−3)=1，并说“减去负数就是减去它的绝对值”。哪项指出错误并给出正确结果？',
    '减去负数要加上它的相反数，4−(−3)=4+3=7。',
    [
        '运算过程正确，但结果应为−7。',
        '减去负数仍是减去3，所以结果是1。',
        '两个负号可以直接删去，结果是4−3=1。',
    ],
    '把减数−3看成一个整体，再用“减去一个数等于加上它的相反数”核对。',
    '4−(−3)=4+3=7。原算式把减去负数误作减去正数。',
)
batch.questions[-1]['coverage'] = {
    'point_id': 'math-g7-upper:2:subtract',
    'task': 'distinguish',
    'family': 'g7:subtract:negative-subtrahend-error',
    'role': 'direct',
    'rationale': '要求判断具体错误并给出正确变形与结果；不同于只计算减法结果。',
}

batch.choice(
    'math-g7-upper', '2', 'normal', '负因数和零因子辨析',
    '小林作出两项判断：①(−1)×(−2)×(−3)=6；②(−2)×0×4=0。哪项评价正确？',
    '①错误，积为−6；②正确，含零因子的积为0。',
    [
        '①正确，积为6；②错误，忽略零因子后积为−8。',
        '①错误，积为−6；②错误，忽略零因子后积为−8。',
        '①正确，积为6；②正确，含零因子的积为0。',
    ],
    '分别检查非零负因子的个数奇偶，再检查乘积中是否有零因子。',
    '三个非零负因子个数为奇数，积为负；任何因数为0，积就是0。',
)
batch.questions[-1]['coverage'] = {
    'point_id': 'math-g7-upper:2:multiply',
    'task': 'distinguish',
    'family': 'g7:multiply:zero-and-negative-parity-diagnosis',
    'role': 'direct',
    'rationale': '分别判断奇数个非零负因子的积与含零因子的积；同时要求识别两类常见错误。',
}

batch.write()
