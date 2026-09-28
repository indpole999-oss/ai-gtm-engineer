# AI GTM Engineer V2 implementation progress

## Authority and starting point

Current authorization: finish Phase 10, commit/push its validated checkpoint, then continue automatically into Phase 11 Production Hardening.
Phases 1–9 are validated history and must not be repeated.
Overall V2 completion at this checkpoint: **95%** (user-specified Phase 10 milestone).
Base: validated Phase 0 commit `69b267ca315c1cac1de1476948c7ccf3e9e84fd3`.
Branch: `codex/ai-gtm-engineer-v2-full-build`.
Do not merge main, deploy, modify production data, or incur paid-service costs.
The full product specification is preserved in `docs/V2_SPECIFICATION.md`.

## Phase 1 implementation

- Workspace and role/status-constrained membership models; atomic signup workspace.
- Central active membership/workspace resolution with explicit `X-Workspace-ID`
  when a user belongs to multiple workspaces; single-workspace V1 compatibility.
- Fail-closed ORM query scoping, insert/update/delete checks, immutable ownership,
  relationship validation, and database composite relationship foreign keys.
- Owner/admin/member can create/update ordinary records; viewer is read-only.
  Owner/admin can delete and administer integrations. Only owners can change
  memberships; the last active owner cannot be removed. Suspended users,
  memberships and workspaces cannot access customer data.
- Integrations belong to workspaces; user attribution is retained. Response
  credentials are excluded and provider errors are generalized.
- Workspace-scoped company-domain/contact-email uniqueness.
- Deterministic integration backfill; ambiguous legacy data quarantined with audit.
- PostgreSQL transaction-local workspace RLS, including pool/commit handling.
- Application startup no longer creates schemas; Alembic owns schema evolution.
- Unsafe V1 agent/workflow/outbound/CRM/calendar execution routes return 409 until
  the V2 approved execution service is implemented. This is an intentional
  temporary compatibility restriction, not a finished replacement feature.

## Validation and current work

Phase 1 passed at `b1668c6`: backend, frontend and PostgreSQL security CI green
(run 35642316058). No production actions were performed.

Phase 2 passed at `4495880`, CI run 35732166994 (all three jobs green): workspace provider contracts, connection
health/scopes/expiry/reconnect/audit, durable one-time Google OAuth/PKCE, persistent
Google refresh and revoke, safe frontend return and supported provider choices.
Local validation: 56 passed, 1 PostgreSQL-only skip; TypeScript and targeted lint
passed. Callback membership revalidation, declined consent and reconnect refresh
retention are covered. PostgreSQL RLS/migrations and frontend build passed in CI.

Google OAuth and live provider smoke tests need staging credentials supplied at
release time. Unit/contract tests use fake providers and make no paid API calls.
Gmail/Outlook/Salesforce currently support bring-your-own authorized access tokens;
only Google Calendar has an interactive OAuth/automatic refresh flow. Serper is
explicitly configured-unverified until research execution uses it; health checks
never spend search credits. No fake connected/sent/calendar-created state.

Phase 3 implements guided Company Brain drafts in Settings, source/document
previews, approved/prohibited claims, revision-based saves and explicit reviewed
publication. Published versions and children are immutable in ORM and SQL.
Local validation: 64 passed, 1 PostgreSQL-only skip; TypeScript and targeted lint
passed. Clean/baseline/Phase 2 upgrades and SQLite immutability passed. Browser
save/reopen/review/publish passed against a disposable local database. GitHub CI
passed at `8fb2748`, CI run 35735042223. See `docs/V2_COMPANY_BRAIN.md`.

Phase 4 adds source captures, quoted evidence, validated local-model research,
exact-Brain ICP qualification, buyer observations with unknown verification,
audited administrator fact review and company-detail account intelligence UI.
Final full suite: 83 passed, 1 PostgreSQL-only skip. CI run 35770276072 passed
all three jobs at `029cc03`.
No paid calls; development uses injected deterministic providers. Existing OpenAI
configuration is preserved. See `docs/V2_RESEARCH.md` for boundaries and risks.

