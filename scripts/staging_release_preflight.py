"""Operator-only read-only checks. Never import application startup or print secrets."""
import argparse
import json
import os
from urllib.parse import urlsplit

from cryptography.fernet import Fernet

API_HOST = "gaps-ai-v2-staging-api.onrender.com"
WEB_HOST = "gaps-ai-v2-staging-web.onrender.com"
STAGING_REF = "xhjkahbtckrrhuzamysr"
PRODUCTION_REF = "qjkcqdiznthffbqmltrr"
REQUIRED = (
    "APP_ENV", "DEBUG", "AUTO_CREATE_TABLES", "ALLOW_LEGACY_ENV_CREDENTIALS",
    "AUTH_ADMISSION_STORE", "SECRET_KEY", "ALGORITHM", "INTEGRATION_ENCRYPTION_KEY",
    "DATABASE_URL", "FRONTEND_URL", "CORS_ORIGINS", "OUTBOUND_EMAIL_ENABLED",
    "MAILBOX_INGESTION_ENABLED", "CRM_READS_ENABLED", "GTM_HOSTED_AI_ENABLED",
    "EMBEDDED_EXECUTION_WORKER",
)
OFF = ("DEBUG", "AUTO_CREATE_TABLES", "ALLOW_LEGACY_ENV_CREDENTIALS",
       "OUTBOUND_EMAIL_ENABLED", "MAILBOX_INGESTION_ENABLED", "CRM_READS_ENABLED",
       "GTM_HOSTED_AI_ENABLED", "EMBEDDED_EXECUTION_WORKER")


def origin_matches(value, host):
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.hostname == host and url.port in (None, 443)
                and not url.username and not url.password and url.path in ("", "/")
                and not url.query and not url.fragment)
    except (ValueError, TypeError):
        return False


def environment_report(env, frontend=False):
    if frontend:
        return {"presence": {"VITE_API_BASE_URL": bool(env.get("VITE_API_BASE_URL"))},
                "checks": {"staging_api_origin": origin_matches(env.get("VITE_API_BASE_URL", ""), API_HOST)}}
    checks = {name + "_off": env.get(name, "").strip().lower() in {"0", "false", "off", "no"}
              for name in OFF}
    checks.update({"production_security_profile": env.get("APP_ENV") == "production",
                   "shared_admission": env.get("AUTH_ADMISSION_STORE") == "database",
                   "signing_algorithm": env.get("ALGORITHM") == "HS256",
                   "signing_key_nondefault": len(env.get("SECRET_KEY", "")) >= 32
                       and env.get("SECRET_KEY") not in {"your-secret-key-min-32-chars", "change-me-in-production"},
                   "staging_frontend_origin": origin_matches(env.get("FRONTEND_URL", ""), WEB_HOST)})
    try:
        Fernet(env.get("INTEGRATION_ENCRYPTION_KEY", "").encode())
        checks["encryption_key_format"] = True
    except (ValueError, TypeError):
        checks["encryption_key_format"] = False
    try:
        origins = json.loads(env.get("CORS_ORIGINS", ""))
        checks["exact_staging_cors"] = (isinstance(origins, list) and len(origins) == 1
                                         and origin_matches(origins[0], WEB_HOST))
    except (ValueError, TypeError):
        checks["exact_staging_cors"] = False
    return {"presence": {name: bool(env.get(name)) for name in REQUIRED}, "checks": checks}


def database_report(env, expected_revision="20261011_0016"):
    """Separate probe URL: do not reinterpret asyncpg TLS settings as libpq settings."""
    from sqlalchemy.engine import make_url
    import psycopg2

    # Operator supplies a libpq URL with the SAME runtime identity, expected host
    # and database through a private environment. No defaults or target inference.
    url = make_url(env.get("STAGING_PREFLIGHT_DATABASE_URL", ""))
    host, database = env.get("STAGING_PREFLIGHT_EXPECTED_HOST"), env.get("STAGING_PREFLIGHT_EXPECTED_DATABASE")
    if (url.drivername != "postgresql" or not host or not database
            or url.host != host or url.database != database
            or host != "db." + STAGING_REF + ".supabase.co" or PRODUCTION_REF in host
            or url.username != "gaps_staging_runtime"
            or url.query.get("sslmode") != "verify-full"
            or not url.query.get("sslrootcert")
            or set(url.query) - {"sslmode", "sslrootcert"}):
        raise ValueError("Probe target validation failed")
    with psycopg2.connect(url.render_as_string(hide_password=False), connect_timeout=5,
                          options="-c default_transaction_read_only=on -c statement_timeout=5000") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user = 'gaps_staging_runtime', current_database() = %s, "
                        "current_setting('transaction_read_only') = 'on', "
                        "EXISTS (SELECT 1 FROM pg_stat_ssl WHERE pid=pg_backend_pid() AND ssl), "
                        "current_setting('server_version_num')::int / 10000 = 17", (database,))
            identity = cur.fetchone()
            cur.execute("SELECT version_num = %s FROM public.alembic_version", (expected_revision,))
            revisions = cur.fetchall()
            cur.execute("SELECT has_table_privilege(current_user,'public.alembic_version','SELECT') "
                        "AND NOT (has_table_privilege(current_user,'public.alembic_version','INSERT') "
                        "OR has_table_privilege(current_user,'public.alembic_version','UPDATE') "
                        "OR has_table_privilege(current_user,'public.alembic_version','DELETE') "
                        "OR has_table_privilege(current_user,'public.alembic_version','TRUNCATE') "
                        "OR has_table_privilege(current_user,'public.alembic_version','REFERENCES') "
                        "OR has_table_privilege(current_user,'public.alembic_version','TRIGGER'))")
            least_privilege = bool(cur.fetchone()[0])
    return dict(zip(("runtime_identity", "expected_database", "read_only_transaction", "tls_connection", "postgres_17"), identity),
                allowed_revision=len(revisions) == 1 and revisions[0][0], revision_select_only=least_privilege)


def main(argv=None, env=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", action="store_true")
    parser.add_argument("--database", action="store_true")
    parser.add_argument("--expected-revision", choices=("20261009_0015", "20261011_0016"))
    args = parser.parse_args(argv)
    if args.frontend and args.database:
        parser.error("Select API database checks or frontend checks")
    if args.database and not args.expected_revision:
        parser.error("Database check requires an explicit expected revision")
    env = os.environ if env is None else env
    report = environment_report(env, args.frontend)
    if args.database:
        try:
            report["database"] = database_report(env, args.expected_revision)
        except Exception:
            # Driver/URL exceptions can contain credentials; never print them.
            report["database"] = {"probe_completed": False}
    print(json.dumps(report, sort_keys=True))
    return 0 if all(all(values.values()) for values in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
