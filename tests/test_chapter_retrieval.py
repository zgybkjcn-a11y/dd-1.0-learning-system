"""Scoped retrieval and incomplete-result contracts, with synthetic data only."""
from copy import deepcopy
import json

import pytest

from learning_service.gateway_http import GatewayResult
from learning_service.textbooks import bounded_references, search_scope, SEARCH_CANDIDATE_LIMIT
from scripts import textbook_passage_retrieval as candidate
from scripts.textbook_passage_sample import quote_answer, verify_quote_answer
from test_textbooks import retrieval_gateway
from test_login_gateway import gateway_env, gateway_login
from test_browser_auth import auth_env, csrf
from test_learning_service import env
from test_readonly_study_tools import chat_tools, invoke, module
from test_family_math import family
from test_math_references import reference_family


@pytest.fixture
def corpus():
    profiles = {f'synthetic-{name}': name for name in candidate.CONCEPTS}
    passages = [{'id': key, 'text': f'ORIGINAL SYNTHETIC rule text for {name}.',
                 'retrieval_terms': ['synthetic'],
                 'evidence': {'evidence_id': 'e-' + name, 'book_id': 'math-g7-upper',
                              'chapter_id': '2', 'pdf_page': 70 - i, 'printed_page': 63 - i}}
                for i, (key, name) in enumerate(sorted(profiles.items()))]
    return passages, profiles


def retrieve(corpus, query, **kwargs):
    passages, profiles = corpus
    return candidate.retrieve(passages, 'math-g7-v1', kwargs.get('book_id', 'math-g7-upper'),
                              kwargs.get('chapter_id', '2'), query, concept_by_id=profiles)


@pytest.mark.parametrize('query,concepts', [
    ('两个异号数求和该取哪个符号？', {'addition'}),
    ('-8 + 13 的运算用哪条规则？', {'addition'}),
    ('r－（－z）如何转成加号形式？', {'subtraction'}),
    ('请定位减法法则。', {'subtraction'}),
    ('j·k=1 对应什么定义？', {'reciprocal'}),
    ('两数的乘积为一时，它们属于哪种关系？', {'reciprocal'}),
    ('7*(2+8) 的展开用哪一条法则？', {'distribution'}),
    ('(r+s)t 的变形用哪条规则？', {'distribution'}),
    ('5*3+5*9 改写时依据哪条规律？', {'distribution'}),
    ('三个负因子连乘的符号规则是什么？', {'product_sign'}),
    ('两个负数求和与相乘的符号分别查哪处？', {'addition', 'product_sign'}),
    ('(r-s)*v 先转成 (r+(-s))*v 再展开的依据是什么？', {'subtraction', 'distribution'}),
])
def test_rule_intents_select_bound_full_quotes(corpus, query, concepts):
    result = retrieve(corpus, query)
    assert {corpus[1][p['id']] for p in result['items']} == concepts
    assert result['retrieval']['coverage_complete'] is True
    assert result['retrieval']['coverage_scope'] == 'loaded_reviewed_excerpts_only'
    assert result['grounding']['can_answer_from_textbook'] is False
    answer = quote_answer(result)
    assert verify_quote_answer(result, answer) and answer['generated_answer'] is None
    assert all('retrieval_terms' not in p for p in result['items'])


@pytest.mark.parametrize('query', [
    '给出分配律的证明。', '结合律与加法如何联系？', '查减法的发明历史。',
    '有理数除法中倒数的用法。', '矩阵分配律的条件。', '画出相加的数轴。',
    '加法练习的标准答案。', '求出 7*(2+8) 的数值结果。',
    '倒数函数的图像。', '非整数次幂的符号。',
])
def test_related_words_do_not_support_out_of_scope_tasks(corpus, query):
    result = retrieve(corpus, query)
    assert result['items'] == []
    assert result['retrieval']['reason'] == 'unsupported_task'
    assert not result['grounding']['can_quote_textbook']


