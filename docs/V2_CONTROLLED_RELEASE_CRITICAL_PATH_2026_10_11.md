# Controlled staging release: actual critical-path evidence

Status: **NO-GO; readiness 74/100 unchanged**. The user has conditionally authorized
the staging release after recovery, fallback, executor shutdown and write-freeze
gates pass. That authorization does not grant protected archive/key access. Do not
ask for the same conditional release approval again; prove its prerequisites.

## Fresh observations

- Starting local/remote HEAD: `f5ecee5e3dcbe25229ece46c4398f33c77e7a700`, V2 branch.
- Recovery `tyvqriqbfjnimtzageoj`: ACTIVE_HEALTHY, PostgreSQL 17.11; read-only SQL
  returned zero public tables, no app revision and no pg_cron extension. Managed
  schema contents and original-key custody were not inspected.
- Staging `xhjkahbtckrrhuzamysr`: revision `20261009_0015`; runtime SELECT=true,
  effective INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER=false on alembic_version.
- Render workspace `tea-d8eu2t6k1jcs73ace2ug`: API `srv-daui93navr4c739a4chg` and
  Web `srv-daul2r0u01pc73855lig` are free, one instance each, unsuspended,
  autoDeploy=no, maintenance=false, health paths empty. No background worker/cron
  service appears in the returned workspace inventory. External executors and
  manual restart paths are not independently fenced.
- Latest live API is `237818dd3ba815411f9d1eed1961fff1a5a047f1`; Web is
  `22df230021cf7734a223d8342b3fa0341e8b56a4`. No deployment was triggered.

## No-cost host attempt: BLOCKED, not TLS acceptance

GitHub reports the repository is public. Standard public GitHub-hosted Linux
runners are free; larger runners are excluded. The dedicated workflow uses no
secrets, application startup, artifacts or caches. Evidence is retained in its
redacted log and job summary (no additional artifact-storage charge).

