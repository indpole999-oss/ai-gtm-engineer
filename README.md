# AI GTM Engineer

AI GTM Engineer V1 is a FastAPI and TanStack Start application for company research,
contact enrichment, outbound email, CRM synchronization, and calendar operations.
The repository is being hardened incrementally; V2 product features are not part of
the Phase 0 production-safety baseline.

## Current stack

| Layer | Implementation |
|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic Settings |
| Persistence | Async SQLAlchemy; SQLite for local/test, PostgreSQL for production |
| Migrations | Alembic |
| Frontend | React 19, TanStack Start/Router/Query, Vite, Tailwind CSS |
| Authentication | Local bcrypt passwords and signed JWT access tokens |
| Research | Serper/Tavily search, Ollama analysis |
| Enrichment | Apollo and public browser/search fallbacks |
| Email | OpenAI composition; Resend, SendGrid, or SMTP development fallback |
| CRM | Per-user encrypted HubSpot/Salesforce connections; development-only env fallback |
| Calendar | Per-user Google OAuth; development-only service-account fallback |
| Browser | Playwright and HTTP/Jina fallback |

See [the architecture notes](docs/ARCHITECTURE.md) and
[operations guide](docs/OPERATIONS.md) for boundaries and production requirements.

## Local development

Requirements: Python 3.12.13, Node 22, and npm.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn backend.main:app --reload
```

In a second shell:

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

For an entirely local PostgreSQL-backed stack:

```bash
docker compose up --build
```

The Compose credentials are explicitly local-only and must not be reused in any
shared or production environment.

## Validation

```bash
pytest -q
DATABASE_URL=sqlite+aiosqlite:////tmp/migration.db alembic upgrade head
cd frontend && npm run build
cd frontend && npx tsc --noEmit
```

The historical repository has substantial Prettier lint debt. Phase 0 treats the
TypeScript compiler and production build as release-blocking, while lint is run on
files changed for frontend correctness rather than formatting the full application.

## Production startup

Production is intentionally fail-closed. Set `APP_ENV=production`, provide all
settings documented in `docs/OPERATIONS.md`, run `alembic upgrade head` as a
separate release step, and then start:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Never use `Base.metadata.create_all()` in production. Set
`AUTO_CREATE_TABLES=false`. Never apply the baseline upgrade to an existing V1
production database without first following the baseline verification and stamping
procedure in the operations guide.

## Repository layout

- `backend/` — FastAPI application, routers, settings, persistence, logging.
- `agents/` — specialist integrations and agent implementations.
- `workflows/` — current V1 in-process workflow executor.
- `migrations/` — authoritative Alembic history.
- `frontend/` — TanStack Start application.
- `tests/` — local, provider-free backend safety tests.
- `deployment/` — backend container image.
- `docs/` — architecture and operations documentation.
