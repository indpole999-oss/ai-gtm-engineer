"""Synthetic backup/restore rehearsal; only an explicit disposable CI service."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg2
from psycopg2 import sql
import pytest
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_URL"), reason="Disposable PostgreSQL service not configured")
def test_populated_backup_restore_then_additive_upgrade(tmp_path):
    service = make_url(os.environ["POSTGRES_TEST_URL"])
    names = ["gaps_restore_" + uuid4().hex for _ in range(2)]
    runtime = "gaps_runtime_" + uuid4().hex
    admin = psycopg2.connect(service.render_as_string(hide_password=False))
    admin.autocommit = True
    created = []
    role_created = False

    def migrate(name, revision):
        env = dict(os.environ, APP_ENV="test", DATABASE_URL=service.set(
            database=name, drivername="postgresql+asyncpg").render_as_string(hide_password=False))
        result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision],
                                env=env, capture_output=True, timeout=120)
        assert result.returncode == 0, "Isolated migration failed; inspect protected CI diagnostics"

    def archive_command(tool, name, *args):
        # Passwords stay out of argv and subprocess output is never echoed.
        env = dict(os.environ, PGHOST=service.host or "localhost",
                   PGPORT=str(service.port or 5432), PGUSER=service.username or "postgres",
                   PGPASSWORD=service.password or "", PGDATABASE=name)
        executable = str(Path(os.environ.get("PG_BIN", "")) / tool)
        result = subprocess.run([executable, *args], env=env, capture_output=True, timeout=120)
        assert result.returncode == 0, f"Isolated {tool} failed"

    try:
        with admin.cursor() as cur:
            for name in names:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(runtime)))
            role_created = True
        migrate(names[0], "20260926_0012")
        workspace_a, workspace_b, company_a, company_b, quarantine = [str(uuid4()) for _ in range(5)]
        with psycopg2.connect(service.set(database=names[0]).render_as_string(hide_password=False)) as source:
            with source.cursor() as cur:
                cur.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES (%s,'Synthetic A','restore-a','active',now(),now()),(%s,'Synthetic B','restore-b','active',now(),now())", (workspace_a, workspace_b))
                cur.execute("INSERT INTO companies(id,name,domain,workspace_id) VALUES (%s,'Synthetic A','restore.example',%s),(%s,'Synthetic B','restore.example',%s),(%s,'Quarantined','quarantine.example',NULL)", (company_a, workspace_a, company_b, workspace_b, quarantine))
                cur.execute("SELECT id::text,name,domain,workspace_id::text FROM companies ORDER BY id")
                expected = cur.fetchall()
        archive = str(tmp_path / "synthetic.dump")
        archive_command("pg_dump", names[0], "--format=custom", "--no-owner", "--no-acl", "--file", archive)
        # Restore into a newly created empty database; never clean/replace a target.
        archive_command("pg_restore", names[1], "--exit-on-error", "--single-transaction",
                        "--no-owner", "--no-acl", "--dbname", names[1], archive)
        with psycopg2.connect(service.set(database=names[1]).render_as_string(hide_password=False)) as restored:
            with restored.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version")
                assert cur.fetchone() == ("20260926_0012",)
                cur.execute("SELECT id::text,name,domain,workspace_id::text FROM companies ORDER BY id")
                assert cur.fetchall() == expected
        migrate(names[1], "head")
        migrate(names[1], "head")  # Repeated release operation must be a no-op.
        with psycopg2.connect(service.set(database=names[1]).render_as_string(hide_password=False)) as restored:
            with restored.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version")
                assert cur.fetchone() == ("20261008_0014",)
                cur.execute("SELECT id::text,name,domain,workspace_id::text FROM companies ORDER BY id")
                assert cur.fetchall() == expected
                cur.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='companies'::regclass")
                assert cur.fetchone() == (True, True)
                cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(names[1]), sql.Identifier(runtime)))
                cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(runtime)))
                cur.execute(sql.SQL("GRANT SELECT ON companies TO {}").format(sql.Identifier(runtime)))
                cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(runtime)))
                cur.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
                assert cur.fetchone() == (False, False)
                cur.execute("SELECT id FROM companies")
                assert cur.fetchall() == []
                cur.execute("SELECT set_config('app.workspace_id',%s,true)", (workspace_a,))
                cur.execute("SELECT id::text FROM companies")
                assert cur.fetchall() == [(company_a,)]
                cur.execute("SELECT has_table_privilege(current_user,'auth_admission_buckets','SELECT')")
                assert cur.fetchone() == (False,)
                cur.execute("SELECT has_schema_privilege(current_user,'public','CREATE')")
                assert cur.fetchone() == (False,)
    finally:
        # Only exact generated resources created by this invocation are removed.
        with admin.cursor() as cur:
            for name in created:
                cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            if role_created:
                cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(runtime)))
        admin.close()
