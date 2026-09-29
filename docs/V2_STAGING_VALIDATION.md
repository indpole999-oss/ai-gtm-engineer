# V2 staging prerequisites and acceptance matrix

No isolated live-provider staging environment is currently confirmed. Do not use
production data/accounts or spend provider credits to substitute for this gate.
No secret values belong in chat, tickets, screenshots, test logs or PR comments.

## Minimum isolated setup

1. An isolated API + frontend + separate durable worker, PostgreSQL database,
   least-privilege runtime role, migration role and operator-controlled local model.
   Two API processes share the database, signing key and admission configuration.
   HTTPS endpoints and exact CORS/OAuth callback URLs are required. No deployment
   or account purchase is authorized by this document.
2. Two synthetic application workspaces, each with an owner; additional admin,
   member and viewer memberships in the first workspace. No production customers.
3. A provider-supported sandbox/test sender and controlled recipient mailbox for
   the chosen mail transport, plus authenticated inbound/delivery callbacks.
   The transport must prove durable idempotency and authoritative reconciliation.
   Do not enable live sending if the provider cannot meet this contract.
4. A Google OAuth test project/consent configuration and a dedicated test calendar
   account; a second controlled attendee account/mailbox. These may serve as the
   controlled email recipients where provider contracts permit. No personal or
   production calendars; exact scopes and revocation authority must be reviewed.
5. One CRM developer/sandbox account (the existing adapter supports HubSpot) with
   synthetic company/contact/deal objects and narrowly scoped credentials. Do not
   substitute unsupported Salesforce writes; they remain fail-closed.
6. A test-owned HTTPS source with permitted robots rules and truthful synthetic
   company/buyer/buying-signal content, plus opt-out/denial variants. A local model
   with sufficient capacity; no paid-provider fallback or invented real facts.
7. An isolated log/alert sink, restore-test backup target and operator responsible
   for incident recovery. Credentials go through the deployment secret manager
   or approved integration UI. Confirm no-cost quotas or obtain cost approval first.

## Evidence matrix

All rows require the exact SHA, time, reviewer, outcome and redacted evidence.
Offline fixtures prove contracts only; **all live column items are NOT RUN**.

| Gate | Offline evidence | Required isolated staging test |
|---|---|---|
| Tenant/RBAC | Workspace, PostgreSQL RLS, FK and role tests | Cross-workspace reads/mutations and suspended users through deployed UI/API |
| Schema | Empty/populated upgrades; additive 0013; readiness tests | Restore a synthetic backup, upgrade with migration role, verify runtime grants and readiness |
| Admission | Atomic independent-pool tests and PostgreSQL CI probe | Alternate attempts across two API replicas; one shared 429 budget, restart without reset, database outage -> 503; verify proxy spoof resistance |
| OAuth | State/PKCE/refresh/reconnect/revoke contracts | Actual consent/decline, one-time callback, expiry, refresh rotation, revoked access and reconnect |
| Model/research | Fake planner, cited fixture evidence and signal, unknown verification | Local model generates a valid plan and accurate cited report; unsupported signals remain unknown |
| Source privacy | SSRF and robots/storage-policy tests | Test-owned deny/404/timeout/noarchive sources; no denied source capture, no credentials logged |
| Approval | Immutable approval and invalidation tests | No effect before current authorized approval; revoke membership/approval before dispatch |
| Workflow durability | Restart/lease/retry/CAS suites | Kill worker around dispatch, restart, reconcile before retry, no duplicate effect |
| Email acceptance/delivery | Durable fake provider plus distinct deduplicated delivery receipt | Send only to controlled recipient after review; authoritative acceptance, signed delivery event and duplicate callback |
| Suppression | Reply/unsubscribe/bounce/complaint tests | Controlled unsubscribe before queued dispatch; subsequent sends blocked even after restart |
| AI Inbox | All categories/overrides/evidence tests | Authenticated actual inbound receipt, thread association, one classification, human review for ambiguity |
| Calendar | Conflict/overlap/identity/reconciliation tests | One approved test event, lost acknowledgement, duplicate retry, remote changes and revoked OAuth |
| CRM | Stable identity/version/conflict/reconciliation tests | One approved synthetic object write; remote version conflict never overwritten; cursor/reconcile evidence |
| Insights/gaps | Canonical evidence/hash and insufficient-data tests | Verify real receipt lineage; absent cost/revenue and small samples remain unknown |
| Next cycle | Fake full journey requires separate approval | Recommendation cannot dispatch; new reviewed plan creates a new approved cycle |
| Frontend | Contract tests, TypeScript, lint and production build | Full primary journey in browser, role/workspace switching, expired session, rejected/ambiguous states |
| Monitoring | Correlated logs, scoped alerts/ages/counts | Operator receives an actual test alert; queue stall and worker restart; protect logs and metrics |
| Cost | Explicit unavailable value, never fabricated zero | Obtain authoritative sandbox usage receipt; if unavailable retain unavailable status and document budget controls |
| Retention | Scoped inventory, unset periods, retained-delete 409 | Approved policy plus synthetic rights-request/export/delete/backup process; no integrity/audit damage |

