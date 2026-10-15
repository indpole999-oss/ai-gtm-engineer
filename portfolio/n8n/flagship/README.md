# Signal-to-Action GTM Engine — Enterprise-Style Portfolio Case Study

**Status:** Offline test suite passes, and **two real n8n 2.25.7 CLI executions passed** in a separate, inactive Windows test database (baseline and all-DNC negative path). Clay, HubSpot, Google Calendar and real business outcomes remain **unverified**. Built on an isolated portfolio branch; GAPS AI production is untouched. [See local runtime evidence](./LOCAL_N8N_RUNTIME_EVIDENCE_2026-10-16.md).

## Why this is different from toy automations

This flagship system models a real RevOps problem: account/prospect signals must survive incomplete data, false-positive matching, repeated enrichment, stale intent, customer and deal suppression, owner routing, approvals, and measurable execution history **before anyone is contacted**.

The workflow contains **39 meaningful Code-node processing stages**, one manual trigger, a genuine **IF** node with populated true/false paths, and 12 explanatory sticky notes. It is inactive and has no HTTP Request, Gmail, HubSpot, Clay, SMTP, or Calendar action nodes.

### Source → controls → revenue operations → action review

\`\`\`text
Fictional CRM + buyer signals
    |
    v
Policy / contract / deterministic run clock
    |
    v
Account & contact identity resolution ----> Quality incidents and rejected duplicates
    |
    v
Signal freshness + evidence provenance ---> Stale signal quarantine
    |
    v
Mock enrichment waterfall ----------------> Zero spend and NULL preservation
    |
    v
Firmographic + persona + intent scoring --> Explainable 100-point scores
    |
    v
Suppression matrix: customer, open deal, unsubscribe, DNC, consent, cooldown,
email validity and founder-owned exec contacts
    |
    v
Territory / account-owner rules -> SLA tier -> action idempotency keys -> batch cap
    |
    v
Evidence-only outreach draft -> HUMAN APPROVAL REQUIRED
    |
    v
Simulated CRM/task handoff, audit receipts, 0 live writes
    |
    v
Reconciliation + invariants -> IF review queue available?
   / \
yes  no
 |    |
Review queue (never send)   Empty-queue auditable report
\`\`\`

## Reproducible evidence

Requires **Node 22**, no API keys, DB, paid AI or network:

\`\`\`bash
node portfolio/n8n/flagship/validate_flagship.mjs
\`\`\`

### Baseline synthetic run

- **7 fictional accounts, 14 fictional contacts, 6 fabricated signals** in fixture.
- Duplicate handling: **1 account + 1 contact + 1 signal** deduplicated without fuzzy substring merging.
- **7 contacts suppressed** for independently recorded policy reasons.
- **4 remaining eligible**, **3 review-only draft actions** after run quota.
- **0 external HTTP/provider calls, 0 emails sent, 0 CRM writes, 0 calendar bookings, 0 paid credits**.
- Exact name-match and DNC protections keep related but distinct brands separate.
- Owners, priority scores, and suppression explanations are recorded with every planned review item.

### Test coverage and what it proves

Local validation executes the entire **39-stage JavaScript chain** with a compatibility shim for n8n \`$input.all()\` and checks both IF outcomes. It covers:

1. Unsubscribe-all yields no review queue
2. No signals yields no review queue
3. Run quota limits actions
4. Strict account-fit threshold rejects actions
5. Missing consent suppresses all
6. Expired signals suppress signal-led action
7. Invalid evidence provenance removes eligible signal
8. Orphan CRM reference is blocked
9. A newly flagged DNC record cannot escape duplicate merge
10. Unsafe live-write policy fails closed
11. Nonzero credit cap fails closed
12. Deterministic repeated fixture executions return identical JSON

**Limit:** None of the above tests is a live n8n execution, measured staff time saving, prospect research accuracy, email delivery, or proof of a customer result. Deterministic action keys are modeled but not persisted in a production transactional ledger.

## n8n import / change control

- File: [gtm_signal_to_action_39_stage.json](./gtm_signal_to_action_39_stage.json)
- Import into a **disposable/non-production n8n workspace**.
- Verify inactive/manual-only, no credentials, no HTTP/outbound action nodes.
- Execute by hand. The final **IF** routes to review-queue or empty-audit output.
- Take n8n run ID, node screenshots, output JSON, timestamps and operator/version notes.
- Do not activate a schedule or add live write nodes without a sandbox plan, approval scope, readback tests, and rollback.

## Roadmap to true commercial proof

1. Connect Clay and HubSpot sandbox only, with approved permissions; add real source-data contracts and cost controls.
2. Prove idempotent and reversible CRM test writes with receipts and readback.
3. Approve a closed-loop test recipient/meeting; no mass email or existing customer data.
4. Measure human baseline research minutes vs automated minutes across an authorized sample and publish raw measurement method.
5. Capture 2–3 minute n8n Loom video on the actual workspace and document failure modes.
6. Publish customer outcomes and testimonials only with the owners' permission.

Inspired by the **engineering bar** of practitioner portfolios like Neeraj Kumar and Jorge B. Macías; no source code, client results, or testimonials copied.
