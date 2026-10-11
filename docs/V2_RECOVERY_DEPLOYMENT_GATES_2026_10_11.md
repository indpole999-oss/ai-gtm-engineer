# Single recovery and deployment-safety checklist

Decision: **NO-GO**. Read-only inspection from verified source
`0abd65aa1194e886154dc0f0a3c9842807e26eb2`, 2026-10-11. This checklist replaces
neither the user-edited release checklist nor prior historical evidence. No sensitive
recovery material was accessed; no backup exported/restored or cloud mutation executed.

| Release gate | Status | Actual evidence / exact prerequisite |
|---|---|---|
| Source and checklist preservation | SATISFIED | V2 HEAD verified before work; only existing checklist modification and prior untracked audits present. Checklist hash `1f215c9d1bc1cab51531b0d6c1caf5a8adde27b3` retained. |
| Staging source identity / database major | SATISFIED | Supabase project `xhjkahbtckrrhuzamysr`, name gaps-ai-staging, ACTIVE_HEALTHY, metadata 17.6.1.171; SELECT reports server 17.6, database postgres, revision 20261009_0015. Database name alone is not unique identity; project and privately verified host/role/TLS must match. |
| Migration dependency / rollback policy | SATISFIED as source review | 0016 depends on required 0015. 0016 downgrade intentionally refuses removal of approval history. Prepared function hardening requires 0016 and is a separate approved operation, not an automatic Alembic step. Older one-message-per-step binaries cannot be fallback after replacement. No hosted upgrade/fallback rehearsal performed. |
| PostgreSQL17 synthetic compatibility | SATISFIED within synthetic scope | Prior verified CI 38122759348: PG17 4 passed plus restore 1 passed, zero skips. Synthetic archive/restore, migration, grants, RLS/approval/cancellation and function-path guards are tested. This does not prove actual staging archive/key recovery. Completed work not repeated manually. |
| Staging Render inventory | SATISFIED within workspace scope | Read-only include-previews inventory: only staging API `srv-daui93navr4c739a4chg` and web `srv-daul2r0u01pc73855lig`, both web services, not suspended, autoDeploy=no. No named staging worker/cron/preview service appears. External/local processes and pending manual/API deployments remain unverified. |
| Protected backup availability/integrity/scope | BLOCKED / UNVERIFIED | Project metadata contains no backup inventory. No callable backup-list tool or approved non-secret archive manifest/storage locator is available. Need timestamp/revision, SHA256 verified by authorized custodian, protected retention/access and complete app/managed-schema scope. No archive bytes inspected. |
| Original encryption/signing key custody | BLOCKED / UNVERIFIED | Need named custodian, independent secure escrow locator and retrieval authorization, matching original key/version and recovery procedure. No key inspected/generated/replaced. Format checks and synthetic keys are insufficient evidence. |
| Independent PG17 restore destination | IDENTITY VERIFIED; ISOLATION BLOCKED | Read-only recheck of `tyvqriqbfjnimtzageoj`: ACTIVE_HEALTHY, PG17.11, zero public tables, no application revision. Managed schemas not inspected. Need isolated app host, certificate verification, target-only credentials, enforceable source/production/provider egress denial and approved materials. Empty public schema is not isolation proof. |
| Compatible fallback | BLOCKED / UNVERIFIED | Need distinct pinned fallback artifact tested with 0016 replacement/cancelled history, approval/receipt preservation and measured RPO/RTO on isolated restore. No approved artifact supplied. |
| Full executor inventory and shutdown proof | BLOCKED | Source paths below identified; no runtime env/process/restart-policy proof for every external executor. Embedded worker starts/restarts inside API. Rendering one instance or maintenance routing does not eliminate version overlap. |
| Local cooperative stop | TESTED, NOT DEPLOYED | Since dee8e80 the embedded supervisor supplies/sets stop_event and waits up to ten seconds before cancellation. New sweeps stop; an entered run_once may still claim work. Quiescence requires task exit. This does not fence old binaries or direct API writes. Cancellation preserves durable recovery state. |
| Metadata release gate | TESTED LOCALLY, NOT INFRASTRUCTURE PROOF | New scripts/recovery_release_gate.py rejects missing fields, source/production restore targets, truthy string approval flags, invalid counters/digests and same candidate/fallback. Reads only an operator-supplied NON-SECRET JSON manifest; never reads archive/key bytes or executes a command. Even complete metadata outputs actual_recovery_verified=false. |
| Recovery-material access / isolated rehearsal | AWAITING AUTHORIZATION plus blocked materials | Separate approval must name protected archive/key material, custodian, isolated target/host and exact read/restore/fallback scope. No access or restore under this task. |
| Coordinated release | AWAITING AUTHORIZATION plus blocked recovery | Separate approval for downtime, ingress/write freeze, stopping/preventing restart of all executors, final backup, 0015→0016 migration, function hardening and exact pinned API/web/worker start. Any restart-affecting Render config change needs approval before execution. |