## Explicit retention release decisions — approval required

The user confirmed there is **no approved retention policy**. No automatic purge
period is chosen or enforced. The absence of purge is an unresolved release
decision, not a claim that indefinite retention is appropriate.

| Dataset | Duration | Required decision and safeguards |
|---|---|---|
| Customer evidence, Brain versions, research | Unset | Purpose, expiry trigger, immutable provenance/dependency closure, review/hold and deletion method |
| Inbox content, outbound drafts and receipts | Unset | Content minimization, provider copies, thread evidence and suppression dependency handling |
| Audit/approval/run history | Unset | Audit obligations, integrity-preserving redaction/export, hold and incident needs |
| Backups and replicas | Unset | Expiry, encryption/access, restoration, deletion propagation and re-deletion after restore |
| Logs/operational exports | Unset | Redaction, access, expiry, incident holds and export copies |
| Suppression records | Unset | Preserve opt-out enforcement while deciding minimal retained identity and access |

Rights requests must first authenticate the requester and workspace, record a
reviewable scope, inventory dependents/provider copies/backups, and receive
authorized privacy/legal and operator review. Current APIs do not promise full
account erasure. They block operations that would break retained relationships.
No operator should bypass immutable constraints or delete audit evidence ad hoc.
After a policy is approved, implement and validate its exact lifecycle separately
on synthetic data before enabling any retention executor.

## Release decision

Green offline CI does not authorize deployment. Live mail/CRM/calendar transport
capability must be selected and demonstrated before enabling its write path;
default transports still reject live mutations. Live staging, retention decisions,
source permission/legal review, restore evidence and deployment authorization all
remain required. Record unsupported cases as blocked, never simulated success.

## Ordered operator rehearsal (stop at the first unmet prerequisite)

1. Record the V2 SHA and successful CI run. Inventory a dedicated non-production
   host, HTTPS frontend/API names, PostgreSQL 16, separate worker and local model.
   Do not reuse an existing customer service or database. Confirm resource costs
   before provisioning; no paid API fallback. Store credentials only in the host's
   secret manager, never in this document or evidence attachments.
2. Set the production configuration checks described in V2_PRODUCTION_READINESS.md
   on this isolated environment: APP_ENV=production, DEBUG=false,
   AUTO_CREATE_TABLES=false, ALLOW_LEGACY_ENV_CREDENTIALS=false and database-backed
   admission. Inject a unique signing key and Fernet key. Use exact HTTPS CORS,
   frontend and API URLs. Leave retention durations unset and purge disabled.
3. Restore a synthetic populated backup into a NEW empty database with writers
   stopped. Use a dedicated migration owner for restoration/upgrades and a separate
   non-owner runtime login without SUPERUSER/BYPASSRLS/DDL. Reapply reviewed grants
   explicitly: archives exported without ACLs do not restore access privileges.
   Never use pg_restore --clean, a production URL, or Alembic stamp/downgrade.
   Record backup SHA-256, source/target schema revisions, row/evidence comparisons,
   quarantine counts, RLS/immutable-trigger checks, elapsed recovery time and
   available recovery point. Check encryption-key recovery separately without
   exporting keys into evidence. An unencrypted synthetic CI dump proves neither
   encrypted backup custody nor production RPO/RTO compliance.
