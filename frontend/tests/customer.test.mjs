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
const {
  readExecutionSelection,
  executionSearch,
  executionSelectionStorageKey,
  readStoredExecutionSelection,
  writeStoredExecutionSelection,
  resolveExecutionSelection,
  planAuthorLabel,
} = await load('../src/components/customer/execution-selection.ts');

test('refresh selection is workspace scoped and preserves unrelated query parameters', () => {
  const plan = '11111111-1111-4111-8111-111111111111';
  const cycle = '22222222-2222-4222-8222-222222222222';
  const search = executionSearch('?filter=active', 'workspace-a', plan, cycle);
  assert.deepEqual(readExecutionSelection(search, 'workspace-a'), {plan, cycle});
  assert.deepEqual(readExecutionSelection(search, 'workspace-b'), {plan:'', cycle:''});
  assert.equal(new URLSearchParams(search).get('filter'), 'active');
  const cleared = executionSearch(search, 'workspace-a', '', 'invalid-id');
  assert.deepEqual(readExecutionSelection(cleared, 'workspace-a'), {plan:'', cycle:''});
  assert.deepEqual([...new URLSearchParams(search).keys()], ['filter', 'gtm_workspace', 'gtm_plan', 'gtm_cycle']);
  assert.deepEqual(readExecutionSelection('?gtm_workspace=workspace-a&gtm_plan=private-content', 'workspace-a'), {plan:'',cycle:''});
});


test('saved execution selection is isolated by user and workspace', () => {
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  const plan = '11111111-1111-4111-8111-111111111111';
  const cycle = '22222222-2222-4222-8222-222222222222';
  writeStoredExecutionSelection(storage, 'workspace-a', 'user-a', plan, cycle);
  assert.deepEqual(readStoredExecutionSelection(storage, 'workspace-a', 'user-a'), {plan, cycle});
  assert.deepEqual(readStoredExecutionSelection(storage, 'workspace-b', 'user-a'), {plan:'', cycle:''});
  assert.deepEqual(readStoredExecutionSelection(storage, 'workspace-a', 'user-b'), {plan:'', cycle:''});
  assert.notEqual(
    executionSelectionStorageKey('workspace-a', 'user-a'),
    executionSelectionStorageKey('workspace-a', 'user-b'),
  );
});

test('explicit URL selection wins over saved navigation state', () => {
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  const savedPlan = '11111111-1111-4111-8111-111111111111';
  const urlPlan = '33333333-3333-4333-8333-333333333333';
  writeStoredExecutionSelection(storage, 'workspace-a', 'user-a', savedPlan, '');
  const fromStorage = resolveExecutionSelection('', 'workspace-a', 'user-a', storage);
  assert.equal(fromStorage.source, 'storage');
  assert.equal(fromStorage.selection.plan, savedPlan);
  const fromUrl = resolveExecutionSelection(
    '?gtm_workspace=workspace-a&gtm_plan=' + urlPlan,
    'workspace-a',
    'user-a',
    storage,
  );
  assert.equal(fromUrl.source, 'url');
  assert.equal(fromUrl.selection.plan, urlPlan);
});

test('malformed or blocked saved navigation state fails closed', () => {
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  values.set(executionSelectionStorageKey('workspace-a', 'user-a'), '{"plan":"not-an-id","cycle":42}');
  assert.deepEqual(readStoredExecutionSelection(storage, 'workspace-a', 'user-a'), {plan:'', cycle:''});
  const blocked = {
    getItem() { throw new Error('blocked'); },
    setItem() { throw new Error('blocked'); },
    removeItem() { throw new Error('blocked'); },
  };
  assert.deepEqual(readStoredExecutionSelection(blocked, 'workspace-a', 'user-a'), {plan:'', cycle:''});
  assert.doesNotThrow(() =>
    writeStoredExecutionSelection(
      blocked,
      'workspace-a',
      'user-a',
      '11111111-1111-4111-8111-111111111111',
      '',
    ),
  );
});

test('clearing selection removes only that user workspace record', () => {
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  const plan = '11111111-1111-4111-8111-111111111111';
  writeStoredExecutionSelection(storage, 'workspace-a', 'user-a', plan, '');
  writeStoredExecutionSelection(storage, 'workspace-a', 'user-b', plan, '');
  writeStoredExecutionSelection(storage, 'workspace-a', 'user-a', '', '');
  assert.deepEqual(readStoredExecutionSelection(storage, 'workspace-a', 'user-a'), {plan:'', cycle:''});
  assert.equal(readStoredExecutionSelection(storage, 'workspace-a', 'user-b').plan, plan);
});

test('plan provenance distinguishes templates, local AI and hosted AI', () => {
  assert.equal(planAuthorLabel('explicit_research_template'), 'guided research template');
  assert.equal(planAuthorLabel('ollama:qwen3:4b'), 'local AI');
  assert.equal(planAuthorLabel('groq:test-model'), 'hosted AI');
  assert.equal(planAuthorLabel('unexpected'), 'unknown author method');
});

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


test('readiness diagnostics show paused Groq fields without exposing extra response data', async () => {
  const { readinessDetails } = await load('../src/components/customer/research-provider.ts',
    s => s.replace('import { useData } from "./ui";', 'const useData = () => { throw new Error("hook is not used by this test"); };'));
  const value = {provider:'groq',state:'paused',can_attempt:false,message:'Paused',api_key:'synthetic-secret'};
  assert.deepEqual(readinessDetails(value), {provider:'groq',state:'paused',can_attempt:false});
  assert.equal(JSON.stringify(readinessDetails(value)).includes('synthetic-secret'), false);
  assert.deepEqual(readinessDetails({...value,state:'configured_unverified',can_attempt:true}),
    {provider:'groq',state:'configured_unverified',can_attempt:true});
});

