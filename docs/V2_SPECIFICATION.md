You are the lead engineer responsible for completing GAPS AI's AI GTM Engineer V2 from the current repository to a production-deployable product.

This is a LONG-RUNNING IMPLEMENTATION TASK.

Do not stop after each phase merely to ask me whether to continue.

Execute the roadmap sequentially, validate each phase, commit stable checkpoints, and continue automatically whenever the validation gate passes.

Only stop when:

1. A required secret/credential is missing.
2. A production-data decision would be destructive.
3. A paid service/action is required.
4. A requirement is materially impossible or contradictory.
5. A validation failure cannot be safely corrected from the repository.

Do not deploy to production until the entire V2 build and final validation are complete.

Do not modify live production data.

Do not expose secrets.

COST REQUIREMENT

Keep the architecture as low-cost as practical.

Prefer:

* existing FastAPI backend
* existing TanStack/React frontend
* PostgreSQL/Supabase
* existing Render infrastructure
* open-source or free-tier components where technically reasonable

Do not introduce paid infrastructure or APIs without clearly identifying why they are required.

PRODUCT VISION

GAPS AI is building AI employees for companies.

AI GTM Engineer is the first AI employee.

The V2 product must feel like the customer is managing an AI GTM employee — NOT operating separate agents, workflows, lead tools, CRM utilities, or automation screens.

The AI GTM employee should:

Understand the customer's company
→ understand ICP and GTM strategy
→ accept a natural-language business goal
→ create a transparent execution plan
→ obtain approval
→ research the market
→ identify buying signals
→ qualify accounts
→ identify buyers
→ discover and verify contacts
→ create source-backed Account Intelligence
→ draft personalized outreach
→ obtain approval before outbound communication
→ execute approved follow-ups
→ understand replies
→ recommend next actions
→ convert interested prospects into meetings
→ synchronize CRM/pipeline
→ measure outcomes
→ identify GTM gaps
→ recommend the next execution cycle.

TARGET CUSTOMER NAVIGATION

The primary customer navigation must eventually become:

* AI GTM
* Prospects
* Outreach
* Inbox
* Pipeline
* Insights
* Integrations
* Settings

Agents, raw workflows, provider debugging, execution traces, and internal orchestration must not remain primary customer-facing navigation.

They may remain as internal/admin/operator capabilities.

==================================================
ENGINEERING RULES
=================

1. Reuse good V1 foundations rather than rewriting everything.

2. Preserve useful:

* FastAPI
* async SQLAlchemy
* TanStack Start / React
* Google Calendar integration logic
* CRM provider adapter logic
* browser/research/enrichment capabilities
* existing UI primitives
* authentication foundations

3. Rework unsafe or incomplete architecture.

4. Every customer-owned business record must be workspace-scoped.

5. No external side effect should execute merely because an LLM decided to do it.

6. Sending email, altering important CRM state, or creating meetings must pass policy and approval controls.

7. Planning and execution must be separate.

8. Every externally sourced factual claim used for qualification or outreach must retain evidence/provenance.

9. AI-generated structured output must be schema validated.

10. Background execution must be durable and resumable.

11. External side effects must support idempotency.

12. Customer data must never cross workspace boundaries.

13. Do not report fake success states.
    For example:

* do not mark email "sent" before provider acceptance
* do not mark calendar event created if only a local DB row exists

14. Use Alembic exclusively for schema evolution.

15. Do not run destructive migrations against live production data.

16. Run automated validation continuously.

==================================================
PHASE 1 — WORKSPACE SECURITY BOUNDARY
=====================================

Implement secure multi-tenancy.

Create:

workspaces
workspace_memberships

Roles:

owner
admin
member
viewer

Registration must create an initial workspace and owner membership.

Add workspace ownership to all customer records including existing:

companies
contacts
leads
CRM records
email logs
meetings
integrations

Centralize:

