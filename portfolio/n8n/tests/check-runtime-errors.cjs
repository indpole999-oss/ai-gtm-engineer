'use strict';
// Read local CLI logs only; publish a sanitized error-match summary, never raw logs.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(process.argv[2]);
const read=p=>{const b=fs.readFileSync(p);return b[0]===255&&b[1]===254?b.toString('utf16le').replace(/^\uFEFF/,''):b.toString('utf8').replace(/^\uFEFF/,'')};
const cases=JSON.parse(read(path.join(root,'manifest.json')));const summary=[];
for(const c of cases){const s=read(path.join(root,c.id+'.log'));const found=s.includes(c.expectedError);assert(found,c.case+': expected error not observed');assert(!/Could not find workflow|Workflow .* not found/.test(s),c.case+': missing import');summary.push({case:c.case,expectedError:c.expectedError,matched:found});}
console.log(JSON.stringify({status:'PASS',cases:summary},null,2));
