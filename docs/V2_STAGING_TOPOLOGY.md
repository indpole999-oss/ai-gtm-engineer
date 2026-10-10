# Phase 11 staging topology decision — 2026-09-29

Status: **PREPARED, NOT PROVISIONED OR LIVE-VALIDATED**.

## Decision and cost

Use an operator-attended, local-process rehearsal first, with a completely new
Supabase Free project `gaps-ai-staging`. Run frontend, two API processes, durable
worker and Ollama as separate processes on an existing non-production laptop.
The worker continues to use the existing PostgreSQL commands/outbox/leases;
there is no in-process task queue or production architecture change.

Estimated incremental platform cost: **$0/month** for this rehearsal: Supabase's
account-specific quote was zero, local processes have no hosting charge, and no
Render resources, cloud inference, paid APIs, add-ons or new hardware are selected.
Existing electricity, internet and model-download data consumption are not priced
here. This estimate requires adequate existing hardware and remaining Free limits;
it is not an authorization to upgrade if limits are reached.

This is a partial staging tier, not a substitute for the entire release matrix.
Retain the planned Render API/frontend/separate worker architecture for the later
deployment-parity gate. No cheaper substitute is silently accepted as that gate.

## Completed account checks (reuse; do not repeat without a material change)

- User confirmed read-only inspection of Render `indpole's workspace`
  (`tea-d8eu2t6k1jcs73ace2ug`) and Supabase `AI-GTM-engineer`
  (`wfuddlmtxdueevjyrtar`). Supabase reports Free and quoted a new project at
  **$0/month**. Final slot availability still belongs to the creation flow.
- Requested Render staging names were absent. No resources were created, secrets
  read/copied, deployments triggered, or charges approved.
- Existing Render services are on `main`. Do not change `ai-gtm-engineer`,
  `ai-gtm-engineer-web`, `ai-gtm-engineer-frontend`, their environment groups,
  deploy settings, domains, or shared billing settings.
- Never connect to or alter Supabase `qjkcqdiznthffbqmltrr`, including restoring,
  resuming, branching, reading its data, or copying its credentials.
- Local Python and Node are available. The subsequent authorized read-only host
  inspection below resolves the earlier sandbox-denied hardware inventory.
  No software/model was installed or downloaded. No machine settings were changed.

## Laptop capacity inspection — 2026-09-29

Inspection started from clean checkpoint 503f8fe. WMI/CIM required read-only
sandbox escalation; no installation, process termination, service start, machine
configuration change, or external account recheck was performed.

| Item | Observed result |
|---|---|
| Windows | Windows 11 Home Single Language, 25H2, 64-bit; build 26200.9550. The registry's legacy ProductName says Windows 10, but CIM Caption identifies Windows 11. |
| CPU | Intel Core i3-1215U (12th generation), 6 cores / 8 logical processors |
| RAM | 8.00 GiB installed, 7.69 GiB OS-visible; 1.12–1.15 GiB available during inspection |
| Graphics | Intel UHD integrated graphics; no discrete GPU observed. Do not treat reported AdapterRAM as dedicated model memory or assume acceleration. |
| Disk C: | 267.76 GiB free of 454.94 GiB |
| Python / Node | Existing project Python 3.12.14 and bundled Node executable available |
| Docker | Not found on PATH, standard Docker Desktop executable path, uninstall inventory, or matching running processes/services; no usable engine discovered |
| WSL | wsl.exe exists, but wsl --status reports WSL is not installed |
| Ollama / version | No PATH executable, standard user/system executable, uninstall entry or running process/service found; loopback /api/version unavailable. Version not available. |
| Local models | No default model manifest directory, no configured OLLAMA_MODELS path, and loopback /api/tags unavailable. No available models discovered. |

**Decision: do not run the complete model-backed rehearsal under current memory
pressure.** This is a capacity assessment, not a measured model benchmark or a
claim that this CPU can never run a 4B model. The configured qwen3:4b Q4_K_M
artifact alone is listed at 2.5 GB; inference adds context/runtime memory before
the browser, frontend, two APIs and worker are counted. Paging is not evidence of
adequate capacity, and the existing 90-second request deadline is unverified.
Disk and Windows compatibility are adequate; CPU is plausible for the non-model
services, but inference latency has not been measured. All-process headroom is
currently insufficient for a responsible readiness run.

