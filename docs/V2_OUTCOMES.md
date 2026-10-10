# Phase 8 — Pipeline, CRM and Calendar

Phase 8 adds six tenant-owned tables at Alembic revision `20260926_0012`:
`pipeline_records`, `pipeline_history`, `crm_mappings`, `outcome_actions`,
`calendar_bookings` and `crm_receipts`. It extends Phase 5 plan steps and the
existing action-command worker with `crm_sync` and `calendar_schedule`. There is
no second execution queue, scheduler or workflow system.

## Pipeline evidence

Accounts and contacts receive a discovered record and history atomically when
persisted. Migration backfills discovered records only for existing explicitly
owned accounts/contacts; it never adopts quarantined data or infers past outcomes.
A contact remains associated with its original account in retained history.
Deletion/reparenting that would invalidate this history returns 409; administrator
RBAC does not grant permission to erase audit evidence.

Stages are discovered, qualified, contacted, engaged, interested, meeting,
opportunity, won and lost. Every evaluated transition retains timestamp, source,
reason, evidence, actor when applicable, prior stage and whether it applied.
Campaign/sequence-version and original cycle links accompany outreach/inbound
history; CRM/calendar actions retain their own approved execution cycles.

- Qualified derives only from completed, evidence-backed Phase 4 potential-fit
  research. History explicitly records that this is ICP potential-fit qualification,
  not independently verified buyer interest or a promised business outcome.
- Contacted requires a persisted provider-confirmed outbound send.
- Engaged requires a deterministically linked human reply; auto-generated and OOO
  replies do not imply engagement. Positive/meeting-intent classification supports
  interested, and retains its exact classification/evidence ID.
- Meeting requires a confirmed calendar provider receipt. Classification alone
  never books a meeting or promotes the record to meeting.
- Opportunity/won/lost require explicit reviewed user data or reviewed CRM
  opportunity evidence; there is no automatic inference of those outcomes.

Automatic events never overwrite terminal/explicit opportunity outcomes or demote
stages. Source identities prevent replay from undoing a later correction. Manual
corrections use an expected revision and a reason. Evidence-backed stages still
require matching persisted evidence; an administrator cannot fabricate a send or
meeting by changing a dropdown. Classification overrides preserve earlier stage
history; use a reviewed pipeline correction to change the current stage.

## Approved provider operation lifecycle

Owner/admin request creation produces an immutable outcome payload and an unapproved
Phase 5 plan. It does not call a provider. The command center displays the exact
saved payload before approval. The plan pins its hash, published Brain and target.
Existing plan approval, active-approver checks, cancellation, leases, admission
limits, timeout, bounded retries and persisted step-output validation still apply.

The outcome UUID is the stable provider operation key. The CRM mapping UUID is the
stable remote creation identity; Google event IDs are generated before dispatch
from the outcome UUID. Request-key reuse with a changed payload returns 409.
A different request cannot bypass an unresolved mapping operation or an overlapping
calendar reservation. Confirmation requires a matching provider request hash,
nonempty object/event ID, version and confirmed status, persisted before the step
can succeed. No optimistic success is reported.

The worker first reconciles the stable operation key. Before a new write, it
persists send intent, then reacquires the workspace/cycle/command/integration locks
and rechecks approval, lease, account binding, current local data, mapping revision,
intent and suppression as appropriate. Local company/contact rows stay locked
through dispatch. Remote writes require atomic expected-version enforcement, not
an unsafe read/check followed by an unconditional overwrite.

A lost response leaves the operation reconciling. A restart looks up the same
provider key before resubmission, and a stale lease cannot acknowledge a newer
worker's command. Administrator reconciliation requeues the original command and
key with a fresh bounded retry budget; it never performs provider writes in HTTP.
A definitive conflict/blocked operation needs corrected, newly reviewed input.
Confirmed outcomes and their receipts are immutable. Newer webhook observations
are retained rather than overwritten by an older acknowledgement.

## CRM mapping and conflict contract

HubSpot is the implemented request/response adapter path for companies, contacts
and deals, using the existing CRM Integration and its workspace credentials.
Company/contact data comes from the exact reviewed local snapshot. Deal sync
requires an explicit account opportunity/won/lost stage plus reviewed provider
pipeline/stage IDs; no provider stage identifiers are guessed. Salesforce uses the
same adapter boundary but rejects writes as unsupported.