Actual [capability run 38139770845](https://github.com/indpole999-oss/ai-gtm-engineer/actions/runs/38139770845)
on `9e941dabc00e4089e5e8747cfebe13a3463f6146` returned:

```json
{
  "status": "BLOCKED",
  "blockers": ["no_host_ipv6_route_to_direct_recovery"],
  "public_repository": true,
  "linux_namespace_tools": true,
  "target_has_ipv4": false,
  "target_has_ipv6": true,
  "host_ipv6_route": false,
  "tls_probe_attempted": false,
  "host_isolation_verified": false,
  "actual_target_verified": false,
  "actual_recovery_verified": false
}
```

Full structured evidence SHA256:
`6444445b92526681fb956b5aa161bdce45c3dedf0df365fe122106caba73c546`.
The workflow deliberately exits 2, so its red CI status is an infrastructure
BLOCKED result, never an isolation PASS. The public direct endpoint is IPv6-only.
No pooler, IPv4 paid add-on, tunnel or paid host was substituted. Local Docker is
unavailable. No other authorized IPv6-capable Linux host is available in-session.
No Render service was created; the existing free services do not establish root
namespace/firewall control or independent recovery-host custody.

The namespace evidence contract now reports `target_tls_verified` separately and
always leaves `actual_target_verified=false`: a TLS certificate does not prove SQL
identity, credential scope or independent host custody.

## Prepared release operations — not executed

Freeze code candidate `9e941dabc00e4089e5e8747cfebe13a3463f6146` after green Validate CI.
Fallback candidate remains `dee8e80ec59611ab362897537a6e9e42854cfb3e`; it is NOT a
rehearsed fallback until executed against the approved restored data at 0016.
Documentation-only successors do not silently change these pinned artifacts.

1. Supply an existing independently administered, no-additional-cost Linux host
   with root Docker/nft/nsenter/iproute2 and working native IPv6 to the direct
   recovery endpoint. Run the credential-free namespace workflow and separately
   verify whole-host custody/network boundaries. No protected material may enter
   the public GitHub runner or probe-only image.
2. Obtain separate authorization naming the backup/key custodian and protected
   material scope. Verify archive integrity, original key recovery, isolated
   restore, 0015→0016 migration and the pinned compatible fallback. Record actual
   RPO/RTO and preservation of approvals, receipts and tenant isolation.
3. Finish ALL seven executor classes in `recovery_release_gate.py`, plus private
   runtime identity/TLS/configuration checks. A complete metadata manifest is
   necessary but not independent proof. Preserve its evidence privately.
4. Under the existing conditional staging authorization, freeze ingress and
   drain/suspend all verified executors. Prepared Render REST operations:

```text
POST https://api.render.com/v1/services/srv-daui93navr4c739a4chg/suspend
POST https://api.render.com/v1/services/srv-daul2r0u01pc73855lig/suspend
```

   Use private authenticated tooling; never put bearer values in shell arguments
   or reports. Verify API writes/webhooks unavailable, every process stopped,
   no advancing worker heartbeat/in-flight work/runtime sessions, no queued deploy,
   and restart prevention across Render and external supervisors. Suspension of
   these two services alone does not prove the complete inventory. Capture the
   final consistent protected backup only under its separate material approval.
5. On the verified staging migration host, privately supply the independently
   verified staging migration-role DATABASE_URL with certificate verification.
   Require revision 0015 before execution, providers/embedded worker OFF and the
   bounded lock timeout proven in rehearsal. Prepared commands:

```sh
set -euo pipefail
python scripts/recovery_release_gate.py /approved/non-secret-release-evidence.json
python -m alembic current
python -m alembic upgrade 20261011_0016
python -m alembic current
```

   The first command validates metadata only. An operator must independently prove
   the gate before the remaining commands. Existing runtime SELECT-only grants
   need no repeat mutation. Any function hardening is a distinct reviewed action
   after 0016, never an automatic side effect of this preparation.
6. Prepared pinned deployment requests, only after platform behavior proves the
   old artifact cannot restart while suspended/resuming:

```text
POST https://api.render.com/v1/services/srv-daui93navr4c739a4chg/deploys
POST https://api.render.com/v1/services/srv-daul2r0u01pc73855lig/deploys
Content-Type: application/json
{"commitId":"9e941dabc00e4089e5e8747cfebe13a3463f6146","clearCache":"do_not_clear"}
```

   Keep auto-deploy off and providers/embedded worker off. Set reviewed health
   paths `/api/v1/ready` and `/` only within the approved release sequence.
   The available Render MCP `trigger_deploy` has no commit pin parameter; do not
   use it for this release. A moving branch deploy is not the prepared request.
   **Resume ordering remains BLOCKED:** resuming a service may run its old artifact.
   Do not issue resume until a supported pinned activation sequence or reviewed
   replacement topology is proven. No API request above has been executed.
7. Verify returned deployment commit IDs, revision 0016, runtime permissions/TLS,
   isolated synthetic hosted auth/approval/reload journey and actual write-freeze
   status before reopening ingress. Only start matching workers after the complete
   old-executor inventory is quiescent; provider gates stay off.

Abort before migration: retain write freeze and diagnose without changing revision.
After migration: preserve 0016 and all cancellation/receipt history; stay stopped
and use the genuinely rehearsed compatible fallback or repair forward. Never
deploy the old live binaries, downgrade history or restore over newer receipts.

## Remaining user action

Provide the non-secret connection/ownership details of an authorized no-cost Linux
host with working IPv6 (or have its administrator run the reviewed probes). Then
separately authorize the named custodian's protected archive/key access and isolated
restore scope. Conditional release authorization is already recorded. Until these
prerequisites and executor/pinned-activation evidence exist, release remains NO-GO.

References: [GitHub no-cost standard runner policy](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[Supabase direct connectivity](https://supabase.com/docs/guides/database/connecting-to-postgres),
[Render pinned deploy API](https://api-docs.render.com/reference/create-deploy).
