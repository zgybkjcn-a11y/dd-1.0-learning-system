#!/usr/bin/env python3
"""Reuse the loader protocol against ONLY the new synthetic reuse project."""
import argparse
import hashlib
import json
from pathlib import Path

from probe_reuse_runtime import ROOT, call, compose, save


def probe(run: Path):
    manifest=json.loads((run/'manifest.json').read_text())
    if not manifest['project'].startswith('dd-learning-reuse-'):
        raise ValueError('new reuse project required; historical P0 is excluded')
    cid=compose(run,'ps','-q','open-webui',restored=(run/'compose.restore.json').exists())
    call(['docker','cp',str(ROOT/'learning_service/tools.py'),cid+':/tmp/dd-reuse-tools.py'])
    call(['docker','cp',str(run/'secrets/learning_adapter_secret'),cid+':/tmp/dd-reuse-adapter.secret'])
    # Same native API/loader protocol, with new issuer/learner/context and source.
    source=(ROOT/'scripts/isolated_tool_probe.py').read_text()
    source=source.replace('/tmp/dd-p0-tools.py','/tmp/dd-reuse-tools.py')
    source=source.replace('os.environ["DD_LEARNING_ADAPTER_SECRET"]','Path("/tmp/dd-reuse-adapter.secret").read_text()')
    source=source.replace('"dd-p0"','"synthetic-webui-installation"').replace('p0-learner-a','synthetic-learner')
    source=source.replace('DD Learning V1 P0','DD Learning V1 isolated reuse').replace('mock-only P0 adapter','mock-only reuse adapter')
    source=source.replace(
        'assert len(result["items"]) == 1 and result["items"][0]["id"] == "synthetic-learner"',
        '''assert result == {"learner_count": 1, "selection_in_workbench": True,
                          "workbench_url": "https://172.19.116.53/learning/ui"}
        mistakes = json.loads(await loaded["get_mistakes"]["callable"]())
        progress = json.loads(await loaded["get_progress"]["callable"]())
        assert len(mistakes["items"]) == 1 and "error" not in progress
        assert all(set(item) <= {"id", "objective_id", "status", "diagnosis_status"} for item in mistakes["items"])
        assert set(progress) <= {"cards", "attempts", "workbench_url"}''')
    results={}
    for phase in ('register','load'):
        output=call(['docker','exec','-i',cid,'python','-',phase],stdin=source,timeout=120)
        rows=[json.loads(line) for line in output.splitlines() if line.startswith('{')]
        result=rows[-1]
        result.pop('user_id',None)
        results[phase]=result
    results['scope']={'learner_count_projection':True,'shared_context_reads':True,
                      'mistakes_and_progress_minimal_projection':True,'formal_tool_sharing':False,
                      'model_call':False,'native_browser_callback':False,
                      'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'protocol_source_sha256':hashlib.sha256((ROOT/'scripts/isolated_tool_probe.py').read_bytes()).hexdigest()}
    save(run/'tools-report.json',results)
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True)
    a=p.parse_args();print(json.dumps(probe(a.directory.resolve())))
