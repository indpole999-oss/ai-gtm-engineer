# Hosted staging customer acceptance — 2026-10-10

Overall: **BLOCKED — not customer-ready**. The complete hosted journey has not
passed. Successful research, supported qualification, personalized draft creation,
message approval, delivery authorization, real inbox ingestion, and provider-backed
outcomes remain unverified. No production changes, deployment, paid AI generation,
real email sends, or external calendar events were performed.

## Deployment and scope

- Branch: `codex/ai-gtm-engineer-v2-full-build`.
- Web: `https://gaps-ai-v2-staging-web.onrender.com`.
  Render deploy `dep-db55ql8473hc73a03su0`, status `live`, commit
  `39a54d14a4b62ae901d94a83e75616e815d84d03`, confirmed through Render.
- API: `https://gaps-ai-v2-staging-api.onrender.com`.
  Latest live deploy `dep-db4l0sbncjis73fub2u0`, commit
  `237818dd3ba815411f9d1eed1961fff1a5a047f1`. Web and API are not at identical
  commits; API acceptance applies to this deployed backend, not a newer build.
- Both staging services report auto-deploy off. No deployment was triggered.
- Database: Supabase project `xhjkahbtckrrhuzamysr`, verified as
  `gaps-ai-staging`, `ACTIVE_HEALTHY`. SQL was read-only and restricted to synthetic
  workspace records. Application API writes were restricted to the test workspace.
- No existing browser tab was available. A new in-app browser tab was used.
  Desktop viewport: 1440×1000. Mobile viewport: 390×844; measured content width
  was 375 with a scrollbar and 390 without it. No physical-device test was run.

## Synthetic records and persistence evidence

Primary account: `gaps-hosted-qa-20261010-1630@example.com`.
Workspace `0512dcec-1987-4dac-b1a5-a734be589e16`, owner,
`Synthetic Hosted QA 20261010 workspace`.

Secondary account: `gaps-hosted-qa-mobile-20261010@example.com`.
Workspace `01815c4b-1386-459a-8b38-168a73fbd99c`, owner,
`Synthetic Mobile Isolation QA workspace`.

| Persisted record | Exact evidence |
| --- | --- |
| Company Brain | `8557ad53-5e39-4bcb-90a2-cad415964cfb`, version 1, published, revision 3; hash `860ad586881ad37382b5877231eeee1396952c760926dcd9c569b1a8bf3d7099` |
| Account | `93518322-93de-4575-8e50-46c0e52a9cda`, Synthetic Hosted Account 20261010, example.com |
| Contact | `2aa7cc12-793e-4daf-8256-813f6176f3ce`, Synthetic Buyer; manually entered and unverified |
| Goal | `65e8666d-04ff-4be5-9988-1a51d9f1782f` |
| Plan | `e18ebfd2-2d39-4602-852d-dda8caea3aac`, draft, `explicit_research_template`; hash `52c561e31ea7a103ec1d8c69f051ca43afb1f1947a0b3ee09cc4222b3c54a533` |
| Research guard-test job | `452695b6-2cc3-4334-b471-f19b0406671b`, queued, zero captures and research claims. Created through API for a rejection test; not executed or approved. |
| Fake mailbox | `f8dc58d7-d947-4177-80c9-bd875ab8e0aa`, explicitly provider `fake` |
| Fake inbox thread | `c2968613-dbcd-42c5-9933-df2d64599574`, one synthetic opt-out message |
| Account pipeline | `44a724b4-5e72-4e7d-8b26-f55004886d89`, discovered |
| Contact pipeline | `f1759253-3f2e-4d37-9c40-3d21b1c1ffb8`, discovered |

SQL confirmed exactly one primary Brain version, account, contact, goal, plan,
campaign, sequence, sequence version, sender, inbox thread, inbound message,
inbound receipt, and suppression. Account and contact each have their own pipeline
record; these two records are intentional, not duplicates. Zero enrollments,
outreach drafts, outbound messages, execution cycles, source captures, research
claims, or integrations exist in the primary workspace. The secondary has one
owner membership and zero Brain versions, accounts, or goals.

## Hosted acceptance matrix

