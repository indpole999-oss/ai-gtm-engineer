# Phase 9 — Insights and GTM Gap Intelligence

`GET /api/v1/insights?start=<offset-aware ISO time>&end=<offset-aware ISO time>&entity_type=contact`
returns workspace-scoped descriptive analytics. `entity_type=account` selects
account pipelines instead. All active workspace roles can read; unauthenticated,
inactive and foreign-workspace access follows the existing membership boundary.
There are no analytics write, approve, schedule or execute routes.

## Evidence and reproducibility

The versioned `gtm-insights-v1` projection reads canonical Phase 3–8 records:
research reports and jobs, immutable draft envelopes, provider-confirmed messages,
delivery events, inbound messages and append-only classification versions,
pipeline history, confirmed outcome receipts and execution cycles. Each normalized
event has a stable source identity, occurrence/recording times, dimensions,
evidence references and an execution-cycle link where available. Worker attempts,
outbox deliveries and command retries are not business outcomes.

No additional tables or schema changes are needed: normalized events are a
read-only projection, not a second event log or execution system. Existing
Alembic revision `20260926_0012`, forced PostgreSQL RLS and composite tenant keys
remain authoritative. NULL-workspace legacy records remain quarantined.

Reports include the complete normalized evidence manifest, algorithm version,
workspace, date range, evidence hash, report hash and generation timestamp. Retain
the response to audit a recommendation. The pure `build` function can reproduce
the report from that manifest, version, workspace and date range; generated_at is
intentionally excluded from the deterministic hash. Source-reference IDs resolve
through the existing workspace-scoped canonical APIs. No recommendation is
persisted as an approved plan. Reports do not promise a materialized historical
database snapshot: late-arriving evidence may change a later response, and the
manifest records exactly what was used. Each source is capped at 20,000 rows;
larger workspaces fail explicitly rather than return truncated metrics. A future
batched reporting path is required beyond that limit.

## Metric definitions

- UTC `[start,end)` intervals require explicit offsets, start before end, and no
  future end. Both occurrence and recording must precede end. Latest classification
  means the highest persisted classification version recorded before end.
- Funnel cohort: distinct account OR contact pipelines discovered in the interval.
  Accounts and contacts are never combined in a denominator. Stage-entry counts
  require actual applied history. Conversion requires both stages observed in order;
  a skipped stage is never filled in. Won/lost are separate opportunity branches.
- Current-stage counts use the latest applied history as of end. Historical entries
  stay visible after a correction. Equal-time conflicting final entries are reported
  as ambiguous and excluded from current-stage totals.
- Outreach cohort: distinct provider-confirmed messages accepted in the interval.
  Replies/delivery events must link to those exact messages and occur after acceptance,
  before end. Repeated receipts/replies count at most once per message per metric.
  Automated, unclassified and out-of-office replies are not human engagement.
  Positive replies require positive or meeting-intent classifications. Acceptance is
  not delivery. Provider confirmation of scheduling is not meeting attendance.
- Confirmed-meeting conversion: distinct contacted cohort pipelines with a confirmed
  calendar action after contact, divided by distinct contacted cohort pipelines.
- Research coverage: cohort accounts with completed persisted research / distinct
  cohort accounts. Message evidence coverage uses immutable draft evidence IDs.
- CRM coverage: cohort pipelines with at least one confirmed CRM sync / cohort
  pipelines. This measures confirmed coverage, not current remote freshness.

Every rate includes numerator, denominator, sample size and exact member IDs.
Zero denominators yield null rates. Fewer than 20 observations are marked
`insufficient_data`; arithmetic counts/rates remain visible, but do not trigger
performance recommendations. This is a review policy, not a significance test.
Pending/unclassified linked replies also make reply performance insufficient for
a low-reply recommendation; delayed classification is never treated as evidence
that the recipient did not respond.

## Dimensions and unsupported data

Campaign, sequence version, message, Brain, research and prospect IDs come from
immutable snapshots. Segment is the exact pinned Brain ICP, not proven segment
membership. Persona is a unique, exact recipient-email-matched, evidence-linked
research title observation; conflicting titles remain unknown. Buying signal is
the exact evidence-linked why-now statement, not verified purchase intent or a
standardized signal taxonomy. CTA recognizes only the exact stored template text.
Industry, company-size and message-angle labels are unavailable in historical
canonical snapshots and remain unknown. Mutable company/contact edits never
rewrite historical groups. These unknowns remain in denominators and are visible.

No actual-cost/currency or booked-revenue ledger exists. Cost per reply, cost per
meeting and revenue therefore return `insufficient_data` and null. Budgets, fake
provider receipts and won stages are never converted to fabricated costs/revenue.

## Advisory recommendations and approval

Deterministic rules flag research coverage below 100%, confirmed CRM coverage below
100%, or observed reply rate below 10%, only with at least 20 denominator members.
Thresholds are disclosed review policies, not industry benchmarks. Each rule includes
its version, as-of time, exact supporting metric and member IDs, sample size, range,
confidence, limitations, proposed action, expected outcome, unknown cost and risk.
Evidence IDs join the report manifest. Low-evidence cohorts receive
`insufficient_data`; adequate cohorts above threshold receive `no_gap_observed`.

Recommendations are descriptive associations with no causal inference, guaranteed
revenue/uplift or unsupported statistical claims. Selection bias, source uncertainty
and unequal follow-up time are disclosed. Applying any advice requires a separately
created/reviewed Phase 5 plan and its existing approval flow. Insights cannot create
commands, edit Brain/configuration, send outreach, sync CRM or create calendar events.
No LLM, paid API, provider transport or external network request is used.

Phase 10 customer frontend work is outside this checkpoint.
