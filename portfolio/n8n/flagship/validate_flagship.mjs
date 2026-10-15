import fs from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
import {performance} from "node:perf_hooks";
const path = new URL("./gtm_signal_to_action_39_stage.json",import.meta.url);
const wf=JSON.parse(fs.readFileSync(path,"utf8"));
const nonVisual=wf.nodes.filter(n=>n.type!=="n8n-nodes-base.stickyNote");
const ifAt=nonVisual.findIndex(n=>n.type==="n8n-nodes-base.if");
assert(ifAt>30,"Expected substantive processing chain and real conditional branch");
const chain=nonVisual.slice(0,ifAt),gate=nonVisual[ifAt],good=nonVisual[ifAt+1],empty=nonVisual[ifAt+2];
assert.equal(chain.length,40);
assert.equal(wf.active,false);
assert.equal(chain[0].type,"n8n-nodes-base.manualTrigger");
const unique=new Set(wf.nodes.map(n=>n.id));
assert.equal(unique.size,wf.nodes.length);
for(let i=1;i<chain.length;i++){
 const n=chain[i];
 assert.equal(n.type,"n8n-nodes-base.code");
 assert.equal(wf.connections[chain[i-1].name]?.main?.[0]?.[0]?.node,n.name);
 assert(!/\b(fetch|XMLHttpRequest|require|process|globalThis|eval)\s*\(/.test(n.parameters.jsCode),"Unexpected unsafe call");
}
assert.equal(wf.connections[chain.at(-1).name].main[0][0].node,gate.name);
assert.equal(wf.connections[gate.name].main[0][0].node,good.name);
assert.equal(wf.connections[gate.name].main[1][0].node,empty.name);
function execute(patch=()=>{}){
 let items=[{json:{}}];
 for(let i=1;i<chain.length;i++){
   if(i===2){const draft=structuredClone(items[0].json);patch(draft);items=[{json:draft}];}
   const n=chain[i],ctx={data:structuredClone(items),Date,JSON,Math,Set,Object,Number,String,Boolean,Array,Error};
   const source="(function(){const $input={all:()=>data};"+n.parameters.jsCode+"\n})()";
   const result=new vm.Script(source,{filename:n.name}).runInNewContext(ctx,{timeout:1500});
   assert(Array.isArray(result)&&result.length===1&&result[0].json,"Invalid Code node result: "+n.name);
   items=structuredClone(result);
 }
 const report=items[0].json;
 const branchNode=report.metrics.plannedDrafts>0?good:empty;
 const ctx={data:structuredClone(items),JSON,Error};
 const result=new vm.Script("(function(){const $input={all:()=>data};"+branchNode.parameters.jsCode+"\n})()").runInNewContext(ctx,{timeout:1500});
 return structuredClone(result[0].json);
}
const base=execute(),m=base.metrics;
assert.equal(m.ingested.accounts,7);
assert.equal(m.ingested.contacts,14);
assert.equal(m.ingested.signals,6);
assert.equal(m.duplicateAccounts,1);
assert.equal(m.duplicateContacts,1);
assert.equal(m.duplicateSignals,1);
assert.equal(m.blockedContacts,7);
assert.equal(m.plannedDrafts,3);
assert.equal(m.emailsSent,0);
assert.equal(m.crmWrites,0);
assert.equal(m.calendarWrites,0);
assert.equal(m.creditsSpent,0);
assert.equal(base.branch,"REVIEW_QUEUE_PREPARED_NO_EXTERNAL_SEND");
assert(base.holds.some(h=>h.reasons.includes("OPEN_OPPORTUNITY")));
assert(base.holds.some(h=>h.reasons.includes("UNSUBSCRIBED")));
assert(base.holds.some(h=>h.reasons.includes("EXISTING_CUSTOMER")));
assert(base.holds.some(h=>h.reasons.includes("CONSENT_NOT_CONFIRMED")));
assert(base.qualityFindings.some(q=>q.type==="stale_or_future_signal"));
const scenarios=[
 ["all_unsubscribed",d=>d.contacts.forEach(c=>c.unsubscribe=true),x=>assert.equal(x.metrics.plannedDrafts,0)],
 ["no_signals",d=>{d.signals=[];},x=>assert.equal(x.metrics.plannedDrafts,0)],
 ["quota_one",d=>{d.policy.maxActions=1;},x=>assert.equal(x.metrics.plannedDrafts,1)],
 ["strict_fit",d=>{d.policy.minAccountScore=101;},x=>assert.equal(x.metrics.plannedDrafts,0)],
 ["all_consent_blocked",d=>d.contacts.forEach(c=>c.privacyOk=false),x=>assert.equal(x.metrics.plannedDrafts,0)],
 ["all_stale",d=>{d.meta.now="2027-01-16T12:00:00Z";},x=>assert.equal(x.metrics.plannedDrafts,0)],
 ["no_sources",d=>d.signals.forEach(s=>s.source="unverified"),x=>assert.equal(x.metrics.plannedDrafts,0)],
 ["orphan_contact",d=>{d.contacts[0].account="unknown";},x=>assert(x.metrics.blockedContacts>7)],
 ["duplicate_dnc",d=>{d.contacts.find(c=>c.id==="c01dup").dnc=true;},x=>assert(!x.topPlans.some(p=>p.contactId==="c01"))]
];
for(const [name,patch,check] of scenarios){
 const report=execute(patch);check(report);
 assert.equal(report.metrics.emailsSent,0);
 assert.equal(report.metrics.crmWrites,0);
 if(report.metrics.plannedDrafts===0)assert.equal(report.branch,"EMPTY_QUEUE_AUDITED");
 console.log("PASS scenario:",name);
}
assert.throws(()=>execute(d=>d.meta.liveWritesAllowed=true),/Unsafe environment/);
assert.throws(()=>execute(d=>d.policy.perRunCreditLimit=1),/Unsafe environment/);
assert.deepEqual(execute(),execute(),"Deterministic fixture reruns must match");
const timings=[];for(let i=0;i<10;i++){const t=performance.now();execute();timings.push(performance.now()-t);}
timings.sort((a,b)=>a-b);
console.log("PASS 39 processing stages + conditional paths; nine negative/messy-data scenarios, two fail-closed safety cases");
console.log("SYNTHETIC FIXTURE",JSON.stringify({dedupAccounts:m.duplicateAccounts,dedupContacts:m.duplicateContacts,blocked:m.blockedContacts,plannedReviewOnly:m.plannedDrafts,sends:m.emailsSent,medianVmMs:Math.round(timings[4]*10)/10}));
