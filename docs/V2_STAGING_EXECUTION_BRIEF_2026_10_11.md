# GAPS AI V2 — reconciled staging execution brief

Allowed branch only: `codex/ai-gtm-engineer-v2-full-build`. Preserve the existing
user-edited release checklist; never stage, reset or commit it. No main/production
changes. Follow `V2_STAGING_RELEASE_APPROVAL_PLAN_2026_10_11.md` with these clarifications.

## Reconciled evidence

Separate-session observations supplied by the user: revision 0015, runtime SELECT
only on alembic_version, and nine mutable function-search-path warnings. Preserve
their provenance; independently classify each as VERIFIED, NOT REPRODUCED or UNVERIFIED.

Current read-only staging recheck on 2026-10-11: **VERIFIED** revision
20261009_0015; SELECT=true and INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER=false
for gaps_staging_runtime. **VERIFIED** advisor count nine at 07:35:58 UTC, all nine
public protect_* functions with no fixed search_path, SECURITY INVOKER, owned by
gaps_staging_migrator. Earlier writable-revision evidence is historical, not current.
Do not repeat the permission correction unless regression is verified.

## Approval boundary

Any Render configuration change that may restart, replace or redeploy a running
staging service requires separate explicit approval **before execution**. Existing
authorization does not cover restarts, deployments, infrastructure/config mutations,
live function changes or migrations. Read-only checks, local fixes/regression tests
and verified V2 commits may proceed. Health paths remain API /api/v1/ready and web /;
successful endpoint GETs do not mean platform settings have been corrected.

## Synthetic isolation

Hosted synthetic tests require a dedicated identifiable workspace, records prefixed
with a unique run identifier, a manifest of created record IDs and a controlled,
explicitly authorized cleanup scope. Never inject fabricated provider success,
receipts, research evidence, inbox events or CRM outcomes into an existing customer
workspace. Fixtures cannot count as real hosted-provider acceptance. Tests in a
generated disposable CI database are synthetic and do not establish hosted recovery.
Human approval remains mandatory. Providers and hosted AI stay OFF.

## Execute and validate

1. Inspect current branch/changes and verify checklist preservation. Recheck cloud
   configuration and health endpoints read-only; privately verify env presence,
   runtime DB/TLS identity and frontend API target without emitting values.
2. Investigate function warnings and prepare narrowly scoped tested code/SQL fixes;
   do not mutate live functions. Prepared `scripts/staging_function_search_path.sql`
   runs only after approved 0016 migration under the function-owning identity. It
   qualifies Company Brain relation lookups and fixes pg_catalog-only search paths
   for nine existing guards plus the new 0016 cancellation guard. Retains invoker
   rights, owners, approval/immutability and tenant protections; no schema-head change.
   Immutable historical migrations remain unchanged. This explicit post-migration
   hardening operation must be included in release approval/rehearsal; Alembic alone
   does not apply it. Rerun advisor after authorized application; current warnings
   remain outstanding. On failure transaction rolls back; avoid resetting secure
   paths as rollback. Use a reviewed forward fix if compatibility fails.
3. Inventory every executor and restart path. No worker startup binary/schema fence
   exists; verified downtime/stop/drain/restart prevention is mandatory before 0016.
   Routing maintenance alone is insufficient. Preserve attempted/unknown deliveries.
4. Verify protected staging backup, original-key escrow/custodian, PG17 target/tooling
   and compatible fallback. If unavailable, report exact missing material and continue
   independent tests. Never expose/replace keys or claim synthetic restore as real PASS.
5. Test safe customer journey where deployed compatibility permits: Company Brain →
   Goal → Prospects → Research readiness → Qualification → Outreach draft → Human
   approval → Inbox → Pipeline → Insights, including auth/session/reload, tenant
   isolation, desktop/mobile and error states. No real email, paid AI, provider
   activation, calendar events or external CRM writes. Report unsupported stages BLOCKED.
6. Fix reproducible local defects, run relevant tests and CI, commit verified files
   only. Do not repeat completed unchanged verification unnecessarily. Report files,
   SHA/CI, actual cloud changes, resolved/outstanding findings, exact PASS/FAIL/BLOCKED,
   prerequisites and specific approvals. No invented readiness percentage.

Release remains **NO-GO** until recovery, configuration, coordinated migration and
the complete real customer journey have verified acceptance evidence.
