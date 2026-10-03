# Phase 7 — AI Inbox

Phase 7 adds persisted inbound conversations to the Phase 6 Outreach Engine. It
uses deterministic rules and draft-only templates; no model key or external
provider is required. No calendar, CRM, pipeline, or outbound reply action runs.

## Ingestion and association

`POST /api/v1/inbox/simulated-events/{sender_id}` is an authenticated owner/admin
simulation endpoint and accepts only an explicitly fake mailbox. There is no live
or unauthenticated webhook endpoint. A future real adapter must authenticate the
provider, resolve its workspace/mailbox from server-owned configuration, and call
`inbox_service.ingest` with that bound session. Never trust a payload workspace ID.

The strict input contract stores provider event/message/thread identifiers,
In-Reply-To, normalized sender/recipient, subject/body, Auto-Submitted and receipt
time. Recipient must match the authenticated mailbox. Provider IDs are scoped to
the mailbox; conflicting reuse returns 409. A repeated event returns its original
message; another event for the same message adds a receipt without repeating
classification, pause, suppression, or business audit effects.

Association requires a confirmed outbound provider message ID, a prior inbound
message's explicit stored linkage, or an unambiguous previously linked provider
thread. The sender must match the original immutable recipient. No email-only
contact lookup or inferred buyer is used. Ambiguous, unknown, and mismatched
messages remain reviewable with no invented outreach relationships. Replies to
stored inbound messages can reconstruct a thread without a provider thread ID.
Pinned contact/company, campaign/sequence/version, enrollment, Brain version,
research and prior outbound references are retained. Audit events retain the
original execution cycle where one exists.

## Persistence and worker behavior

Alembic revision `20260926_0011` adds inbox_threads, inbound_messages,
inbound_receipts, inbox_thread_links, reply_classifications, inbox_pauses and
suggested_reply_drafts. Evidence and decisions are append-only in ORM and SQL;
all seven tables use composite workspace foreign keys and forced PostgreSQL RLS.
The migration preserves existing execution events/outbox, outbound approvals,
sequence history and unowned legacy quarantine. Downgrade deliberately refuses
to erase evidence; recover from a verified backup instead.

The existing transactional domain-event/outbox architecture records ingestion and
its safety effects in one commit before acknowledgement. Events without an
outreach origin can have no execution cycle. Existing outbox rows gain additive
attempt/due/lease/error fields; only inbound_received events enter this consumer.
The existing `python -m backend.execution_worker` loop consumes inbox work and
approved action commands under the same workspace admission limits. There is no
second scheduler or worker entry point. Classification plus acknowledgement is
atomic; leases, stale-token checks, three-attempt bounded retry/backoff, and an
administrator retry endpoint support recovery. Receipt and safety state survive
a failed classifier. Restart the existing worker to reclaim expired work.

## Classification and safety

`inbox-rules-v1` records category, confidence when applicable, reason/evidence,
version, recommendation and review state. Nine outcomes are supported: positive,
negative, objection, out_of_office, wrong_person, question, meeting_intent,
unsubscribe and other. Quoted messages/footers are excluded from authored text.
Explicit opt-outs and common automatic absence signals precede engagement rules.
Conflicting or insufficient signals become other with no confidence claim.
Rule confidence is a heuristic, not a calibrated probability. Language variants
outside the rules require administrator review; there is no claim of general
semantic understanding.

A linked human reply immediately records an immutable enrollment hold and pauses
future steps, before deferred classification. OOO records a distinct hold/reason
and no positive intent or guessed return date. Auto-generated diagnostics do not
imply a human reply. Explicit opt-outs immediately enter Phase 6's suppression
system, even when no contact/outbound association is possible. Duplicate receipts
do not repeat these effects. Manual classification overrides append history and
never remove a suppression or release a hold.

Outreach scheduling, approval context, enrollment activation and dispatch all
respect persistent inbox holds. Dispatch and ingestion share the workspace lock,
including fresh checks after the persisted send-intent commit. Already-approved
and already-claimed follow-ups cannot cross that boundary after a committed reply
or suppression. A provider send already in progress before receipt commits
cannot be retroactively recalled. Completed outbound history stays immutable.
Phase 7 provides no resume policy that could silently restart these sequences.

## Customer APIs and recovery

All paths are under `/api/v1/inbox` and require active workspace membership:

- GET `/threads` and `/threads/{id}`: paginated conversations and stored messages.
- GET `/messages/{id}`: classifications/history, recommendation, processing status,
  suppression and sequence-hold state.
- POST `/messages/{id}/override`: owner/admin review with expected classification
  number, category, reason and explicit reviewed acknowledgement.
- POST `/messages/{id}/suggested-reply`: member/admin/owner, deterministic draft;
  GET `/drafts/{id}`: stored draft with source/classification/context linkage.
- POST `/messages/{id}/retry-classification`: owner/admin retry of failed outbox
  processing, audited and bounded again. It does not release sequence holds.

Suggestions are immutable drafts tied to the inbound message, thread and exact
classification; prior outreach evidence/Brain context is retained when available.
Suppressed recipients and negative, unsubscribe, wrong-person or OOO outcomes do
not receive suggested replies. Meeting intent only suggests reviewing availability;
it creates no meeting or CRM record. There is no draft-send endpoint in this phase.
An eventual send must use Phase 6's reviewed, approved durable outbound safeguards.

For conflicts, review original provider identifiers and the stored payload; do not
invent a new event ID to bypass identity checks. For failed classification, inspect
the status and append an explicit manual review or retry the existing outbox item.
No raw message contents or provider secrets are copied into failure messages.

## Validation boundary

Deterministic fake providers use a separate durable SQLite acceptance ledger with
explicitly closed connections. Tests cover nine classifications, ambiguous cases,
thread linkage, duplicate/conflicting events, manual overrides, RBAC/isolation,
queued and claimed follow-up blocking, the send-intent commit gap, stale leases,
rollback/retry/restart, draft-only behavior and absence of calendar/CRM mutations.
Disposable PostgreSQL probes cover concurrent ingestion/claiming, forced RLS,
composite tenant references and SQL immutability. Populated Phase 6 migration tests
preserve audit/outbox and legacy quarantine. Live authenticated provider adapters
and staging smoke tests remain a separately authorized future integration gate.
