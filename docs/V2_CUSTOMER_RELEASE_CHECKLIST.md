# Customer release checklist

Status uses only PASS, BLOCKED, or NOT YET VERIFIED. Tests alone never establish
customer acceptance. Scope: existing V2 staging; production release is blocked.

| Customer gate | Status | Evidence / remaining requirement |
| --- | --- | --- |
| Existing Brain → guided Vercel plan → review → refresh | PASS | Staging browser + SQL on 2026-10-04: published Brain 3d5e60fe-6091-49d6-a0f3-07bfc4cab88a; saved plan 79e52388-796e-4ef8-b481-255f984458f8; approval recorded against exact hash. Full onboarding remains below. |
| Real source retrieval and retained capture after failed analysis | PASS | Vercel capture 5851857a-749f-4756-b3c3-c50d3a2320df, 3,693 characters; browser/API/SQL readback; failed Groq analysis did not remove it. |
| Worker polling and restart recovery on awake staging | PASS | 18 database sweeps, clean redeploy stop, new instance with repeated sweeps; free-instance idle sleep remains a topology limitation. |
| Real research → span evidence → qualification | BLOCKED | Last live call returned HTTP 200 but old excerpt contract rejected Unsupported claim. New span contract requires a newly authorized controlled live test; hosted AI stays paused. |
| Signup/login/session/refresh/logout/workspaces/roles | NOT YET VERIFIED | Existing signed-in staging readback and local role tests do not establish full live multi-user acceptance. |
| Company Brain creation and complete customer onboarding | NOT YET VERIFIED | Published version readback proven; full hosted onboarding still required. |
| Personalized outreach draft → human approval | BLOCKED | Await validated real research; no new model authorization. |
| Real email send/provider receipt and idempotent recovery | NOT YET VERIFIED | No live customer send accepted. |
| Inbox/reply handling | NOT YET VERIFIED | Requires real send/reply provider evidence. |
| Pipeline and Insights reflect real outcomes | BLOCKED | No accepted live qualification/outreach journey yet. |
| Calendar connection test create/readback | PASS | Historical real Google event a8dc0553d0b253788166c49f6d8b7841, browser refresh/provider readback and one persisted meeting; see V2_EARLY_ACCESS_QA.md. Do not repeat without regression. |
| Calendar execution in full approved customer journey | NOT YET VERIFIED | Connection test is not approved-worker meeting/invitation acceptance. |
| CRM execution | NOT YET VERIFIED | Real provider outcome and retry acceptance needed. |
| Mobile + desktop full journey UX | NOT YET VERIFIED | Prior viewport checks cover only partial journey. |
| Error/retry/reconnect behavior | NOT YET VERIFIED | Research rejection is honest; remaining live providers/reconnect flows unverified. |
| Privacy/retention decisions | BLOCKED | Customer retention periods and operator decisions remain outstanding. |
| Pricing | NOT YET VERIFIED | Customer-facing pricing needs acceptance. |
| Support/contact | NOT YET VERIFIED | Customer support path needs acceptance. |
| Legal pages | NOT YET VERIFIED | Legal content and links need acceptance. |
| Onboarding/demo/customer guidance | NOT YET VERIFIED | Full customer guidance needs acceptance. |
| Secrets/security/logging | NOT YET VERIFIED | Regression tests and scoped logs are not a complete live security release review. |
| Production deployment and rollback readiness | NOT YET VERIFIED | No production changes authorized; runbook/recovery acceptance required. |

## Span contract (source-span-v1)

Immutable SourceFetch content is hashed and split into exact 1,200-character
slices without normalization. UUIDv5 IDs bind capture ID, content hash, version,
and start offset. Every slice is persisted as an immutable EvidenceItem before
analysis. Only complete spans within the first 30,000 source characters are
offered to the model, preserving the prior prompt budget. References outside
that offered set, including another job's identically worded capture, fail.
Retry reuses the same capture and EvidenceItem IDs/text; integrity mismatches fail.

Model output contains span_id, never a reproduced excerpt. Provider assertions
require null text and resolve to the exact persisted span. Paraphrases are only
accepted as labeled model inferences with a real span reference; a citation is
not independent verification. Unknown claims have no span and require text;
unknown fit is valid and does not qualify the account. Buyer name/title/email
must occur together in at least one cited span. Empty or unsupported buyers fail.

No schema migration, new credentials, legacy execution engine, relaxed approval,
source policy, or provider fallback is introduced. Existing reports remain
readable; legacy evidence has no span_id. Captured spans are source material, not
accepted claims or qualification results.
