# Approval-ready staging release preparation

Prepared from `cf2d1777c1aa6d031232a8ebc6dfc881b5ac5bb9`. Deployment remains **NO-GO**.
This supplements `V2_STAGING_RELEASE_GATE_AUDIT_2026_10_11.md`; its cloud evidence
is not a fresh verification. No cloud configuration, permission, database or secret
changes are authorized by preparation alone. Existing checklist edit is excluded.

## Exact proposed actions and reversal

| Approval scope | Target and effect | Reversal / abort |
|---|---|---|
| Revision metadata permission correction only | Staging project `xhjkahbtckrrhuzamysr`, `public.alembic_version`: remove direct runtime privileges, grant SELECT; migration owner retains writes. Prepared `scripts/staging_revision_permissions.sql` uses a transaction, owner/current-user/revision checks and effective-privilege assertion. It does not create roles, alter data/RLS/default grants or revoke PUBLIC/inherited permissions. | Any failed pre/postcondition rolls back the entire transaction. Capture direct grant/grantor/grant-option baseline privately before approval. If inherited/PUBLIC rights remain, stop and prepare their narrowly reviewed correction; do not expand scope. After commit, retain SELECT-only as secure recovery; restoration of former unsafe writes would require separate approval and exact captured grant provenance. |
| Render health-check configuration only | Authorized workspace `tea-d8eu2t6k1jcs73ace2ug`: API `srv-daui93navr4c739a4chg` path `/api/v1/ready`; web `srv-daul2r0u01pc73855lig` path `/`. The web root is an existing public landing route; no application route change. Changes affect platform health decisions, not database schema. | Record previous empty paths; restore those settings only if separately authorized. A config change might trigger a deploy/restart: verify provider behavior before saving. Approval must explicitly permit that effect or use a verified non-deploying save mechanism. Do not perform a restart/deploy under config-only approval. |
| Read-only runtime preflight | Run the prepared operator command in the actual private service/runtime context, with startup/provider execution excluded. Emit names and booleans only. Separately inspect linked env groups and effective build-time frontend configuration privately. | No data/config mutations. Probe failure returns exit 1 with no exception text. Local laptop success is not deployed-runtime proof. |
| Coordinated staging migration/release | ALL old executors stopped and restart prevented; migration owner upgrades **0015 → 0016**; pinned compatible API/web/worker restarted under verified configuration. This includes downtime and schema/index/trigger changes and requires separate explicit approval. | Before committed migration, inspect actual transaction/revision state. After 0016, use only a tested forward-compatible fallback against retained schema/history, or remain stopped and fix forward. Never deploy an old one-message-per-step worker or downgrade/delete approval history. |
| Protected recovery rehearsal only | Approved source archive/key retrieval; restoration and migration/fallback execution on a separately allowlisted empty PG17 target with no source/production/provider write reachability. | Destroy only explicitly disposable rehearsal resources under their own lifecycle authorization; never restore or cut over into staging/production. No archive/key material or target currently available to this session. |

## Read-only checks without disclosure

1. An operator authenticates to the staging Render Dashboard privately; check variable
   **names/presence** and linked environment groups without revealing values. API/worker
   names: APP_ENV, DEBUG, AUTO_CREATE_TABLES, ALLOW_LEGACY_ENV_CREDENTIALS,
   AUTH_ADMISSION_STORE, SECRET_KEY, ALGORITHM, INTEGRATION_ENCRYPTION_KEY,
   DATABASE_URL, FRONTEND_URL, CORS_ORIGINS, OUTBOUND_EMAIL_ENABLED,
   MAILBOX_INGESTION_ENABLED, CRM_READS_ENABLED, GTM_HOSTED_AI_ENABLED,
   EMBEDDED_EXECUTION_WORKER. Frontend VITE_API_BASE_URL is build-time; runtime
   presence cannot establish what is baked into the deployed bundle.
2. `python scripts/staging_release_preflight.py` checks effective API environment
   booleans without importing backend startup or printing values. Missing flags fail
   closed. Production security profile is required even though resources are staging.
   It checks key **format**, not custody/recoverability or key equivalence.
   `--frontend` checks the staging API origin; run in the approved build context.
3. For an optional connection probe, privately configure
   STAGING_PREFLIGHT_DATABASE_URL, STAGING_PREFLIGHT_EXPECTED_HOST and
   STAGING_PREFLIGHT_EXPECTED_DATABASE; run `--database`. The probe accepts only the
   exact direct staging host `db.xhjkahbtckrrhuzamysr.supabase.co`, a libpq PostgreSQL
   URL for `gaps_staging_runtime`, `sslmode=verify-full`, and `sslrootcert`.
   Do not put URLs/secrets on command lines. It enforces connection/statement timeouts,
   read-only transactions and SELECT-only queries, verifies current identity/database,
   encrypted connection/PG17, known revision and effective SELECT-only revision grants.
   All connection errors are redacted. Direct-host IPv6 access and a trusted CA file
   are prerequisites. Pooler support is intentionally not inferred or silently used.
4. The separate libpq probe does **not** prove application asyncpg connection TLS or
   equivalence to deployed DATABASE_URL. A reviewer must privately confirm same target/
   identity and asyncpg certificate+hostname verification in the actual API/worker
   connection configuration; record only booleans. Query pg_stat_ssl for the actual
   app session from that connection. If unavailable, keep TLS/runtime identity BLOCKED.
   An encrypted socket alone is insufficient certificate-authentication evidence.
