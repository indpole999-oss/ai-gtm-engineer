"""Exercise proposed grants only on a generated disposable loopback PG17 database."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg2
from psycopg2 import sql
import pytest
from postgres_safety import require_disposable_service, verify_major


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_URL"), reason="Disposable PostgreSQL service not configured")
def test_staging_permission_proposal_atomicity_and_inherited_grants():
    service = os.environ["POSTGRES_TEST_URL"]
    url = require_disposable_service(service)
    admin = psycopg2.connect(service)
    verify_major(admin)
    admin.autocommit = True
    name = "gaps_release_" + uuid4().hex
    roles = ("gaps_staging_migrator", "gaps_staging_runtime")
    created = []
    made_database = False
    db = None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT rolname FROM pg_roles WHERE rolname IN %s", (roles,))
            assert cur.fetchall() == [], "Reserved test roles already exist; refuse reuse"
            for role in roles:
                cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE").format(sql.Identifier(role)))
                created.append(role)
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            made_database = True
        db = psycopg2.connect(url.set(database=name).render_as_string(hide_password=False))
        db.autocommit = True
        proposal = (Path(__file__).parents[1] / "scripts/staging_revision_permissions.sql").read_text()
        with db.cursor() as cur:
            cur.execute("CREATE TABLE public.alembic_version(version_num text PRIMARY KEY)")
            cur.execute("INSERT INTO public.alembic_version VALUES ('20261009_0015')")
            cur.execute("ALTER TABLE public.alembic_version OWNER TO gaps_staging_migrator")
            cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.alembic_version TO gaps_staging_runtime")
            # A wrong operator identity must abort without changing grants.
            with pytest.raises(psycopg2.errors.RaiseException):
                cur.execute(proposal)
            cur.execute("ROLLBACK")
            cur.execute("SET ROLE gaps_staging_migrator")
            cur.execute(proposal)
            cur.execute("SET ROLE gaps_staging_runtime")
            cur.execute("SELECT version_num FROM public.alembic_version")
            assert cur.fetchone() == ("20261009_0015",)
            for statement in ("INSERT INTO public.alembic_version VALUES ('forged')",
                              "UPDATE public.alembic_version SET version_num='forged'",
                              "DELETE FROM public.alembic_version"):
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute(statement)
            cur.execute("SET ROLE gaps_staging_migrator")
            cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.alembic_version TO gaps_staging_runtime")
            cur.execute("GRANT UPDATE ON public.alembic_version TO PUBLIC")
            with pytest.raises(psycopg2.errors.RaiseException, match="Inherited/PUBLIC"):
                cur.execute(proposal)
            cur.execute("ROLLBACK")
            cur.execute("SELECT has_table_privilege('gaps_staging_runtime','public.alembic_version','DELETE')")
            assert cur.fetchone() == (True,), "Failed proposal must roll back its direct revoke"
            cur.execute("REVOKE UPDATE ON public.alembic_version FROM PUBLIC")
            cur.execute(proposal)
            cur.execute(proposal)  # safe repeat
            cur.execute("UPDATE public.alembic_version SET version_num='20261011_0016'")
            cur.execute("SELECT version_num FROM public.alembic_version")
            assert cur.fetchone() == ("20261011_0016",), "Migration owner retains write access"
    finally:
        if db:
            db.close()
        with admin.cursor() as cur:
            if made_database:
                cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            for role in reversed(created):
                cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        admin.close()
