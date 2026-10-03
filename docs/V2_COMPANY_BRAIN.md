# Company Brain

The Settings page contains a four-step Company Brain editor: company/market,
sources, claims, and review/publication. Members can save drafts; only owners and
admins can publish. Viewers can inspect versions. Publication requires explicit
review, the current revision, and complete company/product/value/ICP/persona/goal
fields. Every published version records its publisher, time, and canonical SHA256
content hash. Subsequent work clones the previous snapshot into a new draft.

Tables: company_brains, company_brain_versions, company_brain_sources, brain_claims.
All carry required workspace ownership and composite relationship foreign keys.
ORM scoping remains mandatory; PostgreSQL forced RLS adds defense in depth. Raw
client roles have no table grants. SQLite/PostgreSQL triggers reject changes to
published versions and their source/claim records. Optimistic revisions plus
PostgreSQL row locks prevent stale saves or stale review approvals.

Sources support guided answers, manually captured website/product/case-study
excerpts, uploaded documents, manual edits and CRM metadata. URLs are provenance
labels, not an automatic fetch operation or verification claim. Phase 4 adds
retrieval/evidence. Upload preview extracts TXT/Markdown/DOCX/text PDF without
persisting a file or fetching document links. Limits: 2 MB, 50 PDF pages, 100,000
characters per source, 500,000 per draft. Scanned/encrypted PDFs need customer
text extraction. DOCX archive expansion is bounded. Untrusted document parsers
still require production resource isolation/rate limits in Phase 11.

Claims distinguish customer-approved from prohibited language. Customer approval
does not establish independent factual verification. A source reference must
belong to the same version. Future planning must reference an exact published
version ID and hash; it must never resolve a moving latest version at execution.

Migration 20260922_0006 is additive after Phase 2: no legacy customer records are
assigned or changed. Validate on an isolated restored database before production.
Check foreign keys, workspace grants/RLS, and immutable triggers. Existing data
ownership quarantine from Phase 1 remains intact. Recovery is a verified backup
restore; automatic downgrade refuses to discard reviewed knowledge. Do not deploy
until all later phase gates and explicit production authorization are complete.
