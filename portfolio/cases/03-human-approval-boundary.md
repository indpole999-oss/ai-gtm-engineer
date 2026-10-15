# Case study 03 — Human-approval boundary for AI outreach

**Status:** Functional no-side-effect sample; GAPS AI V2 external-action E2E remains pending independent acceptance.

## Problem
A model-generated draft should not silently become an outbound email or a CRM action.

## Design
Qualification -> evidence-based draft -> PENDING_REVIEW -> explicit reviewer action -> APPROVED_IN_MEMORY_ONLY.

The browser and Python demonstrations allow changing approval state locally, but deliberately contain no SMTP, CRM, or calendar integration. This makes the approval behavior testable without contacting real people.

## Reproduction
Run the portfolio browser sample. Click "Approve sample in memory only" and inspect the status. It never claims "email sent." In Python:
  python -m unittest discover -s portfolio -p "test_*.py" -v

## Engineering controls to add before production
- Verified signed-in reviewer identity and workspace permissions
- Durable approval record and audit history
- Token-bound external send authorization and revocation
- Idempotency and explicit provider receipts
- Rate controls, unsubscribe policies and safe error handling
- Reproducible staging E2E including failure paths

## Honest interpretation
Passing this example establishes only the approval state model with no external effects. It does not establish that GAPS AI has completed its live outreach and CRM customer journey.
