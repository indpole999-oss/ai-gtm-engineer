# V2 research-to-approval blocker analysis — 2026-10-10

Overall: **BLOCKED — complete hosted customer acceptance has not passed**.
This review uses `V2_HOSTED_ACCEPTANCE_2026_10_10.md` as historical hosted
evidence, current source inspection, and newly executed deterministic local tests.
No new hosted provider execution or hosted database migration/backfill was done.
Hosted AI remains paused. No deployment, paid model call, real email, external
calendar event, production change, or safety-gate bypass was performed.

## Blocker-by-blocker findings

| Flow / category | Precise cause and evidence | Resolution / remaining verification |
| --- | --- | --- |
| Deployment parity — configuration / release state | The acceptance report records web `39a54d14` and API `237818dd`, both auto-deploy off. Current local fixes are not running there. The previously repaired landing title also remains a hosted failure until deployment. | A push is not hosted verification. Explicit staging deployment authorization and subsequent deployed-commit checks are needed; no deployment is performed here. |
| Research readiness — intentional safety gate | `research_readiness.py` and `hosted_model.py` select configured Groq but report paused when `GTM_HOSTED_AI_ENABLED` is false. Hosted GET readiness returned 200 with `provider=groq`, `state=paused`, `can_attempt=false`. The enabled/key checks run before model transport; execution also checks pause before source retrieval. | Preserve pause. A configured key does not authorize charges or establish quota/model compatibility. Never silently fall back to a different provider to evade pause. |
| Research authorization — intentional safety gate | `planning_service.py:149` requires owner/admin approval of the current exact plan hash, published Brain hash and valid targets; paused hosted research rejects approval with 409 before persisting a cycle. The hosted guard-test job is merely a queued row: POST `/research/jobs/{id}/run` returns 409 because approved-plan/durable-worker execution is required. | Use guided Goal → exact reviewed plan → human approval → durable worker. Do not add a direct-run bypass or equate a queued row with worker execution. A focused test confirms approval rejection and already-queued work pausing without output. |
| Research execution — external provider / runtime configuration | `execution_worker.py:126` executes approved leased commands and reuses a deterministic job ID on retry. `research_service.py:158` retrieves allowed public sources, persists immutable captures and spans, then validates structured model output against actual spans and ICP before saving intelligence/claims. Retrieval failure, model unavailability and invalid output are distinct failures. Staging has zero captures/claims and no completed research. Current worker heartbeat, source reachability, provider credentials/quota and live structured output have not been verified in this review. | No missing research-execution logic was established. Real source retrieval plus a bounded approved model execution and database/reload readback remain required. Local fixture completion proves application contracts only. |
| Qualification prerequisite — intentional evidence gate | `pipeline_service.py:49` requires persisted `potential_fit` and a supported buyer with matching contact name and email; manual contact entry does not imply qualification. Hosted eligibility returned 200 `[]`; unsupported manual promotion returned 409. Research is not independent identity, mailbox, consent or deliverability verification. | Correct rejection while no validated report exists. Preserve buyer matching and evidence lineage. |
| Qualification ordering — genuine application defect, fixed | Contacts created after completed research previously stayed `discovered`, because projection ran only when research completed. The new regression failed before the fix: expected `qualified`, got `discovered` (1 failed). | Contact creation now projects the latest completed report atomically under the existing workspace lock. Shared transition logic preserves job/Brain lineage and idempotency. A newer unknown/not-fit report never falls back to an older positive one. Wrong name/email, unknown/not-fit and absent research remain discovered. No existing hosted contacts were retroactively altered. |
| Personalized drafting — prerequisite, not a paid-generation requirement | `outreach_service.py` composes via `evidence_template`: recipient first name, source-backed assertion and approved Brain claim, with a generic subject/CTA. This is deterministic evidence personalization, not demonstrated generative copywriting. `outreach_review.py:65` checks fit, supported buyer, capture/excerpt provenance, immutable hashes and claim policy. Hosted queued research was rejected with 409 and zero drafts/enrollments. | Once validated eligible research exists, composing and reviewing this template requires no additional model call. Campaign/sequence/enrollment, sender, unsuppressed recipient and eligible evidence are still required. Advanced generative personalization is not implemented by this template and is not claimed as passing. |
| Suppression — intentional safety gate | The hosted synthetic contact received a fixture opt-out and has a persisted suppression; UI disables enrollment. Missing research is not its only blocker. | Preserve suppression. Use a fresh dedicated synthetic eligible contact for a future authorized rehearsal; do not delete an opt-out to force progress. |
| Human approval — intentional safety gate / downstream prerequisite | No hosted draft means the Approval Queue is correctly empty. Submit precedes owner/admin approval; current content hash/revision, source validation and explicit acknowledgement of unverified human edits are enforced. `approve_message` saves a message and DRAFT delivery plan, not a send. A separate exact delivery-plan approval and worker checks remain necessary. | No missing approval logic was established. Local desktop/mobile tests pass draft creation, submit, message approval and separate delivery authorization. Hosted success remains unverified until a valid eligible draft exists. No approval gate was removed. |
| Outbound email — missing application adapter | `outreach_service.py:180–191` returns `DisabledProvider` for every sender, including stored `fake` senders. Its send/lookup operations are disabled. Only tests inject a fake transport. Gmail/Outlook connection/execution is not offered by the integration contract. | Credentials, human approval or an AI flag alone cannot enable real email. Implement and safely test a genuine mail adapter/connection flow before requesting any real-send authorization. Outbound transport was deliberately not enabled in this fix. |
| Real inbound email — missing application ingestion logic | `routers/inbox.py:40` exposes owner/admin simulated events for fake senders. Hosted double-ingestion produced one receipt/message/thread/suppression. This is not a real provider webhook or received email. | Implement trusted, authenticated provider ingestion and reconnect handling before live mailbox verification. Existing fixture deduplication remains useful but cannot establish real inbox acceptance. |
| Pipeline / Insights — downstream provider evidence | Their persistence and aggregation logic is exercised locally; the hosted report has discovered records and zero confirmed sends/research outcomes. The late-contact defect distorted the qualified projection and therefore Insights. | Fixed projection now persists one qualified history entry and one Insights qualified-stage entry across fresh DB sessions and replay. Provider-confirmed sends/replies/meetings/costs remain unverified in hosting. Fixture outcomes are not real outcomes. |
| Calendar / CRM — configuration vs missing logic | Google Calendar has a real transport, but the synthetic workspace has no OAuth integration and no event was authorized. CRM transports remain disabled; Salesforce writes are not implemented. `routers/integrations.py` advertises only configured Google Calendar connection/execution. | Google Calendar needs dedicated OAuth and explicit event authorization. CRM needs implementation before provider-write authorization is useful. Neither is required to save/review an outreach draft. |

