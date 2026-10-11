"""Only an explicitly supplied disposable PostgreSQL service may run this test."""
import os
from postgres_safety import require_disposable_service, verify_major
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg2
from psycopg2 import sql
import pytest
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_URL"), reason="Disposable PostgreSQL service not configured")
def test_postgres_original_deadlock_and_workspace_first_regression():
    service = os.environ["POSTGRES_TEST_URL"]
    require_disposable_service(service)
    name = "gaps_lock_" + uuid4().hex
    admin = psycopg2.connect(service)
    verify_major(admin)
    admin.autocommit = True
    created = False
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created = True
        url = make_url(service).set(database=name, drivername="postgresql+asyncpg")
        env = dict(os.environ, APP_ENV="test", DATABASE_URL=url.render_as_string(hide_password=False),
                   AUTO_CREATE_TABLES="false", OUTBOUND_EMAIL_ENABLED="false",
                   MAILBOX_INGESTION_ENABLED="false", CRM_READS_ENABLED="false", GTM_HOSTED_AI_ENABLED="false")
        root = Path(__file__).resolve().parents[1]
        for arguments in (["-m", "alembic", "upgrade", "head"],
                          [str(Path(__file__).with_name("postgres_mailbox_lock_probe.py"))],
                          [str(Path(__file__).with_name("postgres_signed_mailbox_probe.py"))]):
            result = subprocess.run([sys.executable, *arguments], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=120)
            assert result.returncode == 0, result.stdout + result.stderr
    finally:
        if created:
            with admin.cursor() as cursor:
                cursor.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        admin.close()
