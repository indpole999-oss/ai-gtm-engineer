# Goals, plan approvals and durable execution

The dashboard command center accepts a business goal, published Company Brain,
target account and source URLs. Local AI planning receives the pinned Brain,
integration health, workspace policy, budget, historical outcome counts and pipeline
counts. All output is schema validated. A separately labelled research template is
available only when explicitly selected; it never masquerades as AI generation.
Customers can create revised plan versions and regenerate. Approved versions cannot
be edited. Owners/admins approve the exact document hash with explicit review.

Plans persist objective, success metrics, segment, constraints, assumptions, risks,
ordered dependency graph, outputs, rationale, zero paid-cost estimate, side-effect
classification, approval requirement, stop conditions and review checkpoint.
Phase 5 introduced read-only research commands. Phase 6 adds separately reviewed
outreach commands through the same worker; see `docs/V2_OUTREACH.md`. Live outbound
providers, paid calls, calendar creation and CRM mutation remain disabled. Max 20 steps, three attempts and 120 seconds per attempt.

Approval atomically creates execution_cycles, step_runs and action_commands plus
domain_events/outbox_events. Run `python -m backend.execution_worker` separately
from the web process. No production service has been configured or deployed.
Each execution cycle has one persisted workflow_runs record, with step_runs linked
by a composite workspace foreign key. Step outputs are schema validated and must
reference the command's own completed research job. Admission is serialized per
workspace, with at most two active leases and ten claims per minute, including
retries. The approved envelope pins both Company Brain version ID and content hash.
The worker binds each workspace session, rechecks the active approving membership,
checks the plan hash and exact command payload, and atomically claims one lease.
Expired leases can be reclaimed; stale lease tokens cannot acknowledge newer work.
Attempt timeouts, persisted exponential backoff and hard attempt limits bound work.
Deterministic research job IDs make restart retries reuse completed research.

Pause prevents further claims; resume rechecks approval. Cancellation invalidates
queued/running command leases. An in-flight read can finish its capture, but cannot
acknowledge a cancelled command or trigger subsequent work. Loss of approver access
pauses the cycle. The public synchronous research-run route now rejects execution;
company detail instead proposes a plan for review. Worker execution never depends
on a web request staying alive.

Outbox entries are transactional pending internal events. They are not marked sent
or delivered and do not send customer messages. Later integrations must add an
idempotent consumer before using them for external notifications. Research output
still needs customer review and unverified contacts cannot silently become verified.

Migrations 20260923_0008 and 20260923_0009 are additive, with workspace foreign keys/indexes, forced
PostgreSQL RLS, and immutable plan/audit triggers. Test on an isolated restored
database, verify RLS and concurrent claims, then start a staging worker only after
authorization. Recovery preserves approved plans and audit; destructive downgrade
is disabled. Migration 0009 creates workflow records from existing cycles using
their exact IDs, timestamps and proven workspace ownership, then adds the step
foreign key. All database operations in development/CI use disposable data.

Production gates still include provider-side reconciliation/idempotency for future
external actions, mailbox rate limits, full end-to-end tests, observability and
staging model/provider smoke tests. These are required before deployment readiness.
