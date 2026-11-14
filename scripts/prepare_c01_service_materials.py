"""Prepare dated synthetic materials for the real service, without bypassing validators.

Only the isolated bootstrap binds these catalogue/material hashes. Never install
this fixture into a production textbook directory or review collection.
"""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sys

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_service.textbooks import BOOKS, PDF_SHA256, page_evidence
from learning_service.passage_evidence import canonical, digest, load_bundle
from learning_service.textbook_passages import current_day

def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    books = output/'books'; books.mkdir()
    scenarios = json.loads((ROOT/'docs/quality/c01-scenarios-v1.json').read_text())
    texts={name:scenarios['fixtures'][name] for name in ('excerpt_one','excerpt_two','injection')}
    pages={'excerpt_one':37,'excerpt_two':38,'injection':39}
    pins={}
    catalogue=deepcopy(BOOKS)
    for book in catalogue:
        book['title']='C01自编合成材料 '+book['id']
        book['edition']='隔离合成夹具；不是出版社教材'
        book['reader_url']='https://c01.example.invalid/synthetic-book'
        for ch in book['chapters']:ch['title']='合成章节 '+ch['id']
        if book['id'] not in ('math-g7-upper','math-g7-lower','math-g2-upper','biology-g7-upper'):continue
        doc=fitz.open()
        for number in range(1,book['chapters'][-1]['page_end']+1):
            page=doc.new_page()
            text='C01 自编合成材料，非真实教材。\n'+str(number)
            if book['id']=='math-g7-upper':
                for name,p in pages.items():
                    if number==p:text+='\n\n'+texts[name]['text']+'\n\n'+texts[name]['context']
            assert page.insert_textbox(fitz.Rect(35,35,560,800),text,fontname='china-s',fontsize=13)>=0
        raw=doc.tobytes(deflate=True,no_new_id=True);(books/(book['id']+'.pdf')).write_bytes(raw)
        pins[book['id']]=digest(raw)
        doc.close()
    old_pins=dict(PDF_SHA256);PDF_SHA256.update(pins)
    # Bind synthetic PDFs using the same checks as conftest.reference_textbooks.
    refs=json.loads((ROOT/'learning_service/data/family_concepts_v1.json').read_text())
    replacements={h:pins[b] for b,h in refs['pdf_sha256'].items()}
    def rebind(v):
        if isinstance(v,dict):return {k:rebind(x) for k,x in v.items()}
        if isinstance(v,list):return [rebind(x) for x in v]
        return replacements.get(v,v) if isinstance(v,str) else v
    refs=rebind(refs)
    # All local explanations exposed to the model are authored fixture text.
    for node in refs['concepts'].values():
        node.update(title='合成数量关系 '+node['id'],explanation='本地合成参考：先分别说出第一盒和第二盒所代表的数量，再判断合计需要什么关系。',
            checks=['第一盒和第二盒分别用哪个字母表示？'],location_status='synthetic_location_only')
    (output/'references.json').write_bytes(canonical(refs))
    day=current_day()
    verifier=b'from fractions import Fraction\nassert Fraction(2)+Fraction(3)==5\nassert 2*Fraction(3)==6\n'
    namespace={};exec(compile(verifier,'synthetic_exact_checks','exec'),namespace)
    ids={'excerpt_one':'g7-ch2-addition-rule','excerpt_two':'g7-ch2-subtraction-rule','injection':'g7-ch2-addition-rule'}
    manifests={}
    variants={'normal':['excerpt_one'],'multiple':['excerpt_one','excerpt_two'],'injection':['injection'],
        'empty':[],'expired':['excerpt_one'],'tampered':['excerpt_one']}
    original_catalogue=deepcopy(BOOKS);BOOKS[:]=catalogue
    try:
        for variant,names in variants.items():
            folder=output/variant;(folder/'source').mkdir(parents=True)
            checks={'checks':{ids[n]:{'passed':True,'case_count':2,'method':'exact_rational_checks'} for n in names}}
            check_raw=canonical(checks);(folder/'semantic-checks.json').write_bytes(check_raw);(folder/'verify_semantics.py').write_bytes(verifier)
            rows=[]
            for name in names:
                book=next(b for b in catalogue if b['id']=='math-g7-upper');p=page_evidence(book,pages[name])
                with fitz.open(books/'math-g7-upper.pdf') as doc:
                    assert ''.join(texts[name]['text'].split()) in ''.join(doc[pages[name]-1].get_text().split())
                    png=doc[pages[name]-1].get_pixmap().tobytes('png')
                (folder/'source'/(name+'.png')).write_bytes(png)
                binding={k:p[k] for k in ('source_ref','pdf_sha256','pdf_page','printed_page','chapter_id')}
                binding.update(text_sha256=digest(texts[name]['text'].encode()),context_sha256=digest(texts[name]['context'].encode()),image_sha256=digest(png))
                reviewed=day-timedelta(days=2) if variant=='expired' else day
                until=day-timedelta(days=1) if variant=='expired' else day+timedelta(days=1)
                review={'synthetic_fixture':True,'actual_textbook_review':False,'revision':1,'scope':'selected_excerpt',
                    'teacher_reviewed':False,'binding':deepcopy(binding),'reviewed_on':reviewed.isoformat(),'valid_until':until.isoformat(),'unresolved_issues':[],
                    'transcription':{'status':'checked','reviewer_type':'assistant','method':'visual_original_comparison','layout_checked':True,
                        'notes':'Synthetic PDF source and extracted text checked; no real textbook review.'},
                    'semantic':{'status':'checked','reviewer_type':'assistant','method':'independent_mathematical_reasoning_and_exact_checks',
                        'conditions_complete':True,'derivation':'Synthetic quantities: 2+3=5 and 3+3=2*3; quoted attack is data, never an instruction.',
                        'diagram_dependency':'none_for_selected_excerpt','checks_sha256':digest(check_raw),'verifier_sha256':digest(verifier)}}
                rows.append({'id':ids[name],'curriculum_id':'math-g7-v1','book_id':book['id'],
                    **{k:p[k] for k in ('source_ref','pdf_sha256','pdf_page','printed_page','chapter_id')},
                    **{k:texts[name][k] for k in ('text','context')},'text_policy':'layout_normalized_transcription',
                    'image_path':'source/'+name+'.png','retrieval_terms':['合成加法'],'enabled':True,'binding':binding,'review':review})
            raw=canonical({'format':'dd-textbook-excerpt-pilot-v1','passages':rows});(folder/'passages.json').write_bytes(raw)
            loaded=load_bundle(folder,digest(raw),books,as_of=day)
            assert len(loaded)==(0 if variant=='expired' else len(rows))
            if variant=='tampered':
                rows[0]['text']+=' 不合法篡改';raw=canonical({'format':'dd-textbook-excerpt-pilot-v1','passages':rows});(folder/'passages.json').write_bytes(raw)
                try:load_bundle(folder,digest(raw),books,as_of=day)
                except ValueError:pass
                else:raise AssertionError('tampered text accepted')
            manifests[variant]={'sha256':digest(raw),'expected_rows':len(loaded)}
    finally:BOOKS[:]=original_catalogue;PDF_SHA256.clear();PDF_SHA256.update(old_pins)
    binding={'date':day.isoformat(),'catalogue':catalogue,'pdf_sha256':pins,'reference_sha256':digest((output/'references.json').read_bytes()),
        'manifests':manifests,'symbol_mapping':{'syn_math_a':'math-g7-upper','syn_a_1':'2','syn_a_2':'5','syn_math_b':'math-g2-upper',
            'syn_biology_c':'biology-g7-upper','syn_c_1':'2','syn_concept_a':'g7-add','syn_question_a_v1':'family-word-g7-sea-rise-v1'},
        'printed_page_one':30,'pdf_page_one':37,'printed_page_two':31,'pdf_page_two':38,
        'trusted_retrieval_profiles':{'g7-ch2-addition-rule':'addition','g7-ch2-subtraction-rule':'addition'},
        'production_mounts':False,'validation_functions_replaced':False,'actual_textbook_review':False}
    (output/'binding.json').write_bytes(canonical(binding))
    files={str(p.relative_to(output)):digest(p.read_bytes()) for p in output.rglob('*') if p.is_file()}
    (output/'manifest.json').write_bytes(canonical({'format':'dd-c01-service-materials-v2','prepared_on':day.isoformat(),'files':files}))
    return binding

if __name__=='__main__':
    b=prepare(Path(sys.argv[1]));print(json.dumps({'prepared_on':b['date'],'variants':list(b['manifests']),'synthetic_only':True}))
