# Webhook/worker lock-order correction — 2026-10-11

Base: `21a46e3`, branch `codex/ai-gtm-engineer-v2-full-build`. No deployment,
provider activation, paid AI, real email/calendar action, CRM write or production
mutation was performed. Existing release-checklist edit and historical audit
report are excluded from the fix commit.

## Root cause and change

The old callback held Integration FOR UPDATE and then waited for Workspace;
dispatch held Workspace and then waited for Integration. PostgreSQL can abort
one transaction with SQLSTATE 40P01. Every locking integration lookup now takes
Workspace first and reloads current integration state under FOR UPDATE.
Outcome integration validation follows the same rule. OAuth completion takes
Workspace before Membership/Integration; execution completion and cycle control
take Workspace before Cycle/Command. Inbox ingestion, reconciliation, dispatch,
suppression, approval and outbox workers already use the workspace boundary.
Child order cannot form a cycle between these cooperating transactions while
one owns their common workspace lock. Reacquiring that workspace lock inside
one transaction does not release it or take a different child-first lock.

Callbacks verify the signature without row locks, then verify current connection,
workspace status and signature again under the lock. A credential rotation or
revocation during the wait cannot authorize the stale generation. Malformed
non-string signing secrets fail authentication rather than raising AttributeError.
No approval, lease, suppression, provider-identity or tenant check was removed.

Receipt reconciliation and delivery-event helpers retain their default standalone
commit behavior. The webhook requests flush-only behavior and commits acceptance,
RFC alias, pipeline evidence, receipt, audit and bounce/complaint suppression in
one transaction. Failed/conflicting callbacks roll back that transaction. Durable
outbound intent-before-dispatch behavior is unchanged. Receipt audit entries still
describe each verified callback attempt; duplicate facts and suppressions remain
deduplicated, but the audit is not claimed to deduplicate every HTTP attempt.

## PostgreSQL regression and limits

`test_postgres_mailbox_locks.py` creates a uniquely named disposable database only
when POSTGRES_TEST_URL is explicitly configured; it migrates to head, runs a child
probe, terminates only connections to that unique database and removes it.
It must never be pointed at staging or production. No provider calls occur.

The probe uses two real connections and barriers to require the former lock order
to produce 40P01. It then exercises the actual shared integration lock entry point
against a worker holding Workspace, observes PostgreSQL's waiting statement to
assert the callback is blocked on Workspace, permits worker completion, and checks
both callback commit and rollback cases. A second workspace can progress and
cannot read the first workspace's integration. These are lock-entry-point tests,
not a claim that every complete HTTP journey runs against PostgreSQL.

The existing PostgreSQL CI job now includes this regression alongside the RLS and
worker boundary suite. **Local PostgreSQL execution is BLOCKED:** no disposable
service is configured; no local postgres/pg_ctl/docker executable was found on
PATH. Concurrency, RLS and restore tests all skip with the explicit reason
“Disposable PostgreSQL service not configured.” Syntax checking is not PG PASS.
CI execution/result must be verified separately before claiming PG success.

## Verification

- Broad deterministic suite: **153 passed, 1 skipped, 7122 warnings in 234.01s**.
  Integration, OAuth, outreach, inbox, outcomes, draft review and populated SQLite
  migrations. This run began before the later completion/control/outcome edits;
  the final-source suite below verifies those changes.
- New authentication-before-lock and receipt-rollback/retry tests: **2 passed,
  1 PostgreSQL skip, 105 warnings in 9.11s**. The rollback test was subsequently
  strengthened to count persisted receipts and confirm only one mock dispatch;
  its final version is included in the final-source suite.
- Migration contract: **1 passed in 16.83s**. Requires a single 0015 head,
  verifies 0013 → 0014 → 0015 ordering, repeated no-op upgrade, preserved synthetic
  rows/FKs and explicit refusal of destructive 0014/0015 downgrade.
- Explicit PostgreSQL check: **3 skipped in 0.09s**, concurrency/RLS/restore each
  blocked by missing disposable POSTGRES_TEST_URL.
- Initial final-source run without a workspace basetemp: **59 passed, 27 setup
  errors in 98.23s**; all errors were Windows access denial on pytest's default
  temporary directory. It is rerun with a unique workspace-local basetemp.
- Final-source suite with workspace-local basetemp: **86 passed, 3834 warnings
  in 139.39s**. Covers planning execution/control, outcomes, integration boundaries
  and workspace security. No assertion failures or setup errors remain in this
  rerun. Strengthened receipt persistence test separately: **1 passed, 92 warnings
  in 3.04s**.
- `python -m alembic heads`: `20261009_0015 (head)`; Python compile and
  `git diff --check` pass. No frontend source changes; browser/hosted verification
  is not claimed by these backend tests.

## Security review and next audit

Reviewed the complete intended code/test/CI/runbook diff. Secrets stay encrypted
and omitted from responses. Authentication remains before trusted mutation;
tenant guards and PostgreSQL workspace policy binding remain intact. New locking
reads reload state, while transaction composition prevents partial receipt safety
effects. Integration enable flags remain unchanged and disabled by default.
No database schema change or destructive migration was introduced.

The migration runbook now requires 20261009_0015, identifies the role-specific
review grants and documents application-only rollback with workers/integrations
paused, schema/key/evidence preserved, and uncertain deliveries reconciled.
Actual PostgreSQL role/grant verification and isolated backup restoration remain
unverified. Provider calls still occur under locks and lack an overall wall-clock
deadline; the prior audit's timeout/reconnection-recovery prerequisites remain.

Ready for a new pre-deployment source audit after the final-source checks pass.
Deployment and integration activation remain **NO-GO** until PostgreSQL concurrency,
staging environment/permissions, backup/rollback and other outstanding audit gates
are verified. The earlier audit remains historical evidence for its original SHA.
