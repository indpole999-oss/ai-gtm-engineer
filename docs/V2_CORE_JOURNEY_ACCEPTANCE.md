# Core journey continuation from b2d2db1 — 2026-10-03

Branch: `codex/ai-gtm-engineer-v2-full-build`. Main and production were not changed.
Calendar live create/readback acceptance was retained; no further live Calendar
operation was performed. Hosted AI and workers were not enabled. No staging
configuration, migration, membership, or customer record was changed. Code changes
below are local and have not been deployed to staging.

## Authenticated staging audit

Browser: `https://gaps-ai-v2-staging-web.onrender.com`, signed in by the user.
Read-only SQL: isolated staging project `xhjkahbtckrrhuzamysr`, workspace
`7ebdcce9-6551-41a2-b7cb-24fd7dd1aa0d`.

| Step | Browser observation | Backend evidence |
| --- | --- | --- |
| Company Brain | Version 1 published | Brain `3d5e60fe-6091-49d6-a0f3-07bfc4cab88a`, published; hash `68e98554afd0028a9d8b9eb8f71409a65dbf7ba2101ec65ba575876a4beb142c` |
| Goal and plan | Existing Vercel plan is an approved guided template; exact target/source visible | Six goals reference that Brain. Template provenance does not establish AI planning success. |
| Prospect | Vercel and existing synthetic QA account displayed as discovered | Two pipeline records at `discovered` |
| Research | Two failed executions, each displaying three generic failed attempts | Jobs `fb7bdda0-4b12-5cb8-a819-2b0d6a38bd47` and `98c44f76-97b0-5ed3-8075-d754ee76f9dc`: failed, `retrieval_or_model_validation_failed`, source `https://vercel.com/`; each has zero captures, zero claims, zero reports |
| Qualification | No supported qualification | No report or qualified pipeline record. Live qualification is BLOCKED. |

The old combined error and rolled-back captures cannot identify whether source
retrieval or model analysis failed in those historical attempts. No root cause is
invented from the empty records. Prospects hid both failures because it selected
only completed jobs.

## Repairs

- Prospects now displays the latest attempt's actual status/error and mounts the
  account research view. Users can prepare a guided plan from that account, open
  its exact workspace-scoped plan URL, inspect all attempts, and refresh research.
- Provider readiness checks are authenticated and read-only. Paused Groq performs
  no provider request. Local readiness checks `/api/tags` for the configured model,
  without generation. Availability is distinct from validated research success.
- AI preparation and research approval/resume are disabled in the UI when the
  provider cannot be attempted. Backend approval/resume independently reject a
  configured paused hosted provider. Already-approved worker research pauses with
  `hosted_ai_paused`, retains the pending step, and does not burn repeated retries.
- Actual source captures persist before analysis: URL, content, retrieval time,
  publisher, extractor version, and SHA-256. Model failure retains captures without
  accepting claims, intelligence, or qualification. Retry reuses immutable captures.
  A new job is required for new source content.
- Errors distinguish `source_retrieval_failed`, `model_provider_unavailable`, and
  `model_output_validation_failed`. Source captures are visible even without a
  qualification report and are explicitly labeled insufficient to establish fit.
- Buyer titles now require exact source provenance alongside names/emails.
  Account fit qualifies only saved contacts matching a supported buyer's name and
  email; manual contact qualification enforces the same requirement. Source-backed
  email observations remain unverified.

Existing tenant scoping, RLS, immutable evidence, approval envelopes, worker leases,
Calendar adapters, and database schema remain in place. No mock provider or fallback
success path was added to runtime selection.

## Local browser plus backend acceptance

The real V2 frontend and FastAPI ran against a disposable SQLite database. All
inherited provider settings were removed; no dotenv file was loaded; hosted AI and
workers were disabled. The manually supplied business profile is labeled synthetic
QA. No fake research, claims, buyers, or qualification were inserted in this browser
rehearsal.

