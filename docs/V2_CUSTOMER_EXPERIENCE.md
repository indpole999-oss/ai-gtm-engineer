# Phase 10 customer experience

The default customer workspace contains AI GTM, Prospects, Outreach, Inbox,
Pipeline, Insights, Integrations and Settings. The original GAPS AI system uses
restrained teal accents, system typography, generous spacing, subtle depth and
short opacity/transform transitions. Reduced-motion preferences disable motion.
60fps is a performance target, not a measured guarantee.

## Boundaries

- Explicit workspace selection scopes requests. Switching cancels queries,
  clears cached customer data and remounts page state. The backend remains the
  authority for tenant isolation and permissions.
- Viewers cannot edit; members prepare work; owners/admins approve. Unknown roles
  fail closed. Normal customers cannot render internal routes even by direct URL.
  `VITE_OPERATOR_UI=true` is an explicit operator-build opt-in, also requiring an
  owner/admin role; it does not grant backend permissions.
- Published Brain versions, research evidence, buyer verification, immutable
  sequence versions and message content are visible during review. Manual contact
  entry does not establish independent verification.
- Message approval and plan approval remain separate. A queued action is not a
  confirmed send. A sent label requires provider identity and acceptance evidence.
  Suppression blocks outreach; inbound classification does not silently send.
- Calendar/CRM views display persisted outcomes and history. Reviewed business
  stage corrections preserve original history and do not establish revenue.
- Analytics show date/cohort/sample/evidence/limitations and insufficient data.
  Recommendations have no execution control. Missing costs/revenue remain unknown.
- Read-only data queries retry a transient network/server failure once; mutations
  are never automatically retried by the customer frontend.

## Validation

- TypeScript `--noEmit`, production Vite/Nitro build: passed.
- Correctness ESLint across customer components, shell, API/workspace code,
  authentication/public routes and authenticated routes: no errors. Four existing
  mixed component/hook-export Fast Refresh warnings remain non-blocking.
- `node --test tests/customer.test.mjs`: 4 tests passed (send confirmation,
  approval roles, insufficient metrics, workspace request/reset/error behavior).
- Focused workspace-security and Insights API tests: 35 passed.
- Full backend regression with disposable PostgreSQL: 205 passed, including
  migrations, RLS, role boundaries, retries, suppression and provider reconciliation.
- Browser review used `tests/preview_customer.py`: a temporary Alembic database,
  local fixture identities and deterministic fake research/mail/CRM/calendar.
  Reviewed login, all eight routes, Brain version fields, research/buyer evidence,
  draft review gating, explicit plan approval, reply classification, confirmed
  meeting state, analytics limitations, integration health, viewer restrictions,
  workspace cache clearing, direct internal-route denial and mobile navigation.

## Known scope limits

Live writes remain disabled by existing provider adapters. Collection caps and
available pagination are disclosed; no synthetic contacts, outcomes or metrics
are substituted for absent evidence. Inbox list labels use conversation numbers
because the canonical list contract has no summary. CRM/calendar preparation APIs
remain available through the existing approved execution architecture; this phase
adds their customer state/history views without redesigning the backend.

Local checks do not certify a live provider connection, deployment environment,
production backup recovery, or universal accessibility/performance conformance.
Those remain explicit Phase 11/release checks. No deployment occurred.