def test_no_evidence_low_relevance_and_partial_support_are_distinct(corpus):
    assert retrieve(corpus, '请帮我理解这段话。')['grounding']['status'] == 'low_relevance'
    assert retrieve(corpus, '加法', chapter_id='5')['grounding']['status'] == 'no_evidence'
    passages, profiles = corpus
    reduced = ([p for p in passages if profiles[p['id']] != 'product_sign'], profiles)
    incomplete = retrieve(reduced, '相加与相乘的符号分别是什么规则？')
    assert incomplete['grounding']['status'] == 'insufficient_evidence'
    assert not incomplete['items']


def test_scope_filter_precedes_limit_even_with_forty_off_scope_hits(corpus):
    passages, profiles = corpus
    target = next(p for p in passages if profiles[p['id']] == 'subtraction')
    outside = []
    for i in range(40):
        p = deepcopy(target); p['id'] = f'outside-{i}'; p['evidence'].update(evidence_id=f'outside-{i}', chapter_id='1')
        outside.append(p)
    result = retrieve((outside + [target], profiles), '请查减法规则。')
    assert [p['id'] for p in result['items']] == [target['id']]
    assert result['retrieval']['scoped_count'] == 1
    with pytest.raises(ValueError, match='book outside current grade'):
        candidate.retrieve(None, 'math-g2-v1', 'math-g7-upper', '2', 'query')
    assert retrieve(corpus, '减法', book_id='math-g7-lower', chapter_id='7')['items'] == []


def test_rank_dedup_and_display_order_are_separate(corpus):
    passages, profiles = corpus
    addition = next(p for p in passages if profiles[p['id']] == 'addition')
    sign = next(p for p in passages if profiles[p['id']] == 'product_sign')
    addition['evidence'].update(pdf_page=60, evidence_id='z')
    sign['evidence'].update(pdf_page=70, evidence_id='a')
    result = retrieve(([addition, deepcopy(addition), sign], profiles), '求和与相乘的符号分别查哪条？')
    assert [p['evidence']['evidence_id'] for p in result['items']] == ['a', 'z']
    assert result['retrieval']['display_order'] == ['z', 'a']
    assert result['retrieval']['scoped_count'] == 2
    conflict = deepcopy(addition); conflict['text'] = 'changed'
    with pytest.raises(ValueError, match='conflicting excerpt identity'):
        retrieve(([addition, conflict], profiles), '加法')


@pytest.mark.parametrize('query', ['', 'a' * 121, 'text\n', ['query']])
def test_bad_queries_rejected(corpus, query):
    with pytest.raises(ValueError, match='invalid query'): retrieve(corpus, query)


def synthetic_vector(scope, pages):
    return {'documents': [['ORIGINAL SYNTHETIC locator'] * len(pages)], 'metadatas': [[
        {'file_id': scope['book']['file_id'], 'page_number': page, 'edition': 'pep-2022-standard-current'} for page in pages]]}


def test_legacy_top40_counterexample_must_report_incomplete_coverage():
    scope = search_scope('math-g7-v1', {'book_id': 'math-g7-upper', 'chapter_id': '2', 'query': 'synthetic'})
    rows = synthetic_vector(scope, [8] * 40 + [38])
    truncated = {k: [v[0][:40]] for k, v in rows.items()}
    result = bounded_references(scope, truncated, candidate_limit=40)
    assert not result['items']
    assert result['retrieval']['status'] == 'incomplete'
    assert result['retrieval']['coverage_complete'] is False
    assert '按页阅读' in result['notice']
    assert bounded_references(scope, rows)['items'][0]['pdf_page'] == 38
    with pytest.raises(ValueError, match='candidate limit'):
        bounded_references(scope, rows, candidate_limit=40)


def test_legacy_selection_keeps_rank_before_page_sort_and_dedup():
    scope = search_scope('math-g7-v1', {'book_id': 'math-g7-upper', 'chapter_id': '2', 'query': 'synthetic'})
    result = bounded_references(scope, synthetic_vector(scope, [49, 49, 38, 47, 34, 48]), candidate_limit=40)
    assert [p['pdf_page'] for p in result['items']] == [34, 38, 47, 49]
    assert [p['retrieval_rank'] for p in result['items']] == [5, 3, 4, 1]
    ranked = sorted(result['items'], key=lambda p: p['retrieval_rank'])
    assert result['retrieval']['ranking'] == [p['evidence']['evidence_id'] for p in ranked]
    assert result['retrieval']['coverage_complete'] is False  # Fewer than 40 is not an exhaustive scan.