current user
current workspace
membership resolution
authorization
role checking

Scope every customer-data query by workspace.

Prevent:

* cross-workspace listing
* guessed-ID access
* cross-workspace update/delete
* cross-workspace actions
* cross-workspace relationships

Replace global uniqueness with workspace-scoped uniqueness where appropriate.

Add exhaustive cross-tenant tests.

Add PostgreSQL RLS where practical as defense-in-depth, but retain application-level authorization.

Use staged safe migrations:
nullable column
→ backfill
→ validate
→ index/FK
→ non-null where appropriate.

==================================================
PHASE 2 — INTEGRATION FOUNDATION
================================

Convert integrations from primarily user/global-provider configuration into workspace-owned connections.

Support clear provider-specific connection contracts.

Implement/rework:

Google Calendar
HubSpot
Salesforce where currently supported
email/mailbox providers
search providers
enrichment providers

Remove unsafe production fallback to deployment-global customer credentials.

Persist:
provider
workspace
scopes
status
health
last success
last error
token expiry
reconnect state
audit information

Fix Google OAuth durability:

* one-time short-lived state
* durable PKCE verifier
* token refresh persistence
* frontend OAuth return experience
* revoke/reconnect

Create provider adapters/interfaces rather than monolithic business logic.

Add fake providers and contract tests.

==================================================
PHASE 3 — COMPANY BRAIN
=======================

Build guided onboarding.

Customer must be able to provide:

company
product/service
value proposition
ICP
industries
geographies
buyer personas
pain points
competitors
GTM objectives
positioning
approved claims
prohibited claims
tone/brand guidance

Support sources such as:

guided answers
website
product pages
case studies
uploaded documents
approved manual edits
CRM metadata where appropriate

Implement versioned Company Brain.

Required concepts:

company_brains
company_brain_versions
company_brain_sources
brain_claims

Every published version must be immutable.

Every future plan must record the exact Company Brain version it used.

Customer must review/edit before publishing.

==================================================
PHASE 4 — RESEARCH, PROVENANCE & PROSPECT INTELLIGENCE
======================================================

Refactor research into:

retrieval
→ source capture
→ extraction
→ evidence
→ structured claim
→ signal
→ qualification
→ account intelligence

Create appropriate models such as:

sources
source_fetches
evidence_items
claims
claim_evidence
research_jobs
research_reports
account_signals
account_qualifications
account_intelligence_reports
buyer_candidates
contact observations
contact verification

The UI must answer:

Why this company?
Why now?
Why this buyer?
What evidence supports this?

Qualification must use the customer's Company Brain ICP.

Do not use the old fixed qualification score.

Differentiate:

verified fact
provider assertion
model inference
unknown

Persist:
source URL
title
publisher/domain
published date if available
retrieval time
excerpt/fact
confidence
freshness
model/extractor version

Outreach factual claims must come only from:

* evidence-backed research, or
* customer-approved Company Brain claims.

==================================================
PHASE 5 — AI GTM COMMAND CENTER, GOALS, PLANS, APPROVALS & EXECUTION
====================================================================

Build AI GTM Command Center.

Customer gives a natural-language GTM goal.

Persist goals.

Build Goal Planner.

Planner inputs:

goal
Company Brain version
available integrations
workspace policies
budget/limits
historical outcomes
pipeline state

Planner must output schema-validated:

objective
success metrics
target segment
constraints
assumptions
risks
steps
dependencies
expected outputs
rationale
cost estimate
side-effect classification
approval requirements
stop conditions
review checkpoint

Customer can:

review plan
edit/modify
regenerate
approve

No execution before plan approval.

Persist immutable approved plan version/hash.

Implement durable execution primitives:

execution_cycles
workflow_runs
step_runs
action_commands
domain_events
outbox_events

Execution must support:

background worker execution
persistent state
retry/backoff
timeouts
cancellation
pause for approval
resume after restart
idempotency
parallel safe research
budget/rate limits
typed step input/output
audit trail

