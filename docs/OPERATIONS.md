# Operations and Migration Guide

## Configuration modes

`APP_ENV` accepts ordinary environment labels; only the exact value `production`
enables production validation. Tests set `APP_ENV=test`. Development defaults remain
convenient but are not production-safe.

### Required production values

- `APP_ENV=production`
- `SECRET_KEY`: unique random value of at least 32 characters; rotate through a
  controlled session invalidation procedure.
- `INTEGRATION_ENCRYPTION_KEY`: a valid Fernet key. Back it up in a secret manager;
  losing it makes stored integration credentials unreadable.
- `DATABASE_URL`: a non-local PostgreSQL URL. `postgresql://` is normalized to
  `postgresql+asyncpg://`, but the explicit async form is recommended.
- `ALLOW_LEGACY_ENV_CREDENTIALS=false`
- `AUTO_CREATE_TABLES=false`
- `DEBUG=false`
- `CORS_ORIGINS`: JSON list of explicit HTTPS frontend origins; wildcard is rejected.

Provider credentials must be stored through user-owned Integration records. Global
`HUBSPOT_API_KEY`, Salesforce tokens, Resend/SendGrid/SMTP credentials, and Google
service-account configuration are development compatibility paths only and are not
silently consulted in production.

## Migration strategy

Revision `20260921_0001` is the V1 baseline. It accurately creates the current
SQLAlchemy tables on an **empty** database. Its upgrade intentionally uses normal
`CREATE TABLE` statements and will fail if the tables already exist. This guards
against silently declaring an unknown production schema compatible.

### Empty database

```bash
alembic upgrade head
alembic current
```

### Already-existing V1 database

Do not run the baseline upgrade directly. Instead:

1. Take and verify a restorable database backup.
2. Put schema-changing application releases on hold.
3. Inspect the target database and compare all seven tables, columns, types,
   nullable constraints, primary keys, foreign keys, and indexes against both
   `backend/database.py` and `migrations/versions/20260921_0001_v1_schema_baseline.py`.
4. Resolve any drift with a separately reviewed, forward-only reconciliation
   migration. Never drop/recreate a production table to match the baseline.
5. In a restored staging copy, run application smoke tests and verify row counts and
   representative reads.
6. Only after exact compatibility is confirmed, mark the existing schema without
   executing baseline DDL:

   ```bash
   alembic stamp 20260921_0001
   alembic current
   ```

7. Apply future revisions normally with `alembic upgrade head`.

`alembic stamp` changes only Alembic's version marker; it does not validate or alter
existing application tables. Therefore the verification and backup steps are
mandatory and must be recorded in the release change ticket.

### Release order

1. Backup and validate recovery.
2. Run `alembic upgrade head` from the exact application release image.
3. Require migration success before starting/replacing API instances.
4. Start the API with `AUTO_CREATE_TABLES=false`.
5. Poll `/api/v1/health` and perform authenticated smoke checks.
6. Keep rollback application-compatible; do not automatically run destructive
   Alembic downgrades against production data.

## Containers

`deployment/Dockerfile` builds the backend. `frontend/Dockerfile` produces the
TanStack/Nitro Node server. `docker-compose.yml` provides local PostgreSQL, a
one-shot migration service, backend, and frontend. Production systems should use
the same image separation and health probes but external managed secrets/databases.

The frontend API URL is embedded at build time through `VITE_API_BASE_URL`; build a
frontend artifact for the intended API origin. Backend provider secrets must never
be passed as frontend build arguments.

## Logging

Backend logs are one-line JSON with timestamp, level, logger, message, and request
ID. HTTP responses echo `X-Request-ID`. Do not log request bodies, Authorization or
Cookie headers, integration records, decrypted provider responses, or connection
URLs. Redaction is defense-in-depth, not permission to log secret-bearing objects.

## Safe checks

```bash
pytest -q
DATABASE_URL=sqlite+aiosqlite:////tmp/phase0-migration.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:////tmp/phase0-migration.db alembic current
cd frontend && npx tsc --noEmit && npm run build
```

External provider calls are excluded from Phase 0 tests.

## Unresolved production risks

- Core company/contact/email/CRM/meeting data is not tenant-scoped. Multi-customer
  production use must wait for Phase 1.
- JWT sessions have no refresh/revocation or managed identity provider.
- V1 workflows run synchronously and lack durable retries/idempotency.
- The email API contains legacy mock behavior and must not be interpreted as
  provider-confirmed delivery.
- Provider webhook verification and reconciliation are not implemented.
- Secrets are encrypted with one application Fernet key, not a managed per-tenant
  envelope-encryption system.
