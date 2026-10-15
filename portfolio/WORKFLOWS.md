# GTM workflow library — executable offline references

The eight reference implementations in workflow_gallery.py have strict **fictional, local-only behavior**. Each is an executable example, not a claim that HubSpot, Clay, Apollo, n8n, Google Calendar, or an LLM has been connected.

## Reproduce each one
Run from repository root with Python 3.10+:

  python portfolio/workflow_gallery.py research
  python portfolio/workflow_gallery.py enrichment
  python portfolio/workflow_gallery.py qualification
  python portfolio/workflow_gallery.py outreach
  python portfolio/workflow_gallery.py crm
  python portfolio/workflow_gallery.py calendar
  python portfolio/workflow_gallery.py reporting
  python portfolio/workflow_gallery.py orchestration
  python portfolio/workflow_gallery.py all ridge

Tests:
  python -m unittest discover -s portfolio -p "test_*.py" -v

## Eight portfolio stories

| # | Business problem | Offline proof | What is *not* proven |
|---|---|---|---|
| 01 | Unreliable company research | Invented facts with source labels | Fresh real-world research |
| 02 | Incomplete provider enrichment | Mock waterfall and missing contact | Live Apollo/Clay coverage |
| 03 | Unclear lead priority | Weighted scoring with explicit checks | Predictive revenue performance |
| 04 | Risky AI outreach | PENDING_REVIEW draft, never sends | Deliverability or outbound conversion |
| 05 | CRM duplicate records | Idempotent dictionary upsert | Live HubSpot/Salesforce writeback |
| 06 | Meeting automation risk | UTC scheduling preview | Real calendar bookings |
| 07 | Inflated metrics | Local event counts; revenue remains unknown | Attributed customer revenue |
| 08 | Fragmented sales tooling | Six-step mock orchestrator, activity log | Real provider E2E or paid agent calls |

### Safe integration plan
After the user connects providers and approves controlled staging-only operations, implement each adapter with granular permission controls, credential isolation, explicit review, readback, test fixtures, trace logging and provider receipts. Preserve production and all user/contact data.
