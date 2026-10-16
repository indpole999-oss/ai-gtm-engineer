# Current V1 Architecture

## Request path

The React 19/TanStack Start frontend calls the FastAPI API directly using a bearer
JWT. FastAPI routers expose authentication, companies, contacts, leads, emails,
CRM, calendar, integrations, agent execution, and two V1 workflows. The workflow
engine synchronously invokes a ManagerAgent, which dispatches to research,
enrichment, email, CRM, and calendar agents.

Async SQLAlchemy is the system of record. SQLite remains supported for development
and tests; PostgreSQL with `asyncpg` is required in production. Alembic owns schema
evolution. Application startup may create tables only in development/test when
`AUTO_CREATE_TABLES=true`.

## Safety boundaries introduced in Phase 0

- Production settings are validated during import/startup and reject insecure keys,
  missing integration encryption, SQLite/localhost databases, debug mode, wildcard
  CORS, automatic table creation, and legacy global customer credentials.
- API access logs are JSON and carry an inbound or generated `X-Request-ID`.
- Logging redacts authorization, cookies, passwords, secrets, tokens, API keys, and
  credential-shaped data.
- Global CRM/email/calendar environment credentials are compatibility fallbacks only
  and are disabled when `ALLOW_LEGACY_ENV_CREDENTIALS=false` (required in production).
- Migrations run as a separate release step; the production server does not mutate
  schema automatically.

## Known V1 boundaries

Phase 0 does not add workspace tenancy. Most V1 business rows are not owner-scoped,
so the application is not ready for multi-customer production use. Workflows are
also synchronous and some V1 email/calendar routes remain mock or local-record-only
behavior. These are explicitly deferred to later phases and documented as risks in
the operations guide.
