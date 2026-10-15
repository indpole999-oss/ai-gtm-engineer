# Case study 02 — Safe enrichment waterfall & ICP qualification

**Status:** Mock-provider example, not a verified Apollo/Clay end-to-end integration.

## Problem
Single-provider enrichment can return missing, contradictory, or stale contact data. The resulting sales records may be duplicated or misrouted.

## Demo implementation
The Python runner simulates a first mock provider, then an optional mock fallback. It records attempted providers, marks fictional emails as not real-world verified, and applies a deterministic ICP rubric.

## Why this structure
- Auditability: every output reports its mock provider and attempts.
- Conservative defaults: missing contact information stays missing.
- Fit logic is explainable rather than opaque model opinion.
- Fictional emails use the .example reserved domain; nothing is sent.

## Test evidence
The unit suite verifies zero external calls and zero CRM writes across all fixtures, including the missing-contact case. It also verifies stable qualification results and no fixture mutation leakage.

## Live integration milestones (not yet completed here)
Authorize sandbox/test access for enrichment and CRM, establish consent and data policies, implement timeouts/retries, add response normalization, duplicate checks, reconciliation and tests against authorized sample accounts. Record accuracy, coverage and cost rather than estimating them.
