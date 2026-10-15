"use strict";
// This demo contains fictional fixture data only. There is no network, email or CRM integration.
const fixtures = Object.freeze({
 aster:{name:"Aster Cloud",industry:"SaaS",employees:220,signal:"Hiring revenue operations engineers",evidence:[{fact:"B2B subscription software",source:"fictional-fixture:sector"},{fact:"Hiring revenue operations engineers",source:"fictional-fixture:signal"}],email:"team@aster.example"},
 ridge:{name:"Ridgeway Logistics",industry:"Transport",employees:820,signal:"No documented automation buying signal",evidence:[{fact:"Freight logistics operator",source:"fictional-fixture:sector"}],email:null},
 mira:{name:"MiraCare Analytics",industry:"Healthtech",employees:110,signal:"Expanded its data partnerships team",evidence:[{fact:"Health analytics platform",source:"fictional-fixture:sector"},{fact:"Expanded its data partnerships team",source:"fictional-fixture:signal"}],email:"team@miracare.example"}
});
const sel=document.getElementById("account-select");
const run=document.getElementById("run-demo");
const approve=document.getElementById("approve-demo");
const body=document.getElementById("result-body");
const empty=document.getElementById("result-empty");
const score=document.getElementById("result-score");
const fit=document.getElementById("result-fit");
const trace=document.getElementById("result-trace");
const draft=document.getElementById("result-draft");
const status=document.getElementById("trace-status");
const note=document.getElementById("approval-note");
let current=null;
function evaluate(item){
 const sectorFit=item.industry==="SaaS"||item.industry==="Healthtech";
 const sizeFit=item.employees>=50&&item.employees<=500;
 const signalFit=item.signal!=="No documented automation buying signal";
 const sourceFit=item.evidence.length>=2;
 const total=(sectorFit?40:0)+(sizeFit?20:0)+(signalFit?25:0)+(sourceFit?15:0);
 const tier=total>=80?"HIGH FIT":total>=50?"REVIEW":"LOW FIT";
 const logs=[
  "Research: "+item.evidence.length+" source-tagged fictional facts loaded",
  "Mock enrichment: "+(item.email?"contact placeholder available":"no test contact found"),
  "Qualification: sector "+(sectorFit?"match":"outside ICP")+"; employee range "+(sizeFit?"match":"outside range"),
  "Evidence gate: "+(sourceFit?"2+ fixture facts":"additional evidence needed"),
  "Outreach: draft generated for human review; no sending capability"
 ];
 const line=signalFit?"The available sample data mentions "+item.signal.toLowerCase()+".":"The sample data does not contain a verified buying signal.";
 return {name:item.name,score:total,tier,logs,draft:"Subject: Idea for "+item.name+"\n\nHi there,\n\n"+line+" I'm exploring ways that a structured account-intelligence and revenue-automation workflow could support teams like yours.\n\nWould a short conversation be useful?\n\n— Anil\n\n[FICTIONAL SAMPLE ONLY — NOT FOR SENDING]"};
}
function addTraceLine(message){
 const row=document.createElement("div");row.className="trace-item";
 const tick=document.createElement("b");tick.textContent="✓";
 const info=document.createElement("span");info.textContent=message;
 row.append(tick,info);trace.appendChild(row);
}
run.addEventListener("click",function(){
 const item=fixtures[sel.value];if(!item)return;
 current=evaluate(item);
 score.textContent=String(current.score)+"/100";
 fit.textContent=current.tier;fit.style.color=current.tier==="HIGH FIT"?"#d0f383":"#f6d490";
 trace.replaceChildren();current.logs.forEach(addTraceLine);
 draft.textContent=current.draft;
 body.hidden=false;empty.hidden=true;approve.disabled=false;
 status.textContent="DRY RUN COMPLETE";
 note.textContent="Review pending. External calls: 0; emails sent: 0; CRM writes: 0.";
});
approve.addEventListener("click",function(){
 if(!current)return;
 approve.disabled=true;status.textContent="APPROVED IN MEMORY";
 note.textContent="Sample marked approved locally in this browser. No email sent, CRM write, provider calls, or persisted action.";
});
const year=document.getElementById("year");if(year)year.textContent=String(new Date().getFullYear());