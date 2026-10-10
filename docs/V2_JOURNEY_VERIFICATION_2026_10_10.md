# V2 journey verification — 2026-10-10

Branch: `codex/ai-gtm-engineer-v2-full-build`; base commit
`20c37e45da758747448cc8f262149c087b494902`, plus the local changes described here.
At initial verification these changes had not been pushed or deployed. The pre-existing edit to
`V2_CUSTOMER_RELEASE_CHECKLIST.md` is preserved.

## Changes

- Outreach enrollment offers completed research only for the selected contact's
  account. Changing contact clears the research selection, including when the
  other contact has no completed research. Server checks remain authoritative.
- Primary buttons retain their visible arrow but omit it from accessible names.
  Chromium reproduced the original `Add account →` name; exact button-name
  interaction now exercises the fix.
- Replaced a damaged separator in the latest research failure label.
- Added opt-in Chromium journey coverage and a separate Linux CI job with a
  ten-minute timeout, browser traces, screenshots and seven-day artifact retention.

## Verification scope

The browser drives real React forms, calls FastAPI over loopback HTTP, and reads
back records from disposable SQLite. Brain editing, reviewed claim publication,
account/contact creation, goal/plan preparation, exact-plan refresh, research
approval, campaign/sequence/version creation, enrollment, draft preparation, both
approval checkpoints, inbox, pipeline and insights use the existing application.
Worker sweeps use the real worker via the test harness.

Only external boundaries are fixtures: source retrieval/model analysis,
sender identity provisioning, durable mail acceptance and inbound receipt ingestion.
The browser blocks requests outside its two local application origins. Hosted AI
stays disabled. No real email, hosted database mutation, production change, paid
AI call, Calendar write or CRM write was performed.

The test asserts no send before both approvals, exactly one fake provider send,
no repeated dispatch, Brain hash lineage, account qualification from persisted
research, incompatible research selection clearing, a classified meeting-intent
reply, interested contact pipeline state, and `1 sent · 1/1 replied` in Insights
after refresh. Meeting intent does not imply a confirmed meeting. Delivery is not
inferred from fake provider acceptance.

## Results

| Check | Status | Exact evidence |
| --- | --- | --- |
| Backend regression | PASS | `python -m pytest -q`: 316 passed, 2 skipped, 8045 deprecation warnings, 1158.17 seconds. Collected before the new browser test was added. |
| Frontend contracts | PASS | `node --test tests/customer.test.mjs`: 7 passed, 0 failed. |
| TypeScript | PASS | `node node_modules/typescript/bin/tsc --noEmit`: exit 0. |
| Changed frontend correctness lint | PASS | ESLint on outreach/prospects with the existing Prettier exemption: exit 0. |
| Final production build | PASS | `node node_modules/vite/bin/vite.js build`: exit 0; client, SSR, Nitro and `.output/nitro.json` completed outside the restricted process environment. |
| Initial desktop browser journey | PASS | Complete journey: 1 passed, 126 deprecation warnings, 48.62 seconds. External success is deterministic fixture evidence only. |
| Final desktop/mobile browser journey | PASS | `RUN_BROWSER_E2E=1 python -m pytest -q tests/test_browser_journey.py -x -p no:cacheprovider --basetemp=.venv/browser-e2e-final2 --tb=short --disable-warnings --show-capture=no`: 2 passed, 252 deprecation warnings, 154.02 seconds; 1280×900 and 390×844. Both completed all journey stages and the Insights viewport overflow assertion. |
| Existing API journey modes | PASS | `python -m pytest -q tests/test_v2_journey.py -p no:cacheprovider --basetemp=.venv/api-journey-final --disable-warnings --show-capture=no`: 2 passed, 420 deprecation warnings, 17.11 seconds; both guided-template and injected local-AI planning modes. |
| PostgreSQL boundary/restore | BLOCKED | Two suite skips: no explicitly configured disposable `POSTGRES_TEST_URL`. Existing CI jobs are retained; no new CI execution claimed. |
| Hosted staging full E2E / live providers | BLOCKED | Not exercised in this continuation. Existing hosted AI pause and live research/qualification acceptance gaps remain. Real model output, sender/provider receipts and real replies require separately authorized verification. |
| Customer readiness | BLOCKED | Deterministic local E2E does not establish hosted staging, real-provider, multi-user, operational or release acceptance. |

