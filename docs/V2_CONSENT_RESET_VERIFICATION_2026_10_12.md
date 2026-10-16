# Inbox/Pipeline consent reset verification — 2026-10-12

Baseline: `d877d8ed41959359d77c420aafb845c1d8cd4247`, independently matched
against the remote V2 branch before changes. Existing recovery-target preflight
implementation and its four regression tests were inspected and retained.

## Defect and correction

Uncontrolled review forms retained old selections, reasons and checked consent
after their backing record revision changed. Their submit handlers meanwhile
used the new revision, permitting old consent to accompany newly loaded state.
Inbox reproduction failed with expected category `question`, actual `positive`
after an independent synthetic reviewer saved the newer classification.

Inbox now keys the review form by message ID and classification number; Pipeline
keys its form by pipeline ID and revision. A changed identity/revision clears
the draft and requires fresh consent. Same-revision request failures preserve
the draft. Existing authorization, optimistic concurrency, append-only history
and suppression protections are unchanged.

Regression coverage exercises concurrent Inbox review and refresh, a fresh
review saved through HTTP, consent reset after success, a Pipeline HTTP 503
without persistence, explicit retry, one persisted outcome history entry and
invalid native form state until fresh consent. Both desktop and mobile use
disposable local databases and synthetic provider fixtures. No hosted provider
acceptance follows from these tests.

## Executed local verification

- Browser: **PASS**, 2 passed (desktop 1280×900 and mobile 390×844),
  zero skips, 288.64 seconds. Real local HTTP/database persistence; provider
  behavior explicitly synthetic. The initial failing Inbox reproduction and
  corrected test-selector failures are not counted as acceptance passes.
- Frontend unit tests: **PASS**, 17 passed, zero skipped.
- TypeScript and frontend build: **PASS**. Customer-component correctness lint:
  **PASS**, zero errors and three existing fast-refresh warnings.
- Diff whitespace check: **PASS**. Full backend and the complete post-push CI
  matrix are reported separately with the exact committed SHA/run URL; this note
  does not pre-claim their results or a local PostgreSQL execution.

## Release gates

**74/100, unchanged; NO-GO.** This work strengthens already-awarded local review
and integrity criteria. It earns no new hosted acceptance points.

- Real recovery-host verification: **BLOCKED**. The user confirmed no verified
  free Linux host with IPv6, Docker, nftables and root access is available.
  The previous actual-target run remains BLOCKED before TLS; no repeat probe or
  chargeable provisioning was attempted.
- Protected archive integrity, original-key recovery, real isolated restore and
  compatible fallback rehearsal remain unverified. Synthetic restoration is not
  staging recoverability evidence.
- Complete old-executor shutdown/restart inventory and safe pinned activation
  remain required before a coordinated release. Current source is not deployed.
- Latest-version hosted desktop/mobile customer and provider acceptance remain
  blocked; research, email and CRM fixtures do not establish provider execution.

Next prerequisite is an independently protected, no-additional-cost recovery
host with verified routing and egress denial. After it is available, separately
authorize the named custodian's protected archive/original-key access and an
isolated restore into only `tyvqriqbfjnimtzageoj`, including migration/fallback
rehearsal. Expected writes are restricted to that disposable target and host;
cleanup must remove only approved test artifacts, preserving redacted evidence.
Conditional staging-release approval does not waive these gates. No deployment,
restart, live migration, material access or provider activation occurred here.

The pre-existing release checklist, generated route file and five untracked audit
documents are excluded from this change and preserved.