5. Read-only inspect effective grants, PUBLIC, inherited roles, ownership and default
   privileges; retain migration/runtime credential separation. Repeat after 0016.
   Check index, cancellation trigger/check constraint, composite tenant FKs and FORCE
   RLS. Do not use a blanket GRANT ON ALL TABLES to repair runtime permissions.

## Stop / drain / migrate / pinned restart

1. Finish isolated recovery/fallback rehearsal first. Freeze a full candidate SHA and
   fallback SHA, operators, maintenance window, RPO/RTO and abort criteria. Preserve
   original signing/encryption keys; automatic deployment remains off.
2. Inventory Render, local, CI and any other API/worker/cron executor. Identify embedded
   flags and startup/restart policies. Routing maintenance is not worker shutdown.
   No automatic worker schema/version fence exists in the current code.
3. Under separate downtime authorization, stop accepting all writes/webhooks and
   initiate graceful drain before termination. Stop ALL old API instances with
   embedded workers and standalone executors, disable their restart paths, and prove
   process termination, no progressing heartbeat, no runtime sessions/in-flight locks,
   and no pending deployments. Durable queued commands may remain; preserve leases,
   attempted/unknown deliveries and approval history for safe recovery/reconciliation.
   Never clear attempt markers, receipts, leases or cancellation history to force retry.
4. Obtain a final protected consistent backup while writers are stopped. Only now
   connect the separately scoped migration identity to verified staging, confirm 0015,
   and upgrade to 20261011_0016. Bound lock timeout per isolated rehearsal; on failure
   stop and inspect actual revision/transaction result. No migration in build/start.
5. Validate revision, evidence preservation, guards/indexes/RLS/effective grants and
   repeat-upgrade no-op. Start pinned API with embedded worker OFF; require ready 200,
   correct runtime identity/TLS and all providers paused. Start matching web artifact
   with verified API origin and public health response. Keep ingress blocked until
   safe tenant/login/approval/reload verification succeeds.
6. Start ONLY the matching pinned executor topology after all old binaries are proven
   gone, if separately approved. Test synthetic blocked/provider-fixture execution,
   graceful restart and persistence/deduplication. Record exact hosted evidence.
   Rolling deploy, one instance, and changing an embedded-worker env flag alone do
   not prevent overlap. Stop if termination/restart prevention cannot be proved.

## Protected backup, key recovery and rollback rehearsal

Required before execution: approved current staging archive/export identity,
checksummed timestamped manifest and revision, protected off-service archive storage,
an independently accessible original-key escrow locator/custodian, signing-key
recovery plan, PostgreSQL17 backup tools/CA, a newly empty independently protected
target plus isolated application host, and a tested forward-compatible fallback.
None is supplied by synthetic CI success. Do not request secret values in chat.

1. Verify approved source/target identities independently. Target identity must differ
   from staging and production; target credentials/network cannot write either source
   or reach any real provider. Deny provider network egress and keep all gates/workers
   off. Never pass a hosted URL to disposable CI tests.
2. Validate source checksum/manifest/export completeness and custody. Scope managed
   Supabase auth/storage separately if needed; app-only restore is not whole-project
   recovery. Restore atomically with error-stop into the empty target, without --clean,
   disabling RLS, stamping revision, or reusing a database with newer receipts.
3. Recover the original encryption key privately. Verify existing encrypted records
   decrypt without plaintext logging; if no nonempty records exist, report actual
   persisted-credential recovery unproven. Key format verification alone is insufficient.
4. Compare counts and immutable projections/tenant relationships/approvals/receipts/
   audit chains; reconstruct reviewed owners/grants. Upgrade 0015→0016, measure lock
   time, repeat no-op, verify two-tenant denial, cancellation guards and synthetic
   replacement/reload/deduplication. Keep network effects impossible.
5. Verify actual downgrade refusal preserves data. Rehearse pinned compatible fallback
   against 0016 cancellation/replacement history; refusal itself is not rollback PASS.
   Measure RPO/RTO and capture redacted evidence. For any actual release failure keep
   ingress/workers/providers paused, preserve snapshots/receipts and use compatible
   fallback or repair forward. Do not restore over newer receipts or delete history.

## Verification boundary

Local deterministic tests validate preflight secret redaction, missing/enabled safety
gates, exact origins, pre-connect target rejection, read-only connection options/queries
and effective privilege failure. PostgreSQL permission regression is restricted to a
generated database/roles on explicit disposable loopback PG17; it verifies read-only
runtime, retained migration writes, wrong-identity rejection, atomic rollback on PUBLIC
rights, and safe repeat. It is included in the isolated CI job, not run against staging.
Record executed CI results separately; skipped local PostgreSQL is not PASS.

Local verification: **25 passed, 1 skipped, 2 warnings in 2.38s** (preflight plus
API readiness tests). The skip is the new PostgreSQL permissions test because no
disposable local service exists. Python compilation and whitespace checks passed.
The first sandbox readiness run stalled; the completed isolated local rerun above
is the result used. No hosted connection was used by these tests.

Remaining gates: authenticated deployed environment/runtime TLS evidence; authorized
staging grant and health corrections with postchecks; protected recovery materials/
independent target; actual fallback and stop/restart rehearsal; separately approved
0016 migration/deployment. No provider verification or customer readiness claimed.
