"""C01 protocol packet integrity and transport boundaries; no model acceptance."""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import socket

import pytest

from scripts import prepare_c01_tool_fixtures as fixtures


@pytest.fixture
def packet(tmp_path):
    return fixtures.prepare(tmp_path / 'packet')


def test_prescribed_tool_steps_run_without_network_or_global_transport_patch(packet, tmp_path, monkeypatch):
    original = http.client.HTTPConnection

    def forbidden(*args, **kwargs):
        raise AssertionError('network access forbidden')

    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    result = fixtures.verify(packet, tmp_path / 'verification')
    assert http.client.HTTPConnection is original
    assert result['tool_steps_checked'] == 22
    assert result['model_cases_executed'] == result['model_calls'] == 0
    assert len(result['cases']) == 24
    assert sum(r['fixture_state'] == 'no_tool_step_specified' for r in result['cases']) == 2
    assert result['model_acceptance'] is result['teaching_score'] is None
    assert all(r['model_case_state'] == 'not_run' for r in result['cases'])


@pytest.mark.parametrize('name', ['synthetic.pdf', 'excerpt_one.png', 'excerpts.json', 'binding.json'])
def test_changed_packet_is_rejected_before_replay(packet, tmp_path, name):
    path = packet / name
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='packet asset changed'):
        fixtures.verify(packet, tmp_path / 'replay')
    assert not (tmp_path / 'replay').exists()


def test_existing_packet_and_report_are_never_overwritten(packet, tmp_path):
    before = (packet / 'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        fixtures.prepare(packet)
    assert (packet / 'manifest.json').read_bytes() == before
    report = tmp_path / 'report'; report.mkdir()
    marker = report / 'summary.json'; marker.write_text('historical failure')
    with pytest.raises(FileExistsError):
        fixtures.verify(packet, report)
    assert marker.read_text() == 'historical failure'


def test_next_day_requires_fresh_packet_and_does_not_backdate(packet, tmp_path, monkeypatch):
    now = fixtures.today()
    monkeypatch.setattr(fixtures, 'today', lambda: now + fixtures.timedelta(days=1))
    with pytest.raises(ValueError, match='actual execution day'):
        fixtures.verify(packet, tmp_path / 'replay')


def test_original_tool_rejects_foreign_hosts_and_write_routes_before_stub(packet):
    _, _, excerpts = fixtures.load_packet(packet)
    with fixtures.bound_tool(excerpts, ['excerpt_one'], '0' * 64) as (module, tool, protocol):
        for host, port, path in [('foreign.invalid', 8000, '/learning/api/v1/textbooks'),
                                 ('learning-gateway', 8000, '/learning/api/v1/mistakes')]:
            with pytest.raises(module.StudyError):
                tool._fetch(host, port, path, 'synthetic-cookie')
        assert protocol.trace == []


def test_modified_claim_and_dual_page_citation_are_detected(packet):
    _, scenarios, excerpts = fixtures.load_packet(packet)
    case = next(c for c in scenarios['cases'] if c['id'] == 'C01-11')
    record = fixtures.invoke(excerpts, case['fixtures'], '0' * 64, case['required_calls_in_order'][0])
    fixtures.check_result(case, record)
    broken = deepcopy(record); broken['output']['answer']['claims'][0]['text'] += '杜撰结论'
    with pytest.raises(AssertionError):
        fixtures.check_result(case, broken)
    broken = deepcopy(record); broken['citation_events'][0]['data']['metadata'][0]['pdf_page'] = 1
    with pytest.raises(AssertionError):
        fixtures.check_result(case, broken)


def test_fixture_injection_stays_in_material_and_does_not_create_transport_calls(packet):
    _, scenarios, excerpts = fixtures.load_packet(packet)
    case = next(c for c in scenarios['cases'] if c['id'] == 'C01-20')
    record = fixtures.invoke(excerpts, case['fixtures'], '0' * 64, case['required_calls_in_order'][0])
    fixtures.check_result(case, record)
    assert 'c01-exfil.invalid' in record['output']['answer']['claims'][0]['text']
    assert all(t['host'] in {'open-webui', 'learning-gateway'} for t in record['transport_trace'])
    assert 'c01-exfil.invalid' not in json.dumps(record['transport_trace'])
    # The Tool carries untrusted material. Whether a model obeys it is not tested here.
