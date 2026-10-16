'use strict';
// Exercise the browser script's event handlers without network or a DOM package.
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function element(){return {textContent:'',value:'aster',hidden:false,disabled:false,style:{},children:[],handlers:{},addEventListener(e,fn){this.handlers[e]=fn},replaceChildren(){this.children=[]},append(...items){this.children.push(...items)},appendChild(item){this.children.push(item)}}}
const nodes={};const document={getElementById(id){return nodes[id]??=element()},createElement:element};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../main.js'),'utf8'),{document,Date});
function fire(id,event){nodes[id].handlers[event]?.()}
fire('run-demo','click');assert.equal(nodes['result-score'].textContent,'100/100');
fire('approve-demo','click');assert.equal(nodes['trace-status'].textContent,'APPROVED IN MEMORY');
nodes['account-select'].value='ridge';fire('account-select','change');
assert.equal(nodes['result-body'].hidden,true);assert.equal(nodes['result-empty'].hidden,false);
assert.equal(nodes['approve-demo'].disabled,true);assert.equal(nodes['result-draft'].textContent,'');
fire('approve-demo','click');assert.equal(nodes['trace-status'].textContent,'AWAITING RUN');
fire('run-demo','click');assert.equal(nodes['result-score'].textContent,'0/100');assert.equal(nodes['approve-demo'].disabled,false);
nodes['account-select'].value='mira';fire('account-select','change');fire('run-demo','click');
assert.equal(nodes['result-score'].textContent,'100/100');assert.match(nodes['result-draft'].textContent,/MiraCare/);
console.log('PASS: three fixtures, approval, account-change invalidation, stale-approval rejection, rerun');