Phase 5 implements persisted goals, schema-validated local planning, exact Brain
version/hash references, versioned review and immutable approval, transactional
commands/events/outbox, and a separate durable worker with leases, bounded retries,
timeouts, cancellation/resume and workspace admission controls. Local backend:
The intermediate checkpoint `c4ebff4` passed CI run 35867895187.
Browser create/revise/review/approve/pause/resume/cancel passed on disposable data.
Final specification checks add explicit workflow_runs and validated persisted
step outputs. Final local suite: 97 passed, 1 PostgreSQL-only skip, including
populated-cycle backfill and rejection of invalid step success output.
Final Phase 5 implementation checkpoint: `adba93e3ebb2124f5af8a305f152ebbd32d916df`.
CI run 35900333913 passed all three jobs: backend tests and clean migration,
PostgreSQL security/isolation/concurrent worker claims, and frontend TypeScript,
build and targeted lint. **PHASE 5 PASSED.** See `docs/V2_EXECUTION.md`.

Approved plans pin the published Brain ID/hash and exact targets. Approval creates
the cycle, workflow run, step runs, commands and audit/outbox atomically. Step
success requires a schema-valid reference to that command's own completed,
workspace-scoped research result. Migration 0009 backfills workflow ownership
only from existing cycles and preserves their steps; no legacy reassignment.

Phase 5 validated migration head: `20260923_0009`.
Current validated migration head: `20260926_0012`.
Production adoption, quarantine remediation and recovery: `docs/V2_MIGRATIONS.md`.

## Phase 6 checkpoint

**PHASE 6 PASSED locally (2026-09-26).** Built only the Outreach Engine from
verified clean starting HEAD `d446f49841f24cfab2f463e84698d1c8af722dcb`.

- Campaigns, sequences, immutable sequence versions/steps, pinned enrollments,
  scheduled messages, immutable evidence-backed drafts and message approvals,
  sender identities, provider acceptance, separate delivery events and suppressions.
- Separate draft composition, owner/admin message review and plan approval. Sends
  reuse Phase 5 execution cycles, workflow/step runs, leased action commands,
  admission limits, bounded retries, audit and transactional outbox.
- Stable provider idempotency keys and lookup-before-retry reconciliation; no
  sent state without provider acceptance. Tests cover provider rejection, unknown
  lookup, lost acknowledgement, worker restart and stale lease acknowledgement.
- Workspace/RBAC isolation, immutable SQL approvals and snapshots, active-approver
  checks, due/prior-step ordering, recipient/sender validation, daily limits,
  suppression/unsubscribe blocking and fresh-state checks across dispatch commits.
- Additive Alembic `20260926_0010`, with forced PostgreSQL RLS, composite workspace
  foreign keys and preservation of populated Phase 5 execution history.
- Command-center contracts and labels distinguish outbound plans from research.

Validation: full backend regression run **120 passed**, including disposable
PostgreSQL migration/security and concurrent-worker/restart probes. After final
race hardening, targeted outreach + actual Alembic migration + PostgreSQL run
**24 passed**. Frontend TypeScript, targeted ESLint and production build passed.
GitHub CI is checked after pushing this checkpoint; its exact run/result is
reported with the delivery commit. No live provider sends, paid calls, API keys,
production data changes, Render deployment or main merge occurred.

Live delivery remains disabled by default. Fake adapters have a separate durable
provider ledger and are injected only in tests. A real adapter must guarantee
provider-side durable idempotency and authoritative lookup before a separately
approved staging rollout. This is not a production-readiness claim.
See `docs/V2_OUTREACH.md` for API lifecycle, provider contract and recovery.

## Phase 7 checkpoint

**PHASE 7 implementation complete and locally validated (2026-09-26).** Built only
AI Inbox from verified clean HEAD `c570560d979bf0e048b7ba4d16fc49da478888ba` on the
specified branch. Phase 6 CI run `36187223415` passed all three jobs. PR #2 was
verified open, draft and unmerged before Phase 7 work.

- Immutable inbound messages, provider receipts, conversations and deterministic
  outbound/thread/reply-chain associations, retaining pinned outreach/research/
  Brain context. Unknown or ambiguous associations remain explicitly unresolved.
- All nine required deterministic reply categories, confidence/reasons/evidence,
  classifier version, recommendations and append-only administrator overrides.
- Immediate persistent sequence holds for genuine replies and distinct OOO state;
  unsubscribe integrates with existing suppression before acknowledgement.
  Queued and claimed sends respect holds, including the dispatch commit gap.
- Atomic deferred classification through the existing Phase 5 outbox and worker,
  shared admission, leases, bounded retries, stale-token rejection and recovery.
  Duplicate provider events/messages cannot repeat business side effects.
- Workspace/RBAC-protected list/detail/review/retry APIs and optional immutable
  reply suggestions. Suggestions remain drafts; meeting intent remains intent.
