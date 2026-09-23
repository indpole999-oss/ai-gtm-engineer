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
                uid, ba, bb, va = [str(uuid4()) for _ in range(4)]
                cursor.execute("INSERT INTO users(id,email,hashed_password,is_active) VALUES(%s,'brain@example.com','hash',true)", (uid,))
                cursor.execute("INSERT INTO workspace_memberships(workspace_id,user_id,role,status,created_at,updated_at) VALUES(%s,%s,'owner','active',now(),now())", (a,uid))
                cursor.execute("INSERT INTO company_brains(id,workspace_id,created_at) VALUES(%s,%s,now()),(%s,%s,now())", (ba,a,bb,b))
                cursor.execute("INSERT INTO company_brain_versions(id,workspace_id,brain_id,number,status,profile,revision,created_by,created_at) VALUES(%s,%s,%s,1,'draft','{}',1,%s,now())", (va,a,ba,uid))
                cursor.execute("UPDATE company_brain_versions SET status='published',content_hash=%s WHERE id=%s", ("a" * 64,va))
                ja, fa = str(uuid4()), str(uuid4())
                cursor.execute("INSERT INTO research_jobs(id,workspace_id,company_id,brain_version_id,created_by,status,source_urls,created_at) VALUES(%s,%s,%s,%s,%s,'queued','[]',now())", (ja,a,ca,va,uid))
                cursor.execute("INSERT INTO source_fetches(id,workspace_id,job_id,url,title,publisher,retrieved_at,content,content_hash,extractor_version) VALUES(%s,%s,%s,'https://example.com','Source','example.com',now(),'Original','hash','test')", (fa,a,ja))
                cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
                cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
                cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                cursor.execute("SELECT id FROM companies")
                assert cursor.fetchall() == []
                cursor.execute("SELECT set_config('app.workspace_id',%s,false)",(a,))
                cursor.execute("SELECT id::text FROM companies")
                assert cursor.fetchall() == [(ca,)]
                cursor.execute("SELECT id::text FROM company_brains")
                assert cursor.fetchall() == [(ba,)]
                cursor.execute("SELECT id::text FROM research_jobs")
                assert cursor.fetchall() == [(ja,)]
                with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
                    cursor.execute("UPDATE source_fetches SET content='tampered' WHERE id=%s", (fa,))
                with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                    cursor.execute("INSERT INTO research_jobs(id,workspace_id,company_id,brain_version_id,created_by,status,source_urls,created_at) VALUES(%s,%s,%s,%s,%s,'queued','[]',now())", (str(uuid4()),a,cb,va,uid))
                with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
                    cursor.execute("UPDATE company_brain_versions SET profile='{}' WHERE id=%s", (va,))
                with pytest.raises(psycopg2.errors.RaiseException, match="immutable"):
                    cursor.execute("INSERT INTO brain_claims(id,workspace_id,version_id,text,disposition) VALUES(%s,%s,%s,'Unreviewed','approved')", (str(uuid4()),a,va))
                cursor.execute("DELETE FROM companies WHERE id=%s", (cb,))
                assert cursor.rowcount == 0
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cursor.execute("INSERT INTO companies(id,name,workspace_id) VALUES(%s,'forged',%s)",(str(uuid4()),b))
                with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                    cursor.execute("INSERT INTO contacts(id,email,workspace_id,company_id) VALUES(%s,'bad@example.com',%s,%s)",(str(uuid4()),a,cb))
                cursor.execute("SELECT version_num FROM alembic_version")
                assert cursor.fetchone()[0] == "20260923_0008"
            probe = Path(__file__).with_name("postgres_worker_probe.py").read_text()
            result = subprocess.run([sys.executable, "-c", probe, a, ca, va, uid], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        finally:
            db.close()
    finally:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
            cursor.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.close()
