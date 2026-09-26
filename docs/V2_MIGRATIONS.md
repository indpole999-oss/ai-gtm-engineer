# V2 migration and recovery runbook

No production database has been contacted or changed during implementation.
Run schema changes using Alembic only. Application startup no longer creates
tables. Preserve the Phase 0 baseline adoption procedure for pre-Alembic databases.

## Phase 1 order

1. Back up the existing database and demonstrate restoration in an isolated clone.
2. Stop old application writers and background workers during the ownership cutover.
   An old binary cannot safely run alongside the new tenant-aware binary.
3. Upgrade to `20260922_0002`: workspaces, memberships, audit inventory and nullable
   ownership columns. No existing customer rows are deleted or reassigned.
4. Upgrade to `20260922_0003`: create one deterministic UUIDv5 workspace per
   existing user, with owner membership. Inactive users receive suspended memberships.
   Map integrations using their existing `user_id` foreign key only.
   Companies, contacts (including leads), CRM records, emails and meetings have no
   provable user owner in the Phase 0 schema. Keep them NULL/unassigned. Do not infer
   ownership from email domain, registration order, sole-user count, or company name.
5. Review `legacy_ownership_audit`, grouped by table, disposition and reason.
   Every existing customer record is inventoried as mapped or quarantined.
6. Upgrade to `20260922_0004`: reject invalid owners and mixed-tenant relationships,
   add indexes/FKs/composite relationship FKs and workspace-scoped domain/email
   uniqueness. Require integration ownership; other legacy NULLs remain quarantined.
7. Verify schema, counts, ownership and FK integrity; run security tests on the clone.
8. Deploy the tenant-aware binary only after a separately authorized production gate.

## Quarantine and manual mapping

Quarantine means `workspace_id IS NULL`, not a shared customer workspace. Normal
API queries cannot return these records, and normal API writes cannot adopt them.
There is no customer-facing remediation endpoint.

Export the audit inventory using a privileged migration connection. For each
proposed assignment, retain the record ID, target workspace, independent ownership
evidence, reviewer, approval time and relationship closure. Resolve companies before
contacts, and contacts before CRM/email/meeting children. All linked rows must agree
on the target workspace. Never infer ownership from a customer's request alone.

Prepare an explicit reviewed mapping as a new data migration: assert the source is
still unassigned, assert target membership/workspace legitimacy, check duplicate
domains/emails within the target, update parent and children in one transaction,
and update the audit disposition/reason with the evidence reference. Abort on any
mismatch. Review both mapped and remaining quarantined counts before release.

## PostgreSQL role and RLS

Use a separate migration role. The runtime role must have no SUPERUSER, BYPASSRLS,
schema alteration, or migration-audit access. Customer tables have ENABLE/FORCE
RLS and a workspace policy. The application sets transaction-local
`app.workspace_id` only after authenticating and checking active membership; it
reapplies the setting after commits. Missing settings expose no customer rows.
The runtime role must not be available to clients or arbitrary SQL tools.
RLS does not replace application checks; membership and role policy remains in the
central dependency/service. Do not expose these tables directly through Supabase
client roles without separate reviewed policies/grants.

## Validation and operational risks

Run `python -m pytest -q`, the disposable PostgreSQL test job, `alembic upgrade head`
on a new database and on a populated baseline clone, then `alembic current`.
Check row counts, `legacy_ownership_audit`, NULL counts, FK consistency and tenant
uniqueness. Test every workspace with representative users before enabling traffic.

SQLite batch migrations copy tables locally; PostgreSQL index/FK creation can take
locks and needs a maintenance window sized on a production clone. Backfill reads
legacy rows and writes an audit row per record; assess scale before production.
No new customer inserts may be made through unscoped SQL. Remaining nullable
legacy columns cannot safely become globally NOT NULL until quarantine is resolved.

Downgrades deliberately refuse to erase ownership or restore global uniqueness.
After new tenant writes, reverting to V1 would expose data and may introduce global
uniqueness conflicts. Recover by rolling forward or restoring the verified backup
with writers stopped. Retain the audit trail and document any lost writes. Never
blindly stamp revisions or drop customer tables to recover.

## Phase 6 additive upgrade

Upgrade from `20260923_0009` to `20260926_0010` using Alembic. This adds outreach
snapshots, enrollments/schedules, message approvals/provider state, sender identities,
delivery events and suppressions, with composite workspace FKs, forced PostgreSQL
RLS and SQL immutability triggers. It does not alter or reassign Phase 1–5 rows.
Validate a clean database and a populated execution-history clone; test immutable
sequence definitions/message approvals and cross-workspace foreign keys under a
non-BYPASSRLS runtime role. Start the existing worker only with live delivery still
disabled until an idempotent adapter passes its separately authorized staging gate.
Downgrade refuses to discard approvals, provider receipts or suppression history.


## Phase 7 additive upgrade

Upgrade `20260926_0010` to `20260926_0011` using Alembic. Seven immutable,
workspace-scoped inbox tables gain forced PostgreSQL RLS and composite foreign
keys. Existing outbox rows gain retry/lease fields with zero attempts and no due
work; existing execution cycles and audit content remain unchanged. Domain events
may now omit a cycle for independently received inbound mail. SQLite's audit
immutability triggers are explicitly restored after its required table rebuild.
Test populated Phase 6 audit/outbox, legacy NULL ownership and immutable evidence
before adopting the upgrade. No customer ownership is backfilled or reassigned.
Use the existing worker for deferred inbox classification; live ingestion and
outbound providers remain disabled. Downgrade refuses to discard inbound evidence
or sequence holds. See `docs/V2_INBOX.md` for idempotency and recovery contracts.


## Phase 8 additive upgrade

Upgrade `20260926_0011` to `20260926_0012` through Alembic. Six new outcome tables
receive composite workspace references, forced PostgreSQL RLS, identity/approval
protection and immutable history/receipt triggers. PostgreSQL JSON payload guards
compare JSONB values. Existing inbox/outreach/command tables are unchanged.

Discovery backfill visits each explicit workspace with transaction-local RLS
context, creates stable account/prospect identities and discovered-only history,
and leaves NULL ownership quarantined. It does not infer earlier qualification,
sends, replies, meetings or revenue. Verify owned-account/contact counts against
pipeline discovery and inspect retained inbox/outreach history on a populated
clone. The runtime role still needs no BYPASSRLS or schema privileges. Historical
pipeline references prevent hard deletion/reparenting of their customer records.
Downgrade refuses to discard provider identities, approvals or audit evidence.
