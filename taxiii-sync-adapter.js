/* 運轉手帳本 5.0.2 read-only sync adapter.
 * No credentials are persisted. No push/write endpoint is implemented.
 */
(function(g){
'use strict';
const BASE='https://backup.23.95.165.241.sslip.io';
const EP={pull:'/v2/sync/pull',snapshot:'/v2/sync/snapshot'};
const LEDGER_TYPES=new Set(['ledger_income','ledger_expense','ledger_time_clock']);
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
function dateOnly(v){
  if(v==null||v==='') return '';
  const d=typeof v==='number'?new Date(v<1e12?v*1000:v):new Date(v);
  if(!Number.isNaN(d.getTime())) return d.toISOString().slice(0,10);
  const m=String(v).match(/\d{4}[-\/]\d{1,2}[-\/]\d{1,2}/);
  return m?m[0].replaceAll('/','-').split('-').map((x,i)=>i?x.padStart(2,'0'):x).join('-'):'';
}
function platformName(p){
  const v=p.platformType??p.platform??p.platformName??p.customPlatformName??'運轉手';
  const s=String(v),k=s.toLowerCase().replace(/[^a-z0-9]/g,'');
  return ({uber:'Uber',line:'LINE GO',linego:'LINE GO','55688':'55688',cash:'現金',ubereats:'Uber Eats',foodpanda:'foodpanda'})[k]||s;
}
function ledgerToBookkeeping(r){
  r=normalizeRecord(r); if(r.deleted||!LEDGER_TYPES.has(r.recordType)) return null;
  const p=r.payload||{},meta={taxiiiRecordType:r.recordType,taxiiiRecordId:r.recordId,taxiiiRevision:r.revision,taxiiiSequence:r.sequence};
  if(r.recordType==='ledger_income'){
    const amount=Number(p.actualIncome??p.fareAmount??p.originalFare??p.amount??0);
    if(!(amount>0)) return null;
    const fee=Number(p.platformFeeAmount??0)||0;
    return {id:'taxiii:'+r.recordId,type:'income',amount,category:platformName(p),date:dateOnly(p.dateTime??p.createdAt),km:Number(p.mileage??0)||0,hours:0,note:[p.note,fee?`平台費 ${fee}`:''].filter(Boolean).join(' · '),source:'運轉手',syncMeta:meta};
  }
  if(r.recordType==='ledger_expense'){
    const amount=Number(p.expense??p.expenseAmount??p.amount??0); if(!(amount>0)) return null;
    return {id:'taxiii:'+r.recordId,type:'expense',amount,category:String(p.customCategoryName??p.categoryName??p.category??'其他支出'),date:dateOnly(p.dateTime??p.createdAt),km:0,hours:0,note:String(p.note??''),source:'運轉手',syncMeta:meta};
  }
  const a=p.clockInTime?new Date(p.clockInTime):null,b=p.clockOutTime?new Date(p.clockOutTime):null;
  if(!a||Number.isNaN(a.getTime())) return null;
  const hours=b&&!Number.isNaN(b.getTime())?Math.max(0,(b-a)/36e5):0;
  const km=Math.max(0,Number(p.clockOutMileageKm??0)-Number(p.clockInMileageKm??0));
  return {id:'taxiii:clock:'+r.recordId,type:'income',amount:0,category:'工時',date:dateOnly(p.clockInTime),km,hours:+hours.toFixed(2),note:'運轉手工時',source:'運轉手',metaOnly:true,syncMeta:meta};
}
function mapLedgerRecords(records){return records.map(ledgerToBookkeeping).filter(Boolean)}
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
    if(!r.hasMore) return {records:out,ledger:mapLedgerRecords(out),headSequence:r.headSequence,nextCursor:r.nextCursor};
    if(typeof nextRequest!=='function') throw new Error('API 尚有下一頁，但尚未提供已驗證的分頁 request builder');
    req=nextRequest(req,r);
  }
  throw new Error('同步頁數超過安全上限');
}
g.TaxiiiSync={BASE,EP,LEDGER_TYPES,pullPage,snapshotPage,collectPull,normalizeRecord,ledgerToBookkeeping,mapLedgerRecords};
})(window);