| Gate | Status | Reproducible evidence and limits |
| --- | --- | --- |
| Signup/login/logout | PASS | Desktop signup created primary private workspace; mobile signup created secondary private workspace. Both reached their own dashboard. Correct desktop and mobile login tested; explicit logout returned to Sign in. API login 200; wrong-password login 401 and mobile alert `Invalid credentials`; duplicate registration 400. UI signup response codes were not independently captured; successful persistence was verified by SQL. |
| Refresh/session | PASS | Published Brain, exact guided plan, primary inbox/pipeline and second-account dashboard survived refresh. One older browser session redirected to login during Integrations navigation; fresh login recovered saved records and integration navigation passed. Fresh token lifetime was 3,599 seconds. Expiry is consistent with the long rehearsal, but the original browser 401 response was not captured, so its exact cause is not asserted. |
| Company Brain | PASS | UI open draft → enter synthetic profile and manual claim → save → acknowledge saved content → publish. GET `/api/v1/company-brain` 200 and SQL agree on ID/status/hash/revision. Desktop refresh and mobile published-version access retained one version. No model-generated or independently verified claims are implied. |
| Goal/guided plan | PASS | Prospects → select published Brain and example.com source → Propose research plan → exact command-center link → reload. GET `/gtm/goals` and exact saved plan 200; SQL confirms one draft template. Mobile restores version 1. This is guided preparation, not AI planning success. |
| Prospects | PASS | UI account/contact writes persisted; GET `/companies/` and `/contacts/` 200, one each. Desktop and mobile readback show discovered/unverified rather than qualified. |
| Research readiness/safety gates | PASS | GET `/research/readiness` 200: `provider=groq`, `state=paused`, `can_attempt=false`. Approval button remains disabled after review acknowledgement and reload. POST exact `/gtm/plans/{id}/approve` 409: `Hosted AI is paused. Save and review the plan; research cannot be queued until explicitly authorized.` Zero cycles persisted. POST `/research/jobs/{id}/run` 409: approved plan/durable worker required. |
| Real research execution | BLOCKED | Hosted AI is paused and paid AI is prohibited. No model generation, source retrieval execution, supported intelligence or completed job was produced. A queued guard-test job is not worker execution evidence. |
| Qualification | BLOCKED | Successful qualification needs completed source-backed research. GET contact eligibility 200 `[]`. Unsupported manual qualified transition returned 409 `Supported qualification required`; pipeline remained discovered. |
| Outreach configuration | PASS | Desktop UI created one campaign, sequence and immutable version; reload/API/SQL agree. Mobile enrollment shows no completed research. Suppressed synthetic contact is disabled after opt-out. No enrollment sends mail. |
| Personalized outreach draft | BLOCKED | POST `/outreach/prospects/{contact_id}/draft` with queued research returned 409 `Source-backed account fit and matching buyer qualification required`. Zero drafts and enrollments persisted. No provider composition was attempted. |
| Human approval | BLOCKED | Desktop/mobile empty Approval Queue shows `No drafts awaiting approval` without scheduled records, confirming remote queue fix. Successful submit/review/message approval/separate delivery authorization cannot be accepted without an eligible draft. Prior local fixture tests are not substituted for this hosted gate. |
| Inbox — explicit fixture | PASS | Fake-adapter POST `/inbox/simulated-events/{sender_id}` twice returned 202 with the same inbound ID. GET threads 200 with one thread. SQL: one message, one receipt, one thread, one suppression. Desktop detail renders original synthetic body, `unsubscribe`, confidence 0.99, suppressed state and disabled suggested reply. Mobile reload retains the conversation. This is fixture ingestion, not received email. |
| Inbox — real provider | BLOCKED | No real email sent or received; live webhook/provider integration not verified. |
| Pipeline readback | PASS | GET `/outcomes/pipeline` 200 and SQL match two discovered records. Desktop/mobile display account/contact separately, with no inferred qualification or engagement from the unassociated fake inbox event. |
| Pipeline provider outcomes | BLOCKED | No accepted research, send, linked real reply, provider meeting or CRM sync. |
| Insights readback | PASS | Valid UTC range GET `/insights?start=...&end=...` 200. Desktop/mobile show contact cohort 1, discovered 1, qualified 0, provider-confirmed sends 0, human replies 0; conversion/recommendations show insufficient data. Unassociated fixture was not counted as a real reply. |
| Insights real outcomes | BLOCKED | No complete real-provider journey or actual cost ledger. |
| Integrations availability/isolation | PASS | GET `/integrations` 200, empty in both test workspaces. GET `/integrations/providers` 200, 13 contracts. Desktop/mobile show available Google Calendar connection and explicitly unavailable email/CRM. Existing customers' integrations were not accessed or changed. |
| Integration execution/reconnect | BLOCKED | No synthetic-workspace Google account connected; no OAuth access grants, external events, email or CRM execution/reconnect performed. |
| Workspace isolation | PASS | Secondary own lists empty. First workspace account, Brain version, plan and inbox thread IDs each return 404 under secondary membership; first workspace header returns 403 `No active workspace membership`. Foreign plan URL in secondary browser shows only its empty workspace, no first-workspace records. Invalid bearer returns 401. |
| Error handling | PASS | Missing Insights dates and malformed UUID return 422; nonexistent company 404; invalid company UUID on contact create 400; wrong login 401 visible in mobile UI; unsupported research/draft/qualification 409 with concrete blockers. No success inferred from rejected operations. Initial future-end Insights range was rejected 422; valid range then passed. |
| Desktop/mobile complete journey | BLOCKED | Available pages and persistence were exercised on both viewports with no horizontal document overflow observed. Mobile navigation closes after transition. Full successful journey cannot proceed past research and qualification under current restrictions. No network outage/reconnect or physical-device acceptance claimed. |
| Landing title | FAIL (hosted); PASS (local fix) | Hosted `/` title is `GAPS AI â€” Evidence-backed growth`. Reproduces by opening staging root and reading tab title. Corrected title and Open Graph metadata locally; verified by built frontend HTTP 200 with exact `GAPS AI — Evidence-backed growth` and no corrupted title. Staging still serves the earlier build because no deployment is authorized. |

