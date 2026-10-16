# Portfolio continuation verification — 16 October 2026

Base commit: `20cf67a7c22eada3b354e4e201b00f2acb593e72`.

## Observed hosting and source

PASS: homepage, work, writing, resources, about and signal-to-action case study returned HTTP 200 and matched the base checkout byte for byte. This is a point-in-time observation, not continuous uptime monitoring. Local HTML relative links resolved to existing files.

GitHub portfolio offline run 38811214366 succeeded. Product Validate run 38811214450 failed; this work does not diagnose or fix the separate product pipeline.

## Fixed demo regression

Changing the selected account previously retained the earlier account result and its approval. Selection changes now invalidate current review data, hide the stale result, clear the draft and disable approval until the selected account is executed. The regression test fails against the base script and passes against the fix.

PASS: `node portfolio/tests/demo-state.cjs` covers all three fixtures, in-memory approval, selection reset, stale approval rejection and rerun. This runs event handlers in a simulated DOM; it is not browser E2E.

PASS: 15 Python tests; eight n8n export simulation checks; flagship 39-stage harness with nine negative scenarios and two fail-closed cases. These are offline checks, not new live n8n/provider executions.

BLOCKED: independent Chromium layout/accessibility/browser QA. Playwright is available but its browser executable is absent; browser download returned an invalid archive. No browser-rendered screenshots are claimed.

BLOCKED: HubSpot read-only proof. Earlier local inspection found no HubSpot credential in the isolated DB; the original DB credential was not used because its app provenance was unverified.

## Change boundary

Portfolio-only changes include the demo reset fix, three hardened exports, runbook, safety tests, resources link, CI checks and evidence. No deployment, main/product edits, external CRM/calendar writes, email sends or paid API calls. Updated CI requires a new GitHub run.

## Workflow-pack hardening and current hosting

Render service `srv-db8iip6q1p3s73dg3iqg` is a static site with publish path `portfolio`, branch `portfolio/gtm-engineer-20261016` and auto-deploy off. Latest deployment `dep-db8kf4g473hc739udsu0` is live at base commit `20cf67a`. No deploy was requested.

CRM mock now handles reserved object-property IDs using Map and rejects malformed events. Calendar now rejects ambiguous timezone and invalid duration. Journey validates source provenance fields and refuses changed approval state. `tests/safety.mjs` passes replay, invalid input, timezone and bypass cases. These controls remain simulations, not provider guarantees.

Measured five whole-process eight-export harness runs (Node v24.19.0, Linux): 155.60, 90.19, 87.99, 71.47, 75.93 ms; median 87.99 ms. Includes process startup and VM simulation; not n8n execution latency, provider performance, throughput or customer ROI. Reproduce with five timed invocations of `node portfolio/n8n/tests/validate.mjs`; machine/runtime load will change timings.

Actual eight-export import/runtime acceptance was started on authorized Windows n8n 2.25.7 in fresh `GTM-Local-Test/pack-runtime-20261016` with independent broker port 5684 and loopback binding. All eight baseline runs subsequently passed with success/finished flags and expected final outputs. See `n8n/RUNTIME_EVIDENCE_2026-10-16.md`. Existing original and flagship test databases were not changed by this new import.
