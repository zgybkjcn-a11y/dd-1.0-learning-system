"""Read-only, version-bound math references for the selected learner.

No model calls, student-answer reads, question publication, vector writes or
mastery decisions. Local selected-page review is never new grading authority.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .practice import bank, BANK_PATH, BANK_SHA256
from .textbooks import catalogue, PDF_SHA256, practice_scope, page_evidence

REFERENCE_PATH = Path(__file__).parent/'data/family_concepts_v1.json'
REFERENCE_SHA256 = 'b9f483f264d9be9124e1f682a9736e37010a5d78919510eaf47de604c916c9ba'
ID = re.compile(r'[A-Za-z0-9_-]{1,128}')


class ReferenceError(ValueError):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()


def load_reference():
    try:
        raw=REFERENCE_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=REFERENCE_SHA256:
            raise ValueError('changed reference')
        data=json.loads(raw)
        if (data['format']!='dd-family-math-reference-v1' or data['question_bank_sha256']!=BANK_SHA256
                or data['reference_only'] is not True or data['eligible_as_grading_basis'] is not False
                or data['teacher_reviewed'] is not False or len(data['concepts'])!=18
                or len(data['question_mappings'])!=20):
            raise ValueError('invalid review boundary')
        # practice.bank caches its parsed data; check the deployed bytes too.
        if hashlib.sha256(BANK_PATH.read_bytes()).hexdigest()!=BANK_SHA256:
            raise ValueError('changed question bank')
        for book, digest in data['pdf_sha256'].items():
            if PDF_SHA256.get(book)!=digest:
                raise ValueError('changed textbook edition')
        return data
    except (OSError,ValueError,KeyError,TypeError):
        raise ReferenceError(503,'MATH_REFERENCE_UNAVAILABLE','知识参考资料版本校验未通过')


def _prerequisites(data, roots, book_id):
    seen=set(roots)
    frontier=list(roots)
    preview=[]
    for depth in range(1,3):
        following=[]
        for target in frontier:
            for edge in data['prerequisite_edges']:
                child=edge['prerequisite']
                if edge['target']!=target or child in seen or len(preview)>=6:
                    continue
                if edge['role']!='reference_only' or data['concepts'][child]['book_id']!=book_id:
                    raise ReferenceError(503,'MATH_REFERENCE_UNAVAILABLE','先修参考关系校验未通过')
                seen.add(child)
                following.append(child)
                preview.append((child,depth,edge))
        frontier=following
    return preview


def _approved(conn, learner_id):
    # Only approved shared question versions; no attempts, raw answers, chats
    # or personal question material are read by this feature.
    rows=conn.execute("SELECT v.id,v.version,v.question_id,v.content_json,v.answer_key_json,v.validator_version,q.objective_id "
        "FROM question_versions v JOIN questions q ON q.id=v.question_id "
        "JOIN review_objectives o ON o.id=q.objective_id JOIN knowledge_points k ON k.id=o.knowledge_point_id "
        "JOIN learners l ON l.curriculum_id=k.curriculum_id WHERE l.id=? AND v.approval='approved' "
        "AND q.approval='approved' AND q.visibility='shared' ORDER BY v.id", (learner_id,)).fetchall()
    return {row['id']:row for row in rows}


def _check_question(row, mapping, question):
    try:
        stored={'question_id':row['question_id'],'validator_version':row['validator_version'],
                'content':json.loads(row['content_json']),'answer_key':json.loads(row['answer_key_json'])}
        valid=(row['version']==1
            and row['objective_id']==f"objective-family-word-math-g{mapping['grade']}-ch{mapping['chapter_id']}"
            and hashlib.sha256(canonical(question)).hexdigest()==mapping['question_sha256']
            and hashlib.sha256(canonical(stored)).hexdigest()==mapping['stored_version_sha256'])
    except (ValueError,TypeError,KeyError):
        valid=False
    if not valid:
        raise ReferenceError(503,'MATH_REFERENCE_VERSION_MISMATCH','题目版本已变化，需重新核对知识点映射')


def query_reference(conn, learner_id, curriculum_id, textbook_dir, *, book_id='', chapter_id='',
                    question_version_id='', concept_id=''):
    for value in (book_id,chapter_id,question_version_id,concept_id):
        if type(value) is not str or value and not ID.fullmatch(value):
            raise ReferenceError(422,'MATH_REFERENCE_SCOPE_INVALID','请选择当前年级的数学课本和有效章节')
    if question_version_id and concept_id:
        raise ReferenceError(422,'MATH_REFERENCE_SCOPE_INVALID','题目查询与知识点查询请分别使用')
    books=[b for b in catalogue(curriculum_id) if b['subject']=='math']
    if not book_id:
        book_id=next((b['id'] for b in books if b['semester']=='上册'),'')
    book=next((b for b in books if b['id']==book_id),None)
    if not book or (chapter_id and not any(c['id']==chapter_id for c in book['chapters'])):
        raise ReferenceError(422,'MATH_REFERENCE_SCOPE_INVALID','该课本或章节不属于当前档案')
    data=load_reference()
    result={'reference_version':data['version'],'reference_sha256':REFERENCE_SHA256,
        'scope':{'book_id':book_id,'grade':book['grade'],'semester':book['semester'],'edition':book['edition'],
                 'pdf_sha256':PDF_SHA256[book_id],'chapter_id':chapter_id},
        'mapping_status':'unmapped','concepts':[],'prerequisites':[],'questions':[],
        'reference_only':True,'eligible_as_grading_basis':False,'teacher_reviewed':False,
        'mastery_claim':None,'diagnosis_status':'possible_checks_not_confirmed_cause',
        'provenance':{'structure_reference':data['provenance']['structure_reference'],
                      'commit':data['provenance']['commit'],'graph_license':'CC BY-NC-SA 4.0',
                      'question_license':'CC BY-NC 4.0'}}
    if book_id not in data['pdf_sha256']:
        if question_version_id or concept_id:
            raise ReferenceError(404,'MATH_REFERENCE_NOT_FOUND','本册尚未建立这项精确映射')
        return {**result,'mapped_question_count':0,'notice':'本册尚未建立精确知识映射，可继续阅读教材。'}
    try:
        path=Path(textbook_dir)/(book_id+'.pdf')
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=PDF_SHA256[book_id]:
            raise ValueError('changed original PDF')
    except (TypeError,OSError,ValueError):
        raise ReferenceError(503,'MATH_REFERENCE_TEXTBOOK_UNAVAILABLE','当前教材原件版本校验未通过')
    approved=_approved(conn,learner_id)
    try:
        current=bank()
    except (OSError,ValueError,KeyError,TypeError):
        raise ReferenceError(503,'MATH_REFERENCE_UNAVAILABLE','题库版本校验未通过')
    mappings={qid:m for qid,m in data['question_mappings'].items()
              if qid in approved and m['book_id']==book_id and (not chapter_id or m['chapter_id']==chapter_id)}
    for qid,mapping in mappings.items():
        _check_question(approved[qid],mapping,current.get(qid))
    result['mapped_question_count']=len(mappings)
    selected=None
    if question_version_id:
        if question_version_id not in approved:
            raise ReferenceError(404,'MATH_REFERENCE_NOT_FOUND','当前档案没有该已核验题目')
        scope=practice_scope(question_version_id)
        if scope and (scope['book_id']!=book_id or (chapter_id and scope['chapter_id']!=chapter_id)):
            raise ReferenceError(422,'MATH_REFERENCE_SCOPE_INVALID','题目不在所选课本或章节范围')
        selected=mappings.get(question_version_id)
        result['question_version_id']=question_version_id
        if selected is None:
            return {**result,'notice':'本题尚无精确知识映射，请在工作区核对题目。'}
        result['mapping_role']=selected['mapping_role']
        roots=list(selected['concept_ids'])
        result['scope']['chapter_id']=selected['chapter_id']
    else:
        roots=sorted({key for m in mappings.values() for key in m['concept_ids']})
    preview=_prerequisites(data,roots,book_id)
    if concept_id:
        if concept_id not in set(roots) | {key for key,_,_ in preview}:
            raise ReferenceError(404,'MATH_REFERENCE_NOT_FOUND','所选范围没有该知识点映射')
        roots=[concept_id]
        # The selected concept gets its own chain, including prerequisites
        # that also occurred as direct concepts elsewhere in the scope.
        preview=_prerequisites(data,roots,book_id)
    order={c['id']:i for i,c in enumerate(book['chapters'])}
    limit=order.get(result['scope']['chapter_id'],len(order))
    def node(key):
        n=data['concepts'][key]
        return {'id':key,'title':n['title'],'explanation':n['explanation'],'checks':list(n['checks']),
            'location_status':n['location_status'],'reference_only':True,'eligible_as_grading_basis':False,
            'pages':[{'book_id':book_id,'chapter_id':p['chapter_id'],'chapter_title':p['chapter_title'],
                      'printed_page':p['printed_page'],'pdf_page':p['pdf_page'],'pdf_sha256':p['pdf_sha256'],
                      'evidence':page_evidence(book,p['pdf_page']),
                      'label':p['label'],'scope_relation':'current_chapter' if p['chapter_id']==result['scope']['chapter_id'] else
                         'within_book' if not result['scope']['chapter_id'] else 'prior_foundation',
                      'page_image_path':f"/api/v1/textbooks/{book_id}/pages/{p['printed_page']}/image"}
                     for p in n['textbook_pages'] if order[p['chapter_id']]<=limit]}
    result['concepts']=[node(key) for key in roots]
    result['prerequisites']=[{**node(key),'depth':depth,'from_concept':edge['target'],
                             'strength':edge['strength'],'rationale':edge['rationale']}
                            for key,depth,edge in preview]
    candidates=[]
    for qid,mapping in mappings.items():
        if qid==question_version_id or (selected and mapping['chapter_id']!=selected['chapter_id']):
            continue
        overlap=len(set(mapping['concept_ids']) & set(roots))
        if (selected and not overlap) or (concept_id and concept_id not in mapping['concept_ids']):
            continue
        candidates.append((-overlap,qid,mapping))
    candidates.sort(key=lambda row:row[:2])
    result['questions']=[{'question_version_id':qid,'title':m['title'],'difficulty':m['difficulty'],
                          'book_id':book_id,'chapter_id':m['chapter_id'],'mapping_role':m['mapping_role'],
                          'source':deepcopy(m['source'])} for _,qid,m in candidates[:3 if selected else 20]]
    result['mapping_status']='mapped' if roots else 'unmapped'
    result['notice']='知识点与先修仅供回顾；局部原页核对不等于整页或教师审核。' if roots else '本章暂未建立精确知识映射，可继续阅读教材。'
    return result
