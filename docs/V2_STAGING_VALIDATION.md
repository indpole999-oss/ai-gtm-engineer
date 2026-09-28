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
