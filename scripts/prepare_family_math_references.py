#!/usr/bin/env python3
"""Freeze reviewed local reference metadata; never import a question or vector."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_service.practice import bank, BANK_SHA256


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def prepare():
    sample = ROOT/'learning_data/verification/family-concept-prototype-20261106'
    manifest = json.loads((sample/'manifest-v2.json').read_text())
    raw = (sample/'demo-v2-data.json').read_bytes()
    if digest(raw) != manifest['data_sha256']:
        raise ValueError('reference sample changed; repeat review')
    payload = json.loads(raw)
    review_raw = (sample/'page-review.json').read_bytes()
    if digest(review_raw) != manifest['page_review_sha256']:
        raise ValueError('location review changed')
    review = json.loads(review_raw)
    questions = bank()
    nodes = {}
    mappings = {}
    for item in payload['items']:
        q, mapping = item['question'], item['mapping']
        if digest(canonical(questions[q['id']])) != mapping['question_sha256']:
            raise ValueError('frozen question changed')
        for node in mapping['concepts']:
            nodes[node['id']] = node
        for node in mapping['prerequisite_preview']:
            key = node['id']
            # Find the full source node in the prototype, including nodes that
            # appear only as prerequisites. This is local reviewed metadata.
            if key not in nodes:
                sys.path.insert(0, str(sample))
                from page_anchors import PagePrototype
                nodes[key] = PagePrototype().nodes[key]
        units = list(q['units'])
        for name, aliases in {'米':['m'],'厘米':['cm'],'千米':['km'],'℃':['摄氏度','度']}.items():
            if name in units:
                units += aliases
        content = {'prompt':q['prompt'],'hint':q['hint'],'input_type':'text','source':q['source'],'practice_bank':'family-word-v1'}
        key = {'numeric_answer':q['answer'],'units':units,'explanation':q['explanation']}
        stored = {'question_id':q['id'].removesuffix('-v1'),'validator_version':'numeric-answer-v1',
                  'content':content,'answer_key':key}
        mappings[q['id']] = {'book_id':q['book_id'],'grade':q['grade'],'chapter_id':q['chapter_id'],
            'question_sha256':mapping['question_sha256'],'stored_version_sha256':digest(canonical(stored)),
            'concept_ids':[n['id'] for n in mapping['concepts']], 'mapping_role':mapping['mapping_role'],
            'title':q['title'],'difficulty':q['difficulty'],'source':q['source']}
    fields = ('id','grade','book_id','pdf_sha256','chapters','title','explanation','checks',
              'textbook_pages','location_status','eligible_as_grading_basis')
    nodes = {key:{field:node[field] for field in fields} for key,node in nodes.items()}
    for node in nodes.values():
        for page in node['textbook_pages']:
            page.pop('image_asset', None)
    snapshot = {'format':'dd-family-math-reference-v1','version':'2026-11-06-original-location-v1',
        'question_bank_sha256':BANK_SHA256,'pdf_sha256':review['pdf_sha256'],
        'concepts':nodes,'question_mappings':mappings,'prerequisite_edges':review['edges'],
        'peer_relations':review['peer_relations'],'provenance':payload['provenance'],
        'reviewed_sample_sha256':manifest['data_sha256'],'reviewed_locations_sha256':manifest['page_review_sha256'],
        'reference_only':True,'eligible_as_grading_basis':False,'teacher_reviewed':False,
        'fully_reviewed_textbook_pages':0}
    data=(json.dumps(snapshot,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    target = ROOT/'learning_service/data/family_concepts_v1.json'
    if target.exists() and target.read_bytes()!=data:
        raise ValueError('existing reference version differs; create a new reviewed version')
    target.write_bytes(data)
    reference = ROOT/'learning_data/verification/faststudy-mapping-20261106'
    for source,name in [('LICENSE-DATA','faststudy-LICENSE-DATA.txt'),('NOTICE','faststudy-NOTICE.txt')]:
        content=(reference/source).read_bytes()
        path=target.parent/name
        if path.exists() and path.read_bytes()!=content:
            raise ValueError('existing source notice differs')
        path.write_bytes(content)
    print(json.dumps({'reference_sha256':digest(data),'concepts':len(nodes),'mapped_questions':len(mappings),
                      'production_database_writes':0,'vectors_written':0},ensure_ascii=False))


if __name__=='__main__':
    prepare()
