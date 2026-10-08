import os
import re
import secrets
import uuid
import json
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from .services import required, rows, execute, storage, cognee, complete, TUTOR
from langchain_core.messages import HumanMessage, SystemMessage

app = FastAPI(title='FYD study service')
MAX_FILE = 20_000_000

def allowed_users():
    raw=os.environ.get('ALLOWED_CLERK_USER_IDS', os.environ.get('ALLOWED_CLERK_USER_ID',''))
    users={x.strip() for x in raw.split(',') if x.strip()}
    return users if 0<len(users)<=2 and all(re.fullmatch(r'user_[A-Za-z0-9]+',x) for x in users) else set()

def identity(x_fyd_secret: str = Header(default=''), x_fyd_user: str = Header(default='')):
    # Only the Clerk-verified Next.js gateway can call this private API.
    if not secrets.compare_digest(x_fyd_secret, required('FYD_BACKEND_SECRET')):
        raise HTTPException(401, 'Unauthorized')
    if not x_fyd_user or x_fyd_user not in allowed_users():
        raise HTTPException(403, 'Account not allowed')
    return x_fyd_user

def document(doc_id, user):
    found = rows('select * from fyd_documents where id=%s and owner=%s', (doc_id, user))
    if not found: raise HTTPException(404, 'Document not found')
    return found[0]

def reserve(user):
    if not rows('select fyd_reserve_v2(%s) as allowed', (user,))[0]['allowed']:
        raise HTTPException(429, 'Allowance reached: 30 operations/day, 300/month.')

@app.get('/health')
def health(): return {'status':'ok'}

class Upload(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    type: str
    size: int = Field(gt=0, le=MAX_FILE)

@app.post('/documents')
def upload(body: Upload, user=Depends(identity)):
    if body.type not in ('application/pdf','image/png','image/jpeg','image/webp'):
        raise HTTPException(400, 'Use PDF, PNG, JPG or WebP')
    reserve(user)
    doc_id = str(uuid.uuid4())
    path = f'{user}/{doc_id}'
    rows('insert into fyd_documents(id,owner,name,mime,size,path) values(%s,%s,%s,%s,%s,%s) returning id',
         (doc_id,user,body.name,body.type,body.size,path))
    signed = storage('POST', 'object/upload/sign/fyd-documents/' + path, json={}).json()
    from urllib.parse import urlparse, parse_qs
    token = signed.get('token') or parse_qs(urlparse(signed.get('url','')).query).get('token',[None])[0]
    if not token: raise HTTPException(502, 'Upload service did not return a token')
    return {'id':doc_id,'path':path,'token':token}

@app.post('/documents/{doc_id}/process')
def process(doc_id: uuid.UUID, user=Depends(identity)):
    document(doc_id, user)
    execute("update fyd_documents set status='queued', error=null where id=%s and status='uploading'", (doc_id,))
    return {'queued':True}

@app.post('/documents/{doc_id}/retry')
def retry(doc_id: uuid.UUID, user=Depends(identity)):
    document(doc_id, user)
    reserve(user)
    execute("update fyd_documents set status='queued',error=null where id=%s and status='failed'", (doc_id,))
    return {'queued':True}

@app.get('/documents')
def documents(user=Depends(identity)):
    return rows('select id,name,status,pages,processed,error from fyd_documents where owner=%s order by created_at desc limit 100', (user,))

@app.get('/documents/{doc_id}/pages/{page}')
def source(doc_id: uuid.UUID, page:int, user=Depends(identity)):
    document(doc_id,user)
    found=rows('select text from fyd_pages where document_id=%s and page=%s',(doc_id,page))
    if not found: raise HTTPException(404,'Page not found')
    return {'text':found[0]['text']}

class Chat(BaseModel):
    question: str = Field(min_length=1,max_length=12000)
    documents: list[uuid.UUID] = Field(default_factory=list,max_length=5)
    conversation: uuid.UUID

@app.get('/conversations')
def conversations(user=Depends(identity)):
    return rows('select id,title from fyd_conversations where owner=%s order by created_at desc limit 100',(user,))

@app.get('/conversations/{chat_id}')
def history(chat_id:uuid.UUID,user=Depends(identity)):
    return rows('select m.role,m.content from fyd_messages m join fyd_conversations c on c.id=m.conversation where c.id=%s and c.owner=%s order by m.id',(chat_id,user))

@app.post('/chat')
def chat(body:Chat,user=Depends(identity)):
    docs=[document(d,user) for d in dict.fromkeys(body.documents)]
    if any(d['status']!='ready' for d in docs): raise HTTPException(409,'Wait until all selected documents are ready.')
    existing=rows('select owner from fyd_conversations where id=%s',(body.conversation,))
    if existing and existing[0]['owner']!=user: raise HTTPException(404,'Conversation not found')
    reserve(user)
    context='No documents selected. Use general knowledge and label it as such.'
    if docs:
        result=cognee('search',json={'query':body.question,'datasets':[d['dataset'] for d in docs], 'search_type':'GRAPH_COMPLETION','only_context':True,'session_id':f'{user}:{body.conversation}','top_k':12})
        context=json.dumps(result,ensure_ascii=False)
        if len(context)>90000: raise HTTPException(422,'Retrieved material exceeds the answer capacity. Ask a more focused question.')
    prior=history(body.conversation,user)[-12:]
    answer=complete([SystemMessage(content=TUTOR),HumanMessage(content=json.dumps({'conversation':prior,'retrieved_context':context,'question':body.question},ensure_ascii=False))])
    # Atomic persistence of question and answer.
    from .services import pool
    with pool().connection() as conn:
        conn.execute('insert into fyd_conversations(id,owner,title) values(%s,%s,%s) on conflict do nothing',(body.conversation,user,body.question[:100]))
        conn.execute("insert into fyd_messages(conversation,role,content) values(%s,'user',%s),(%s,'assistant',%s)",(body.conversation,body.question,body.conversation,answer))
    return {'answer':answer}

@app.post('/documents/{doc_id}/summary')
def summary(doc_id:uuid.UUID,user=Depends(identity)):
    doc=document(doc_id,user)
    if doc['status']!='ready': raise HTTPException(409,'Document must be ready first')
    reserve(user)
    execute("insert into fyd_summaries(document_id,status) values(%s,'queued') on conflict(document_id) do update set status='queued',error=null where fyd_summaries.status not in ('queued','processing')",(doc_id,))
    return {'queued':True}

@app.get('/documents/{doc_id}/summary')
def get_summary(doc_id:uuid.UUID,user=Depends(identity)):
    document(doc_id,user)
    found=rows('select status,content,error from fyd_summaries where document_id=%s',(doc_id,))
    return found[0] if found else {'status':'none','content':None}

@app.get('/usage')
def usage(user=Depends(identity)):
    found=rows("select case when day=(now() at time zone 'UTC')::date then day_count else 0 end as day_count,case when month=date_trunc('month',now() at time zone 'UTC')::date then month_count else 0 end as month_count from fyd_usage_v2 where owner=%s",(user,))
    return found[0] if found else {'day_count':0,'month_count':0}

@app.post('/documents/{doc_id}/delete')
def delete_document(doc_id:uuid.UUID,user=Depends(identity)):
    document(doc_id,user)
    changed=rows("update fyd_documents set status='queued_delete',error=null where id=%s and status not in ('processing','deleting') and not exists(select 1 from fyd_summaries where document_id=%s and status in ('queued','processing')) returning id",(doc_id,doc_id))
    if not changed: raise HTTPException(409,'Wait for document processing and summary jobs to finish before deleting.')
    return {'queued':True}
