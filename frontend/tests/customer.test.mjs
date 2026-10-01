import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

async function load(path, transform = s => s) {
  const source = transform(await readFile(new URL(path, import.meta.url), 'utf8'));
  const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
}
const { sendLabel, canApproveRole, percent, connectionLabel } = await load('../src/components/customer/contracts.ts');

test('saved credentials cannot imply a verified provider connection', () => {
  assert.equal(connectionLabel({status:'connected',health:'configured_unverified',reconnect_required:false}), 'Saved · verification unavailable');
  assert.equal(connectionLabel({status:'connected',health:'healthy',reconnect_required:false}), 'Provider verified');
  assert.equal(connectionLabel({status:'connected',health:'healthy',reconnect_required:true}), 'Reconnect required');
  assert.equal(connectionLabel({status:'disconnected',health:'healthy',reconnect_required:false}), 'Not verified');
  assert.equal(connectionLabel({status:'error',health:'provider_unavailable',reconnect_required:false}), 'Needs attention');
});

test('a sent label needs both provider identity and acceptance evidence', () => {
  assert.equal(sendLabel({state:'sent'}), 'Confirmation unavailable');
  assert.equal(sendLabel({state:'sent',provider_message_id:'p'}), 'Confirmation unavailable');
  assert.equal(sendLabel({state:'sent',accepted_at:'2026-09-27T00:00:00Z'}), 'Confirmation unavailable');
  assert.equal(sendLabel({state:'sent',provider_message_id:'p',accepted_at:'2026-09-27T00:00:00Z'}), 'Provider-confirmed sent');
  for (const state of ['failed','awaiting_approval','pending','reconciling']) assert.notEqual(sendLabel({state,provider_message_id:'p',accepted_at:'date'}), 'Provider-confirmed sent');
});
test('approval roles fail closed', () => {
  for (const role of ['owner','admin']) assert.equal(canApproveRole(role), true);
  for (const role of ['member','viewer','', 'operator', 'OWNER']) assert.equal(canApproveRole(role), false);
});
test('missing rates remain distinct from measured zero', () => {
  assert.equal(percent({rate:null}), 'Not enough data');
  assert.equal(percent({rate:0}), '0.0%');
  assert.equal(percent({rate:0.125}), '12.5%');
});
test('workspace headers, authentication reset, cancellation and failures', async () => {
  const api = await load('../src/lib/api.ts', s => s.replace('import { API_BASE_URL, TOKEN_STORAGE_KEY } from "./api-config";', 'const API_BASE_URL="http://test.invalid"; const TOKEN_STORAGE_KEY="test-token";'));
  const storage = new Map();
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const events=[];
  globalThis.window = {dispatchEvent:e=>events.push(e.type),localStorage:{getItem:k=>storage.get(k) ?? null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}};
  const calls=[];
  globalThis.fetch = async (url,init) => {calls.push({url,...init});return new Response('{}',{status:200});};
  try {
    api.setToken('test-only'); api.setWorkspaceId('workspace-a');
    const controller = new AbortController();
    await api.apiFetch('/api/v1/companies/',{signal:controller.signal});
    assert.equal(calls.at(-1).headers.get('X-Workspace-ID'),'workspace-a');
    assert.equal(calls.at(-1).signal,controller.signal);
    api.setWorkspaceId('workspace-b');
    await api.apiFetch('/api/v1/insights');
    assert.equal(calls.at(-1).headers.get('X-Workspace-ID'),'workspace-b');
    for (const path of ['/api/v1/auth/me','/api/v1/workspaces']) {
      await api.apiFetch(path); assert.equal(calls.at(-1).headers.has('X-Workspace-ID'),false);
    }
    api.setToken(null); await api.apiFetch('/api/v1/companies/');
    assert.equal(calls.at(-1).headers.has('X-Workspace-ID'),false);
    assert.equal(calls.at(-1).headers.has('Authorization'),false);
    globalThis.fetch=async()=>new Response('{"detail":"Approval required"}',{status:403});
    await assert.rejects(()=>api.apiFetch('/api/v1/outreach/messages'),e=>e.status===403);
    globalThis.fetch=async()=>{throw new Error('offline');};
    await assert.rejects(()=>api.apiFetch('/api/v1/companies/'),e=>e.status===0);
    api.setToken('expired-test-only'); api.setWorkspaceId('workspace-a');
    globalThis.fetch=async()=>new Response('{"detail":"Token expired"}',{status:401});
    await assert.rejects(()=>api.apiFetch('/api/v1/companies/'),e=>e.status===401);
    assert.equal(api.getToken(),null);
    assert.equal(api.getWorkspaceId(),null);
    assert.deepEqual(events,['gaps:session-expired']);
    api.setToken('old-test-session');
    let reply;
    globalThis.fetch=()=>new Promise(resolve=>{reply=resolve;});
    const stale=api.apiFetch('/api/v1/companies/');
    api.setToken('new-test-session');
    reply(new Response('{}',{status:401}));
    await assert.rejects(()=>stale,e=>e.status===401);
    assert.equal(api.getToken(),'new-test-session');
    assert.equal(events.length,1);
  } finally {globalThis.fetch=originalFetch;globalThis.window=originalWindow;}
});