Native Python/Node processes do not require Docker or WSL; do not install either
to perform this rehearsal. Connecting to remote Supabase does not require a local
database server, but the isolated project and its credentials are still absent,
so connectivity/roles/TLS have not been tested. Do not probe the production project.

If a model trial is later authorized after establishing sufficient headroom, the
exact missing software is the free **Ollama native Windows x64 application** from
the official installer, followed by **qwen3:4b** (for example, `ollama pull qwen3:4b`).
Ollama documents at least 4 GB of installation disk space, plus model storage.
Keep OLLAMA_HOST=127.0.0.1:11434 and OLLAMA_NO_CLOUD=1; record the actual version
and model digest. Do not install yet, use a smaller model as acceptance evidence,
extend timeouts to manufacture a pass, change paging settings, or close user apps.
Sources: [Windows installation](https://docs.ollama.com/windows),
[exact model artifact](https://ollama.com/library/qwen3:4b).

Safest free alternative: use another already-owned non-production computer with
more available RAM for this same separate-process topology, keeping Ollama on
loopback. A **16 GiB or larger host is a practical planning target**, not a verified
minimum or a performance guarantee; benchmark the original workload and deadline.
Moving the whole rehearsal there avoids exposing Ollama to the network. No host
is assumed to exist and no hardware purchase is authorized. This laptop may still
be used for bounded non-model tests after freeing headroom voluntarily, but those
tests cannot complete model/live-provider or hosted deployment acceptance.

No staging services were started, resources created, credentials requested, paid
calls made, or provider writes enabled. Model/version, simultaneous resource use,
Supabase connectivity and the primary staging journey remain NOT RUN/BLOCKED.

## Options considered

| Option | Decision | Honest validation scope / constraint |
|---|---|---|
| API + worker in one Free Render service | Reject as the main rehearsal | Separate child processes could smoke-test dispatch, but share sleep, memory and service restart. Cannot prove independent worker deployment/availability. The existing worker is not an HTTP server; supervising multiple children would add staging-only machinery. No keep-alive workaround. |
| Render API + local dedicated worker and model | Defer | Database queue permits outbound-only local worker access. However API planning also calls Ollama. Current HTTP clients have no model authentication configuration; do not expose port 11434 or put credentials in a URL. A reviewed private network/authenticated gateway plus client support is required. Shared Render hours/overage eligibility also remains a prerequisite. |
| Scheduled GitHub Actions / cron as the worker | Reject for durability acceptance | Bounded scheduled jobs are not the long-running worker lifecycle. Do not use CI as an always-on host. Existing CI remains useful for disposable offline tests. |
| Local API(s), frontend, separate worker/model + separate Supabase | **Selected for the zero-cost rehearsal** | Preserves code paths, persistent queue, real PostgreSQL and independent process failure. Model remains loopback-only. Host/power/network failure is shared and Render-specific gates remain open. |
| Separate paid Render worker + Free web services | Deferred cost option | Minimum listed worker compute is `0.5c-512mb` (legacy Starter), **$7/month** at current public pricing, prorated for actual duration. This is only the worker cost floor, not a full-staging quote: model hosting, sufficient memory, usage and availability need separate assessment. No paid resource is authorized. |

Render Free web instances share 750 hours/month across the workspace, sleep after
15 minutes without inbound traffic, and do not provide a Free worker type. Adding
staging could exhaust the pool used by existing services. Free web services also
have build/bandwidth quotas and possible supplementary billing. Therefore no
Render resource is selected for this zero-cost tier, and no shared billing setting
is modified to enforce its budget. Source: [Render Free](https://render.com/docs/free).
Worker plans and current pricing: [compute plans](https://render.com/docs/compute-plans),
[pricing](https://render.com/pricing). Reconfirm the quote only if a paid option is
later explicitly requested; $7 does not guarantee this workload fits 512 MB.

## Exact selected topology

```text
Browser -> frontend 127.0.0.1:3000 -> API A 127.0.0.1:8000
                                   API B 127.0.0.1:8001 (replica tests)
API A/B -------------------------> separate Supabase gaps-ai-staging
separate execution_worker -------> same staging PostgreSQL queue/leases
API A/B + worker ----------------> Ollama 127.0.0.1:11434
separate operator observer ------> health/ready/operations + process state
```

Use the same manually selected, CI-green SHA on
`codex/ai-gtm-engineer-v2-full-build` for all processes. No watchers, scheduled
deploys, paid jobs, or automatic branch deploys. A local process restart does not
update code unless the operator explicitly selects a new validated SHA.

The current frontend is TanStack Start/Nitro `node-server`, not a static export.
Build in `frontend` with `npm ci` then `npm run build`; start with
`node .output/server/index.mjs` and HOST=127.0.0.1, PORT=3000. Set the build-time
VITE_API_BASE_URL before building; it is an origin, without `/api/v1`.

From repository root, each API uses its own process:

```text
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --no-access-log --no-proxy-headers
python -m backend.execution_worker
```

Run the worker independently, not as a child of the API. Stop/restart only these
known staging PIDs during failure tests. Laptop sleep/offline time means an
intentional outage, not a successful availability test. Neither APIs nor Ollama
listen on all interfaces. Do not create a public model tunnel.

Ollama: OLLAMA_HOST=127.0.0.1:11434 and OLLAMA_NO_CLOUD=1; use the repository's
qwen3:4b local model, recording its digest and Ollama version. First confirm disk,
memory and licensing/download feasibility. Measure schema-valid responses and
research quality within the application's existing 90-second provider timeout.
If the laptop cannot meet it, report BLOCKED; do not silently shorten test inputs,
change models/timeouts, buy a GPU, or fall back to a cloud model. Official setup:
[Ollama FAQ](https://docs.ollama.com/faq).

## Environment and secret destinations

The local non-secret template is `deployment/staging/local.env.example`. Do not
load the repository's legacy `.env.example` or copy an existing production `.env`.
Supply secrets through a local password manager/process environment; do not commit
an actual env file or print environment dumps. The running API/worker need only
runtime database credentials; migration/bootstrap credentials must never be in
those processes or the frontend.

| Variable | Local rehearsal value / destination |
|---|---|
| APP_ENV | `staging` for loopback HTTP; deliberately NOT evidence of production HTTPS/config validation |
| DEBUG / AUTO_CREATE_TABLES / ALLOW_LEGACY_ENV_CREDENTIALS | `false` / `false` / `false` |
| DATABASE_URL | New Supabase runtime role URL, SQLAlchemy asyncpg, TLS required and verified; never postgres/admin or production ref |
| SECRET_KEY | Newly generated >=32-character secret; identical across API replicas/worker |
| INTEGRATION_ENCRYPTION_KEY | Newly generated Fernet key; identical across processes; protected recovery copy |
| AUTH_ADMISSION_STORE / AUTH_PEER_LIMIT / AUTH_GLOBAL_LIMIT | `database` / `30` / `300`, identical across replicas |
| ALGORITHM / ACCESS_TOKEN_EXPIRE_MINUTES | `HS256` / `60` |
| FRONTEND_URL / CORS_ORIGINS | `http://localhost:3000` / `["http://localhost:3000"]`; use this browser origin consistently |
| VITE_API_BASE_URL | `http://localhost:8000`, frontend build only |
| GTM_LOCAL_MODEL_URL / GTM_LOCAL_MODEL | `http://127.0.0.1:11434` / `qwen3:4b` |
| LOG_LEVEL | `INFO`; protected local metadata logs; no retention duration chosen |
| GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | Empty until dedicated OAuth test project gate; then local secret store |
| GOOGLE_REDIRECT_URI | `http://localhost:8000/api/v1/calendar/oauth/google/callback` for a separately registered local test OAuth client; hosted HTTPS gate remains distinct |
| SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_KEY | Empty; V2 uses direct PostgreSQL and application auth, not browser Supabase access |
| OpenAI/NVIDIA, search/enrichment, mail/SMTP, CRM/provider keys | Empty; later workspace test credentials go through reviewed integration UI only |
| Retention durations / purge | Unset / disabled; no new purge or lifecycle variables invented |

Loopback HTTP intentionally does not pass the production URL validator. Do not
weaken that validator, relabel this as APP_ENV=production, or expose this profile
publicly. A later HTTPS deployment must use APP_ENV=production and pass every
existing security check. Set even the non-required local safety flags explicitly.

## Database roles and migration/restore sequence

Use the new project's Connect panel to obtain its real host/reference, never infer
them from production. Prefer shared **session** pooler port 5432 for IPv4 access;
do not use transaction pooler port 6543 with the current asyncpg configuration.
Use `postgresql+asyncpg://` for application/Alembic and driver-appropriate TLS
verification with the project's CA; do not copy libpq `sslmode` options blindly
into asyncpg. Verify encryption/identity before any rehearsal. Use direct access
for administrative/dump tools when reachable; do not buy an IPv4 add-on.
[Supabase connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres).

| Identity | Required privileges | Restrictions |
|---|---|---|
| New-project bootstrap operator | Create staging roles and grant access, disable unused Data API exposure | One-time setup only; never an app identity |
| gaps_staging_migrator | LOGIN, schema USAGE/CREATE and ownership of app objects, migration/data-backfill rights | NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE; no runtime membership in this role |
| gaps_staging_runtime | LOGIN, CONNECT, schema USAGE; explicit SELECT/INSERT/UPDATE/DELETE on migrated app tables needed by API/worker; sequence USAGE where required | NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE, no schema CREATE/ownership/admin membership |
| runtime exceptions | SELECT on alembic_version; DML on auth_admission_buckets | No mutation of alembic_version and no access to legacy_ownership_audit |
| anon/authenticated/PUBLIC | No app table access, including auth_admission_buckets | No browser Data API escape around FastAPI authorization |

Provision only in a verified new, empty project. Review effective privileges,
including PUBLIC/default grants and role memberships: NOINHERIT alone does not
prevent SET ROLE. Prevent default grants to Supabase client roles for objects made
by the migrator. Recheck grants after each migration instead of blanket granting
all managed Supabase schemas. Preserve forced RLS and immutable evidence triggers.
App authorization uses workspace membership plus `app.workspace_id`, not
Supabase auth.uid(). Reference: [Supabase roles](https://supabase.com/docs/guides/database/postgres/roles).

1. Resolve the zero-cost tier decision and verify a free project slot at creation;
   if the quote changes or payment is required, stop. Generate the new project's
   database password in the operator's password manager, not chat.
2. Record and allowlist the new project ref. Explicitly reject
   `qjkcqdiznthffbqmltrr` in every deployment/migration target review. Disable unused
   Data API exposure on this project. Create the roles above, with passwords set
   privately; verify TLS and identities. No migration command runs until this is done.
3. With the migration role in a separate terminal, run `python -m alembic upgrade
   head`, `python -m alembic current`, and `python -m alembic upgrade head` again.
   Expect 20260928_0013 and a no-op second upgrade. Grant reviewed runtime access.
4. Start API only; require /api/v1/ready=200 and runtime role constraints before
   seeding. Through application registration/workspace APIs create two synthetic
   tenants and owner/admin/member/viewer cases; never import customer records.
5. For the populated 0012-to-0013 rehearsal, reuse the existing disposable CI test
   evidence initially. Hosted restore needs a separately allowlisted EMPTY target
   and matching PostgreSQL-major tools, not an overwrite of the staging project.
   Export only app-owned synthetic tables/functions/evidence (not Supabase managed
   auth/storage schemas) with ownership/ACL restoration handled explicitly. Record
   hashes, revisions, counts, immutable evidence and quarantine checks. Full recovery
   stays BLOCKED until a free isolated target and scoped archive are verified.
   Never point POSTGRES_TEST_URL at Supabase: that test creates/drops databases/roles.
6. Validate readiness, RLS, grants and immutable chains after restore, including
   an absent workspace context and deliberately mismatched tenant relationships.
   Never downgrade, stamp, disable RLS, use pg_restore --clean or overwrite data.

Supabase's installed major version must be recorded after creation; existing CI
restore evidence is PostgreSQL 16, not proof for an untested hosted major. No
production upgrade is implied. Latest Supabase changelog includes extension and
operator restore changes; the application migration source contains no explicit
ltree/btree_gist/custom-operator creation, but inspect the NEW project extensions
before restore. [Supabase changelog](https://supabase.com/changelog).

## What this tier can genuinely prove

All execution results below are **NOT RUN in this topology**. Capability is not
evidence. Tie each actual result to SHA, environment, UTC time and reviewer.

| Gate | Local + separate Supabase capability | Still required for release |
|---|---|---|
| Schema/readiness/tenant/RBAC | Real PostgreSQL migrations, runtime-role grants, two tenants and API/browser negative tests | Hosted major compatibility, full restore target, least-privilege migration/backup evidence |
| Shared admission | Two local API processes sharing one database; alternate requests, restart, outage | Render replicas/ingress IP and spoof resistance; cannot claim public proxy equivalence |
| Durable worker | Separate real worker process; kill only worker during approved synthetic work, restart and lease recovery | Dedicated host/service isolation, Render SIGTERM/redeploy/OOM, continuous availability and supervision |
| Model/research | Actual local Ollama model, reviewed permitted sources, citations/unknowns and bounded timeout | Stable production-like private model service, capacity/concurrency, host isolation and availability |
| Browser journey | Actual frontend server and browser, workspace/role switching, expired sessions, approvals | Hosted TLS/CORS/cold starts, real-provider portions and deployed end-to-end journey |
| OAuth | Can test local callback after a separate Google web test client/consent | Actual dedicated account authorization, hosted HTTPS callback, ingress redaction; NOT RUN until authorized |
| Mail/inbox/calendar/CRM | Fail-closed states and explicitly labeled fake-provider contract tests | Live transport implementations, signed callbacks, durable identity/conflicts, dedicated provider accounts; no fake live claims |
| Monitoring | Observe separate PIDs, queue/lease errors, database outage, scoped operations JSON and logs | External notification delivery/ack/recovery, independent-host observer, worker heartbeat and provider telemetry |
| Recovery | CI synthetic restore evidence plus future scoped restore into separate empty target | Full evidence/key custody, exact hosted version, RPO/RTO/locking/scale and isolated recovery target |
| Retention/cost | Unset durations, no purge, cost remains unavailable without receipts | Approved policy, implementation and authoritative provider usage; no fabricated zero usage |

Run the existing ordered matrix in V2_STAGING_VALIDATION.md, marking unsupported
rows BLOCKED rather than treating this document as acceptance. Platform account
read-only access is not OAuth consent for a provider, and a healthy connection
is not an approved send/event/CRM mutation.

## Deferred Render configuration (not applied)

| Service | Exact source/start settings | Planned origin |
|---|---|---|
| ai-gtm-engineer-staging-api | V2 branch; root repository; Python 3.12.13; `pip install -r requirements.txt`; `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --no-access-log --no-proxy-headers`; health /api/v1/ready | https://ai-gtm-engineer-staging-api.onrender.com |
| ai-gtm-engineer-staging-web | V2 branch; root frontend; Node 22; `npm ci && npm run build`; `node .output/server/index.mjs`; HOST=0.0.0.0 | https://ai-gtm-engineer-staging-web.onrender.com |
| ai-gtm-engineer-staging-worker | V2 branch; root repository; same Python/build; `python -m backend.execution_worker`; separate service | No public URL; paid worker blocked |

For all three, autoDeployTrigger=off and previews off. Disable raw access logs.
The conservative no-proxy-headers start command means peer buckets may group
ingress peers; trusted proxy handling must be validated before changing it.
No cron, disk, Redis, shared production env group, or migration-on-start is needed.
Render Free lacks one-off jobs/shell; run reviewed migrations from the controlled
operator terminal with only the migration credential, never from build/start.

When the hosted tier is separately authorized, set APP_ENV=production, frontend
origin and CORS to the planned staging web HTTPS origin, VITE_API_BASE_URL to the
API HTTPS origin, and register exactly:
`https://ai-gtm-engineer-staging-api.onrender.com/api/v1/calendar/oauth/google/callback`.
OAuth returns to `https://ai-gtm-engineer-staging-web.onrender.com/settings`.
These names are candidates, not allocated URLs. Verify the actual assigned URLs
before registering consent. Do not change production callbacks or reuse its client.

## Next operator gate

No payment is necessary to select this local rehearsal. Before provisioning,
confirm this laptop (or another already-owned non-production host) may run the
local worker/model, identify whether Ollama is installed, and verify resources
for qwen3:4b. No provider credentials are needed yet. If model capacity is absent,
complete the non-model tests and leave model acceptance blocked rather than
buying compute or changing production design.

Next credential gate is a NEW Supabase project database password and separate
migrator/runtime credentials: configure privately through the new project's
Dashboard/Connect flow and local secret manager, never chat. The quoted Free
project is sufficient for bounded synthetic database tests if a slot is available.
No creation has occurred. Later Google/email/HubSpot connections remain separate
one-time test-account gates described in V2_STAGING_VALIDATION.md.
