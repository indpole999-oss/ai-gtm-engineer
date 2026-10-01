# Phase 11 production-readiness gate

## Current hosted staging checkpoint — 2026-10-01

The existing Free staging API and frontend are now deployed on Render. This
supersedes earlier statements that these services did not exist; it does not
close the production release gates. Current URLs and validation backlog are in
V2_EARLY_ACCESS_BACKLOG.md. Authenticated browser/live-model evidence is pending.

The staging API may explicitly set `EMBEDDED_EXECUTION_WORKER=true` after this
checkpoint. Default is false; tests never start it. This flag is independent of
APP_ENV, so hosted deployments can retain production-strength validation. The
supervisor restarts after failures with a five-second delay and safe logs.
Free-service suspension also suspends execution: this is attended staging,
not an independently available production worker or availability guarantee.

Groq planning/research use GROQ_API_KEY (legacy GROQ-API-KEY accepted), optional
GROQ_MODEL (default openai/gpt-oss-120b) and existing GROQ_BASE_URL override.
Store keys only in the staging service secret environment. Confirm Free-tier
limits before live calls. No live call was made by this repair checkpoint.
Schema compatibility is tested with synthetic HTTP, not provider acceptance.
User chose to keep hosted AI paused. Leave GTM_HOSTED_AI_ENABLED=false (default)
and EMBEDDED_EXECUTION_WORKER=false on staging until execution is authorized.
Both hosted adapters reject before opening HTTP when paused; no local fallback
silently replaces a paused configured provider. Future opt-in requires confirmed
free-only usage, synthetic inputs and explicit execution authorization.
Reference: https://console.groq.com/docs/structured-outputs

Robots wildcard and end-anchor rules are now supported conservatively using
bounded literal matching. Crawl-delay/request-rate policies still fail closed.
Retention durations for customer evidence, inbox content, audit records and
backups remain explicit, unapproved release decisions; no purge policy is set.

Status: **NOT READY FOR PRODUCTION DEPLOYMENT**. This is an operational-hardening
checkpoint, not authorization to deploy. Phases 1–10 remain completed history.

## Implemented and testable without external side effects

- `/api/v1/health` is liveness. `/api/v1/ready` checks database connectivity and
  exact Alembic revision `20260928_0013` with a three-second deadline; failures
  return a generic 503. A test detects future migration-head drift.
- Authentication admission uses atomic database counters and database time across
  API replicas: 30 requests/peer and 300 global per fixed minute, shared by login
  and registration. It returns Retry-After and fails closed (503) on store failure.
  It HMAC-hashes the ASGI peer with the signing secret, never stores raw IPs, and
  ignores arbitrary forwarded headers. All replicas must use identical limits and
  signing secrets. Fixed windows can admit up to twice the limit across a boundary;
  edge request-size/connection/DDoS controls and trusted proxy configuration still
  require staging verification. Memory admission is rejected in production.
  Counter cleanup retains current/previous protocol windows only; these are
  ephemeral abuse counters, not customer evidence retention policy.
- Unexpected API exceptions return a generic error with a request ID. Access
  logs use route templates rather than arbitrary URL paths. Never log request
  bodies, authorization headers, provider responses or OAuth query strings.
  Raw Uvicorn/Gunicorn access logging is disabled by application logging setup;
  HTTP client loggers are restricted to WARNING. The ingress must independently
  omit query strings and sensitive headers; verify this with the staging OAuth test.
- Worker attempts log workspace, goal, run, step and command IDs, action, duration
  and processing outcome. `result_processed` is not proof of provider success;
  canonical command state and provider receipts remain authoritative.
- Owner/admin-only `/api/v1/operations` reports tenant-scoped plan, cycle, command
  and outbox states, stale command/outbox leases, oldest queued/approval ages and
  alerts for expired leases, failed execution and queue age above five minutes.
  The five-minute queue threshold is an operational alert, not data retention.
  Cost is explicitly
  unavailable, never zero or an invented estimate. Counts are an operational
  snapshot, not a billing ledger or alert-delivery service.
- The continuous API journey test reuses one workspace and evidence chain through
  research, separately approved outreach, reply classification, approved calendar
  and CRM actions, measurement, advisory gaps and a next approved research cycle.
  It covers both the explicit research template and an injected fake planner,
  evidence-backed fixture buying signals, and duplicated fake delivery receipts.
  It asserts that provider acceptance alone does not fabricate delivery. It does not test
  real OAuth consent, live AI quality, browser interaction or real delivery.
- Frontend lockfile updates only transitive js-yaml 4.3.1 to 4.3.2 in response to
  npm advisory GHSA-2883-xcg3-v3hh. No application dependency redesign.
- Production settings reject memory admission, non-HTTPS/public frontend and CORS
  URLs, CORS paths, unsupported JWT algorithms and incomplete configured OAuth.
  Passwords are bounded by bcrypt UTF-8 limits; validation errors never echo input.
- Public evidence retrieval checks bounded, DNS-pinned robots.txt before sources;
  unavailable/redirected policies fail closed, 404/410 means absent policy.
  Matching denies override allows conservatively across groups. Wildcard/end-anchor
  rules use bounded literal matching; crawl-delay/rate policies fail closed.
  X-Robots-Tag and HTML meta noarchive/noai/none prevent evidence storage.
- Owner/admin `/api/v1/retention` reports counts and explicitly unset durations.
  There is no purge endpoint or timer. Referenced deletes return safe 409 and
  preserve data. See V2_STAGING_VALIDATION.md for policy approval decisions.

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
5. Verify edge connection/body limits, trusted proxy IP handling, alert routing,
   worker availability monitoring, provider latency/failure aggregation and
   authoritative usage/cost ingestion. Worker attempt duration is not provider latency.
6. Approve and implement a retention/deletion policy spanning immutable evidence,
   audit, contact/inbox data, provider copies, backups and logs. Existing retained
   evidence deliberately blocks some deletes; no automated purge is asserted.
7. Public HTTPS retrieval restricts private addresses, redirects and payload
   size and enforces conservative robots/storage policies. Source permission review remains a release gate.
   Record data purpose, provenance, access policy, notice/consent decisions,
   suppression retention and a rights-request process with the responsible privacy
   and legal reviewers. This document is not a legal-compliance certification.
8. Validate backup restoration and populated production-like PostgreSQL upgrades
   under separate migration/runtime roles. CI disposable databases are not a
   substitute for restoration evidence or production configuration review.
   A dedicated synthetic pg_dump/pg_restore CI rehearsal now covers populated
   0012 restoration followed by additive 0013 upgrade, repeated upgrade and
   runtime-role tenant isolation. It does not prove encrypted backup/key custody,
   full evidence-chain recovery, least-privilege migration ownership or scale.
   See the ordered operator rehearsal in V2_STAGING_VALIDATION.md.

## Required configuration and integrations

- `APP_ENV=production`, `DEBUG=false`, `AUTO_CREATE_TABLES=false`,
  `ALLOW_LEGACY_ENV_CREDENTIALS=false`.
- `AUTH_ADMISSION_STORE=database`, consistent `AUTH_PEER_LIMIT` (default 30) and
  `AUTH_GLOBAL_LIMIT` (default 300) on every API replica. Keep the counter table
  service-only; no client SQL grants. Migration 0013 revokes PUBLIC privileges.
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

The exact isolated staging prerequisites, acceptance matrix, and unapproved
retention release decisions are in `docs/V2_STAGING_VALIDATION.md`. No live gate
is waived by an offline test or a green CI run.