Do not depend on a long-running HTTP request for workflow execution.

A database-backed job system is acceptable for the first production version if it satisfies durability requirements.

Avoid adding expensive infrastructure unnecessarily.

==================================================
PHASE 6 — OUTREACH
==================

Separate composition from delivery.

Generating an email MUST NEVER send it.

Build:

campaigns
sequences
sequence_versions
sequence_steps
enrollments
scheduled_messages
message_drafts
messages
delivery_events
suppression records
sender/mailbox identities

Personalization must use:

Company Brain
account intelligence
buyer reasoning
approved/evidenced claims

First production defaults:

plan approval required
outbound message approval required
server-side sending limits
suppression checks
recipient validation
sender connection validation

Approved content must be immutable or editing must invalidate approval.

Sending must be:

asynchronous
idempotent
provider-confirmed

"Sent" means provider accepted the request.

Delivery/bounce/etc. must be separate provider events.

==================================================
PHASE 7 — AI INBOX
==================

Implement inbound message handling.

Create concepts such as:

threads
inbound_messages
reply_classifications

Classify replies into useful categories including:

positive
negative
objection
out of office
wrong person
question
meeting intent
unsubscribe
other

AI should provide:

classification
reasoning
suggested next action
suggested reply draft

Important communication actions must respect approval policies.

Pause outreach sequences when appropriate after inbound replies.

==================================================
PHASE 8 — PIPELINE, CRM & CALENDAR OUTCOMES
===========================================

Create an outcome-oriented pipeline.

Stages should support concepts like:

Discovered
Qualified
Contacted
Engaged
Interested
Meeting
Opportunity
Won/Lost

Build durable CRM sync architecture:

provider object mapping
external IDs
sync records
sync cursor
webhook ingestion
idempotency
conflict handling
provider health

Do not expose raw provider operations as the main customer experience.

Calendar:

Convert positive intent into meeting workflow.

Create real provider calendar events only through approved/idempotent commands.

Handle:
timezone
duplicate prevention
provider event IDs
token refresh
reconciliation

Calendar must NOT be an automatic terminal step of a generic lead workflow.

==================================================
PHASE 9 — INSIGHTS & GTM GAP INTELLIGENCE
=========================================

Normalize outcome events.

Track dimensions:

industry
company size
persona
signal
research coverage
message angle
CTA
sequence version
delivery
reply
positive reply
meeting
opportunity
revenue where available

Build Insights showing:

funnel
industry performance
persona performance
signal performance
message performance
meeting conversion
evidence coverage
CRM sync completeness

Start GTM Gap Intelligence with explainable descriptive analytics.

Recommendations must include:

observed gap
supporting metrics
sample size
date range
proposed action
expected outcome
confidence
cost/risk
required approval

Do not introduce unsupported predictive claims.

==================================================
PHASE 10 — CUSTOMER EXPERIENCE CUTOVER
======================================

Change main navigation to:

AI GTM
Prospects
Outreach
Inbox
Pipeline
Insights
Integrations
Settings

Hide from normal customers:

Agents
raw Workflows
provider debug tools
raw execution traces
prompt/model debugging

Keep internal operator access where useful.

AI GTM Command Center must show:

current goal
Company Brain readiness/version
plan status
execution progress
blockers
pending approvals
recent completed work
qualified opportunities
evidence coverage
outcomes
recommended next action

==================================================
PHASE 11 — PRODUCTION HARDENING
===============================

Complete:

security review
tenant isolation tests
role tests
migration tests
provider contract tests
workflow retry/resume tests
approval bypass tests
email idempotency tests
suppression tests
OAuth tests
CRM/calendar reconciliation tests
frontend route/component tests
end-to-end test of core V2 flow

Add/complete:

