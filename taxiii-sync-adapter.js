/* 運轉手帳本 5.0.2 read-only sync adapter.
 * No credentials are persisted. No push/write endpoint is implemented.
 */
(function(g){
'use strict';
const BASE='https://backup.23.95.165.241.sslip.io';
const EP={pull:'/v2/sync/pull',snapshot:'/v2/sync/snapshot'};
function headers(idToken,appCheck){
  if(!idToken||!appCheck) throw new Error('需要目前登入工作階段的 Firebase ID token 與 App Check token');
  return {'content-type':'application/json','Authorization':'Bearer '+idToken,'X-Firebase-AppCheck':appCheck};
}
async function post(path,body,auth){
  const r=await fetch(BASE+path,{method:'POST',headers:headers(auth.idToken,auth.appCheck),body:JSON.stringify(body)});
  const text=await r.text(); let json=null; try{json=text?JSON.parse(text):{};}catch{}
  if(!r.ok) throw new Error('運轉手同步 API '+r.status+(json?.message?'：'+json.message:''));
  if(!json) throw new Error('運轉手同步 API 回傳非 JSON');
  return json;
}
function validateRecord(x){
  if(!x||typeof x!=='object') return false;
  const rt=x.recordType??x.record_type, id=x.recordId??x.record_id;
  const rev=Number(x.revision), seq=Number(x.sequence);
  return !!rt&&!!id&&Number.isSafeInteger(rev)&&rev>0&&Number.isSafeInteger(seq)&&seq>0;
}
function normalizeRecord(x){
  let p=x.payload??x.record_json??x.recordJson??{};
  if(typeof p==='string'){try{p=JSON.parse(p)}catch{p={raw:p}}}
  return {recordType:String(x.recordType??x.record_type),recordId:String(x.recordId??x.record_id),revision:Number(x.revision),sequence:Number(x.sequence),deleted:x.deleted===true||x.deleted===1,payload:p};
}
async function pullPage(auth,request){
  const j=await post(EP.pull,request,auth);
  const records=Array.isArray(j.records)?j.records.filter(validateRecord).map(normalizeRecord):[];
  return {...j,records};
}
async function snapshotPage(auth,request){
  const j=await post(EP.snapshot,request,auth);
  const records=Array.isArray(j.records)?j.records.filter(validateRecord).map(normalizeRecord):[];
  return {...j,records};
}
/* Caller supplies the exact request shape after it has been verified from the client.
   This deliberately avoids guessing cursor/device/page fields. */
async function collectPull(auth,firstRequest,nextRequest,maxPages=100){
  let req=firstRequest,out=[],last=-1;
  for(let page=0;page<maxPages;page++){
    const r=await pullPage(auth,req); out.push(...r.records);
    const cursor=Number(r.nextCursor??r.headSequence??-1);
    if(Number.isSafeInteger(cursor)&&cursor>=0){if(last>=0&&cursor<last)throw new Error('同步 cursor 倒退');last=cursor;}
    if(!r.hasMore) return {records:out,headSequence:r.headSequence,nextCursor:r.nextCursor};
    if(typeof nextRequest!=='function') throw new Error('API 尚有下一頁，但尚未提供已驗證的分頁 request builder');
    req=nextRequest(req,r);
  }
  throw new Error('同步頁數超過安全上限');
}
g.TaxiiiSync={BASE,EP,pullPage,snapshotPage,collectPull,normalizeRecord};
})(window);
