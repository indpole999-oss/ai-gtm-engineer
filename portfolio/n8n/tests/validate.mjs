import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
const dir=path.resolve('portfolio/n8n');
const files=fs.readdirSync(dir).filter(n=>/^\d\d-.*\.json$/.test(n)).sort();
assert.equal(files.length,8,'expect eight workflow exports');
for(const file of files){
 const workflow=JSON.parse(fs.readFileSync(path.join(dir,file),'utf8'));
 assert.equal(workflow.active,false);
 assert.equal(workflow.nodes[0].type,'n8n-nodes-base.manualTrigger');
 const ids=new Set(),names=new Set();
 let items=[{json:{}}];
 for(let i=0;i<workflow.nodes.length;i++){
  const node=workflow.nodes[i];
  assert(!ids.has(node.id),'duplicate node ID');ids.add(node.id);
  assert(!names.has(node.name),'duplicate node name');names.add(node.name);
  if(i===0)continue;
  assert.equal(node.type,'n8n-nodes-base.code');
  assert.equal(node.parameters.mode,'runOnceForAllItems');
  const prior=workflow.nodes[i-1];
  assert.equal(workflow.connections[prior.name]?.main?.[0]?.[0]?.node,node.name,'missing/broken edge');
  const source=node.parameters.jsCode;
  assert(!/\b(fetch|XMLHttpRequest|require|process|globalThis|eval)\s*\(/.test(source),'potential external side effect');
  const context={items:structuredClone(items),Date,JSON,Math,Set,Object,Number,String,Boolean,Array,Error};
  const result=new vm.Script('(function(){const $input={all:()=>items};'+source+'})()',{filename:file+'::'+node.name}).runInNewContext(context,{timeout:1500});
  assert(Array.isArray(result)&&result.length>0,'missing result');
  for(const r of result)assert(r&&typeof r.json==='object','invalid n8n item');
  items=result;
 }
 const terminal=JSON.parse(JSON.stringify(items[0].json));
 assert.equal(terminal.externalCalls??0,0,'external calls recorded');
 assert.equal(terminal.sent??terminal.draft?.sent??false,false,'email sent');
 assert.equal(terminal.crmWrites??0,0,'CRM writes');
 assert.equal(terminal.calendarWrites??0,0,'calendar writes');
 if(file.startsWith('03-')){
   assert.equal(terminal.results.length,2);
   assert.equal(terminal.results[0].score,100);
   assert.equal(terminal.results[1].score,0);
 }
 if(file.startsWith('05-'))assert.equal(terminal.merged,1);
 if(file.startsWith('08-'))assert.equal(terminal.draft.approval,'PENDING_REVIEW');
 console.log('PASS',file,workflow.nodes.length,'nodes');
}
console.log('All eight offline import-structure / JS-node simulation checks passed.');
