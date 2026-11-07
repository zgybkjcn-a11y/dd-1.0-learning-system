"""Container-local, additive textbook import. Never deletes files or collections.

Run inside the existing WebUI container with a staged, verified manifest directory.
Uses only the already cached local embedding model. Original books remain archived.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

OLD = {2:'4934772d-5748-4101-a795-9c69af0459b3',7:'9f90ce6b-01c4-48f0-bcca-4e29c47fe9ac'}
MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
SNAPSHOT = '/app/backend/data/cache/embedding/models/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41'

def identifier(value):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,'dd-family-pep-current-20261105/'+value))


def verified_ocr_pages(record, pages, stage):
    """Require a bound, complete review artifact, never a manifest approval flag.

    This permits reference indexing only. Question/answer publication requires
    separate item-level review; a book review cannot grant that permission.
    """
    if record.get('ocr_review_status') != 'all_pages_verified':
        return False
    try:
        name = record['ocr_review_report']
        if not isinstance(name, str) or Path(name).name != name:
            return False
        report_path = stage / name
        if report_path.is_symlink():
            return False
        raw = report_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['ocr_review_report_sha256']:
            return False
        review = json.loads(raw)
        if (review['pdf_sha256'] != record['sha256'] or review['usage'] != 'reference_only'
                or len(review['pages']) != len(pages)):
            return False
        for number, (text, page) in enumerate(zip(pages, review['pages']), 1):
            if (page['page_number'] != number or
                    page['text_sha256'] != hashlib.sha256(text.encode()).hexdigest()):
                return False
            for key in ('transcription_review', 'content_review'):
                check = page[key]
                if (check['status'] != 'verified' or check['method'] != 'independent_review'
                        or not check['reviewer'] or not check['evidence']):
                    return False
            if page.get('unresolved_issues') != []:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def run(stage, apply=False):
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',ANONYMIZED_TELEMETRY='False')
    dbpath=Path('/app/backend/data/webui.db')
    connection=sqlite3.connect(dbpath if apply else dbpath.as_uri()+'?mode=ro',uri=not apply,timeout=30)
    connection.row_factory=sqlite3.Row
    old={grade:dict(connection.execute('SELECT * FROM knowledge WHERE id=?',(kid,)).fetchone()) for grade,kid in OLD.items()}
    config={r['key']:json.loads(r['value']) if isinstance(r['value'],str) else r['value'] for r in connection.execute(
        'SELECT key,value FROM config WHERE key IN (?,?,?,?)',
        ('rag.embedding_engine','rag.embedding_model','rag.embedding_content_prefix','rag.embedding_query_prefix'))}
    assert config['rag.embedding_engine']=='' and config['rag.embedding_model']==MODEL
    assert not config.get('rag.embedding_content_prefix') and not config.get('rag.embedding_query_prefix')
    records=[]
    for path in sorted(stage.glob('*-manifest.json')):
        if path.name=='download-manifest.json': continue
        record=json.loads(path.read_text())
        if not record.get('edition_verified'): continue
        pdf=stage/(record['key']+'.pdf');pages=json.loads((stage/(record['key']+'-pages.json')).read_text())
        if record['extraction'] != 'pymupdf-local-no-ocr' and not verified_ocr_pages(record, pages, stage):
            continue
        assert hashlib.sha256(pdf.read_bytes()).hexdigest()==record['sha256']
        assert len(pages)==record['pages'] and sum(len(x.strip()) for x in pages)>10000
        grade=2 if '-g2-' in record['key'] else 7
        assert record['source_metadata']['publishers']==['人民教育出版社']
        record.update(file_id=identifier(record['sha256']),knowledge_id=identifier('grade-'+str(grade)),grade=grade)
        records.append((record,pages,pdf))
    assert records
    print(json.dumps({'plan':[{'key':r['key'],'file_id':r['file_id'],'pages':len(p)} for r,p,_ in records],
                      'local_embedding_model':MODEL,'apply':apply},ensure_ascii=False),flush=True)
    if not apply: return
    backup=stage/'webui-textbook-backup.json'
    if not backup.exists():
        files=[dict(r) for r in connection.execute('SELECT * FROM file WHERE filename LIKE ? OR filename LIKE ?',('%二年级%','%七年级%'))]
        links=[dict(r) for r in connection.execute('SELECT * FROM knowledge_file WHERE knowledge_id IN (?,?)',tuple(OLD.values()))]
        backup.write_text(json.dumps({'knowledge':list(old.values()),'files':files,'knowledge_file':links},ensure_ascii=False))
        backup.chmod(0o600)
    import chromadb
    from chromadb.config import Settings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from sentence_transformers import SentenceTransformer
    import torch
    torch.set_num_threads(2)
    vectors=chromadb.PersistentClient(path='/app/backend/data/vector_db',settings=Settings(anonymized_telemetry=False,allow_reset=False))
    model=SentenceTransformer(SNAPSHOT,local_files_only=True,device='cpu')
    split=RecursiveCharacterTextSplitter(chunk_size=1000,chunk_overlap=100,add_start_index=True)
    results=[]
    for record,pages,pdf in records:
        owner=old[record['grade']]['user_id'];file_id=record['file_id'];key=record['key']
        meta=record['source_metadata'];filename=f"{meta['subject']}{meta['grade']}{meta['semester']}（人教社·2022课标新版）.pdf"
        texts=[];metadata=[]
        for page,text in enumerate(pages):
            if not text.strip(): continue
            for chunk in split.split_text(text):
                texts.append(chunk)
                metadata.append({'file_id':file_id,'name':filename,'source':filename,'created_by':owner,
                                 'page':page,'page_number':page+1,'grade':record['grade'],
                                 'edition':'pep-2022-standard-current','hash':record['sha256'],
                                 'usage':'reference_only', 'question_answer_approved':False,
                                 'extraction':record['extraction'],'source_url':record['source_url'],
                                 'embedding_config':json.dumps({'engine':'','model':MODEL})})
        ids=[identifier(file_id+':'+str(i)) for i in range(len(texts))]
        collections=[vectors.get_or_create_collection(name=name,embedding_function=None,metadata={'hnsw:space':'cosine'})
                     for name in ['file-'+file_id,record['knowledge_id']]]
        # New deterministic IDs make an interrupted import safe to resume.
        existing=set(collections[0].get(include=[])['ids'])
        for start in range(0,len(texts),64):
            end=min(start+64,len(texts));batch_ids=ids[start:end]
            if all(i in existing for i in batch_ids):
                saved=collections[0].get(ids=batch_ids,include=['embeddings']);lookup=dict(zip(saved['ids'],saved['embeddings']))
                embeddings=[lookup[i].tolist() for i in batch_ids]
            else:
                embeddings=model.encode([s.replace('\n',' ') for s in texts[start:end]],batch_size=16,show_progress_bar=False).tolist()
            for collection in collections:
                collection.upsert(ids=batch_ids,documents=texts[start:end],metadatas=metadata[start:end],embeddings=embeddings)
        assert collections[0].count()==len(texts)
        found=collections[0].query(query_embeddings=model.encode([texts[len(texts)//2].replace('\n',' ')]).tolist(),n_results=1)
        assert found['ids'][0] and found['metadatas'][0][0]['file_id']==file_id
        target=Path('/app/backend/data/uploads')/(file_id+'_'+filename)
        if target.exists(): assert hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256']
        else: shutil.copyfile(pdf,target)
        now=int(time.time());data={'content':'\n'.join(pages),'status':'completed','error':None}
        file_meta={'name':filename,'content_type':'application/pdf','size':target.stat().st_size,
                   'textbook_edition':'pep-2022-standard-current','source_url':record['source_url'],
                   'sha256':record['sha256'],'extraction':record['extraction']}
        with connection:
            connection.execute('INSERT OR IGNORE INTO knowledge(id,user_id,name,description,meta,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                (record['knowledge_id'],owner,f"{meta['grade']}人教社新版教材（当前使用）",
                 '按2022年课程标准修订；2026-11-05多源核验。仅包含已校验新版，旧版单独归档。',json.dumps({'textbook_policy':'pep-latest','verified_on':'2026-11-05'}),now,now))
            connection.execute('INSERT OR IGNORE INTO file(id,user_id,filename,path,hash,data,meta,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                (file_id,owner,filename,str(target),hashlib.sha256(data['content'].encode()).hexdigest(),json.dumps(data,ensure_ascii=False),json.dumps(file_meta,ensure_ascii=False),now,now))
            connection.execute('INSERT OR IGNORE INTO knowledge_file(id,user_id,knowledge_id,file_id,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                (identifier(record['knowledge_id']+file_id),owner,record['knowledge_id'],file_id,now,now))
        result={**record,'filename':filename,'chunks':len(texts),'collection':'file-'+file_id,'vector_verified':True}
        results.append(result)
        (stage/'import-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        print(json.dumps({'key':key,'chunks':len(texts),'imported':True}),flush=True)
    with connection:
        for grade,book in old.items():
            name=book['name'] if book['name'].startswith('【归档旧版】') else '【归档旧版】'+book['name']
            connection.execute('UPDATE knowledge SET name=?,description=?,updated_at=? WHERE id=?',
                (name,'历史教材保留供追溯；不是最新版。当前学习请选择“人教社新版教材（当前使用）”。',int(time.time()),book['id']))
    assert connection.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    print(json.dumps({'completed':len(results),'original_files_deleted':0,'external_model_calls':0}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args();run(a.stage,a.apply)
