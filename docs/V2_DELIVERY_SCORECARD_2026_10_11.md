# GAPS AI V2 delivery acceptance — October 11, 2026

Scope: V2 branch only. Production `qjkcqdiznthffbqmltrr` is excluded. Existing Anil workspace was not accessed or modified. No deployment, restart, live migration, function changes, provider activation, paid AI, email or CRM writes occurred.

## Weighted acceptance rubric

The denominator is 100. Each criterion below has an explicit verification scope. Synthetic functional acceptance earns only the specified isolated-test points; it earns no hosted-provider or hosted-latest-version points. A score does not override release NO-GO gates.

| Category | Verified points / weight | Evidence and withheld acceptance |
|---|---:|---|
| Customer journey functionality | 24 / 30 | Isolated persisted Brain→Goal→Prospects→research→qualification→draft→approval→inbox→pipeline→insights: 20. Approval blocking and reconnect recovery: 4. Full hosted provider journey: 6 withheld. |
| Auth, sessions and workspaces | 12 / 15 | API authorization/tenant/role regressions: 8. Browser refresh and real cross-tab storage logout: 4. Latest-version hosted authenticated acceptance: 3 withheld. |
| Research, outreach and provider controls | 11 / 15 | Honest readiness/disconnection: 3. Deterministic evidence grounding: 3. Approval, suppression, timeout and reconnect protections: 5. Actual supported provider execution: 4 withheld. |
| Data integrity and security | 13 / 15 | Disposable PG17 tenant/approval/immutability/concurrency checks: 10. Synthetic restore and migration: 3. Live function hardening and upgraded runtime compatibility: 2 withheld. |
| Hosted staging and recovery readiness | 6 / 15 | Read-only API/Web HTTP 200: 2. Recovery target identity and emptiness: 2. Render topology/auto-deploy inventory: 2. Actual archive/original-key recovery: 4 withheld; coordinated latest-version migration/quiescence: 3 withheld; pinned fallback rehearsal: 2 withheld. |
| Mobile UX, onboarding and release polish | 8 / 10 | Isolated desktop/mobile responsive journey: 6. Session/error/pagination recovery: 2. Latest-version hosted mobile acceptance: 2 withheld. |
| **Total** | **74 / 100** | **NO-GO. 85 is not established.** |

Baseline verified commit: `dee8e80ec59611ab362897537a6e9e42854cfb3e`, CI https://github.com/indpole999-oss/ai-gtm-engineer/actions/runs/38132388632: backend 448 passed/7 opt-in skipped; browser 2 passed; frontend 17 passed plus TypeScript/build/lint; PG17 4 passed and synthetic restore 1 passed, no PostgreSQL skips; empty database reaches 0016. Current improvements extend this acceptance with prospect input/deduplication and empty-page navigation regressions. Current commit and final CI results are reported in the delivery response; this rubric awards the extended criteria only when those checks pass.

Current local API persistence/tenant validation: 26 passed. Full-batch pagination fixtures are created exclusively in each disposable browser test database. Empty inbox threads are synthetic navigation records, not fabricated inbound provider events. Existing research/delivery fixtures remain explicitly synthetic.

## Current read-only infrastructure evidence

- Recovery project `tyvqriqbfjnimtzageoj`: `gaps-ai-v2-isolated-recovery-test`, ACTIVE_HEALTHY, region ap-southeast-2. Metadata engine 17; SQL server version 17.11, zero public tables, no `public.alembic_version` and no app tables. Empty **public application schema** is verified; managed schemas were not inspected for contents. No restore authorization follows from emptiness.
- Staging `xhjkahbtckrrhuzamysr`: revision `20261009_0015` rechecked with SELECT. No mutation.
- Public staging API `/api/v1/ready`: HTTP 200, 45.88 seconds. Public staging Web `/`: HTTP 200, 23.17 seconds. These prove endpoint responses, not complete hosted acceptance or a verified cause for latency.
- Authorized Render workspace `tea-d8eu2t6k1jcs73ace2ug`: staging API `srv-daui93navr4c739a4chg`, Web `srv-daul2r0u01pc73855lig`, one instance each, autoDeploy=no, both health-check paths empty. No named staging worker/cron/preview in this workspace inventory. External supervisors, local executors, hooks and pending manual replacement paths are not proven absent.
- Latest source is not deployed. User-supplied deployed short SHAs remain 237818d API and 22df230 Web; they were not independently rechecked by this inventory operation.

