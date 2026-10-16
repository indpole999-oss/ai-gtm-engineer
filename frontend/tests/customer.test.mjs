import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

async function load(path, transform = s => s) {
  const source = transform(await readFile(new URL(path, import.meta.url), 'utf8'));
  const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022, jsx: ts.JsxEmit.React } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
}
const { sendLabel, canApproveRole, percent, connectionLabel } = await load('../src/components/customer/contracts.ts');
const { createAuthSession } = await load('../src/lib/auth-session.ts');

function authHarness(profile = async () => ({id:'user-a',email:'a@example.com'})) {
  const value = {token:'stored-token',workspace:'workspace-a',cache:['private-a'],state:null};
  const session = createAuthSession({
    getToken:()=>value.token,
    setToken:token=>{value.token=token;value.workspace=null;},
    clearWorkspace:()=>{value.workspace=null;},
    clearCache:()=>{value.cache=[];},
    profile:()=>profile(),
    publish:state=>{value.state=state;},
  });
  return {value,session};
}
const deferred = () => { let resolve; const promise=new Promise(done=>{resolve=done;}); return {promise,resolve}; };

test('profile verification failures never authorize customer routes and can recover', async () => {
  for (const status of [0,404,405,500,503]) {
    let unavailable=true;
    const {value,session}=authHarness(async()=>{if(unavailable)throw {status};return {id:'user-a',email:'a@example.com'};});
    await session.refresh();
    assert.equal(value.state.status,'unavailable');
    assert.equal(value.state.user,null);
    assert.deepEqual(value.cache,[]);
    assert.equal(value.token,'stored-token');
    unavailable=false;
    await session.refresh();
    assert.equal(value.state.status,'authenticated');
    assert.equal(value.state.user.id,'user-a');
  }
  for (const payload of [null,{},[],{id:'user-a'},{email:'a@example.com'}]) {
    const {value,session}=authHarness(async()=>payload);
    await session.refresh();
    assert.equal(value.state.status,'unavailable');
  }
});

test('logout clears identity, workspace and cache and fences delayed login', async () => {
  const pending=deferred();
  const {value,session}=authHarness();
  await session.refresh();
  const login=session.authenticate(()=>pending.promise);
  const rejected=assert.rejects(login,e=>e.name==='AbortError');
  session.signOut();
  pending.resolve('late-login-token');
  await rejected;
  assert.equal(value.token,null);
  assert.equal(value.workspace,null);
  assert.equal(value.state.status,'anonymous');
  assert.equal(value.state.user,null);
  assert.deepEqual(value.cache,[]);
});

test('latest concurrent sign-in wins and prior-user state is hidden immediately', async () => {
  const old=deferred();
  const {value,session}=authHarness(async()=>({id:'user-b',email:'b@example.com'}));
  const first=session.authenticate(()=>old.promise);
  const rejected=assert.rejects(first,e=>e.name==='AbortError');
  assert.equal(value.state.status,'loading');
  assert.equal(value.workspace,null);
  assert.deepEqual(value.cache,[]);
  await session.authenticate(async()=> 'new-user-token');
  old.resolve('old-user-token');
  await rejected;
  assert.equal(value.token,'new-user-token');
  assert.equal(value.state.user.id,'user-b');
});

test('profile responses cannot resurrect a logged-out session even when a token is reused', async () => {
  const old=deferred();let reads=0;
  const {value,session}=authHarness(()=>++reads===1?old.promise:Promise.resolve({id:'user-b',email:'b@example.com'}));
  const first=session.refresh();
  session.signOut();
  await session.authenticate(async()=> 'stored-token');
  old.resolve({id:'user-a',email:'a@example.com'});
  await first;
  assert.equal(value.state.user.id,'user-b');
});

test('cross-tab identity changes clear tenant state before verification and reject stale profiles', async () => {
  const old=deferred();const fresh=deferred();let reads=0;
  const {value,session}=authHarness(()=>++reads===1?old.promise:fresh.promise);
  const first=session.refresh();
  value.token='other-tab-token'; value.cache=['old-workspace'];
  const synced=session.syncSession();
  assert.equal(value.workspace,null);
  assert.equal(value.state.user,null);
  assert.equal(value.state.status,'loading');
  assert.deepEqual(value.cache,[]);
  fresh.resolve({id:'user-b',email:'b@example.com'});await synced;
  old.resolve({id:'user-a',email:'a@example.com'});await first;
  assert.equal(value.token,'other-tab-token');
  assert.equal(value.state.user.id,'user-b');
  value.token=null;await session.syncSession();
  assert.equal(value.state.status,'anonymous');
});

test('invalid or expired identity clears the token and cache', async () => {
  for (const status of [401,403]) {
    const {value,session}=authHarness(async()=>{throw {status};});
    await session.refresh();
    assert.equal(value.state.status,'anonymous');
    assert.equal(value.token,null);
    assert.equal(value.workspace,null);
    assert.deepEqual(value.cache,[]);
  }
});