test('research draft copy makes one revision request, preserving limits and requiring later approval', async () => {
  const { createResearchRevision } = await load('../src/components/customer/research-revision.ts');
  const original = {id:'existing-plan',goal_id:'existing-goal',status:'approved',document:{
    targets:[{company_id:'existing-company',source_urls:['https://example.com/']}],
    plan:{objective:'Research existing account',max_attempts:1,timeout_seconds:120,
      steps:[{action:'research',side_effect:'read_only',target_index:0,dependencies:[]}]}}};
  const before=structuredClone(original);
  const calls=[];
  const saved={...original,id:'new-draft',status:'draft'};
  const request=async(path,init)=>{calls.push({path,init});return saved;};
  assert.equal(await createResearchRevision(original,request),saved);
  assert.equal(calls.length,1);
  assert.equal(calls[0].path,'/api/v1/gtm/plans/existing-plan/revisions');
  assert.equal(calls[0].init.method,'POST');
  assert.deepEqual(JSON.parse(calls[0].init.body),original.document.plan);
  assert.deepEqual(original,before);
  for (const steps of [[],[{action:'outreach_send',side_effect:'outbound'}],
    [{action:'research',side_effect:'outbound'}],
    [...original.document.plan.steps,{action:'crm_sync',side_effect:'external_write'}]]) {
    await assert.rejects(()=>createResearchRevision({...original,document:{plan:{steps}}},request),/Only read-only research/);
  }
  assert.equal(calls.length,1);
  await assert.rejects(()=>createResearchRevision(original,async()=>{throw new Error('permission denied');}),/permission denied/);
});


const { createReviewClient, reviewPermissions } = await load('../src/components/customer/outreach-review-client.ts');
test('review controls enforce role, submission, current revision and unsaved changes', () => {
  assert.equal(reviewPermissions('member', 'draft', true, false).submit, true);
  assert.equal(reviewPermissions('viewer', 'draft', true, false).edit, false);
  assert.equal(reviewPermissions('member', 'submitted', true, false).decide, false);
  assert.equal(reviewPermissions('admin', 'submitted', true, false).decide, true);
  assert.equal(reviewPermissions('owner', 'submitted', true, true).decide, false);
  assert.equal(reviewPermissions('owner', 'submitted', false, false).decide, false);
  for (const state of ['approved', 'submitted']) assert.equal(reviewPermissions('owner', state, true, false).edit, false);
  for (const state of ['rejected', 'changes_requested']) assert.equal(reviewPermissions('member', state, true, false).edit, true);
});

test('review actions call durable draft endpoints and never delivery execution', async () => {
  const calls = [];
  const client = createReviewClient(async (path, init) => { calls.push({path, body: JSON.parse(init.body), method:init.method}); return {persisted:true}; });
  const draft = {id:'draft-id', content_hash:'a'.repeat(64)};
  assert.deepEqual(await client.run(draft, 4, 'submit'), {persisted:true});
  assert.deepEqual(calls.at(-1), {path:'/api/v1/outreach/drafts/draft-id/submit',method:'POST',body:{content_hash:draft.content_hash,expected_revision:4}});
  await client.run(draft, 5, 'changes_requested', {reason:' Needs detail '});
  assert.equal(calls.at(-1).path, '/api/v1/outreach/drafts/draft-id/decision');
  assert.equal(calls.at(-1).body.action, 'changes_requested');
  assert.equal(calls.at(-1).body.reason, 'Needs detail');
  await client.run(draft, 6, 'rejected', {reason:'Unsupported'});
  await client.run(draft, 7, 'revisions', {subject:'Edited',body:'Source quote'});
  assert.equal(calls.at(-1).body.subject, 'Edited');
  await client.run(draft, 8, 'approve', {acknowledge:true});
  assert.equal(calls.at(-1).body.reviewed, true);
  assert.equal(calls.at(-1).body.acknowledge_unverified_edits, true);
  assert.equal(calls.length, 5);
  assert.equal(calls.some(call => /send|cycles|plans/.test(call.path)), false);
});

test('review client blocks concurrent duplicates and propagates authorization and network failures', async () => {
  let resolve; let calls=0;
  const draft={id:'draft-id',content_hash:'a'.repeat(64)};
  const client=createReviewClient(async()=>{calls++;return new Promise(done=>{resolve=done;});});
  const first=client.run(draft,1,'submit');
  await assert.rejects(()=>client.run(draft,1,'submit'), /already in progress/);
  resolve({status:'submitted'});
  assert.equal((await first).status,'submitted');
  assert.equal(calls,1);
  for (const status of [0,403,409,500]) {
    let count=0;
    const denied=createReviewClient(async()=>{count++;throw Object.assign(new Error('Request failed'),{status});});
    await assert.rejects(()=>denied.run(draft,1,'approve'), error=>error.status===status);
    await assert.rejects(()=>denied.run(draft,1,'approve'), error=>error.status===status);
    assert.equal(count,2); // No hidden retry; a new explicit action can run after failure.
  }
});

test('blank review decisions and unsupported operations never issue a request', async () => {
  let calls=0;
  const client=createReviewClient(async()=>{calls++;});
  const draft={id:'draft-id',content_hash:'a'.repeat(64)};
  await assert.rejects(()=>client.run(draft,1,'rejected',{reason:'  '}), /reason/);
  await assert.rejects(()=>client.run(draft,1,'revisions',{subject:' ',body:'x'}), /required/);
  await assert.rejects(()=>client.run(draft,1,'send'), /Unsupported/);
  assert.equal(calls,0);
});
