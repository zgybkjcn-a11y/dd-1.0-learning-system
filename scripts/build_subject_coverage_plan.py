"""Expand from chapter counts to explicit, reviewable knowledge requirements."""
import hashlib,json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from learning_service.chapter_practice import bank
from learning_service.textbooks import BOOKS,PDF_SHA256,SECTION_STARTS,learning_scope
from subject_knowledge_specs import SPECS,MANUAL
ROOT=Path(__file__).resolve().parents[1]

def canonical(q):return json.dumps(q,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def build():
    data=json.loads((ROOT/'learning_service/data/family_math_coverage_plan_v6.json').read_bytes())
    data.update(format='dd-subject-coverage-plan-v1',version='2026-11-10-v1-knowledge',pdf_sha256=dict(PDF_SHA256))
    data['task_labels'].update(check='知识运用与辨析',express='独立表达与操作')
    for book,text in SPECS.items():
        subject=book.split('-')[0]
        for line in text.strip().splitlines():
            chapter,*entries=line.split('|')
            _,c=learning_scope(f"math-g{book.split('-g')[1][0]}-v1",book,chapter)
            for entry in entries:
                page,key,title,requirement=entry.split('/')
                page=int(page);assert c['printed_page']<=page<=c['printed_page']+c['page_end']-c['page_start'],(book,key,page)
                manual_only=(subject=='english' and key in ('listening','pronunciation')) or (subject=='chinese' and key in ('writing','book','observation'))
                label,prompt,rubric=MANUAL[subject]
                data['rows'].append(dict(id=f'{book}:{chapter}:{key}',book_id=book,chapter_id=chapter,title=title,printed_page=page,location_kind='topic_location_not_quote',
                    requirements={'check':requirement,'express':f'围绕“{title}”完成{label}'},
                    assessment_modes={'check':'human' if manual_only else 'bounded','express':'human'},
                    manual_task={'title':title+' · '+label,'prompt':prompt,'criteria':rubric.split('；'),'record_labels':['独立完成','需要提示','待练习'],'automatically_graded':False},mappings=[]))
    rows={r['id']:r for r in data['rows']};assert len(rows)==len(data['rows'])
    for q in bank('subject_knowledge').values():
        m=dict(q['knowledge']);r=rows[m['point_id']]
        if m['point_id'] in {'math-g7-upper:1:opposite','math-g7-lower:8:real','math-g7-lower:10:elimination'}:
            m['role']='supporting'
            m['rationale']='本题未独立考查零、实数运算或消元系数选择中的全部要求，只计辅助练习。'
        r['mappings'].append(dict(question_version_id=q['id'],question_sha256=hashlib.sha256(canonical(q)).hexdigest(),task=m['task'],role=m['role'],family=m['family'],rationale=m['rationale']))
    # Explicit editorial links for the previous structured batch. Multiple fields
    # remain one question; recognition never fulfills the independent oral task.
    mapped={
      'math-g7-lower':{7:('parallel','parallel'),8:('roots','roots'),9:('move','move'),10:('solution','solution'),11:('system','boundary'),12:('survey','histogram')},
      'chinese-g2-upper':{1:('actions','actions'),2:('order','radical'),3:('cause','comparison'),4:('view','view'),5:('fable','cause'),6:('actions','sequence'),7:('figurative','figurative'),8:('repair','dialogue'),9:('recognition','recognition')},
      'chinese-g2-lower':{1:('observation','observation'),2:('process','change'),3:('radical','radical'),4:('imagination','link'),5:('fable','fable'),6:('order','order'),7:('process','process'),8:('myth','myth'),9:('meaning','punctuation')},
      'chinese-g7-upper':{1:('senses','senses'),2:('order','evidence'),3:('center','center'),4:('evidence','evidence'),5:('facts','facts'),6:('fable','imagination')},
      'chinese-g7-lower':{1:('evidence','evidence'),2:('emotion','rhetoric'),3:('details','details'),4:('argument','argument'),5:('symbol','symbol'),6:('presentation','presentation')},
      'english-g7-upper':{1:('greeting','greeting'),2:('position','position'),3:('there','demonstratives'),4:('personal','personal'),5:('relations','possessive'),6:('location','location'),7:('question','reason'),8:('constraints','constraints'),9:('time','time'),10:('invitation','invitation'),11:('inference','inference'),12:('script','script'),13:('symbol','symbol'),14:('be','present'),15:('context','context'),16:('order','order'),17:('basic','plural'),18:('numbers','numbers')},
      'ethics-g2-upper':{1:('plan','plan'),2:('duty','rules'),3:('observe','environment'),4:('culture','culture')},
      'ethics-g7-upper':{1:('learning','self'),2:('friend','friend'),3:('safety','mental'),4:('labor','labor')},
      'history-g7-upper':{1:('human','agriculture'),2:('sequence','reform'),3:('recovery','silk'),4:('south','three'),5:('source','source'),6:('timeline','timeline')},
      'geography-g7-upper':{1:('evidence','evidence'),2:('coordinate','motion'),3:('map','contour'),4:('continents','continents'),5:('weather','temperature'),6:('population','population'),7:('cooperation','development'),8:('route','evidence'),9:('legend','application')},
      'biology-g7-upper':{1:('observation','observation'),2:('microscope','celllife'),3:('levels','plantlevels'),4:('spore','seed'),5:('mammal','invertebrate'),6:('fungi','food'),7:('rank','key')},
    }
    # A previous reading task need not fully meet every newly specified skill.
    partial={('chinese-g2-upper',3,1),('chinese-g2-upper',4,1),('chinese-g2-upper',7,0),
             ('chinese-g2-lower',2,0),('chinese-g2-lower',6,0),('chinese-g2-lower',6,1),
             ('chinese-g7-upper',1,0),('chinese-g7-upper',2,1),('chinese-g7-lower',2,0),
             ('english-g7-upper',3,0),('english-g7-upper',5,1),('english-g7-upper',7,0),
             ('english-g7-upper',14,0),('english-g7-upper',14,1),('english-g7-upper',17,1),
             ('geography-g7-upper',3,0),('biology-g7-upper',2,0),('biology-g7-upper',3,1),
             ('biology-g7-upper',6,0),('history-g7-upper',3,0),('history-g7-upper',4,1),
             ('math-g7-lower',12,0),('math-g7-lower',8,0),('math-g7-lower',12,1),
             ('chinese-g2-upper',1,1),('chinese-g2-upper',2,1),('chinese-g2-upper',8,0),
             ('chinese-g2-lower',3,0),('chinese-g2-lower',5,0),('chinese-g2-lower',5,1),
             ('chinese-g7-lower',1,1),('chinese-g7-lower',6,0),('chinese-g7-lower',6,1),
             ('english-g7-upper',3,1),('english-g7-upper',6,1),('english-g7-upper',15,0),('english-g7-upper',15,1),
             ('ethics-g2-upper',4,0),('ethics-g7-upper',2,0),
             ('history-g7-upper',2,1),('geography-g7-upper',5,1),('geography-g7-upper',6,0),('geography-g7-upper',6,1),
             ('geography-g7-upper',9,1),('biology-g7-upper',1,0),('biology-g7-upper',1,1),('biology-g7-upper',2,1),
             ('biology-g7-upper',5,0),('biology-g7-upper',6,1)}
    # These older questions do not assess the newly specified point; leave
    # them visibly unmapped until a suitable inventory point is reviewed.
    unrelated={('chinese-g2-upper',3,1),('chinese-g2-upper',5,0),('chinese-g2-upper',7,0),
               ('chinese-g2-upper',9,0),('chinese-g2-lower',3,1),('chinese-g2-lower',6,0),
               ('english-g7-upper',7,0),('english-g7-upper',18,0),('english-g7-upper',18,1)}
    for batch in ('upper_variety','remaining_variety'):
        for q in bank(batch).values():
            book=q['book_id'];ch=int(q['chapter_id']);second=int('-second-v1' in q['id']);key=mapped[book][ch][second]
            if (book,ch,key)==('chinese-g2-lower',2,'process'):key='cooperation'
            if (book,ch,second) in unrelated:continue
            row=rows[f'{book}:{ch}:{key}'];role='supporting' if (book,ch,second) in partial or row['assessment_modes']['check']=='human' else 'direct'
            family=q['design']['family']
            # Prior classification question and new task may test the same
            # narrow rule; do not split a family merely by changing names.
            row['mappings'].append(dict(question_version_id=q['id'],question_sha256=hashlib.sha256(canonical(q)).hexdigest(),task='check',role=role,family=family,rationale='核对原题材料与本项要求；只计指定判断，不能替代自由说明。'+('仅部分涉及要求，作为辅助。' if role=='supporting' else '')))
    # Preserve all source section headings separately. Unlisted points and
    # unmapped old questions remain visible as review work, not assumed covered.
    data['section_inventory']=[]
    qs=bank()
    for book in BOOKS:
        for c in book['chapters']:
            end=c['printed_page']+c['page_end']-c['page_start']
            sections=[dict(printed_page=p,title=t) for p,t in SECTION_STARTS.get(book['id'],{}).items() if c['printed_page']<=p<=end]
            data['section_inventory'].append(dict(book_id=book['id'],chapter_id=c['id'],title=c['title'],source_sections=sections,
                section_inventory_basis='verified_section_headings' if sections else 'chapter_boundary_only',
                point_inventory_complete=False))
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();path=ROOT/'learning_service/data/family_subject_coverage_plan_v1.json';path.write_bytes(raw)
    print(json.dumps(dict(points=len(rows),requirements=sum(len(r['requirements']) for r in rows.values()),scopes=len(data['section_inventory']),sha256=hashlib.sha256(raw).hexdigest())))
if __name__=='__main__':build()
