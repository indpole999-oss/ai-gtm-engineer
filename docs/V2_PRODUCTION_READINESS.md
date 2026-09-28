# Phase 11 production-readiness gate

Status: **NOT READY FOR PRODUCTION DEPLOYMENT**. This is an operational-hardening
checkpoint, not authorization to deploy. Phases 1–10 remain completed history.

## Implemented and testable without external side effects

- `/api/v1/health` is liveness. `/api/v1/ready` checks database connectivity and
  exact Alembic revision `20260926_0012` with a three-second deadline; failures
  return a generic 503. A test detects future migration-head drift.
- Authentication admission is bounded to 30 attempts per peer per 60 seconds,
  shared between login and registration, with bounded memory and Retry-After.
  It uses the ASGI peer, not an arbitrary forwarded header. This is per process:
  production requires independently verified shared edge limits and trusted proxy
  configuration; restarts and multiple replicas are not a global quota.
- Unexpected API exceptions return a generic error with a request ID. Access
  logs use route templates rather than arbitrary URL paths. Never log request
  bodies, authorization headers, provider responses or OAuth query strings.
- Worker attempts log workspace, goal, run, step and command IDs, action, duration
  and processing outcome. `result_processed` is not proof of provider success;
  canonical command state and provider receipts remain authoritative.
- Owner/admin-only `/api/v1/operations` reports tenant-scoped plan, cycle, command
  and outbox states, stale command leases and oldest queued age. Cost is explicitly
  unavailable, never zero or an invented estimate. Counts are an operational
  snapshot, not a billing ledger or alert-delivery service.
- The continuous API journey test reuses one workspace and evidence chain through
  research, separately approved outreach, reply classification, approved calendar
  and CRM actions, measurement, advisory gaps and a next approved research cycle.
  It uses deterministic fake transports and the explicit research template. It
  asserts that provider acceptance does not fabricate delivery. It does not test
  real OAuth consent, live AI quality, browser interaction or real delivery.
- Frontend lockfile updates only transitive js-yaml 4.3.1 to 4.3.2 in response to
  npm advisory GHSA-2883-xcg3-v3hh. No application dependency redesign.

## Release blockers and remaining validation

The initial Python audit reported ChromaDB, ecdsa, PyPDF2 and local pip advisories.
The V2 runtime no longer installs unused python-jose/ecdsa or ChromaDB. Repository
reference inspection found ChromaDB only in the standalone legacy MemoryAgent,
which is not imported by V2 API/workers. Its vector mode is excluded from this
release; do not re-enable it without a security-reviewed dependency and tenant
boundary. Its source was preserved. PDF preview now uses maintained pypdf with
text extraction and encrypted/malformed-file regression tests. Local pip tooling
was updated separately; this does not change the application requirements.

1. Live mail transport, authenticated inbound/delivery receipts, CRM atomic conflict
   handling and calendar provider identity/reconciliation require implementation
   and staging contract evidence. Existing defaults intentionally reject live
   writes. Fake provider success cannot satisfy these gates.
2. Demonstrate interactive OAuth consent, expiry, refresh rotation, revoke and
   reconnect using separately authorized staging identities and no production data.
3. Validate local-model planning and research against reviewed sources, including
   supported buying signals, qualification and buyer evidence. The offline fixture
   correctly leaves absent signals and buyer verification unknown.
4. Complete the primary journey through the actual customer UI in staging, including
   real delivery and inbound evidence, then a separately approved next cycle.
5. Verify shared edge abuse limits, trusted proxy IP handling, alert routing,
   worker availability monitoring, provider latency/failure aggregation and
   authoritative usage/cost ingestion. Worker attempt duration is not provider latency.
6. Approve and implement a retention/deletion policy spanning immutable evidence,
   audit, contact/inbox data, provider copies, backups and logs. Existing retained
   evidence deliberately blocks some deletes; no automated purge is asserted.
7. Public HTTPS retrieval already restricts private addresses, redirects and payload
   size. Robots-policy enforcement and source permission review remain release gates.
   Record data purpose, provenance, access policy, notice/consent decisions,
   suppression retention and a rights-request process with the responsible privacy
   and legal reviewers. This document is not a legal-compliance certification.
8. Validate backup restoration and populated production-like PostgreSQL upgrades
   under separate migration/runtime roles. CI disposable databases are not a
   substitute for restoration evidence or production configuration review.

## Required configuration and integrations

- `APP_ENV=production`, `DEBUG=false`, `AUTO_CREATE_TABLES=false`,
  `ALLOW_LEGACY_ENV_CREDENTIALS=false`.
- `DATABASE_URL`: PostgreSQL runtime role without superuser/BYPASSRLS. Supply a
  separate migration credential only to the release operation; follow V2_MIGRATIONS.md.
- `SECRET_KEY`: unique, non-default, at least 32 characters;
  `INTEGRATION_ENCRYPTION_KEY`: valid Fernet key with a reviewed backup/rotation plan.
- `CORS_ORIGINS`: explicit trusted HTTPS origins; `FRONTEND_URL` and frontend build
  `VITE_API_BASE_URL`: reviewed public HTTPS endpoints. No secrets in frontend values.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`: registered
  callback and reviewed consent/scopes for authorized staging then production.
- `GTM_LOCAL_MODEL_URL`, `GTM_LOCAL_MODEL`: operator-controlled reachable model
  service, with capacity and privacy review. No paid provider fallback is implied.
- Workspace-scoped provider credentials and scopes must be connected through the
  reviewed integration flow. Global legacy email/CRM keys do not enable safe V2 sends.
- `LOG_LEVEL`, protected log collection, retention and alert destinations must be
  reviewed. Run the durable worker separately with `python -m backend.execution_worker`.

## Deployment checklist (execute only after explicit authorization)

1. Close every release blocker and record evidence against the exact release SHA.
2. Require backend, PostgreSQL security and frontend CI green at that SHA.
3. Verify secrets, least-privilege roles, approved integrations and network controls.
4. Back up and restore-test in isolation; review the upgrade plan and rollback strategy.
5. Obtain explicit production deployment authorization. Do not merge implicitly.
6. During the authorized release, apply reviewed migrations, verify revision/readiness,
   start API and worker, validate monitoring and perform the approved smoke scenario.
7. Halt rollout on failed readiness, tenant checks, missing approvals or ambiguous
   provider outcomes. Reconcile authoritative receipts before retrying effects.
