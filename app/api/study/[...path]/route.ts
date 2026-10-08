import { allowedClerkUsers } from '../../../../lib/access';
import { auth } from '@clerk/nextjs/server';
export const runtime='nodejs';
export const maxDuration=300;
const routes=[/^documents$/, /^documents\/[0-9a-f-]{36}\/(process|retry|summary|delete)$/, /^documents\/[0-9a-f-]{36}\/pages\/\d+$/, /^conversations$/, /^conversations\/[0-9a-f-]{36}$/, /^chat$/, /^usage$/];
async function forward(req:Request,{params}:{params:Promise<{path:string[]}>}){
 if(req.method==='POST' && req.headers.get('origin')!==new URL(req.url).origin)return Response.json({error:'Invalid request origin.'},{status:403});
 const {userId}=await auth();
 if(!userId)return Response.json({error:'Sign in first.'},{status:401});
 if(!allowedClerkUsers(process.env.ALLOWED_CLERK_USER_IDS ?? process.env.ALLOWED_CLERK_USER_ID).includes(userId))return Response.json({error:'This study space is restricted to approved accounts.'},{status:403});
 const path=(await params).path.join('/');
 if(!routes.some(r=>r.test(path)))return new Response(null,{status:404});
 if(!process.env.FYD_BACKEND_URL||!process.env.FYD_BACKEND_SECRET)return Response.json({error:'The study backend needs configuration.'},{status:503});
 let body:string|undefined;
 if(req.method==='POST'){
  const reader=req.body?.getReader();const chunks:Uint8Array[]=[];let size=0;
  if(reader)while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>32000){await reader.cancel();return new Response(null,{status:413});}chunks.push(value);}
  body=Buffer.concat(chunks).toString('utf8');
 }
 try{
  const result=await fetch(`${process.env.FYD_BACKEND_URL.replace(/\/$/,'')}/${path}`,{method:req.method,headers:{'Content-Type':'application/json','X-FYD-Secret':process.env.FYD_BACKEND_SECRET,'X-FYD-User':userId},body,signal:AbortSignal.timeout(240000),cache:'no-store'});
  const data=await result.json().catch(()=>({detail:'Study service returned an invalid response.'}));
  if(!result.ok)return Response.json({error:typeof data.detail==='string'?data.detail:'Study service could not complete the request.'},{status:result.status});
  return Response.json(data);
 }catch{return Response.json({error:'Study service unavailable or timed out. Check processing status before retrying.'},{status:502});}
}
export {forward as GET,forward as POST};
