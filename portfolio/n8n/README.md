# Portfolio n8n Workflow Exports

These are eight genuine n8n-shaped JSON workflow definitions using **Manual Trigger** and **Code nodes** only. All are inactive, use fictional fixtures, and make **no network requests** or external writes.

Import the JSON in n8n using **Workflow menu → Import from File**. Official guidance: https://docs.n8n.io/build/manage-workflows/export-and-import

**Actual local runtime verified:** all eight exports were imported and executed successfully on n8n 2.25.7 in a fresh isolated Windows database on 16 October 2026. [Runtime evidence](./RUNTIME_EVIDENCE_2026-10-16.md) records outputs, timings and limits. Six malformed-input and approval-bypass cases also passed actual n8n fail-closed acceptance; replay tests remain Node-harness checks. [Milestone evidence](../MILESTONE_ACCEPTANCE_2026-10-16.md). No live provider integration is claimed. No credentials required.

See [the demonstration runbook](./DEMO_RUNBOOK.md) for per-workflow inputs, expected outputs, errors, replay limitations and a recording script. Run `node portfolio/n8n/tests/safety.mjs` for malformed input and approval-boundary cases.

## Workflows

1. [Account Intelligence](./01-account-research.json) — 3 Code nodes; offline example
2. [Mock Enrichment Waterfall](./02-enrichment-waterfall.json) — 4 Code nodes; offline example
3. [Explainable ICP Qualification](./03-icp-qualification.json) — 3 Code nodes; offline example
4. [Human-Reviewed Outbound Draft](./04-outreach-draft-review.json) — 3 Code nodes; offline example
5. [CRM Idempotency Mock](./05-crm-deduplication.json) — 3 Code nodes; offline example
6. [Calendar UTC Preview](./06-calendar-preview.json) — 3 Code nodes; offline example
7. [GTM Activity Reporting](./07-gtm-event-report.json) — 3 Code nodes; offline example
8. [Controlled GTM Journey](./08-gtm-orchestrator.json) — 6 Code nodes; offline example

## Safe manual verification

1. Import into a disposable n8n workspace and verify *inactive* and no credentials.
2. Run **Execute Workflow** manually.
3. Verify the final JSON has no email sends, provider calls, CRM writes or event creation.
4. Keep these demos separate from authorized live integrations.

For live Clay, HubSpot and Google Calendar case studies, we will need explicit sandbox connections, authorization for each external write, provider receipts and error-path testing.
