# V2 integration foundations — 2026-10-11

Branch: `codex/ai-gtm-engineer-v2-full-build`, starting at `e186485`.
These are implemented foundations with deterministic verification, **not verified
live-provider customer readiness**. No live provider credentials were imported,
no real email or CRM write was attempted, no paid AI was called, and no production
change or deployment was performed. Hosted AI remains paused.

## Implemented functionality

| Boundary | Implementation and limits |
| --- | --- |
| Workspace credentials | Reuses encrypted Integration records, tenant-scoped queries, owner/admin management, connection audit and reconnect error states. New transports reject legacy plaintext credentials and deployment-global customer keys. Tokens/signing secrets are never returned by API responses. Saving credentials starts disconnected; a provider access check is separate from permission to execute. |
| OAuth/token lifecycle | Existing Google PKCE, hashed one-time expiring state, fresh membership checks, encrypted refresh tokens, refresh rotation, audit and revocation are preserved and regression-tested. New Resend connections use workspace API tokens; HubSpot private-app and Salesforce bearer tokens use explicit saved connections. Expired unsupported OAuth tokens require reconnect rather than fabricated refresh success. Gmail/Outlook and new CRM OAuth consent/refresh flows are not implemented or offered by the UI. |
| Outbound Resend | Fixed HTTPS endpoint, verified configured sender domain/address, persisted connection binding in the immutable draft, separate exact message and execution-plan approval, current approval/suppression/limits checks, durable intent before dispatch, stable workspace/message idempotency key and explicit UUID acceptance receipt. Reconnecting/editing the sender integration invalidates previous draft authorization. API requests never call send; only the durable worker does. Acceptance and actual delivery are distinct receipts. |
| Retries/reconciliation | Resend keys last 24 hours, not indefinitely. A known rate-limit rejection can reuse the same payload/key within a conservative 23-hour window, preserving the first attempt time. Uncertain transport/malformed acknowledgement is never blindly resent. Signed sent/delivery webhooks plus authenticated GET of the exact provider email recover acceptance only after matching message tag, sender, recipient, subject, body, immutable approved hash and persisted attempt. Receipt recovery does not issue a send or reactivate cancelled work. Missing/mismatched provider evidence remains reconciling. Existing bounded worker retries/audits are preserved. |
| Trusted mailbox/delivery ingestion | POST `/api/v1/mailbox-webhooks/resend/{workspace_id}/{integration_id}/{sender_id}` resolves an active workspace and matching encrypted, healthy connected mailbox. Svix v1 HMAC verifies exact raw bytes, timestamp within 5 minutes and signature rotation before provider fetch or ingestion. Raw requests are capped at 1 MiB; provider responses at 2 MiB; redirects are disabled and transport timeout is 20 seconds. Provider IDs are UUIDs interpolated only into fixed Resend HTTPS endpoints. Configure only supported events: `email.received`, `email.sent`, `email.delivered`, `email.bounced`, `email.complained`. Other event types return 422. |
| Inbound persistence | Authenticated receiving API supplies content; webhook metadata alone cannot invent a message. Single matching recipient binding, plaintext or safely extracted HTML text, bounded schema and exact provider identity checks precede the existing inbox service. Receipt/message deduplication and payload-conflict rejection, deferred classification, suppression and sequence holds reuse real persistence. Attachments are not fetched. Multi-recipient/forwarded mailbox handling is not accepted by this initial binding contract. Verified provider RFC message-ID receipts link replies; association requires receiving-provider DMARC pass and matching correspondent. Provider authentication alone does not establish sender identity or consent. |
| Delivery receipts | `email.sent` recovery verifies the authenticated provider record. Delivered/bounce/complaint events persist append-only receipts and deduplicate event identity. Bounce/complaint preserve suppression. A signed but conflicting receipt is rejected. Provider lookup failure returns a safe retryable error and audited failure; no success is inferred. No new subscription is created automatically. |
| CRM adapters | HubSpot company/contact/deal and Salesforce Account/Contact/Opportunity GETs use fixed endpoints, allowlisted object types/IDs, matching returned provider ID and healthy encrypted workspace credentials. Owner/admin permission is required; the provider enforces its token's object read grants. Reads and failures are audited. 401/403 mark reconnect required; rate limits provide explicit retry errors; missing records return 404. There is no implicit write grant from a connection test or user-supplied scope list. |
| CRM write permissions | Every CRM contract reports `write_available=false`, and current CRM outcome transports still reject live writes before credential refresh/apply. Existing reviewed local CRM requests and deterministic atomic-transport fixtures remain working. HubSpot/Salesforce writes are not advertised as implemented: this application's stable-operation reconciliation and atomic expected-version contract is not supplied by these read adapters. A read-then-write check would remove a safety gate and was not substituted. |
| Frontend | Owner/admin token connection forms for supported providers appear only when encryption is configured. Secrets use password fields, are cleared after submission, and are not cached as returned credentials. Saved disconnected state survives reload; access checks and removal are explicit. Per-provider read/write availability and reasons show paused/unavailable operation states. Resend is selectable as a sender; Gmail/Outlook remain unavailable transports. Google Calendar functionality is preserved. |

## Operator configuration and provider blockers

All new operator flags default to false in Settings, `.env.example`, and tests:

```dotenv
OUTBOUND_EMAIL_ENABLED=false
MAILBOX_INGESTION_ENABLED=false
CRM_READS_ENABLED=false
```

Encrypted workspace configuration must exist before an operation is eligible:

