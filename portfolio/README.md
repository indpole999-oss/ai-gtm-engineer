# Anil Janga — GTM Engineering Portfolio

Public-facing, static portfolio demonstrating a grounded GTM Engineer story and an isolated, reproducible workflow example.

## Source and safety

- The published portfolio is static HTML, CSS, and JavaScript in this directory.
- The Workflow Lab is a genuine browser-executed, deterministic sample using clearly fictional account fixtures. It does not call any external API.
- The Python example implements the same research -> mock enrichment -> qualification -> draft -> in-memory approval process.
- Neither demo can send messages, write to a CRM, book meetings, or consume paid AI credits.
- GAPS AI V2 is a separate evolving product. Its staging features do not automatically count as verified production customer functionality.
- No fabricated clients, testimonials, ROI, customer metrics, production integration claims, or hiring dates.

## Run website locally

From the repository root:
  python -m http.server 8008 --directory portfolio

Visit http://localhost:8008 (or open index.html directly).

## Run CLI and tests

  python portfolio/demo_workflow.py aster
  python portfolio/demo_workflow.py ridge
  python -m unittest discover -s portfolio -p "test_*.py" -v

No extra dependencies, database, or API keys required.

## How to deploy safely on Render

Use a NEW static site (not any existing GAPS AI service) with:
- Repository: indpole999-oss/ai-gtm-engineer
- Branch: portfolio/gtm-engineer-20261016
- Build command: echo "Portfolio: static assets ready"
- Publish directory: portfolio
- Service URL: a new onrender.com subdomain
- No environment variables, no service-to-service connections, no paid plans.

This path exists only for non-production portfolio work.

## Workflow roadmap and evidence

| Capability | Evidence status |
| --- | --- |
| Account intelligence | Reproducible fictional sample; separate GAPS staging work |
| Enrichment | Mock provider fallback in offline Python example |
| ICP qualification | Deterministic rubric in browser + Python example |
| Drafting | Template draft from fictional evidence; no LLM invocation |
| Human review | State transition in browser/Python; no external writes |
| CRM integration | Planned portfolio demonstration, not verified end-to-end here |
| Calendar | Planned portfolio demonstration, not verified end-to-end here |
| Reporting/orchestration | GAPS staging journey; provider E2E still requires evidence |

## Case studies

See cases/ for detailed breakdowns of account intelligence, the enrichment/qualification path, and safe approval boundaries. All describe demo evidence and honest production gaps.

## Known limitations / next milestones

1. Browser demo and Python demo need a full deployment check; each is intentionally offline.
2. Publish video walkthrough only after recording real interactions; use captions and sample-data disclaimers.
3. Build controlled sandbox HubSpot/Clay/Calendar adapters only after their permissions and test accounts are confirmed.
4. Add screenshots and external evidence without private data or secrets.
5. Refresh external LinkedIn URL only after identity/profile link is verified.

Do not conflate this standalone portfolio with a fully live, customer-ready GAPS AI product.
