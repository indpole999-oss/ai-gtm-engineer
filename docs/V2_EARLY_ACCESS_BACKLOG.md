# V2 Early Access verification backlog

## Current continuation — 2026-10-02

- Resumed remote `0be2df8` without repeating its implementation. CI run
  `36981076689` passed. Older local unfinished changes remain preserved in a
  named stash; only non-overlapping fixes were recovered.
- Validated frontend deployed to the existing Free staging service:
  `dep-davsjp67bikc73faant0` is live on `0be2df8`. API remains on `0e498b5`
  (backend code is identical between those checkpoints). No environment changes.
- Authenticated in-app browser verified actual identity, truthful zero healthy
  connections, existing synthetic guided draft v1 and restoration after full
  refresh. Approval remains unchecked/disabled. No new goal, approval, execution
  or provider call occurred during this continuation. Old executions remain failed.
- P1 found in-browser: selecting an older execution leaves an unrelated draft
  above it. Follow-up loads its associated plan, resets review and blocks selection
  during unsaved edits. Selecting a plan clears the previous execution selection.
- Recovered fixes: mobile workspace selector; expected HTTP rejections roll back
  without misleading database-outage logs; unexpected failures retain exception
  type without raw credential-bearing detail.
- Useful P2: owner/admin Settings surfaces existing tenant-scoped execution and
  approval inventory plus retention decisions. Manual refresh and failure/lease/
  queue alerts; no invented cost, worker-health assertion or retention policy.
- Focused backend: **6 passed** (rollback/log safety, operations tenant/RBAC,
  retention). Frontend: **7 contract tests passed**, TypeScript and changed-file
  lint passed. Follow-up CI and deployed-browser validation are recorded separately.

### Still open, not waived

Hosted AI and embedded worker remain paused. Live-model quality, worker
availability and email/CRM/calendar delivery are not validated. Live-provider
acceptance, operational/backup rehearsal and retention/privacy release decisions
remain required. Earlier sections below are historical evidence.

## Scope and evidence — 2026-10-01

- Repository: indpole999-oss/ai-gtm-engineer, existing V2 branch and draft PR #2.
- Web: https://gaps-ai-v2-staging-web.onrender.com
- API: https://gaps-ai-v2-staging-api.onrender.com
- Isolated staging database: xhjkahbtckrrhuzamysr. No production access.
- Observed deployment baseline: web ebc8f2c; API a661b22. Auto-deploy off.
- Approved obsidian/green design and navigation retained.

## P0

| Finding / gate | Current evidence |
| --- | --- |
| Backend CI fails because HTTP lifespan starts worker before test schema exists | Local regression: 265 passed, 2 PostgreSQL-only skips; final worker opt-in revision: 6 passed. New-commit CI pending. |
| Frontend TS4111 blocks CI build | Fixed typed dictionary access; TypeScript and contract tests pass. Linux production build pending. |
| Hosted AI planning calls loopback Ollama | Groq adapter now selected consistently with research; fake HTTP and policy rejection tests pass. Real provider acceptance pending. |
| Groq strict schema omits defaulted nested fields from required | Normalized both schemas; local validation remains authoritative. Fake transport only. |
| Untrusted robots wildcard regex can backtrack excessively | Replaced with literal segment matching; adversarial rule regression included. |
| Authenticated primary browser journey | Awaiting user sign-in directly in in-app browser. No credentials requested in chat. |

## P1 — remaining inspection and acceptance

2026-10-02: browser confirmed an expired-session dashboard. Fixed same-session
401 invalidation, stale-response protection and cache clearing. Integration UI
no longer reports custom-save success before the response, labels unverified
configuration truthfully, and confirms local disconnect. Browser verification of
the deployed fixes remains open. All CI for 4021e72 passed (run 36891654467).

- Verify workspace membership/role refresh and logout/login cache isolation.
- Improve safely classified research/provider failures and persisted run feedback.
- Verify all visible routes/actions, errors, empty states, responsive layout and
  keyboard access using a staging-only account and synthetic records.
- Prove login → workspace → published Brain → goal → real AI plan → review →
  approval → queued work → research/evidence → prospect → outreach draft → review;
  verify refresh persistence and logout/login return.
- Verify staged worker restart/lease recovery and safe admission/ready behavior.
- Check integration test states against actual adapter support. Email, CRM and
  calendar writes remain disabled; fixture receipts do not prove live delivery.
- User chose to keep hosted AI paused. GTM_HOSTED_AI_ENABLED and embedded worker
  remain false; real-model acceptance is blocked on a later explicit opt-in and
  free-only account confirmation. Do not infer no cost from a key.
- Retention decisions and live-provider/operational gates remain open in
  V2_PRODUCTION_READINESS.md and V2_STAGING_VALIDATION.md.

## P2

- Address Fast Refresh warnings if component extraction is otherwise warranted.
- Review empty-state copy and terminology after the core browser journey.

## Release decision

Not ready for Early Access acceptance or production deployment. Green local
tests alone cannot close authenticated-browser, real-provider, operational or
privacy/retention gates. No schema migration is introduced by this repair batch.
## 2026-10-02 — guided-plan refresh continuation

Resumed the existing `0e498b5` checkpoint; its GitHub CI is green. Authenticated staging reproduced a saved guided plan disappearing from view after refresh (the record itself remained persisted).

Changes in this checkpoint:
- Restore selected saved plan and execution by opaque, workspace-scoped URL IDs; fetch persisted records through authorized APIs. Approval acknowledgement and unsaved edits never persist in the URL.
- Restore saved revisions, offer explicit discard of unsaved edits, and recover goals whose plan preparation failed without creating another goal or calling AI.
- Refresh workspace membership every 30 seconds/on focus; role changes reset routed controls and clear account data caches. Revoked workspace membership removes the active view.
- Scope account research queries to workspace, cancel reads, enforce viewer controls and refresh the actual shared goals cache.
- Replace hardcoded identity, fabricated goal progress and zero-connection success labels with authenticated identity and persisted evidence. Distinguish guided, local and hosted plan provenance; show persisted command failure codes.

Validation: seven frontend contract tests and TypeScript passed; changed-file lint passed with one existing Fast Refresh warning. Disposable local SQLite browser fixture (synthetic account, all provider settings excluded, hosted AI and worker disabled) proved saved plan v1 and revised v2 survive refresh, approval resets, and discard restores the saved revision. No plan was approved or queued. Client/SSR production compilation passed; Windows Nitro packaging still hits the known EPERM readlink limitation. Linux CI is required before staging rollout.

This is frontend/offline evidence, not live model, provider delivery, production-like worker or PostgreSQL rehearsal evidence. Hosted AI remains paused. Staging deployment and further browser checks are recorded separately when completed.