structured logs
request/workspace/goal/run/step IDs
safe errors
secret redaction
rate limiting where necessary
health checks
metrics
cost/token tracking where practical
provider latency/failure metrics
run metrics
approval metrics

Review browser/research behavior for legal/privacy/robots/retention considerations.

==================================================
PRIMARY END-TO-END ACCEPTANCE TEST
==================================

The product is not complete until this full scenario works:

1. New customer signs up.
2. Workspace is created.
3. Customer completes Company Brain.
4. Customer connects required integrations.
5. Customer enters:

"Find one US B2B SaaS company that matches our ICP and prepare personalized outreach for the best RevOps buyer."

6. AI creates a transparent plan.
7. Customer approves the plan.
8. Execution runs durably.
9. AI identifies at least one qualified account.
10. Account has:

* qualification
* buying signal
* Why this company?
* Why now?
* source evidence

11. AI identifies a buyer.
12. UI shows:

* Why this buyer?
* contact confidence/verification

13. AI creates personalized outreach using only approved/evidenced claims.
14. Draft does NOT automatically send.
15. Customer approves outbound action.
16. Approved action is executed idempotently through connected provider.
17. Inbound reply can be ingested/classified.
18. Positive intent can progress toward meeting.
19. CRM/pipeline reflects outcome.
20. Command Center reflects progress and recommended next action.
21. Insights receives normalized outcome data.

==================================================
WORKING METHOD
==============

Create a dedicated V2 implementation branch from latest main.

Do not deploy after individual phases.

For each phase:

1. inspect dependencies
2. implement
3. migrate safely
4. add/update tests
5. run validation
6. fix failures
7. commit a clearly named checkpoint
8. continue automatically if green

Do not ask me to approve routine engineering choices when the product requirements above already determine the answer.

Make reasonable low-cost technical choices and document them.

Do not spend large amounts of time fixing purely cosmetic formatting unless it blocks CI/build/release.

Do not unnecessarily rewrite stable V1 code.

If a task/context/runtime limit prevents completion:

1. commit all validated work
2. create/update `docs/V2_PROGRESS.md`
3. record:

   * phases completed
   * phase currently in progress
   * exact remaining work
   * current test status
   * current migration revision
   * blockers
4. push the branch
5. provide the exact continuation instruction for the next Codex task

This ensures work continues without repeating repository analysis.

==================================================
FINAL DEPLOYMENT GATE
=====================

DO NOT deploy until all required build/test gates are green.

Before production deployment:

1. Confirm latest migrations.
2. Verify production schema adoption/backfill plan.
3. Verify required secrets/config without exposing them.
4. Verify Render configuration.
5. Verify Supabase/PostgreSQL connectivity.
6. Verify frontend production API URL.
7. Verify CORS.
8. Verify OAuth callback URLs.
9. Verify provider credentials.
10. Verify health endpoints.
11. Verify database backup/recovery plan.
12. Verify no destructive migration will execute.
13. Run final CI.
14. Run final staging/safe smoke test.

Only then report:

`READY FOR PRODUCTION DEPLOYMENT`

Do NOT deploy automatically unless I explicitly authorize the final production deployment.

==================================================
FINAL DELIVERABLE
=================

When complete, provide:

A. V2 architecture implemented
B. Completed phases
C. Database migration chain
D. Security/tenant model
E. Company Brain implementation
F. Planner/orchestrator implementation
G. Research/evidence implementation
H. Outreach/Inbox implementation
I. CRM/Calendar/Pipeline implementation
J. Insights/GTM Gap implementation
K. Navigation/customer UX changes
L. Tests and exact results
M. CI status
N. Remaining non-blocking limitations
O. Required production secrets/configuration
P. Deployment procedure
Q. Final end-to-end acceptance-test result
R. Final status:

`READY FOR PRODUCTION DEPLOYMENT`

or

`NOT READY FOR PRODUCTION DEPLOYMENT`

Do not claim completion unless the acceptance criteria actually pass.