Mappings persist provider, local pipeline/object identity, external ID, remote
version/snapshot, revision, sync state, successful-sync time, safe error code and
reviewed cursor. Existing mappings are reused. Legacy contact CRM IDs must be
explicitly reconciled with a reviewed remote revision before a new sync can be
created; they are never silently discarded in favor of a duplicate contact.

Trusted provider receipts are deduplicated by integration/event ID and content
hash. Remote changes become conflicts without mutating local business data or
writing back automatically. Administrator remote review accepts an identified
receipt as a conditional-write base. A stale accepted snapshot still fails the
provider's atomic version check. Explicit opportunity outcomes can update pipeline
history only through that reviewed path. Receipt cursors are synchronization
positions, never authentication tokens.

## Calendar policy

Scheduling requests require a linked prospect, current positive/meeting-intent
classification, unsuppressed attendees and healthy Google Calendar authorization.
Title, attendees, calendar ID, timezone, UTC start/end, source inbound/classification
and planned provider event ID persist before approval. Requests require explicit
UTC offsets compatible with the IANA timezone. Nonexistent local times, missing
zones/offsets, past starts and invalid durations are rejected. Explicit valid DST
fold offsets disambiguate repeated local times.

Overlapping reservations for any attendee are blocked within a workspace, including
requests on another integration/calendar. Reservations remain conservative even
if a request is cancelled or blocked; choose a different slot rather than delete
history or assume an uncertain remote event never existed. Calendar edit/cancel
provider actions and automatic reservation release are outside this phase.

Phase 2 Google token refresh is reused and persisted. Reconnection/account edits
invalidate an old approval; ordinary OAuth refresh/rotation does not. Lost calendar
acknowledgements reconcile to the preselected event ID and cannot create another
meeting. Suppression or changed intent before dispatch blocks creation. A lookup
may confirm a previously completed operation after intent changes, but it cannot
create a new event on that basis.

## API surface and access

All routes below are under `/api/v1/outcomes` and require active workspace membership.
Reads are available to members/viewers; writes require owner/admin review.

- GET `/pipeline`, `/pipeline/{id}`; POST `/pipeline/{id}/stage`.
- POST `/crm/sync`; GET `/crm/mappings`, `/crm/mappings/{id}`.
- POST `/crm/mappings/{id}/review-remote` with receipt and expected revision.
- POST `/calendar/schedule`; GET `/calendar/meetings`.
- GET `/actions`, `/actions/{id}`; POST `/actions/{id}/reconcile`.
- GET `/integration-health/{id}` returns the existing sanitized connection status.
- POST `/crm/simulated-events/{integration_id}` accepts only an injected simulated
  transport. There is no unauthenticated or live webhook endpoint. Real adapters
  must authenticate provider events before calling the trusted ingestion service.

Approval remains `/api/v1/gtm/plans/{id}/approve`. Worker entry point remains
`python -m backend.execution_worker`. Action detail returns its immutable request,
plan, provider state and booking details where applicable. No credentials are
returned. All new tables have forced PostgreSQL RLS, composite tenant foreign keys
and SQL/ORM history/identity protection.

## Provider and release boundary

Live writes are disabled by default and there is no API switch to enable them.
The HubSpot and Google adapters encode the reviewed requests behind a transport
contract. Tests inject a separate durable SQLite provider ledger with atomic
operation receipts, unique object identities and expected-version updates. No
network-backed mutation transport is enabled or claimed production-ready. A real
transport must prove authoritative lookup, durable create idempotency and atomic
conflict handling; especially do not substitute an unsafe HubSpot read-then-PATCH
implementation for that contract. Salesforce remains explicitly unsupported for
writes. Real provider staging and capability validation need separate authorization.

Tests require no paid APIs, real CRM/calendar credentials or OpenAI key. They cover
provider failure/lost response, ID reuse, conflict review, duplicate events/requests,
approval and cancellation, dispatch races, scope/tenant enforcement, token refresh,
timezones, restart recovery, migration preservation and PostgreSQL concurrency/RLS.
No real CRM write, calendar event, deployment, production mutation or merge occurs
as part of this phase. Phase 9 Insights work is not included.
