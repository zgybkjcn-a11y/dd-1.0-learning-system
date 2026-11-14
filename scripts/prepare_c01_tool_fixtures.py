"""Build and replay synthetic C01 Tool protocol fixtures, without a model or server.

Only HTTPConnection is replaced in a private import of the pinned Tool. Its public
methods, transport allowlist, identity recheck and evidence projection run intact.
These are protocol fixtures, not proof of gateway/service or model acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / 'docs/quality/c01-scenarios-v1.json'
TOOL = ROOT / 'deploy/open-webui-reuse/readonly_study_tools.py'
BINDING = {
    'syn_math_a': 'math-g7-upper', 'syn_a_1': '2', 'syn_a_2': '5',
    'syn_math_b': 'math-g2-upper', 'syn_biology_c': 'biology-g7-upper',
    'syn_c_1': '2', 'syn_concept_a': 'synthetic-concept-a',
    'syn_question_a_v1': 'synthetic-question-a-v1',
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def fresh(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink output is not supported')
    path.mkdir(parents=True, exist_ok=False)
    return path


def page_evidence(pdf_sha, printed=1, pdf_page=3):
    book, edition = 'math-g7-upper', 'pep-2022-standard-current'
    source = 'dd-textbook-' + digest(f'{book}\n{edition}\n{pdf_sha}'.encode())
    return {
        'schema': 'dd-textbook-page-evidence-v1', 'kind': 'page_location',
        'source_binding': 'catalogue_sha256', 'locator_precision': 'page',
        'review_status': 'location_only', 'quote_status': 'unavailable',
        'supports_textbook_answer': False, 'eligible_as_grading_basis': False,
        'book_id': book, 'book_title': 'C01 自编合成材料（非教材）', 'subject': 'math',
        'semester': 'upper', 'edition': 'synthetic protocol fixture', 'edition_id': edition,
        'pdf_sha256': pdf_sha, 'chapter_id': '2', 'chapter_title': '合成练习', 'grade': 7,
        'source_ref': source, 'evidence_id': 'dd-page-' + digest(f'{source}\n{pdf_page}'.encode()),
        'printed_page': printed, 'pdf_page': pdf_page,
    }


def prepare(output):
    import fitz

    scenarios = read(SCENARIOS)
    if digest(TOOL.read_bytes()) != scenarios['runtime_candidate']['tool_sha256']:
        raise ValueError('Tool source changed; freeze a new scenario revision first')
    output = fresh(output)
    day = today()
    doc = fitz.open()
    rows = []
    for i in range(5):
        page = doc.new_page()
        name = {2: 'excerpt_one', 3: 'excerpt_two', 4: 'injection'}.get(i)
        text = 'C01 自编合成材料，仅用于协议演练，非真实教材审核。'
        if name:
            text += '\n\n' + scenarios['fixtures'][name]['text']
        remaining = page.insert_textbox(fitz.Rect(48, 48, 540, 780), text,
                                       fontsize=14, fontname='china-s')
        if remaining < 0:
            raise ValueError('synthetic PDF overflow')
        rows.append((name, text))
    pdf = doc.tobytes()
    (output / 'synthetic.pdf').write_bytes(pdf)
    excerpts = {}
    for index, (name, text) in enumerate(rows):
        if name is None:
            continue
        fixture = scenarios['fixtures'][name]
        # Check the generated document itself, not just the source string.
        extracted = ''.join(doc[index].get_text().split())
        if ''.join(fixture['text'].split()) not in extracted:
            raise ValueError('synthetic PDF text extraction differs')
        png = doc[index].get_pixmap().tobytes('png')
        (output / (name + '.png')).write_bytes(png)
        page = page_evidence(digest(pdf), index - 1, index + 1)
        binding = {k: page[k] for k in ('source_ref', 'pdf_sha256', 'pdf_page',
                                        'printed_page', 'chapter_id')}
        binding.update(text_sha256=digest(fixture['text'].encode()),
                       context_sha256=digest(fixture['context'].encode()), image_sha256=digest(png))
        # These labels exercise the wire contract. They are not review signatures.
        review = {'synthetic_protocol_fixture': True, 'actual_content_review': False,
                  'teacher_reviewed': False, 'binding': binding, 'revision': 1,
                  'reviewed_on': day.isoformat(), 'valid_until': (day + timedelta(days=1)).isoformat()}
        review_sha = digest(canonical(review))
        eid = 'dd-excerpt-' + digest(canonical({'binding': binding, 'review_sha256': review_sha}))
        evidence = {**page, **binding, 'schema': 'dd-textbook-excerpt-evidence-v1',
                    'kind': 'assistant_reviewed_excerpt', 'evidence_id': eid,
                    'page_evidence_id': page['evidence_id'], 'review_sha256': review_sha,
                    'review_status': 'assistant_checked_excerpt', 'quote_status': 'layout_normalized_transcription',
                    'teacher_reviewed': False, 'fully_reviewed_page': False, 'review_revision': 1,
                    'reviewed_on': review['reviewed_on'], 'valid_until': review['valid_until']}
        path = '/api/v1/textbooks/math-g7-upper/passages/' + eid
        excerpts[name] = {'id': name, 'text': fixture['text'], 'context': fixture['context'],
                          'evidence': evidence, 'detail_path': path, 'image_path': path + '/image'}
        write(output / (name + '-review.json'), review)
    doc.close()
    write(output / 'excerpts.json', excerpts)
    write(output / 'binding.json', {'symbols': BINDING, 'scope': 'in-memory synthetic protocol only',
          'chapter_meaning': 'Synthetic fixture chapters; no claim about real textbook contents.',
          'edition_id': 'pep-2022-standard-current is a required Tool protocol discriminator, not real provenance.'})
    write(output / 'scenarios.json', scenarios)
    write(output / 'manifest.json', {
        'schema': 'dd-c01-tool-protocol-packet-v1', 'prepared_on': day.isoformat(),
        'scenario_sha256': digest(SCENARIOS.read_bytes()), 'tool_sha256': digest(TOOL.read_bytes()),
        'scenario_canonical_sha256': digest(canonical(scenarios)),
        'material_kind': 'assistant_authored_synthetic_protocol_fixtures',
        'gateway_or_service_acceptance': False, 'actual_content_review': False,
        'model_calls': 0, 'model_acceptance': None,
        'files': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()},
    })
    return output


def load_packet(packet):
    packet = Path(packet).absolute()
    if any(p.is_symlink() for p in (packet, *packet.parents)):
        raise ValueError('symlink packet')
    if (packet / 'manifest.json').is_symlink():
        raise ValueError('symlink manifest')
    manifest = read(packet / 'manifest.json')
    expected = {'synthetic.pdf', 'excerpts.json', 'binding.json', 'scenarios.json'}
    expected |= {name + suffix for name in ('excerpt_one', 'excerpt_two', 'injection')
                 for suffix in ('.png', '-review.json')}
    if set(manifest['files']) != expected:
        raise ValueError('unexpected packet files')
    for name, sha in manifest['files'].items():
        path = packet / name
        if path.is_symlink() or digest(path.read_bytes()) != sha:
            raise ValueError('packet asset changed: ' + name)
    if manifest['tool_sha256'] != digest(TOOL.read_bytes()):
        raise ValueError('Tool source changed')
    scenarios = read(packet / 'scenarios.json')
    if (manifest['scenario_sha256'] != digest(SCENARIOS.read_bytes())
            or manifest['scenario_canonical_sha256'] != digest(canonical(scenarios))
            or scenarios != read(SCENARIOS) or read(packet / 'binding.json')['symbols'] != BINDING):
        raise ValueError('scenario or binding changed')
    if manifest['prepared_on'] != today().isoformat():
        raise ValueError('prepare a fresh packet for the actual execution day')
    return manifest, scenarios, read(packet / 'excerpts.json')


class Protocol:
    """Synthetic REST responses below the actual Tool transport; never a gateway."""

    def __init__(self, module, excerpts, fixture_names, manifest_sha):
        self.module, self.excerpts = module, deepcopy(excerpts)
        self.fixture_names, self.manifest_sha = set(fixture_names), manifest_sha
        self.trace, self.sessions = [], 0

    def search(self):
        names = [n for n in ('excerpt_one', 'excerpt_two', 'injection') if n in self.fixture_names]
        if self.fixture_names & {'expired', 'tampered', 'context_changed'}:
            names = ['excerpt_one']
        items = [deepcopy(self.excerpts[n]) for n in names]
        if 'expired' in self.fixture_names:
            items[0]['evidence']['valid_until'] = (today() - timedelta(days=1)).isoformat()
        if 'tampered' in self.fixture_names:
            items[0]['text'] += '篡改'
        status = next((x for x in ('no_evidence', 'low_relevance', 'insufficient_evidence')
                       if x in self.fixture_names), 'reviewed_excerpts_only')
        pages = [{'book_title': 'C01 合成定位', 'printed_page': 1, 'pdf_page': 3,
                  'content_title': '仅原页定位', 'evidence': page_evidence(items[0]['evidence']['pdf_sha256']
                    if items else self.excerpts['excerpt_one']['evidence']['pdf_sha256'])}]
        result = {'book_id': 'math-g7-upper', 'chapter_id': '2', 'items': pages}
        if 'page_only' in self.fixture_names:
            return result
        ids = [p['evidence']['evidence_id'] for p in items]
        result.update(mode='passages', passage_result={
            'schema': 'dd-textbook-passage-result-v1', 'manifest_sha256': self.manifest_sha,
            'timezone': 'Asia/Shanghai', 'checked_on': today().isoformat(),
            'scope': {'book_id': 'math-g7-upper', 'chapter_id': '2'}, 'items': items,
            'retrieval': {'schema': 'dd-retrieval-coverage-v1', 'method': 'bounded-rules-v1',
                          'coverage_complete': True, 'coverage_scope': 'loaded_reviewed_excerpts_only',
                          'status': status, 'display_order': ids, 'ranking': [{'evidence_id': i} for i in ids]},
            'grounding': {'status': status, 'can_quote_textbook': bool(items),
                          'can_answer_from_textbook': False, 'eligible_as_grading_basis': False},
            'answer': {'claims': [{'kind': 'direct_quote', 'text': p['text'],
                                  'evidence_id': p['evidence']['evidence_id']} for p in items],
                       'generated_answer': None},
        })
        return result

    def respond(self, host, method, path, body, headers):
        route = urlsplit(path).path
        if 'foreign' in host or host not in {'open-webui', 'learning-gateway'}:
            raise AssertionError('unexpected synthetic peer')
        if host == 'open-webui':
            assert route == '/api/v1/auths/' and method == 'GET'
            assert headers['Cookie'] == 'token=synthetic-token'
            return {'id': 'synthetic-parent', 'role': 'user'}
        assert 0 < int(headers['X-DD-Study-Budget-Ms']) <= 12000
        assert '__Host-dd_learning_session=synthetic-session' in headers['Cookie']
        if route == '/learning/api/v1/auth/session':
            self.sessions += 1
            return {'server_context_mode': True, 'account_id': 'synthetic-account',
                    'learner_id': 'synthetic-child-a',
                    'context_version': 2 if 'context_changed' in self.fixture_names and self.sessions > 1 else 1}
        assert headers['X-Learner-Context-Version'] == '1'
        args = json.loads(body) if body is not None else {k: v[0] for k, v in parse_qs(urlsplit(path).query).items()}
        if method == 'POST':
            assert route == '/learning/api/v1/textbooks/search'
            assert headers['X-CSRF-Token'] == 'synthetic-csrf' and headers['Origin'] == self.module.ORIGIN
        else:
            assert method == 'GET'
        if route.endswith('/textbooks'):
            return {'items': [{'id': book, 'title': '合成书 ' + subject, 'subject': subject, 'grade': 7,
                              'chapters': [{'id': '2', 'title': '合成章一'}, {'id': '5', 'title': '合成章二'}]}
                             for book, subject in [('math-g7-upper', 'math'), ('biology-g7-upper', 'biology')]]}
        if route.endswith('/textbooks/search'):
            assert args['book_id'] == 'math-g7-upper' and args['chapter_id'] == '2'
            if 'timeout' in self.fixture_names:
                raise TimeoutError('synthetic transport timeout; no actual 12-second wait')
            return self.search()
        if '/passages/' in route:
            eid = route.rsplit('/', 1)[-1]
            item = next(p for p in self.excerpts.values() if p['evidence']['evidence_id'] == eid)
            assert args['chapter_id'] == '2'
            return {'schema': 'dd-textbook-passage-detail-v1', 'manifest_sha256': self.manifest_sha,
                    'timezone': 'Asia/Shanghai', 'checked_on': today().isoformat(), 'item': item}
        assert route in {'/learning/api/v1/math-references', '/learning/api/v1/study-support'}
        book = args.get('book_id', 'math-g7-upper')
        assert book in {'math-g7-upper', 'biology-g7-upper'} and args['chapter_id'] == '2'
        if 'concept_id' in args:
            assert args['concept_id'] == BINDING['syn_concept_a']
        if 'question_version_id' in args:
            assert args['question_version_id'] == BINDING['syn_question_a_v1']
        return {'scope': {'book_id': book, 'chapter_id': '2', 'subject': args.get('subject', 'math')},
                'reference_only': True, 'eligible_as_grading_basis': False,
                'reference_sha256': digest(b'C01 synthetic local reference'),
                'concepts': [] if book.startswith('biology') else [
                    {'id': BINDING['syn_concept_a'], 'title': '合成数量关系',
                     'explanation': '本地合成参考：先辨认每个符号表示的数量。',
                     'checks': ['第一盒的数量用哪个符号？'], 'pages': []}],
                'questions': [] if book.startswith('biology') else [
                    {'book_id': book, 'question_version_id': BINDING['syn_question_a_v1'],
                     'chapter_id': '2', 'title': '合成练习入口'}],
                'study_steps': [{'title': '观察', 'prompt': '材料讨论什么条件？'}]}

    def connection(self, host, port, timeout):
        protocol = self

        class Connection:
            def connect(self):
                self.sock = self

            def settimeout(self, seconds):
                assert 0 < seconds <= 12

            def shutdown(self, how):
                pass

            def request(self, method, path, body, headers):
                protocol.trace.append({'host': host, 'port': port, 'method': method, 'path': path,
                                       'json': json.loads(body) if body is not None else None,
                                       'budget_ms': headers.get('X-DD-Study-Budget-Ms')})
                self.data = protocol.respond(host, method, path, body, headers)

            def getresponse(self):
                raw = json.dumps(self.data, ensure_ascii=False).encode()
                return SimpleNamespace(status=200, read=lambda limit: raw[:limit], getheader=lambda key: None)

            def close(self):
                pass

        assert (host, port) in {('open-webui', 8080), ('learning-gateway', 8000)} and 0 < timeout <= 12
        return Connection()


@contextmanager
def bound_tool(excerpts, fixtures, manifest_sha):
    spec = importlib.util.spec_from_file_location('c01_isolated_readonly_tool', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    protocol = Protocol(module, excerpts, fixtures, manifest_sha)
    # Replace this module's reference only. Never patch global http.client or sockets.
    module.http = SimpleNamespace(client=SimpleNamespace(HTTPConnection=protocol.connection,
                                 HTTPException=module.http.client.HTTPException))
    yield module, module.Tools(), protocol


def invoke(excerpts, fixtures, manifest_sha, call):
    from fastapi import Request

    with bound_tool(excerpts, fixtures, manifest_sha) as (module, tool, protocol):
        events = []

        async def emit(event):
            events.append(event)

        request = Request({'type': 'http', 'headers': [(b'cookie',
            b'token=synthetic-token; __Host-dd_learning_session=synthetic-session; __Host-dd_learning_csrf=synthetic-csrf')]})
        args = {k: BINDING.get(v, v) for k, v in call['arguments'].items()}
        visible_args = deepcopy(args)
        args.update(__user__={'id': 'synthetic-parent'}, __request__=request)
        if call['method'] != 'get_study_catalogue':
            args['__event_emitter__'] = emit
        result = json.loads(asyncio.run(getattr(tool, call['method'])(**args)))
        return {'method': call['method'], 'bound_arguments': visible_args,
                'output': result, 'citation_events': events, 'transport_trace': protocol.trace}


def check_result(case, record):
    output, events = record['output'], record['citation_events']
    fixtures = set(case['fixtures'])
    error = next((code for name, code in [('expired', 'REFERENCE_INVALID'), ('tampered', 'REFERENCE_INVALID'),
                  ('context_changed', 'CONTEXT_CHANGED'), ('timeout', 'RETRIEVAL_TIMEOUT')] if name in fixtures), None)
    if error:
        assert output['error'] == error and not events
        assert not any(k in output for k in ('passages', 'pages', 'answer', 'concepts'))
        return
    assert 'error' not in output and output['eligible_as_grading_basis'] is False
    method = record['method']
    if method == 'get_study_catalogue':
        assert {b['id'] for b in output['books']} == {'math-g7-upper', 'biology-g7-upper'}
    elif method == 'search_textbook':
        if 'page_only' in fixtures:
            assert output['grounding']['status'] == 'incomplete' and not output['grounding']['can_quote_textbook']
            assert len(events) == 1 and events[0]['data']['metadata'][0]['kind'] == 'page_location'
            return
        expected_status = next((s for s in ('no_evidence', 'low_relevance', 'insufficient_evidence')
                                if s in fixtures), 'reviewed_excerpts_only')
        assert output['grounding']['status'] == expected_status
        claims = output['answer']['claims']
        assert len(claims) == len(output['passages']) == len(events)
        assert bool(claims) == (expected_status == 'reviewed_excerpts_only')
        assert output['grounding']['can_answer_from_textbook'] is False
        for claim, passage, event in zip(claims, output['passages'], events):
            evidence = passage['evidence']; data = event['data']
            assert claim['text'] == passage['text'] == data['document'][0]
            assert claim['evidence_id'] == evidence['evidence_id'] == data['source']['id']
            assert data['source']['url'] == passage['url']
            assert data['metadata'][0]['printed_page'] == evidence['printed_page']
            assert data['metadata'][0]['pdf_page'] == evidence['pdf_page']
            assert not evidence['teacher_reviewed'] and not evidence['fully_reviewed_page']
        trace = record['transport_trace']
        assert sum(t['path'].endswith('/textbooks/search') for t in trace) == 2
        assert trace[-1]['path'].endswith('/auth/session')
    else:
        assert output['scope']['book_id'] == record['bound_arguments']['book_id']
        if method == 'get_study_support':
            assert output['study_steps'] and output['scope']['subject'] == 'biology'
        elif method == 'get_math_question_reference':
            assert output['questions'][0]['question_version_id'] == BINDING['syn_question_a_v1']
        else:
            assert output['concepts'][0]['id'] == BINDING['syn_concept_a']
    raw = json.dumps([output, events])
    assert all(s not in raw for s in ('synthetic-parent', 'synthetic-child-a', 'synthetic-token', 'synthetic-session'))


def verify(packet, output):
    manifest, scenarios, excerpts = load_packet(packet)
    output = fresh(output)
    records = []
    manifest_sha = digest((Path(packet) / 'manifest.json').read_bytes())
    for case in scenarios['cases']:
        results = []
        for call in case['required_calls_in_order']:
            result = invoke(excerpts, case['fixtures'], manifest_sha, call)
            results.append(result)
            write(output / (case['id'] + '.json'), {'case_id': case['id'], 'tool_steps': results,
                  'model_case_state': 'not_run', 'model_output': None, 'teaching_score': None})
            check_result(case, result)
        records.append({'case_id': case['id'], 'tool_steps_checked': len(results),
                        'fixture_state': 'passed' if results else 'no_tool_step_specified',
                        'model_case_state': 'not_run'})
    summary = {'schema': 'dd-c01-tool-protocol-verification-v1', 'state': 'passed',
               'packet_manifest_sha256': manifest_sha, 'cases': records,
               'tool_steps_checked': sum(r['tool_steps_checked'] for r in records),
               'model_cases_executed': 0, 'model_calls': 0, 'model_acceptance': None,
               'teaching_score': None, 'network_connections': 0,
               'gateway_service_executed': False, 'tool_total_budget_seconds': 12,
               'timeout_scope': 'injected transport timeout, not elapsed latency measurement'}
    write(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    prep = subs.add_parser('prepare'); prep.add_argument('--output', type=Path, required=True)
    check = subs.add_parser('verify'); check.add_argument('--packet', type=Path, required=True)
    check.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare(args.output))
    else:
        print(json.dumps(verify(args.packet, args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
