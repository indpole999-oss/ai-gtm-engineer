"""Reproduce temp-table shadowing and verify prepared hardening on disposable PG17."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg2
from psycopg2 import sql
import pytest
from postgres_safety import require_disposable_service, verify_major


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_URL"), reason="Disposable PostgreSQL service not configured")
def test_function_paths_prevent_shadowing_preserve_guards():
    service = os.environ["POSTGRES_TEST_URL"]
    url = require_disposable_service(service)
    admin = psycopg2.connect(service)
    verify_major(admin)
    admin.autocommit = True
    name, role = "gaps_paths_" + uuid4().hex, "gaps_paths_role_" + uuid4().hex
    created_db = created_role = False
    db = None
    root = Path(__file__).parents[1]
    try:
        with admin.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created_db = True
            cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role)))
            created_role = True
        env = dict(os.environ, APP_ENV="test", DATABASE_URL=url.set(database=name,
            drivername="postgresql+asyncpg").render_as_string(hide_password=False))
        result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=root, env=env, capture_output=True, timeout=120)
        assert result.returncode == 0, "Isolated migration failed"
        db = psycopg2.connect(url.set(database=name).render_as_string(hide_password=False))
        db.autocommit = True
        w, u, b, v, claim = [str(uuid4()) for _ in range(5)]
        proposal = (root / "scripts/staging_function_search_path.sql").read_text()
        with db.cursor() as cur:
            cur.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES(%s,'Synthetic security test',%s,'active',now(),now())", (w, w))
            cur.execute("INSERT INTO users(id,email,hashed_password,is_active) VALUES(%s,'paths@example.invalid','synthetic',true)", (u,))
            cur.execute("INSERT INTO company_brains(id,workspace_id,created_at) VALUES(%s,%s,now())", (b,w))
            cur.execute("INSERT INTO company_brain_versions(id,workspace_id,brain_id,number,status,profile,revision,created_by,created_at) VALUES(%s,%s,%s,1,'draft','{}',1,%s,now())", (v,w,b,u))
            cur.execute("UPDATE company_brain_versions SET status='published',content_hash=%s WHERE id=%s", ("a"*64,v))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
            cur.execute(sql.SQL("GRANT SELECT ON company_brain_versions TO {}").format(sql.Identifier(role)))
            cur.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON brain_claims TO {}").format(sql.Identifier(role)))
            cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            cur.execute("SELECT set_config('app.workspace_id',%s,false)", (w,))
            cur.execute("CREATE TEMP TABLE company_brain_versions(id uuid,status text)")
            # Positive control: unfixed invoker trigger resolves the empty temp table.
            cur.execute("INSERT INTO public.brain_claims(id,workspace_id,version_id,text,disposition) VALUES(%s,%s,%s,'Synthetic attack probe','approved')", (claim,w,v))
            cur.execute("DELETE FROM public.brain_claims WHERE id=%s", (claim,))
            cur.execute("RESET ROLE")
            cur.execute(proposal)
            cur.execute(proposal)  # Repeat is safe; owners/grants preserved.
            cur.execute("SELECT count(*),bool_and(NOT prosecdef AND proconfig @> ARRAY['search_path=pg_catalog']) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND proname LIKE 'protect_%'")
            assert cur.fetchone() == (10, True)
            cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            with pytest.raises(psycopg2.errors.RaiseException, match="Published brain content"):
                cur.execute("INSERT INTO public.brain_claims(id,workspace_id,version_id,text,disposition) VALUES(%s,%s,%s,'Synthetic attack probe','approved')", (claim,w,v))
            cur.execute("SELECT count(*) FROM public.brain_claims")
            assert cur.fetchone() == (0,)
            cur.execute("SELECT set_config('app.workspace_id',%s,false)", (str(uuid4()),))
            cur.execute("SELECT id FROM public.company_brain_versions")
            assert cur.fetchall() == []  # Invoker/RLS protections retained.
    finally:
        if db:
            db.close()
        with admin.cursor() as cur:
            if created_db:
                cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            if created_role:
                cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        admin.close()
