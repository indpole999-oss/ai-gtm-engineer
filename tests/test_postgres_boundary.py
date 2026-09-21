"""Run only against an explicitly supplied disposable PostgreSQL CI service."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
import psycopg2
from psycopg2 import sql


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_URL"), reason="Disposable PostgreSQL service not configured")
def test_postgres_rls_and_composite_relationships():
    service = os.environ["POSTGRES_TEST_URL"]
    database = "gaps_test_" + uuid4().hex
    role = "gaps_role_" + uuid4().hex
    admin = psycopg2.connect(service)
    admin.autocommit = True
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role)))
        from sqlalchemy.engine import make_url
        url = make_url(service).set(database=database)
        env = dict(os.environ, APP_ENV="test", DATABASE_URL=url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False))
        result = subprocess.run([sys.executable,"-m","alembic","upgrade","head"],
                                cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        db = psycopg2.connect(url.render_as_string(hide_password=False))
        db.autocommit = True
        try:
            a, b, ca, cb = [str(uuid4()) for _ in range(4)]
            with db.cursor() as cursor:
                cursor.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES(%s,'A','a','active',now(),now()),(%s,'B','b','active',now(),now())", (a,b))
                cursor.execute("INSERT INTO companies(id,name,domain,workspace_id) VALUES(%s,'A','same.example',%s),(%s,'B','same.example',%s)",(ca,a,cb,b))
                cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
                cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
                cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                cursor.execute("SELECT id FROM companies")
                assert cursor.fetchall() == []
                cursor.execute("SELECT set_config('app.workspace_id',%s,false)",(a,))
                cursor.execute("SELECT id::text FROM companies")
                assert cursor.fetchall() == [(ca,)]
                cursor.execute("DELETE FROM companies WHERE id=%s", (cb,))
                assert cursor.rowcount == 0
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cursor.execute("INSERT INTO companies(id,name,workspace_id) VALUES(%s,'forged',%s)",(str(uuid4()),b))
                with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                    cursor.execute("INSERT INTO contacts(id,email,workspace_id,company_id) VALUES(%s,'bad@example.com',%s,%s)",(str(uuid4()),a,cb))
                cursor.execute("SELECT version_num FROM alembic_version")
                assert cursor.fetchone()[0] == "20260922_0004"
        finally:
            db.close()
    finally:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.close()
