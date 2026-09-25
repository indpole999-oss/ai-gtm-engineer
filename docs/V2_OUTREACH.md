# Phase 6 — Outreach engine

Outreach extends the Phase 5 action-command worker, approval envelope, execution
cycles, workflow/step runs, admission control, leases, retries and transactional
domain-event/outbox architecture. No HTTP request sends a message. Run the same
`python -m backend.execution_worker` worker after applying Alembic migrations.

## Persisted lifecycle

1. Create a campaign and sequence through `/api/v1/outreach`.
2. Create a sequence version with ordered steps and delays. Definitions and steps
   are immutable. New versions never change existing enrollments.
3. Register a workspace sender identity and enroll a contact against an exact
   sequence version and completed research job for that contact's company.
   Enrollment creates immutable scheduled-message records. Repeated enrollment
   requests reuse the existing enrollment when the inputs match.
4. Compose a draft through `POST /scheduled/{id}/drafts`. This is an explicitly
   labelled deterministic evidence template, not a claim of AI generation.
   It quotes an evidenced provider assertion, uses a published Brain's approved
   claim, retains account/buyer reasoning, rejects reviewed-rejected and prohibited
   claims, and includes opt-out instructions. Composition never approves or sends.
5. An owner/admin reviews the exact draft hash using
   `POST /drafts/{id}/approve`. This creates an immutable message approval and a
   separate draft execution plan. Repeating this request returns the same message;
   a competing draft for the same scheduled step is rejected.
6. Separately approve that plan through the existing GTM plan approval endpoint.
   Its immutable document pins the message ID and Brain version/hash. Approval
   atomically creates the existing execution cycle, workflow, command and outbox.
7. The worker waits for the due time and prior accepted sequence steps plus their
   delay. Paused campaigns/enrollments are not claimed. Sending rechecks both
   approvals, active workspace memberships, sequence integrity, recipient address,
   sender state and suppressions. Recipient limit: one attempted message per
   rolling 24 hours. Sender limit: default 20, administrator configurable up to 100.
8. Persist dispatch intent before calling the adapter. Only explicit provider
   acceptance with a nonempty provider message ID can set `sent`. This means
   accepted, not delivered. Delivery, bounce, complaint and unsubscribe are
   separate immutable, deduplicated delivery events.

Draft envelopes retain contact/company, research job, evidence/claim, account
intelligence and buyer reasoning, Brain version/hash, campaign, sequence version
and step, sender, due time and composition method. Message → plan → execution cycle
provides execution traceability. SQL composite foreign keys and forced PostgreSQL
RLS protect all outreach tables. ORM and SQL triggers protect snapshots, approvals
and provider acceptance. Viewer access is read-only; message/sender administration
requires owner/admin. Suppressions are normalized per workspace and cannot be
deleted through the customer API.

## Provider boundary and recovery

No live provider adapter is enabled by this checkpoint. `delivery_provider`
defaults to a disabled adapter; registering an identity cannot enable external
sending. Fake identities are explicitly labelled `fake`. Tests inject an adapter
with a separate SQLite provider ledger; they make no network outreach calls.

An adapter must explicitly support durable idempotency and implement:

- `lookup(workspace_id:message_id)`: an accepted receipt, or `None` only when
  authoritatively absent. An unknown/unavailable lookup must raise.
- `send(the_same_key, immutable_envelope)`: atomically deduplicate the stable key
  across concurrent calls, restarts and all retries, and return an accepted
  receipt only after provider confirmation. An SMTP or mailbox wrapper without
  this guarantee must remain disabled.

The key never changes when a lease expires or an administrator requests retry.
An uncertain send becomes `reconciling`; a lost acknowledgement is recovered by
lookup before any resubmission. The worker uses its existing bounded retry/backoff
policy. After terminal failure, an owner/admin can explicitly request
`POST /messages/{id}/retry`, which requeues the same approved message/command and
emits an audit/outbox event. Approval, suppression and limits are checked again.
Unknown outcomes remain unknown when lookup is unavailable; they never become
`sent` based on local intent or successful queuing.

Workspace locking serializes dispatch, quota reservations and suppressions. A
suppression acknowledged before dispatch prevents sending. A request already
accepted by a provider cannot be recalled; subsequent delivery events preserve
that history and block future outreach. The trusted `record_delivery_event`
service validates the provider-message reference, deduplicates event IDs, and
adds suppression on bounce/complaint/unsubscribe. There is deliberately no public
unauthenticated webhook endpoint. Phase 7 will add authenticated inbound handling.

## Migration and boundary

Alembic revision `20260926_0010` is additive from `20260923_0009`. It does not
backfill or alter production records, and downgrade refuses to erase approvals
or delivery history. Existing populated execution cycles and steps survive.

The frontend command center recognizes outbound plans and provider acceptance,
without presenting them as read-only research. Full customer outreach navigation
is part of Phase 10. Real provider rollout requires a separately validated,
idempotent adapter and staging authorization. No paid APIs, API keys, external
messages, deployments, production changes, main merge or Phase 7 implementation
are included in this checkpoint.
