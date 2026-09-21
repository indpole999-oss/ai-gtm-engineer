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

Phase 1 security/migration validation in progress. Initial suite: 33 passed on
SQLite including populated baseline and clean migration. Additional quarantine
test and disposable PostgreSQL RLS CI job added; results pending.
Frontend TypeScript/build/targeted lint in progress. Do not call Phase 1 passed
until all required jobs finish successfully.

Migration head: `20260922_0004` (expand → backfill → validate/enforce).
Production adoption, quarantine remediation and recovery: `docs/V2_MIGRATIONS.md`.

## Remaining phases

2. Workspace provider contracts, OAuth state/PKCE durability, refresh/revoke/health,
   fake adapters and contract tests; replace blocked integration paths safely.
3. Guided onboarding, versioned Company Brain, source/claim model, immutable publish.
4. Retrieval/evidence/claims/signals/qualification/account intelligence and buyer verification.
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