## Recovery preparation and approval boundaries

Non-secret backup inventory, to be supplied by the authorized custodian without opening protected material: source project and revision, capture timestamp, tool/server versions, archive format, application and managed-schema scope, role/RLS/grant scope, SHA256 verified privately, retention/access protection, non-secret storage reference, named custodian and measured recovery objectives. A boolean manifest is not integrity proof.

Original-key custody checklist: named custodian and independent escrow reference; original `INTEGRATION_ENCRYPTION_KEY` identifier/version and continuity; signing `SECRET_KEY` continuity or explicit session invalidation policy; private decryption verification after approved isolated restore; no key generation/replacement, key values, archive plaintext or credential URLs in evidence.

Candidate fallback: pinned `dee8e80ec59611ab362897537a6e9e42854cfb3e` has green 0016-compatible cancellation/replacement tests. It is a candidate, not a rehearsed recovery artifact. Do not use deployed pre-0016 binaries after replacement history exists. Rehearse this distinct pinned artifact with restored cancellation, receipts, approval and tenant history before awarding fallback points. 0016 downgrade intentionally refuses removal of retained history.

Isolation still required for `tyvqriqbfjnimtzageoj`: approved test host; certificate-verified PG17 client/target identity; target-only credentials with no source/production write capability; enforceable network policy denying source/production connections and provider egress; no worker, webhook, scheduler or integration activation; explicit managed-schema restore strategy without overwriting managed services; proof target remains empty immediately before rehearsal. A separate project or different region alone is not network isolation. No network policy or credential capability was inspected or changed here.

Executor/restart inventory must cover embedded API lifespan supervisor, standalone `python -m backend.execution_worker`, all API research/approval/outcome write paths and inbound webhooks, uvicorn replicas/processes, external/local schedulers, Render manual deploy/restart/resume/rollback/config hooks and previews. New cooperative stop is wired into the embedded supervisor, but does not fence historical binaries or direct writes. Source paths and stop/drain barriers are detailed in `V2_RECOVERY_DEPLOYMENT_GATES_2026_10_11.md`; its earlier statement that the supervisor is unwired is superseded by dee8e80.

Separate first authorization required: named custodian/backup/escrow material access and isolated restore into **only** `tyvqriqbfjnimtzageoj` on an approved isolated host, with private checksum/decryption checks, 0015→0016 test upgrade and pinned compatible fallback rehearsal. Expected effect: write only the empty recovery-test database and isolated host, deny provider traffic. Rollback: stop isolated processes and dispose of only approved test artifacts after preserving redacted evidence; never restore staging/production. Materials and enforceable isolation are still prerequisites, so no rehearsal was attempted.

Separate later authorization required: staging write/ingress freeze, stop and prevent restart of every old executor, protected final backup, migration-owner upgrade 0015→0016, prepared function hardening, explicit API `/api/v1/ready` and Web `/` health configuration, pinned API/Web start and matching worker restart after quiescence. Expected effects include downtime, schema/function/config changes and service replacement. Rollback requires the tested compatible pinned fallback or repair forward; no destructive downgrade or restoration over newer receipts. Each restart-affecting Render config action requires explicit approval before execution.

Reaching 85 requires at least 11 additional **passed** points, not approval alone. Protected recovery plus fallback can earn 6; latest-version hosted auth/mobile can earn 5 only after a separately approved safe coordinated release. The necessary coordinated-release gate itself remains independently blocking. Real provider research/send/inbound/CRM verification requires separately scoped authorization, supported configuration, synthetic workspace and human approval; no hosted-provider points are currently awarded.
