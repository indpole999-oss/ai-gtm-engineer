import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
function run(file,name,input){const w=JSON.parse(fs.readFileSync(`portfolio/n8n/${file}.json`));const n=w.nodes.find(n=>n.name===name);return JSON.parse(JSON.stringify(new vm.Script(`(function(){const $input={all:()=>[{json:input}]};${n.parameters.jsCode}})()`).runInNewContext({input:structuredClone(input)},{timeout:1000})))[0].json;}
const crm=(events)=>run('05-crm-deduplication','Deduplicate records',{events});
const events=[{id:'__proto__',stage:'MQL'},{id:'constructor',stage:'MQL'},{id:'__proto__',stage:'SQL'}];
const a=crm(events);assert.equal(a.records.length,2);assert.equal(a.merged,1);assert.equal(a.records[0].stage,'SQL');assert.deepEqual(crm([...events,...events]).records,a.records);
for(const input of [null,{},[{id:' ',stage:'SQL'}],[{id:'x',stage:'BAD'}]])assert.throws(()=>crm(input));
const calendar=(d)=>run('06-calendar-preview','Normalize UTC',d);
assert.equal(calendar({start:'2026-10-20T19:30:00+05:30',minutes:30}).startUTC,'2026-10-20T14:00:00.000Z');
for(const d of [{start:'2026-10-20T14:00:00',minutes:30},{start:'badZ',minutes:30},{start:'2026-10-20T14:00:00Z',minutes:0},{start:'2026-10-20T14:00:00Z',minutes:'30'},{start:'2026-10-20T14:00:00Z',minutes:481}])assert.throws(()=>calendar(d));
assert.throws(()=>run('04-outreach-draft-review','Stop before send',{sent:true,approval:'PENDING_REVIEW'}));
assert.throws(()=>run('08-gtm-orchestrator','Research evidence',{name:'A',employees:20,evidence:[{claim:'unsupported'}]}));
assert.throws(()=>run('08-gtm-orchestrator','Audit stopped execution',{draft:{sent:false,approval:'APPROVED'},trace:[]}));
console.log('PASS duplicate replay/reserved IDs, four malformed CRM cases, timezone normalization, five invalid calendar cases, two approval bypass cases, missing source');
