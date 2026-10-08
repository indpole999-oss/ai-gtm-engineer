# Staging research span contract

Scope: existing V2 branch and isolated staging project `xhjkahbtckrrhuzamysr`.
No production, schema, outreach, email, CRM or Calendar changes.

## Previous live attempt — rejected, evidence retained

- Implementation: `7c2d34c0bc680b2bb1a10821c8337b114ad8c94c`.
- Goal: `66f12001-ff63-4742-be09-f162db083932`.
- Company/prospect: `aea275cd-ea11-4c2d-ab52-fc56c0f4514f` (Vercel).
- Plan v3: `7a87558b-adad-4344-85a6-bdbd8699e07a`.
- Cycle: `cff5b187-d64a-4386-a6f1-73ce57b56e4a`.
- Command: `4ac22da8-d92b-4c4f-be07-4e640cc45591`.
- Research job: `d781a6f1-3405-565c-9935-177c50f48a18`.
- Capture: `ebed0792-9db1-4f8c-88d4-5d52778f2f0d`, `https://vercel.com/`.
- Source: 3,680 characters; SHA-256
  `909c8ceabe77f9e00849a66ffee069ded455d9e1eb597bbb2d9ff472103d19ce`.
- Four deterministic source-span EvidenceItem rows persisted. **Zero claims,
  zero accepted Account Intelligence reports, zero accepted qualifications.**
- Groq `openai/gpt-oss-120b`, one HTTP 200 response; 2,477 prompt + 1,539
  completion = 4,016 tokens. Backend rejected `Invalid source span reference`
  (`model_output_validation_failed`); terminal command `command_execution_failed`.
- The actual invalid reference was not retained in safe logs. Its value and the
  model's reason for returning it are unknown.

The previous output schema allowed any string of at most 36 characters for
`span_id`. Prompt instructions requested supplied IDs, but the schema could not
constrain the model to that finite set. Backend rejection worked correctly.

## Repair and offline acceptance

`supplied_span_output` constructs a fresh Pydantic output type from precisely the
IDs in the budget-filtered source prompt. The strict Groq schema contains the
allowed enum (or const for one ID), plus null for unknown claims. Both Groq and
Ollama responses are parsed against that same request-specific type. Empty input
permits only null; IDs are not coerced, repaired, guessed or reused across jobs.

Existing backend validation still enforces current-job ownership, offered spans,
claim-kind rules, exact persisted source text, source integrity, explanation
indices and buyer provenance. Claims/reports remain transactional; source spans
remain retained when a claim batch is rejected. No fallback or retry was added.

Focused tests: **61 passed**, using synthetic data and mocked provider HTTP only.
Cases cover valid/multiple references, malformed/unknown/foreign/unoffered IDs,
request isolation, empty sets, exact text, atomic rejection and retained evidence.
No live model was called during implementation or tests. No migrations required.

Full local backend regression: **326 passed, 2 skipped** in 483.04 seconds.
The skips require disposable PostgreSQL and are covered by CI. Existing datetime
deprecation warnings remain. Windows invocation sets `tempfile.tempdir` to a
relative synthetic scratch directory and supplies an absolute pytest `--basetemp`
in that scratch directory; no application configuration is changed. Frontend
source is unchanged; its production build and contract tests run in CI.

## Controlled retest boundary

Live retest is pending code CI and deployment. Reuse the goal and company above.
The old execution is terminal, so use one normal reviewed plan revision, maximum
one attempt, with exactly one new cycle/command/research job. Confirm hosted AI
off and zero active work before enabling staging for this attended attempt.
Disable hosted AI immediately afterward regardless of result; no second attempt.

Record the new capture/hash/spans, model HTTP result/usage, accepted claims and
report/qualification, browser/database agreement, duplicate and side-effect
counts, and final runtime pause here. Do not label this gate live-proven until
all required evidence exists.