Earlier failed attempts were resolved: missing declared `pypdf` dependency;
restricted-process Vite startup/Nitro readlink permission; inaccessible shared
pytest temp directory; absent Chromium runtime; select-label matching; expected
HTTP 201 approval response; a hidden source excerpt selector; and missing reviewed
Brain claims in initial synthetic onboarding. A traced run also exceeded the default
five-second assertion timeout while the page was still loading; assertion waits
now use the same twenty-second limit as other UI actions. No application validation
was relaxed to pass.

Saved local browser evidence is under `.venv/browser-e2e-final2/`:
`test_browser_customer_journey_0/` is desktop and
`test_browser_customer_journey_1/` is mobile. Each contains `journey.zip`,
`insights.png`, `frontend.log` and the durable fake mail ledger `provider.db`.
The trace records synthetic UI, HTTP responses and identifiers; test authentication
is disposable. Application SQLite is removed by the existing test fixture on
completion. The traces are local evidence; the newly added CI job has not run.

## Reproduce

Install the repository's existing Python/frontend dependencies and Playwright
Chromium, then run from the repository root (PowerShell):

```powershell
$env:RUN_BROWSER_E2E='1'
.venv/Scripts/python.exe -m pytest -q tests/test_browser_journey.py --basetemp=.venv/browser-results
```

Use a fresh test-owned directory if Windows permissions differ between executions.
For this machine Chromium was installed under `.venv/browser-runtime`; set
`PLAYWRIGHT_BROWSERS_PATH` to that absolute path when reusing that installation.
The test launches and shuts down its own frontend and API processes. Without
`RUN_BROWSER_E2E=1`, browser cases are explicitly skipped, never reported as PASS.
The dedicated CI job sets this switch and installs Chromium before running.

## Synchronization with remote V2 history

The original local commit `18aa5762121da95b2baaba947a8009e6b9588ed3` was
rebased onto `17d1a502d8087a34a07fa50213cc4a717534c655`. All intervening remote
commits are retained, including immutable draft revisions, submit/review decisions,
workspace-scoped Calendar OAuth, and the independent Approval Queue empty state.
Outreach merged automatically. The only rebase conflict was competing readable
research-error separators in Prospects; the local dot separator was retained.

The merged Approval Queue had a TypeScript undefined-data error. Rendering now
uses an empty scheduled-record list until data arrives, while keeping the remote
empty-state condition independent of scheduled records. The browser test now
submits drafts, refreshes, reviews them through Approval Queue, approves the message
only, and separately opens delivery authorization. It asserts the queue is empty
both before any scheduled record exists and after approval, with no provider call
before separate authorization. Existing accessibility and account-specific research
selection fixes remain in place.

The test-session initializer is restricted to the local application origin to
avoid blank-document localStorage errors. Initial navigation explicitly waits for
the authenticated app shell to hydrate (up to sixty seconds); interactions retain
their twenty-second limit. Two earlier post-rebase attempts timed out before the
Brain editor could be used. Application validation was not bypassed.

The release-checklist edit was saved in path-specific stash
`cdb0ab85b2d657e1483fa3e90098aa7bee4b79b8`, then restored. Its Git content hash
before and after restoration is `1f215c9d1bc1cab51531b0d6c1caf5a8adde27b3`.
The edit is excluded from the synchronized commit; the stash backup is retained.
The generated route-tree rewrite has no textual changes and is excluded.

Post-rebase checks: TypeScript exit 0; frontend contracts
17 passed; complete frontend production build exit 0; targeted correctness lint
exit 0; deterministic draft-review/outreach/API-journey suite 37 passed,
2391 deprecation warnings in 223.41 seconds. Desktop and mobile Chromium customer
journeys: 2 passed, 262 warnings in 320.26 seconds. Traces and screenshots are in
`.venv/rebase-browser-tests3/`. Browser checks use only deterministic provider
fixtures and disposable local persistence; no real emails or paid AI calls.
These results supersede the initial verification for merged code;
the initial 316-test suite above is historical and was not rerun after the rebase.