| Completed step | Browser evidence | Backend readback |
| --- | --- | --- |
| Brain draft/save/review/publish | Publication status shows version 1; saved profile is reviewable | Brain `d79af35c-61cc-46e0-8fdf-5bb0f038a608`, revision 3, published; hash `c4f02ffb53cb16c21878bf718774522bcc462f2a9edef071a790a428ee5f9bf4`; GET Brain 200 |
| Account creation | `Vercel — local journey target`, domain `vercel.com`, stage discovered | Company `d47b56c0-24b3-41a5-a931-df03c1e0d7b8`; persisted pipeline discovered |
| Goal and guided plan from Prospects | Propose research plan saves and exposes exact command-center link | Goal `460cace0-b46a-47ae-aa4f-43fe8c9a4cd2`; plan `00383657-c55e-4498-945e-24743c3e007c`, draft, `explicit_research_template`; hash `c1d01315176a3fd3d96c3a76fceedd66e75dc03f0181fb694adb983da4e7ec0e`; document pins Brain hash and account/source |
| Plan handoff and refresh | Exact plan opens; refresh restores version 1 and resets review acknowledgement | GET exact plan 200; GET goals 200 with matching Brain; no execution cycle |
| Provider blocker | Model unavailable message; approval remains disabled even after review checkbox | GET readiness 200: provider ollama, state unavailable, can_attempt false; research jobs `[]`, cycles `[]` |

Screenshots are saved in the chat's visualization directory:
`brain-published.png`, `prospect-research-preparation.png`, `plan-blocked.png`, and
`plan-restored.png`. These are local browser evidence, not staging rollout or live
model acceptance. Initial plan loading needed a retry during development; subsequent
full-page refresh restored the plan successfully.

## Exact remaining blocker and required evidence

Live research/qualification remains BLOCKED. Do not enable hosted AI or workers
without the user's explicit authorization. The existing staging pause is retained
by instruction; this session did not independently read its deployment environment.

For an explicitly authorized hosted rehearsal, an operator must supply a valid
`GROQ_API_KEY`, a compatible structured-output `GROQ_MODEL` (existing default
`openai/gpt-oss-120b`), reviewed quota/budget, and authorize changing
`GTM_HOSTED_AI_ENABLED` from false to true. A key alone never enables execution.
The approved durable worker must also be available on the isolated staging host;
no idle queue or readiness response proves worker liveness.

For a local-model alternative, the API and worker hosts must be able to reach the
operator-controlled `GTM_LOCAL_MODEL_URL` (default `http://127.0.0.1:11434`) and
`/api/tags` must list `GTM_LOCAL_MODEL` (default `qwen3:4b`). Local TCP and the new
readiness API both confirmed that service is unavailable in this rehearsal. No
Ollama/model installation was performed. A paused configured hosted provider does
not silently fall back to local AI.

Source access also needs actual acceptance on the execution host. This computer's
DNS returned NAT64 `64:ff9b::...` addresses for Vercel marked reserved by Python;
the existing all-address SSRF guard rejected the destination. A read-only retrieval
attempt produced `Only public HTTPS sources are supported`. The guard was not
relaxed, and that local result is not evidence of staging source access. Confirm a
source resolves to permitted public addresses, passes TLS and robots/storage policy,
returns readable text, and produces a persisted capture before claiming research.

After authorization/configuration, acceptance requires one customer-reviewed plan
through the existing durable worker, persisted real SourceFetch rows with matching
hashes, supported claims/excerpts, exact Brain ID/hash/ICP, valid model output,
qualification history pointing to that job, and browser/API/SQL readback after
refresh. None of those live research results is claimed here.

## Validation

- Backend journey, research, readiness, planning/worker, outcome, and workspace
  security suite: 90 passed. Model/provider success cases are explicitly injected
  deterministic test transports; they prove contracts, not live provider quality.
- Final paused-resume and retained-capture checks after follow-up edits: 2 passed.
- Final automatic/manual buyer-qualification rejection check: 1 passed.
- TypeScript: passed. Frontend contract tests: 7 passed.
- Changed frontend files: lint checked; final cleanup separates the readiness hook
  from its component to avoid adding a Fast Refresh warning.
- Client and SSR production compilation passed. Nitro packaging failed with the
  previously documented Windows `EPERM readlink C:\Users\sweet` limitation. No
  completed production build, new Linux CI, push, or deployment is claimed.
