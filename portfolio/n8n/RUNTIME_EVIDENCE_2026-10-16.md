# Eight-workflow local n8n acceptance — 16 October 2026

Tested export revision: GitHub `e95d7b78ad85ae81efac145385ceb02bfd08aa05`. This evidence update changes documentation only.

PASS: imported eight workflows, then executed each once through installed n8n 2.25.7 CLI on the authorized Windows device. Every execution JSON reports `status: success` and `finished: true`. Final node output was inspected, not inferred from exit code alone.

Fresh database: `GTM-Local-Test/pack-runtime-20261016/.n8n/database.sqlite`; separate broker port 5684; loopback 127.0.0.1. No existing workflows were overwritten. Imported test copies received unique IDs `portfoliopack2026101601` through `08`; canonical export JSON remains reusable without those IDs. All workflows inactive, no credentials, Manual Trigger and Code nodes only.

| Export | Executed graph nodes | Execution duration ms | Observed terminal output |
|---|---:|---:|---|
| 01 research | 4 | 2893 | sourceCount 2, needsReview false, realWorldVerified false |
| 02 enrichment | 5 | 2059 | two mock misses, email null, UNKNOWN_REQUIRES_REVIEW |
| 03 qualification | 4 | 1948 | two results, scores 100 and 0, humanReview true |
| 04 draft | 4 | 2085 | PENDING_REVIEW, sent false, providerReceipt null |
| 05 CRM mock | 4 | 2261 | 2 records, merged 1, lead-1 SQL, externalWrites 0 |
| 06 calendar | 4 | 2319 | 14:00–14:30 UTC, eventCreated false, pending approval |
| 07 reporting | 4 | 2474 | 4 unique events, 1 duplicate, no revenue/meeting claims |
| 08 journey | 7 | 2039 | score 100, pending unsent draft, terminal STOP |

Durations are each execution's stoppedAt minus startedAt, one synthetic run per export. CLI wall times including startup ranged 11084–15487 ms. Not throughput, production scale or customer performance. No latency SLA implied.

All terminal outputs report externalCalls 0. Export node inspection finds no network/provider action nodes. No email, external CRM write, calendar booking or paid API request was executed by this pack.

Initial import attempt failed because PowerShell did not forward the constructed --input argument. Corrected by passing a single concatenated argument; retry printed “Successfully imported 8 workflows.” Only the disposable test instance was used. An initial summary parser expected UTF-8; PowerShell logs were UTF-16LE. Corrected parser recovered the execution JSON; no raw logs or credential/session fields are published.

## Reproduction

Follow [DEMO_RUNBOOK.md](./DEMO_RUNBOOK.md). For CLI use, set N8N_USER_FOLDER to a new disposable directory and N8N_RUNNERS_BROKER_PORT to an unused port; add unique IDs to import copies if required by the installed CLI. Run `n8n import:workflow --input=<absolute-file>` and `n8n execute --id=<test-id> --rawOutput`. Keep raw execution logs local; publish only sanitized status/output summaries.

## Limits

Baseline executions only. Safety cases in `tests/safety.mjs` pass in a Node VM harness; not yet run as negative cases in actual n8n. These examples do not prove durable idempotency, real approval service operation, provider retries or Clay/HubSpot/Calendar access. Existing flagship has its own separate two-run evidence. No demo video recorded; recording script prepared. Full browser visual/accessibility QA remains blocked by unavailable Chromium download.