4. Apply upgrade head twice with the migration identity; the second run must be a
   no-op. Check readiness using the runtime identity, then negative tenant/RBAC
   checks. Start two API replicas and a separate worker with provider writes still
   disabled. Validate shared admission and ingress limits before any OAuth consent.
5. Exercise monitoring below using synthetic work only. Confirm the actual operator
   receives and acknowledges a test notification, then receives recovery. An
   operations JSON alert alone does not demonstrate notification delivery.
6. Only now configure a dedicated Google test project and calendar identities.
   In the Google project's OAuth consent configuration, restrict access to the
   designated test users; register the exact backend callback URL in the web OAuth
   client. Inject GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/GOOGLE_REDIRECT_URI in the
   staging secret manager. Authorize through the staging integration flow. Free
   test accounts are sufficient for consent testing, subject to available quotas;
   do not enable billing. Validate consent/decline, callback replay, refresh,
   revoke/reconnect and absence of OAuth codes/tokens from every logging layer.
7. Before requesting mail or CRM credentials, select and implement a transport
   satisfying durable lookup/idempotency and atomic conflict semantics. Current
   live mail/calendar/CRM mutations are disabled; connecting an account does NOT
   remove that blocker. Use a mail sandbox plus controlled recipient and a HubSpot
   developer test account only after verifying required capabilities and no-cost
   quotas. Configure their credentials in the staging integration UI, never chat.
   If the selected free tier cannot prove the contract, stop for a capability or
   cost decision; never substitute a fake receipt or a read-then-write conflict check.
8. Execute the matrix in order: research with reviewed synthetic sources/local
   model; review and approve outreach; one controlled send and signed delivery;
   authenticated reply and suppression; separately approved calendar and CRM
   actions; lost-ack/restart reconciliation; insights lineage; a separately
   approved next cycle. Capture the actual browser journey and redacted provider
   evidence. Stop on ambiguous outcomes and reconcile before any retry.

Evidence for each step must record SHA, UTC start/end, operator, synthetic resource
identifiers, expected/observed result, and PASS/FAIL/BLOCKED/NOT RUN. Never record
tokens, authorization codes, raw request headers or mailbox content. Provider
acceptance, delivery, reply and business outcome are distinct evidence states.

### Monitoring drill

Use authenticated owner/admin GET /api/v1/operations independently in both test
workspaces; member/viewer access must fail and data must never cross workspaces.
Stop the isolated worker while approved synthetic work waits more than five
minutes: expect queue_wait_exceeds_5_minutes. Exercise expired leases and a
deterministic failed command: expect expired_leases and failed_execution. Restart
the worker and reconcile; record cleared queue/lease alerts. Historical failed
commands may keep failed_execution present; acknowledgement is not data deletion.
Configure the external collector to deduplicate and route state transitions.

Monitor the worker process separately: worker_liveness=not_measured is intentional
and an idle queue cannot prove worker availability. Simulate a staging database
outage and verify readiness 503 while liveness remains a separate signal. Review
ingress, API, worker and HTTP-client logs using synthetic canaries for callback
queries/headers. Confirm request/command correlation without content or secrets.
Provider latency/failure aggregation and authoritative cost ingestion remain
implementation/validation gaps; worker duration is not provider latency and
provider_cost unavailable must never be displayed as zero.

### Automated restore evidence scope

tests/test_postgres_restore.py uses only an explicit disposable POSTGRES_TEST_URL.
It creates two randomly named databases, migrates the source to 0012, seeds two
synthetic tenants plus a quarantined row, creates a custom-format pg_dump archive,
restores it into the empty target, compares rows, upgrades to 0013 twice, and
checks preserved isolation under a separate non-bypass runtime role. Cleanup is
limited to resources created by that invocation. CI supplies PostgreSQL 16 tools.
The migration connection is privileged in this CI rehearsal; least-privilege
migration-owner deployment, full evidence-chain recovery, encrypted backups,
realistic volume/locking and actual staging recovery remain separate gates.
