# Local n8n runtime validation — 2026-10-16

**Status: PASS for two real n8n CLI executions against an isolated SQLite test instance.** This is not a production integration test and does not establish business impact.

## Test environment

- Runner: n8n **2.25.7**, installed on an authorized Windows computer with Node.js 24.15.0.
- Execution method: `n8n import:workflow` followed by `n8n execute --id=...` using n8n's built-in JavaScript task runner.
- Data isolation: `N8N_USER_FOLDER` points to a *separate local test database*; independent runner broker port 5682, localhost address, no public tunnel.
- Existing instance: original SQLite database has **20 workflows before and after**; no original workflows were imported over, modified, activated, or executed.
- Backup: an on-device SQLite-consistent database backup and local instance config copy were created before testing. Backup files and secrets are not committed or uploaded.
- Workflow was explicitly inactive; only Manual Trigger, Code, IF and note nodes exist; no network, email, CRM or calendar action nodes.
- Initial import into empty isolation database failed because CLI requires workflow `id`; adding a unique test-only ID resolved it. First execution attempt also hit the existing n8n task-runner port; separate port fixed the conflict.

## Actual runtime test A — baseline

- Workflow imported successfully; n8n reports **`status: success`**, `finished: true` and **42 executed graph nodes**.
- Deduplication: 7 account rows → 6 accounts; 14 contact rows → 13 contacts; 6 signal rows → 5 signals.
- **7 blocked contacts**, **2 low-fit contacts**, **4 eligible contacts** before action cap.
- **3 review-required drafts**, **3 approvals pending**, **1 quota-deferred contact**.
- The IF routing node selected **`Ready for human review (NO SEND)`**.
- Confirmed **0 external calls, 0 emails, 0 CRM writes, 0 calendar writes and 0 credits spent**.

## Actual runtime test B — negative path

Test-only seed modification marked every fictional contact as do-not-contact. This modification was made in a *separate isolated imported workflow*, not in the portfolio canonical JSON.

- n8n reports **`status: success`**, `finished: true`, **42 executed graph nodes**.
- **13 blocked contacts**, **0 eligible contacts**, **0 planned drafts**, **0 approvals pending**.
- The IF node took **`No eligible leads — report only`**, with `EMPTY_QUEUE_AUDITED`.
- Confirmed **0 external calls, 0 emails, 0 CRM writes, 0 calendar writes and 0 credits spent**.

## Remaining acceptance gaps

Actual n8n execution is verified for these two synthetic scenarios. Still **not verified**: live Clay enrichment, authenticated HubSpot read/write, Google Calendar event creation, live-email sending, retries against real providers, real customer outcomes, UI walkthrough screenshots, or production scale. These must be tested separately with authorized test accounts and controlled, evidence-backed writes. This evidence does not claim any actual prospect was contacted.

## Independent test checks

- <https://github.com/indpole999-oss/ai-gtm-engineer/actions/workflows/portfolio-flagship-validation.yml>
- <https://github.com/indpole999-oss/ai-gtm-engineer/tree/portfolio/gtm-engineer-20261016/portfolio/n8n/flagship>
