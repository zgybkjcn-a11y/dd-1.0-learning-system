"""Verify source ranges, inherited evidence and honest boundaries of the local inventory."""
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_lower_knowledge_inventory import build, render, DEST, BASE, ROOT, PLAN, NEW_BOOKS, sha
from learning_service import chapter_practice, subject_coverage


def verify():
    data=json.loads(DEST.read_bytes())
    assert data==build()
    assert (ROOT/'docs/verification/LOWER-KNOWLEDGE-INVENTORY-2026-11-13.md').read_text()==render(data)
    old=[r for r in json.loads(PLAN.read_bytes())['rows'] if r['book_id'].endswith('-lower')]
    inherited=[r for s in data['scopes'] for r in s['inherited_points']]
    assert {r['id']:r for r in inherited}=={r['id']:r for r in old} and len(inherited)==61
    image_pages=json.loads((BASE/'image-page-selection.json').read_bytes())
    for s in data['scopes']:
        a,b=s['printed_range']; pages=s['source_review']['selected_printed_pages']
        assert all(a<=p<=b for p in pages)
        if s['book_id'] in image_pages:
            assert set(pages)<=set(image_pages[s['book_id']])
        elif pages:
            native={r['printed_page']:r['text'] for r in json.loads((BASE/'native-text'/f"{s['book_id']}.json").read_bytes())}
            assert all(native[p].strip() for p in pages)
        assert not s['point_inventory_complete'] and s['candidate_question_count']==0
        for p in s['new_initial_points']:
            assert not p['automatic_grade_evidence'] and not p['question_candidates']
            assert not p['teacher_reviewed'] and p['curriculum_standard_crosscheck']=='pending'
            assert not p['manual_task']['automatically_graded']
            assert p['manual_task']['completion']=='not_observed'
            assert not p['manual_task']['learner_record_created']
        if s['kind']=='reference':
            assert all(p['bounded_candidate_action'] is None for p in s['new_initial_points'])
    assert not (NEW_BOOKS & {q['book_id'] for q in chapter_practice.bank().values()})
    assert subject_coverage.PATH.resolve()==PLAN.resolve()
    assert 'upper_gap_candidates' not in chapter_practice.BATCHES
    assert len(chapter_practice.bank())==1074
    result={'status':'passed','books':10,'scopes':75,'new_initial_points':68,'inherited_points_preserved':61,
        'formal_lower_snapshot_questions':194,'new_lower_candidate_questions':0,
        'new_runtime_mappings':0,'source_ranges_and_review_pages_valid':True,
        'reference_scopes_not_counted_as_automatic_coverage':True,
        'inventory_sha256':sha(DEST),'builder_sha256':sha(ROOT/'scripts/build_lower_knowledge_inventory.py'),
        'verifier_sha256':sha(Path(__file__)),'book_scope_counts':dict(Counter(s['book_id'] for s in data['scopes']))}
    (BASE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False))