- Alembic `20260926_0011`, forced PostgreSQL RLS/composite tenant references,
  immutable SQL evidence, preserved Phase 6 audit/outbox and legacy quarantine.

Focused inbox + populated migration + PostgreSQL suite: **32 passed**. Full
backend regression: **152 passed** (186.05 seconds), including PostgreSQL 16
migration/RLS, tenant foreign keys, concurrent ingestion/claims and restart probes.
Frontend source and consumed contracts are unchanged; the existing CI frontend
TypeScript, lint and build checks still run.
CI is verified on the pushed checkpoint SHA before final delivery; its exact run
and result accompany that commit. Phase 7 is not accepted if those jobs fail.

No real provider send, calendar creation, CRM/pipeline mutation, paid API, OpenAI
key, production change, deployment or merge occurred. Live inbound adapters remain
disabled; the only ingestion endpoint is authenticated fake-mailbox simulation.
Inbox holds have no automatic resume policy. See `docs/V2_INBOX.md` for API,
classification limitations, provider authentication gate and restart/recovery.

## Phase 8 checkpoint

**PHASE 8 implementation complete and locally validated.** Implements
**Pipeline + CRM + Calendar only** from the already-verified
Phase 7 checkpoint `55a0c8c58e2c95b4dce66203e3cb590b446e21a9`. Phases 1–7 were
reused; no repeated implementation or dependency reinstall was performed.

- Durable account/prospect pipeline and immutable stage history, supported research,
  confirmed outbound, human reply/interest and confirmed calendar projections.
  Explicit user/CRM evidence is required for opportunity/won/lost. Manual
  corrections use reviewed evidence, reasons and optimistic revisions.
- CRM mappings, reused external IDs, immutable reviewed requests, sync state,
  successful-sync time, safe errors, remote snapshots/versions, deduplicated
  receipts and cursor review. Conflicts never cause blind overwrites.
- Persisted calendar reservations with inbound intent, attendees, IANA timezone,
  UTC interval and preselected provider event ID. Overlaps/duplicates and changed
  intent/suppression block dispatch; confirmed receipts alone create meeting state.
- Existing Phase 5 plans/commands/outbox/worker handle both action types, including
  durable intent, leases, admission, bounded retries, stale acknowledgements and
  lookup-before-retry reconciliation. Phase 2 OAuth refresh persists token rotation.
- HubSpot company/contact/deal and Google Calendar request adapters use an injected
  deterministic transport in tests. Default live mutations remain disabled;
  Salesforce writes explicitly reject unsupported behavior. A real transport must
  prove durable identity and atomic conflict handling at a separate staging gate.
- Alembic `20260926_0012` adds six tables with forced PostgreSQL RLS, scoped foreign
  keys, immutable evidence/identity protection and discovered-only owned-data
  backfill. Legacy NULL ownership and prior inbox/outreach history remain intact.
- Command-center contracts display exact outcome payloads for review and distinguish
  CRM/calendar operations and provider-confirmed outputs. Retained pipeline history
  blocks customer-record deletion/reparenting instead of erasing its evidence.

Focused Phase 8 + populated migration + PostgreSQL validation: **33 passed**.
Frontend TypeScript, targeted ESLint and production build passed. The single
broader regression run passed **184 tests** in 320.34 seconds, including PostgreSQL.
After the final dispatch-time safeguard, **32 focused Phase 8 tests passed**
in 47.71 seconds; the broader suite was not repeated. CI is verified on the pushed
checkpoint before final delivery; its exact run/result accompanies that SHA.
Phase 8 is not accepted if any relevant CI job fails.

No real CRM write, calendar event, external email, production mutation, paid API,
OpenAI key, Render deployment or main/PR merge occurred. Live transport/staging
capability validation remains separate from this offline development checkpoint.
See `docs/V2_OUTCOMES.md` for API contracts, stage semantics, recovery and limits.

## Phase 9 — Insights + GTM Gap Intelligence (complete)

Added a read-only `/api/v1/insights` API and versioned canonical event projection.
Reports include contact/account cohort funnels, actual stage entries and corrected
current-stage counts, confirmed-send/delivery/reply/positive-reply performance,
confirmed meeting conversion, research coverage and confirmed CRM sync coverage.
Campaign, immutable sequence version, message, exact CTA, pinned ICP segment,
evidence-linked recipient-title persona and why-now statement breakdowns retain
source IDs and historical dimensions. Unsupported industry/company-size/message
angle dimensions remain unknown; actual costs and revenue remain insufficient_data.