def test_gateway_does_not_call_an_empty_truncated_result_no_evidence(retrieval_gateway):
    s, _, bridge, client = retrieval_gateway
    scope = search_scope('math-g7-v1', {'book_id': 'math-g7-upper', 'chapter_id': '2', 'query': 'synthetic'})
    bridge.retrieval_body = json.dumps(synthetic_vector(scope, [8] * 40)).encode()
    response = client.post('/learning/api/v1/textbooks/search', headers={**csrf(s, client), 'X-Learner-Context-Version': '1'},
                           json={'book_id': 'math-g7-upper', 'chapter_id': '2', 'query': 'synthetic'})
    assert response.status_code == 200, response.text
    assert response.json()['items'] == [] and response.json()['retrieval']['status'] == 'incomplete'
    call = next(c for c in bridge.calls if c[2] == '/api/v1/retrieval/query/doc')
    assert json.loads(call[4])['k'] == SEARCH_CANDIDATE_LIMIT
    assert not {'where', 'metadata_filter'} & json.loads(call[4]).keys()


@pytest.mark.parametrize('change', ['revision', 'learner', 'identity', 'post_session_error'])
def test_gateway_checks_context_again_after_vector_query(retrieval_gateway, monkeypatch, change):
    s, db, bridge, client = retrieval_gateway
    original = bridge.send; completed = [False]
    def send(upstream, method, path, headers, body=b'', **kwargs):
        if completed[0] and path == '/api/v1/auth/session':
            if change == 'post_session_error': return GatewayResult(503, b'{"error":{"code":"SERVICE_UNAVAILABLE"}}')
            result = original(upstream, method, path, headers, body, **kwargs)
            data = json.loads(result.body)
            if change == 'identity': data['identity']['subject'] = 'synthetic-other'
            elif change == 'learner': data['learner_id'] = 'synthetic-other'
            else: data['context_version'] += 1
            return GatewayResult(200, json.dumps(data).encode())
        result = original(upstream, method, path, headers, body, **kwargs)
        if path == '/api/v1/retrieval/query/doc': completed[0] = True
        return result
    monkeypatch.setattr(bridge, 'send', send)
    response = client.post('/learning/api/v1/textbooks/search', headers={**csrf(s, client), 'X-Learner-Context-Version': '1'},
                           json={'book_id': 'math-g7-upper', 'chapter_id': '1', 'query': 'synthetic'})
    assert response.status_code == (503 if change == 'post_session_error' else 401 if change == 'identity' else 409)
    assert 'items' not in response.json() and 'synthetic-other' not in response.text


def test_tool_preserves_incompleteness_with_or_without_locations(chat_tools):
    data, _ = invoke(chat_tools, 'search_textbook', query='synthetic', book_id='math-g7-upper', chapter_id='2')
    assert data['pages'] and data['grounding']['status'] == 'incomplete'
    chat_tools[-1].retrieval_result = {'documents': [[]], 'metadatas': [[]]}
    data, events = invoke(chat_tools, 'search_textbook', query='synthetic', book_id='math-g7-upper', chapter_id='2')
    assert not data['pages'] and not events and data['grounding']['status'] == 'incomplete'
    assert data['retrieval']['coverage_complete'] is False
    assert '不据此断言教材没有' in data['grounding']['message']


def test_older_service_without_coverage_does_not_imply_complete_search(chat_tools):
    tool = chat_tools[0]
    data = tool._project('textbooks/search', {'book_id': 'math-g7-upper', 'chapter_id': '2', 'items': []}, 1)
    assert data['grounding']['status'] == 'incomplete'
    assert data['retrieval']['reason'] == 'coverage_not_reported'
    with pytest.raises(module.StudyError, match='REFERENCE_INVALID'):
        tool._project('textbooks/search', {'book_id': 'math-g7-upper', 'chapter_id': '2', 'items': [],
                      'retrieval': {'coverage_complete': True}}, 1)
