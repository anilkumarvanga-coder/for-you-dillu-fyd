"""Durable PostgreSQL queue. Run one worker replica; jobs survive API restarts."""
import base64
import io
import json
import time
import uuid
import logging
from PIL import Image
from pypdf import PdfReader
import pypdfium2 as pdfium
from langchain_core.messages import HumanMessage, SystemMessage
from .services import rows, execute, pool, storage, cognee, describe, complete, TUTOR

def image_url(image):
    image=image.convert('RGB')
    image.thumbnail((2000,2000))
    output=io.BytesIO(); image.save(output,format='JPEG',quality=90)
    return 'data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode()

def groups(texts, limit=20000):
    """Cover every character, even a single unusually long page."""
    current=''
    for text in texts:
        while text:
            count=min(limit-len(current),len(text))
            current+=text[:count]; text=text[count:]
            if len(current)==limit:
                yield current; current=''
    if current: yield current

def claim(table):
    if table not in ('fyd_documents','fyd_summaries'): raise ValueError('Invalid queue')
    field='id' if table=='fyd_documents' else 'document_id'
    with pool().connection() as conn:
        statuses=['queued','queued_delete'] if table=='fyd_documents' else ['queued']
        result=conn.execute(f"select * from {table} where status=any(%s) for update skip locked limit 1",(statuses,)).fetchone()
        if result: conn.execute(f"update {table} set status=%s,started_at=now() where {field}=%s",('deleting' if result['status']=='queued_delete' else 'processing',result[field]))
        return result

def ingest(doc):
    if doc['status']=='queued_delete':
        forget(doc)
        return
    data=storage('GET','object/authenticated/fyd-documents/'+doc['path']).content
    if len(data)!=doc['size'] or len(data)>20_000_000: raise ValueError('File size does not match upload')
    texts=[]
    if doc['mime']=='application/pdf':
        if not data.startswith(b'%PDF-'): raise ValueError('Invalid PDF')
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted: raise ValueError('Encrypted PDFs are unsupported')
        total=len(reader.pages)
        # Reject entire over-capacity files; never silently truncate their pages.
        if not 0<total<=500: raise ValueError('PDF must contain 1–500 pages')
        execute('update fyd_documents set pages=%s,processed=0 where id=%s',(total,doc['id']))
        renderer=pdfium.PdfDocument(data)
        try:
            for index,page in enumerate(reader.pages):
                text=page.extract_text() or ''
                # Vision sees each page, including diagrams on text-heavy pages.
                rendered=renderer[index]
                bitmap=rendered.render(scale=1.5)
                try: visual=describe(image_url(bitmap.to_pil()))
                finally: bitmap.close(); rendered.close()
                combined=f'Extracted text:\n{text}\nVisual transcription:\n{visual}'
                texts.append(combined)
                execute('insert into fyd_pages(document_id,page,text) values(%s,%s,%s) on conflict(document_id,page) do update set text=excluded.text',(doc['id'],index+1,combined))
                execute('update fyd_documents set processed=%s where id=%s',(index+1,doc['id']))
        finally: renderer.close()
    else:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ('PNG','JPEG','WEBP'): raise ValueError('Unsupported image')
            texts=[describe(image_url(image))]
        execute('insert into fyd_pages(document_id,page,text) values(%s,1,%s) on conflict(document_id,page) do update set text=excluded.text',(doc['id'],texts[0]))
        execute('update fyd_documents set pages=1,processed=1 where id=%s',(doc['id'],))
    # Stable dataset makes retries re-ingest into the same document namespace.
    dataset='fyd_'+str(doc['id']).replace('-','')
    execute('update fyd_documents set dataset=%s where id=%s',(dataset,doc['id']))
    files=[('data',(f'page_{i+1}.txt',f'[SOURCE {doc["id"]} PAGE {i+1}]\nFilename: {doc["name"]}\n{text}'.encode(),'text/plain')) for i,text in enumerate(texts)]
    cognee('add',files=files,data={'datasetName':dataset})
    cognee('cognify',json={'datasets':[dataset],'run_in_background':False})
    execute("update fyd_documents set status='ready',error=null where id=%s",(doc['id'],))

def summarize(job):
    pages=rows('select page,text from fyd_pages where document_id=%s order by page',(job['document_id'],))
    if not pages: raise ValueError('No pages available')
    sections=[f'\n[SOURCE {job["document_id"]} PAGE {p["page"]}]\n{p["text"]}\n' for p in pages]
    summaries=[]
    for chunk in groups(sections):
        summaries.append(complete([SystemMessage(content=TUTOR),HumanMessage(content='Summarize this section, preserve the source markers and all major study points:\n'+chunk)]))
    # Hierarchical reduction covers every section without dropping the tail.
    while len(summaries)>1:
        previous=len(''.join(summaries))
        summaries=[complete([SystemMessage(content=TUTOR),HumanMessage(content='Combine these summaries concisely. Retain major topics and source markers:\n'+part)]) for part in groups(summaries,24000)]
        if len(''.join(summaries))>=previous and len(summaries)>1:
            raise ValueError('Summary cannot fit safely; no partial summary published')
    execute("update fyd_summaries set status='ready',content=%s,error=null where document_id=%s",(summaries[0],job['document_id']))

def forget(doc):
    import httpx
    if doc['dataset']:
        try: cognee('forget',json={'dataset':doc['dataset']})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code!=404: raise
    storage('DELETE','object/fyd-documents',json={'prefixes':[doc['path']]})
    execute('delete from fyd_documents where id=%s',(doc['id'],))

def run():
    # Hold a session advisory lock so a second replica cannot reset active work.
    import psycopg
    from .services import required
    lock = psycopg.connect(required('DATABASE_URL'), autocommit=True)
    if not lock.execute('select pg_try_advisory_lock(618429001)').fetchone()[0]:
        raise RuntimeError('Another FYD worker is already active')
    execute("update fyd_documents set status='queued_delete' where status='deleting'")
    # Single-worker startup recovery; do not run concurrent worker replicas.
    execute("update fyd_documents set status='failed',error='Worker interrupted; retry processing.' where status='processing'")
    execute("update fyd_summaries set status='failed',error='Worker interrupted; request summary again.' where status='processing'")
    while True:
        work=False
        for table,fn,field in [('fyd_documents',ingest,'id'),('fyd_summaries',summarize,'document_id')]:
            job=claim(table)
            if not job: continue
            work=True
            try: fn(job)
            except Exception as exc:
                logging.error('Job %s failed (%s)',job[field],type(exc).__name__)
                execute(f"update {table} set status=%s,error=%s where {field}=%s",('delete_failed' if job['status']=='queued_delete' else 'failed','Processing failed. Check service configuration, allowance, or file readability; then retry.',job[field]))
        if not work: time.sleep(3)

if __name__=='__main__': run()