Descriptive gap rules include exact cohort/member evidence, numerator/denominator,
sample size, UTC half-open range, confidence, limitations, review thresholds,
version, as-of time, expected outcome, unknown cost, risk and required approval.
Reports include their full normalized evidence manifest and deterministic hashes.
Fewer than 20 observations or incomplete reply classification prevents a low-reply
recommendation. Zero denominators return null. Retries/receipts do not inflate
business outcomes; pipeline corrections preserve historical entries without
misreporting current state. No prediction, causal/revenue guarantee or automatic
execution is introduced. Existing Phase 5 approval/action-command/outbox machinery
is unchanged. All active roles can read only their own workspace's evidence.

No schema change was required; normalized events are derived from existing
canonical tables, not a second event log. Alembic head remains `20260926_0012`.
Existing RLS, composite tenant relationships and legacy quarantine are preserved.
No frontend files changed; Phase 10 remains separate. Synchronous reporting has an
explicit 20,000-row per-source limit and fails without partial results above it.
See `docs/V2_INSIGHTS.md` for exact semantics, evidence lineage and limitations.

Validation:
- Single broader backend regression with PostgreSQL: **204 passed**, 477.05 seconds.
- Final focused Phase 9 suite after the incomplete-classification safeguard:
  **20 passed**, 30.98 seconds. The broader suite was not repeated.
- Focused PostgreSQL migrated-database/security test: **1 passed**, 36.94 seconds,
  including analytics under a non-bypass role and a deliberate ORM/RLS context
  mismatch. The broader run also passed the PostgreSQL test.
- No frontend contract consumer/component changed. Existing GitHub CI runs frontend
  TypeScript, targeted lint and production build on the pushed checkpoint; exact
  CI status/run is reported with the final commit. No dependency reinstall locally.
- No real CRM/calendar/email action, production mutation, paid API, deployment or
  merge occurred. PR #2 remains draft/open; Phase 10 has not started.

## Remaining phases

10. Customer navigation and command-center readiness/plans/execution/approvals/outcomes.
11. Full security/retry/approval/provider/frontend/E2E suite, logging/metrics/rate limits,
    staging smoke test and deployment readiness documentation.

Do not claim readiness until the entire 21-step acceptance scenario passes.

## Continuation

Phase 10 — SaaS Frontend Cutover is complete. Existing work in progress was
preserved and extended on the same branch. Customer navigation, eight workspace
views, original GAPS AI styling, responsive navigation, review boundaries,
workspace switching, evidence and truthful outcome states are implemented.
See `docs/V2_CUSTOMER_EXPERIENCE.md` for scope, validation and limitations.

Validation: TypeScript passed; production build passed; correctness lint has zero
errors and four non-blocking Fast Refresh warnings; frontend contract tests 4/4;
focused backend/API tests 35/35; full backend regression including local PostgreSQL
migration/RLS tests 205/205. No schema change: head remains `20260926_0012`.
The interrupted broad test run was restarted because its process/result was lost;
the completed run is recorded in `.venv/phase10-regression.log` (local artifact).

Exact next step: **Phase 11 — Production Hardening**, beginning at that heading
in `docs/V2_SPECIFICATION.md`. Reuse existing tenant, approval, idempotency,
reconciliation and migration tests; add missing operational hardening and the
21-step fake-provider acceptance test. Review request/workspace/goal/run/step
correlation, safe errors/redaction, auth abuse limits, database readiness and
workspace-scoped operational metrics. Validate research privacy/robots/retention
and document deployment gates without deploying. No production readiness claim
until all actual release gates are verified. Phase 11 is explicitly authorized
by the latest user instruction; continue after Phase 10 checkpoint CI is green.

Preserve this Phase 10 requirement exactly:

“Build the GAPS AI customer frontend with a premium, Apple-inspired SaaS experience: smooth 60fps transitions, restrained motion, clean typography, generous spacing, subtle depth, polished hover/focus states, skeleton loading, responsive layouts, and no heavy visual clutter. Do not copy Apple’s UI directly; create an original GAPS AI design system with the same level of refinement.”

Keep approvals, workspace isolation/RBAC, suppression, immutable versions and
quarantine intact. No real side effects, paid services, deployment, production
changes or merge are implied. Phase 11 is now authorized; deployment and merging are not.
