# AI GTM Engineer V2 implementation progress

## Authority and starting point

Implement Phases 1–11 sequentially, continuing after validated checkpoints.
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
Initial full suite: 79 passed, 1 PostgreSQL-only skip. Final role/PG checks pending.
No paid calls; development uses injected deterministic providers. Existing OpenAI
configuration is preserved. See `docs/V2_RESEARCH.md` for boundaries and risks.

Migration head under test: `20260923_0007`.
Production adoption, quarantine remediation and recovery: `docs/V2_MIGRATIONS.md`.

## Remaining phases

4. Finish research validation/CI and checkpoint.
5. Goals, schema-validated planner, immutable plan approval, durable resumable worker,
   outbox, retries/timeouts/cancellation/budgets/idempotent approved commands.
6. Draft-only composition, sequences/enrollments, immutable outbound approval,
   suppression/recipient/sender limits, provider-confirmed asynchronous delivery.
7. Inbound threads, reply classification/reasoning, sequence pause, proposed responses.
8. Outcome pipeline, idempotent CRM sync and calendar booking/reconciliation.
9. Normalized outcome metrics and evidence-backed descriptive gap recommendations.
10. Customer navigation and command-center readiness/plans/execution/approvals/outcomes.
11. Full security/retry/approval/provider/frontend/E2E suite, logging/metrics/rate limits,
    staging smoke test and deployment readiness documentation.

Do not claim readiness until the entire 21-step acceptance scenario passes.

## Continuation

Continue this branch from its latest checkpoint. Read this file, the specification
and migration runbook; use existing implementation and tests rather than repeating
the repository audit. Finish the current validation gate, then continue phases
sequentially. Never deploy or merge without separate authorization.