## Evidence files and test verification

Local evidence directory: `.venv/hosted-acceptance/` (ignored, not committed).
`http-readback.json` contains 17 authenticated readbacks;
`http-guards.json` contains 18 guard/fixture requests;
`http-isolation.json` contains 15 isolation/error requests. No bearer tokens or
provider credentials are in these result files. Synthetic helper credentials are
kept only in ignored local helper scripts, not committed or included here.
Screenshots: `desktop-inbox.jpg`, `mobile-plan.jpg`, `mobile-insights.jpg`,
`mobile-isolation.jpg`. HTTP scripts hit the real staging API; SQL readbacks use
the real staging database. Browser actions use the deployed React frontend.
The HTTP guard and isolation scripts finished with all assertions passed.

For the only source fix (landing title/OG metadata):

- TypeScript: `node node_modules/typescript/bin/tsc --noEmit` — exit 0.
- Frontend contracts: `node --test tests/customer.test.mjs` — 17 passed,
  0 failed, 2005.82 ms.
- Frontend build: `node node_modules/vite/bin/vite.js build` — exit 0,
  client/SSR/Nitro output generated. Existing tsconfig-paths and LoginPage
  code-splitting warnings are nonblocking.
- Targeted lint: `node node_modules/eslint/bin/eslint.js src/routes/index.tsx
  --no-cache --rule 'prettier/prettier: off'` — exit 0.
- Built loopback HTML: HTTP 200, exact corrected title and no garbled metadata —
  assertions passed. A first inline shell check exited 1 without output; an
  encoding-safe saved script rerun passed. The loopback server was stopped.

The prior 37 backend / 2 local browser / 316 historical tests were not rerun for
this metadata-only change. Their historical evidence remains in
`V2_JOURNEY_VERIFICATION_2026_10_10.md`, separate from this hosted acceptance.

The pre-existing release-checklist edit remains unchanged and excluded from this
commit, content hash `1f215c9d1bc1cab51531b0d6c1caf5a8adde27b3`.
The generated route-tree rewrite was excluded. Only the verified metadata repair
and this report are intended for commit/push. Synthetic records are retained for
reproducible readback; no irreversible cleanup was performed.