- Resend: workspace API token, `from_email` on a verified provider domain; an
  encrypted `webhook_secret` for the configured webhook endpoint; a matching
  sender identity. Receiving also needs the provider's receiving-domain/mailbox
  routing and permission to retrieve received/sent content. A sending-only key
  cannot be assumed to support all access checks or mailbox reads.
- HubSpot: private-app token with the relevant CRM object's read permission.
  Salesforce: workspace bearer token and allowlisted HTTPS `.my.salesforce.com`
  instance, with object/API read permission. No OAuth app configuration for these
  providers was created; rotation uses the existing owner/admin connection-update
  API, then a fresh provider access check.
- API responses explicitly separate application capability flags from a saved
  connection's health and actual object permissions. A successful identity/domain
  check is not proof of every provider scope, deliverability or webhook routing.

**Live verification remains BLOCKED.** Dedicated provider accounts/credentials,
verified domains, receiving routes, token scopes, signature delivery and real
network responses were not established. Operator opt-ins were enabled only by
test monkeypatches with deterministic synthetic credentials. No hosted state was
changed. Gmail/Outlook adapters and consent flows, CRM atomic write transports,
attachments, multi-recipient/forwarded inbox support and unsupported Resend event
types remain outside the implemented contract.

Future deployment/enablement requires explicit user authorization. A real email
test additionally needs reviewed exact recipient/content, message approval,
separate delivery-plan approval, provider quota/charge authorization and dedicated
test mailbox scope. CRM read verification requires approved dedicated account
access; real CRM writes additionally require a safe implemented write adapter and
explicit write approval. Google event verification requires its own consent and
event authorization. None of these approvals is inferred from this code push.

## Verification evidence

Provider HTTP was
deterministic; actual FastAPI HTTP routes and disposable SQLite persisted records.
Browser tests use real React → loopback HTTP → FastAPI → SQLite. They do not target
hosted staging or prove live-provider acceptance.

| Check | Exact result |
| --- | --- |
| Integration foundation + first provider-boundary pass | **PASS:** 41 passed, 681 warnings, 78.49s; exit 0. |
| Signed receipt recovery + RFC association pass | **PASS:** 15 passed, 617 warnings, 50.61s; exit 0. |
| Final provider boundaries, reconnection and retry-window protection | **PASS:** 18 passed, 772 warnings, 123.22s; exit 0. |
| Final strict UUID acceptance receipt validation | **PASS:** 4 passed, 0.49s; exit 0. |
| Final dispatch authentication failure/audit, uncertainty retry, signed receipt recovery and UUID receipt regression | **PASS:** 9 passed, 438 warnings, 26.16s; exit 0. Authentication rejection persists an error/reconnect-required connection and a redacted audit. |
| Broad backend regression: integration foundations, provider boundaries, outreach, draft review, inbox, outcomes, workspace security and configuration | **PASS:** 175 passed, 7135 warnings, 688.69s; exit 0. The final dispatch-audit/UUID refinements are additionally covered by the focused runs above. |
| Desktop/mobile complete safe customer journey and disconnected CRM connection through frontend → API → persistence → reload | **PASS:** 2 passed, 274 warnings, 427.69s; exit 0. |
| Frontend customer contracts | **PASS:** 17 passed, 0 failed, 2164.4682ms; exit 0. |
| TypeScript `tsc --noEmit` | **PASS:** exit 0, including the final frontend changes. |
| Vite production build | **PASS:** exit 0, client/SSR/Nitro generated. Existing tsconfig-paths and LoginPage split warnings remain nonblocking. |
| Targeted ESLint for integrations/outreach components | **PASS:** exit 0; existing prettier rule disabled for targeted lint, updated integration component formatted with Prettier. |
| Hosted/live provider delivery, ingestion and CRM permission verification | **BLOCKED:** not attempted; missing approved dedicated provider configuration and live verification. |
| CRM writes / Gmail / Outlook | **BLOCKED:** unavailable adapters/consent workflows; no fabricated transport success or weakened concurrency contract. |

Counts overlap and are not additive unique tests. Python runs used `-p no:cacheprovider`, distinct ignored
`.venv` basetemp paths, `--disable-warnings --tb=short`, and `--show-capture=no`
except the four strict receipt cases. Browser evidence is under
`.venv/provider-browser-tests/`; no provider secrets are committed. Test setup
explicitly sets all new operator flags false and enables them only with local
monkeypatches for the deterministic cases.

## Preservation and release status

No schema migration is required; the implementation reuses existing workspace,
integration audit, message, delivery event, inbox receipt and durable worker tables.
The existing customer journey and human approval gates remain in place.
`docs/V2_CUSTOMER_RELEASE_CHECKLIST.md` remains unchanged and excluded, Git blob
hash `1f215c9d1bc1cab51531b0d6c1caf5a8adde27b3`. Generated route-tree output is excluded.
Only reviewed, verified source/tests/config documentation are committed. No
deployment or main-branch change is authorized by this push. Full hosted readiness
remains **BLOCKED**.

## Provider contract references

- [Resend idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys)
- [Resend signature verification](https://resend.com/docs/webhooks/verify-webhooks-requests)
- [Resend received email API](https://resend.com/docs/api-reference/emails/retrieve-received-email)
- [Resend sent email API](https://resend.com/docs/api-reference/emails/retrieve-email)
- [HubSpot contacts API](https://developers.hubspot.com/docs/api-reference/legacy/crm/objects/contacts/guide)