test('real auth provider fences a stale profile 401 after a newer verified refresh', async () => {
  const originalFetch=globalThis.fetch, originalWindow=globalThis.window;
  const originalHooks=globalThis.__authTestHooks, originalApi=globalThis.__authTestApi, originalSession=globalThis.__authTestSession;
  const storage=new Map(), replies=[], states=[];let index=0, auth;
  try {
    globalThis.window={localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},dispatchEvent:()=>auth.signOut()};
    globalThis.fetch=()=>new Promise(resolve=>replies.push(resolve));
    const api=await load('../src/lib/api.ts',s=>s.replace('import { API_BASE_URL, TOKEN_STORAGE_KEY } from "./api-config";', 'const API_BASE_URL="http://test.invalid"; const TOKEN_STORAGE_KEY="provider-test-token";'));
    globalThis.__authTestApi=api;
    globalThis.__authTestSession={createAuthSession};
    globalThis.__authTestHooks={createContext:()=>({Provider:null}),useContext:()=>null,useCallback:f=>f,useEffect:()=>{},useMemo:f=>f(),useState:v=>{const i=index++;states[i]=v;return[v,x=>{states[i]=x;}];},useQueryClient:()=>({cancelQueries:async()=>{},clear:()=>{}})};
    const provider=await load('../src/lib/auth.tsx',s=>s
      .replace(/import .* from "react";/,'const {createContext,useCallback,useContext,useEffect,useMemo,useState}=globalThis.__authTestHooks; const React={createElement:(_type,props)=>props.value};')
      .replace(/import .* from "@tanstack\/react-query";/,'const {useQueryClient}=globalThis.__authTestHooks;')
      .replace(/import .* from "\.\/api-config";/,'const API_BASE_URL="http://test.invalid"; const AUTH_ENDPOINTS={token:"/login",me:"/api/v1/auth/me"}; const TOKEN_STORAGE_KEY="provider-test-token";')
      .replace(/import .* from "\.\/api";/,'const {ApiError,apiFetch,getToken,setToken,setWorkspaceId,invalidateSessionRequests}=globalThis.__authTestApi;')
      .replace(/import .* from "\.\/auth-session";/,'const {createAuthSession}=globalThis.__authTestSession;'));
    auth=provider.AuthProvider({children:null});
    api.setToken('synthetic-current-token');
    const old=auth.refresh(), current=auth.refresh();
    replies[1](new Response(JSON.stringify({id:'synthetic-user',email:'synthetic@example.com'}),{status:200}));await current;
    replies[0](new Response('{}',{status:401}));await old;
    assert.equal(api.getToken(),'synthetic-current-token');
    assert.equal(states[0].status,'authenticated');
    assert.equal(states[0].user.id,'synthetic-user');
  } finally {
    globalThis.fetch=originalFetch;globalThis.window=originalWindow;
    globalThis.__authTestHooks=originalHooks;globalThis.__authTestApi=originalApi;globalThis.__authTestSession=originalSession;
  }
});
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
    const cancelled = new AbortController();
    cancelled.abort();
    const abortError = new DOMException('Request cancelled', 'AbortError');
    globalThis.fetch=async()=>{throw abortError;};
    await assert.rejects(()=>api.apiFetch('/api/v1/companies/', {signal:cancelled.signal}), e=>e===abortError);
    assert.deepEqual(events, []);
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
    // JWTs can be identical when the same user signs in within one second.
    api.setToken('same-token');
    const reused=api.apiFetch('/api/v1/companies/');
    api.setToken(null);
    api.setToken('same-token');
    reply(new Response('{}',{status:401}));
    await assert.rejects(()=>reused,e=>e.status===401);
    assert.equal(api.getToken(),'same-token');
    assert.equal(events.length,1);
  } finally {globalThis.fetch=originalFetch;globalThis.window=originalWindow;}
});


test('malformed successful API responses cannot confirm customer saves', async () => {
  const api = await load('../src/lib/api.ts', s => s.replace('import { API_BASE_URL, TOKEN_STORAGE_KEY } from "./api-config";', 'const API_BASE_URL="http://test.invalid"; const TOKEN_STORAGE_KEY="test-token";'));
  const originalFetch = globalThis.fetch;
  let requests = 0;
  try {
    for (const status of [200, 201]) {
      for (const body of ['<html>proxy page: private-diagnostic</html>', '{"saved":', '', '   ']) {
        globalThis.fetch = async () => { requests++; return new Response(body, {status}); };
        const before = requests;
        await assert.rejects(() => api.apiFetch('/api/v1/outcomes/pipeline/test/stage', {
          method: 'POST', body: JSON.stringify({reviewed:true}),
        }), error => error instanceof api.ApiError && error.status === status
          && /Refresh to check whether your changes were saved/.test(error.message)
          && !error.message.includes('private-diagnostic') && error.detail === undefined);
        assert.equal(requests, before + 1); // Never retry an uncertain write automatically.
      }
    }
    globalThis.fetch = async () => new Response('{"revision":2}', {status:201});
    assert.deepEqual(await api.apiFetch('/api/v1/example'), {revision:2});
    globalThis.fetch = async () => new Response('null', {status:200});
    assert.equal(await api.apiFetch('/api/v1/example'), null);
    globalThis.fetch = async () => new Response(null, {status:204});
    assert.equal(await api.apiFetch('/api/v1/example'), undefined);
  } finally { globalThis.fetch = originalFetch; }
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
