"""Historical published Tool source against A07 service; no formal WebUI DB."""
import importlib.util
import json
from pathlib import Path

from learning_service.passage_evidence import digest
from test_runtime_passages import stack, runtime_bundle, QUERY
from test_readonly_study_tools import chat_tools, invoke
from test_math_references import reference_family
from test_family_math import family


def test_historical_tool_100_retains_pages_without_excerpt_authority(stack):
    path = Path(__file__).parent / 'fixtures/readonly_study_tools_v1_0_0.py'
    assert digest(path.read_bytes()) == '733ad01dc38ed6b09fcae69047ff731e0eb83d59b0a2dd2432595a3508c6a650'
    spec = importlib.util.spec_from_file_location('historical_tool', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    tool = module.Tools(); tool._fetch = stack['tool']._fetch
    data, events = invoke((tool, *stack['fixture'][1:]), 'search_textbook', **QUERY)
    assert data['pages'] and events
    assert '原创合成规则' not in json.dumps(data, ensure_ascii=False) + json.dumps(events, ensure_ascii=False)
    assert not data.get('passages') and not data.get('answer')