## Verified fix and exact test evidence

The change is confined to late-contact qualification projection, its regression
coverage, and this report. Existing authentication, human approvals, hosted pause,
claim validation, suppression and delivery limits remain in place.

Real persistence here means disposable local SQLite through the actual FastAPI
routes and SQLAlchemy sessions. Browser tests use React → HTTP → FastAPI → that
database. Research/model and delivery boundaries are deterministic fixtures;
neither a fixture nor a local database is presented as hosted provider success.

| Check | Result |
| --- | --- |
| Before-fix regression: `tests/test_contact_qualification.py::test_contact_added_after_research_persists_qualification_once` | **FAIL reproduced:** expected qualified, actual discovered; 1 failed, 27 warnings, 1.93s. |
| Research, draft review, outreach, outcomes, V2 journey and qualification: `pytest -q tests/test_contact_qualification.py tests/test_research.py tests/test_draft_review.py tests/test_outreach.py tests/test_outcomes.py tests/test_v2_journey.py` | **PASS:** 99 passed, 5200 warnings, 275.88s; exit 0. |
| Latest qualification persistence/replay and Insights: `pytest -q tests/test_contact_qualification.py tests/test_insights.py` | **PASS:** 27 passed, 700 warnings, 60.69s; exit 0. Includes fresh-session SQL readback, one history entry after replay, Insights qualified count 1, HTTP readback, unsupported buyers/latest negative reports, and foreign-workspace 404. Overlaps the broad suite; counts are not additive unique tests. |
| Desktop/mobile full safe local journey: `RUN_BROWSER_E2E=1 pytest -q tests/test_browser_journey.py -x` | **PASS:** 2 passed, 268 warnings, 185.48s; exit 0. Includes persisted late-contact qualification and research job lineage, Brain/Goal/research, draft/review/approval, fixture delivery/inbox, pipeline/Insights and reload behavior. External sender/transport and model boundaries are fixtures. |
| Paused hosted execution: `pytest -q tests/test_planning_execution.py::test_paused_hosted_provider_blocks_approval_and_pauses_existing_work` | **PASS:** 1 passed, 35 warnings, 1.68s; exit 0. |
| Frontend contracts: `node --test tests/customer.test.mjs` | **PASS:** 17 passed, 0 failed, 1006.137ms; exit 0. No frontend source was changed; generated route-tree rewrite excluded. |
| Full hosted research → qualification → draft → approval → real outcomes | **BLOCKED:** no new execution attempted, AI paused, no completed hosted research, disabled mail/CRM transports and absent live inbox ingestion. |

Python runs used `-p no:cacheprovider --disable-warnings --tb=short` and distinct
ignored `.venv` basetemp directories; broad/current/browser runs also used
`--show-capture=no`. Warnings are recorded above, not silently treated as failures.
Browser traces/screenshots are under `.venv/blocker-browser-tests/`.

## External verification that requires explicit approval

1. **Staging deployment:** approve deploying the reviewed commit to staging web/API,
   then verify deployed commits and repeat hosted acceptance. Push alone does not
   deploy this fix; production is outside scope.
2. **Bounded hosted research:** explicitly authorize enabling Hosted AI and any
   potential model charges, specify a provider/model and charge/request cap, and
   review the exact synthetic account, public source and published Brain/plan.
   Confirm worker health, then a human approves that exact research plan. Verify
   real HTTP responses, immutable captures/spans, validated claims/report, qualified
   contact, SQL persistence and reload. Operator authorization to enable a paid
   provider is distinct from customer approval of the plan. No secret values need
   to be disclosed in the report. Invalid output must remain a failure.
3. **Real email/inbox:** requires implementing the currently missing adapter and
   trusted ingestion first, then explicit authorization for a dedicated test
   mailbox/provider connection and each intended recipient/content/send scope and
   charge cap. Exact message and separate delivery-plan human approvals still
   apply. No amount of approval alone fixes the absent transport today.
4. **Calendar/CRM:** dedicated Google OAuth consent and explicit external-event
   creation approval are required for calendar verification. CRM requires an
   implemented adapter before authorization of external writes. These approvals
   are separate from AI research and email.

After valid research exists, deterministic drafting, submission, human message
review and saved delivery-plan inspection do not themselves require a paid AI
call or real email send. They can be rehearsed with the safe synthetic setup while
delivery remains disabled. Complete hosted readiness still requires every required
hosted gate to pass; it is not declared here.

The pre-existing `docs/V2_CUSTOMER_RELEASE_CHECKLIST.md` edit is unchanged and
excluded, Git blob hash `1f215c9d1bc1cab51531b0d6c1caf5a8adde27b3`.
