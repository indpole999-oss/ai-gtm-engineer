# Reproduce the GTM demonstration pack

These eight focused examples complement the existing 39-stage flagship. Use fictional data only. No credentials, database, paid AI, provider calls or delivery nodes are required. Each export is inactive and uses built-in Manual Trigger + Code nodes.

## Configuration and execution

1. Use a disposable local n8n workspace, separate from existing databases. Bind local services to 127.0.0.1. Never import over an existing workflow.
2. Import a numbered JSON file via Import from File. Inspect its Manual Trigger and Code nodes; confirm there are no credentials or provider/action nodes.
3. The first Code node is the editable fixture. Keep its `return [{json:...}]` item envelope (qualification deliberately returns two items). Subsequent nodes process that data. Nothing reads real CRM contacts.
4. Execute manually and inspect the last Code node output against the table below.
5. Re-execute unchanged: business output should remain deterministic. No state persists between runs. Delete disposable imports when finished.

| Export | Example input | Expected output / business decision |
|---|---|---|
| 01 research | Aster, two source-tagged fictional facts | sourceCount 2; realWorldVerified false |
| 02 enrichment | Ridgeway, missing contact | two mock misses; email null; UNKNOWN_REQUIRES_REVIEW |
| 03 qualification | Aster + Ridgeway | two explainable scores: 100 and 0 |
| 04 draft | Aster research | PENDING_REVIEW; sent false; DRAFT_ONLY_NO_SEND |
| 05 CRM mock | lead-1 MQL, lead-1 SQL, lead-2 MQL | two records; merged 1; lead-1 SQL; no provider receipt |
| 06 calendar | 2026-10-20T14:00:00Z, 30 minutes | UTC end 14:30; eventCreated false; PREVIEW_ONLY_NO_BOOKING |
| 07 report | five events including repeated e3 | duplicate event excluded; fictional activity counts; no revenue claim |
| 08 journey | Aster prospect | score 100; pending draft; terminal gate STOP; DRY_RUN_REVIEW_REQUIRED |

## Failure and replay checks

- CRM mock requires an events array, non-empty string IDs and MQL/SQL stages. Invalid events throw before output. IDs use a Map, including `__proto__` and `constructor`. For repeated IDs, last event wins. This illustrates within-run deduplication, **not durable provider idempotency**. There is no cross-run store, write receipt, retry queue or transactional guarantee.
- Calendar requires an explicit timezone, a parseable timestamp and an integer duration of 1–480 minutes. Missing timezone, invalid dates and invalid duration fail before preview output. No availability API is queried.
- Journey requires a named prospect, finite nonnegative employee count and source-tagged evidence. Missing sources throw. Approval-state tampering fails at its terminal boundary.
- Outreach refuses sent/approved state at the stop node. Approval is demonstrated as a pending boundary: no webhook, actual approval service or downstream sender exists. Never add an action node to this demo.
- Empty enrichment results remain null rather than invented addresses. Review flags are data-quality cues, not verified identity.
- Errors are intentional fail-closed Code-node failures; they do not silently become success. No live-provider retry behavior is demonstrated.

## Local validation commands (repository root)

```sh
python -m unittest discover -s portfolio -p 'test_*.py' -v
node portfolio/tests/demo-state.cjs
node portfolio/n8n/tests/validate.mjs
node portfolio/n8n/tests/safety.mjs
node portfolio/n8n/flagship/validate_flagship.mjs
```

The Node harness evaluates Code-node JavaScript in a restricted simulation. It is not n8n. See runtime evidence separately for actual n8n CLI executions and the exact tested revision. Editing an export after a runtime test requires retesting.

## Demonstration script (about 3 minutes)

1. Show export structure and zero credentials (20 seconds).
2. Execute qualification; explain high/low fit with fictional inputs (30 seconds).
3. Execute missing-contact enrichment and show null/review status (25 seconds).
4. Execute CRM mock twice; explain last-event-wins and the lack of durable idempotency (30 seconds).
5. Execute draft/journey; show pending approval and STOP, with no sending capability (30 seconds).
6. Show calendar preview, then invalid timezone failure; show validator output (35 seconds).
7. End with limitations: synthetic evaluation, no customer outcomes, no verified external integrations (10 seconds).

This is a recording script, not a claim that a video was recorded. Review screenshots for tokens and personal data before sharing.

Actual negative-case and browser results: [milestone acceptance](../MILESTONE_ACCEPTANCE_2026-10-16.md).
