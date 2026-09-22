# Research and account intelligence

Company detail now exposes source-based research. A user selects an exact published
Company Brain and up to three public HTTPS URLs. A job captures source text, hashes,
URL/title/publisher and retrieval time, validates structured model output, and saves
an immutable report. The qualification input is the published ICP, never the V1
fixed score. The report explains company fit, timing and buyer observations with
claim/evidence references. It retains the precise Brain ID and content hash.

`GTM_LOCAL_MODEL_URL` defaults to `http://127.0.0.1:11434`; `GTM_LOCAL_MODEL` defaults
to `qwen3:4b`. These are operator settings. The adapter uses Ollama's JSON schema
output and validates it again in Pydantic. Existing OpenAI configuration is retained;
this phase does not call OpenAI or paid search/enrichment services. Test providers
are injected by tests, never selected as a production fallback. If the local model
is unavailable, the job fails explicitly rather than inventing a successful report.

Provider assertions must quote source text; paraphrases and qualification are model
inferences. Unsupported quotations, references, changed ICP, invented buyer emails
and model-generated verification are rejected transactionally. Unknowns are explicit.
Owners/admins can append an exact-text fact verification or rejection with a reason.
This is identified as workspace-admin review, not independent automated verification.
Rejected claims must be excluded by later composition/execution policy.

Buyer names/emails need verbatim source provenance and remain unverified. Discovery
is not proof of mailbox ownership or deliverability. No email is sent. Paid mailbox
verification/search/enrichment must run through the Phase 5 approval/budget layer;
the unknown status must never silently become verified. Buyer observations, timing
signals and qualification are typed report sections linked to immutable claim IDs.

Retrieval validates all DNS answers as public addresses, connects to a validated
numeric IP and checks TLS against the original hostname. Redirects, proxies,
non-HTTPS URLs, custom ports and compressed/non-text responses are refused. Source
text is bounded and scripts/styles excluded. This protects the backend network;
source prose remains untrusted and is never an execution instruction.

Migration `20260923_0007` only adds workspace-owned research tables with composite
foreign keys, forced PostgreSQL RLS and revoked direct-client grants. Captures,
evidence, claims, reviews and reports are immutable in ORM and SQL. No legacy data
is reassigned. Validate an isolated restored database; recovery uses verified backup
restore rather than a destructive downgrade.

Phase boundary: the explicit research-run endpoint is synchronous and read-only
externally. A terminated request rolls back to queued. Phase 5 must replace this
execution path with durable leased worker execution before production. Further
production hardening includes source-fetch total deadlines, parser isolation,
rate limits, model prompt-injection evaluations, and real local-model/staging smoke
tests. CI uses deterministic providers and does not establish live model quality.
