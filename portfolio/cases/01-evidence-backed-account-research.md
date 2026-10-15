# Case study 01 — Evidence-backed account intelligence

**Status:** Reproducible offline demonstration, plus separate GAPS AI staging research work. Not a live third-party research connector in this portfolio.

## Business problem
GTM teams need to know why an account is relevant before spending time crafting outreach. Unchecked AI claims or stale enrichment can make qualification unreliable.

## Design
Fictional account -> source-tagged facts -> evidence completeness check -> explainable ICP score -> reviewable outreach draft.

The sample data includes Aster Cloud, Ridgeway Logistics, and MiraCare Analytics. All names, buying signals, contact addresses, and source labels are invented. No genuine businesses are contacted.

## Architecture and decisions
- Sources are labeled on each fact rather than blended into ungrounded prose.
- An explicit rubric weights industry (40), employee range (20), stated buying signal (25), and evidence completeness (15).
- A missing signal or source changes the score; it isn't silently filled by an LLM.
- External action is disallowed by architecture. Drafts are created in PENDING_REVIEW only.

## Reproduce
Open the static portfolio Workflow Lab, select each fixture, and run it. Or run:
  python portfolio/demo_workflow.py aster
  python portfolio/demo_workflow.py ridge
  python -m unittest discover -s portfolio -p "test_*.py" -v

## Evidence and limitations
Tests assert deterministic scoring, prevention of external side effects, unknown fixture rejection, in-memory approval, and source completeness changes. This is a local model of the behavior; it is not proof of live research quality, third-party contact enrichment, or business lift.

## Next validation
Use approved staging credentials to run one real research query, inspect source spans, compare factual accuracy against ground truth, and document provider cost and failure modes. Do not claim this is done until evidence is recorded.