## Executor and deployment paths identified

- API `backend.main` via Render uvicorn start, local module start or deployment/Dockerfile:
  optional EMBEDDED_EXECUTION_WORKER launches staging_execution_loop, which restarts
  failed workers after five seconds. Multiple uvicorn processes/replicas or ordinary
  rolling replacements can each run it. Lifespan cancellation alone is not a drain
  barrier for old versions. The opt-in source dependency probe is another startup
  task to inventory (read-only fetches, not a worker).
- Standalone `python -m backend.execution_worker`, including manually supervised local
  or container processes. Its run_once also consumes inbox outbox work through
  inbox_worker.consume_once; there is no separate configured inbox process in this
  workspace inventory, but external callers remain possible.
- Authenticated write/execution routes (research jobs/run, legacy agents/run/research,
  plan approval/dispatch, outreach approvals/retries/replacement, inbox ingestion,
  CRM/calendar outcome routes) can produce transactions outside the worker loop.
  Stopping workers alone does not freeze application writes or inbound webhooks.
- Manual Render dashboard/API/deploy hooks, restart, resume, rollback, preview or
  config-triggered replacements; linked V2 branch automatic deploy is disabled but
  manual paths remain possible. Do not inspect or use secret hook URLs. External
  scheduler/local supervisor/cron restart paths require owner inventory/attestation.
- Repository GitHub Validate CI has push/PR triggers and generated test databases;
  no deployment or scheduler job is defined there. Do not equate that with absence
  of external automation. Production services are outside this operation.

## Required release/recovery barrier

1. Finish metadata verification and obtain named isolated-rehearsal approval/materials.
   Confirm source/target distinction and deny provider/source/production writes.
   Verify archive checksum and original-key custody privately; do not include keys,
   credentials, connection URLs, archive contents or plaintext in evidence JSON.
2. Only after separate approval, restore atomically into the empty isolated target
   without --clean, stamp, disabling RLS or overwriting any receipts. Compare evidence,
   grants/RLS/tenant relations and approvals; verify original-key decryption privately.
   Upgrade 0015→0016 and rehearse compatible fallback with replacement history;
   measure locking and RPO/RTO. Downgrade refusal itself is not rollback success.
3. Under a separate coordinated-release approval, freeze API/webhook writes, prevent
   every supervisor/deploy/restart path, stop/drain ALL old processes and verify their
   termination. Cooperatively stopped new workers must be awaited; cancellation or
   timeout preserves leases/attempt markers for reconciliation, not blind retry.
   Check zero in-flight attempts/locks and old runtime sessions plus absent progressing
   heartbeats; absence of a heartbeat alone is insufficient. Preserve queued work.
4. Take final protected backup; migration owner upgrades required 0015→0016. On error
   verify transaction/revision before retry. Verify guards/indexes/grants/RLS and apply
   separately approved function-path preparation. Keep all providers paused.
5. Start only pinned compatible API/web with embedded worker off, verify identity/TLS/
   readiness and synthetic tenant protections. Start matching executor only after old
   binaries cannot restart. If fallback fails, remain stopped and repair forward;
   never revert to incompatible binary, remove approval history or restore over newer
   receipts. No staging/production restore or cutover is authorized by rehearsal.

Use `python scripts/recovery_release_gate.py <non-secret-manifest.json>` only to
validate metadata completeness. Exit 0 is not GO, proof of infrastructure state,
permission to access recovery material, or authority to run restore/deployment.

Precise next approval is **protected material access and isolated rehearsal only**,
after providing the archive/escrow custodian and metadata locators, PG17 target and
isolated host, approved identities/network policy, and pinned fallback. Until those
are provided, no safe actual restore rehearsal can run. Release remains NO-GO.
# Disposable host verification

See [the executable isolation boundary and remaining approvals](V2_RECOVERY_HOST_ISOLATION_2026_10_11.md).
The namespace firewall workflow must pass actual kernel-counter and TLS probes.
Synthetic CI results do not verify the real Supabase target or protected recovery.
Local enforcement is BLOCKED without Linux Docker/nft/nsenter. Readiness remains
74/100 and release NO-GO pending hosted and protected recovery acceptance.
