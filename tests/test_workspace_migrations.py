"""Exercise actual Alembic upgrades on empty and populated Phase 0 databases."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import sqlite3
import pytest

ROOT = Path(__file__).resolve().parents[1]


def migrate(path, revision):
    env = dict(os.environ, APP_ENV="test", DATABASE_URL=f"sqlite+aiosqlite:///{path.as_posix()}")
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision], cwd=ROOT,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("existing", [False, True])
def test_migration_preserves_and_quarantines_legacy_data(tmp_path, existing):
    path = tmp_path / "migration.db"
    uid, cid, integration_id = uuid4().hex, uuid4().hex, uuid4().hex
    if existing:
        migrate(path, "20260921_0001")
        with sqlite3.connect(path) as db:
            db.execute("INSERT INTO users(id,email,hashed_password,is_active) VALUES(?,?,?,1)", (uid,"legacy@example.com","hash"))
            db.execute("INSERT INTO companies(id,name,domain) VALUES(?,?,?)", (cid,"Legacy","legacy.example"))
            db.execute("INSERT INTO integrations(id,user_id,category,provider,auth_type,credentials,config,status) VALUES(?,?,'crm','hubspot','api_key','{}','{}','disconnected')", (integration_id,uid))
    migrate(path,"head")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260922_0006"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        if existing:
            assert db.execute("SELECT name,workspace_id FROM companies WHERE id=?",(cid,)).fetchone() == ("Legacy",None)
            assert db.execute("SELECT disposition FROM legacy_ownership_audit WHERE record_id=?",(cid,)).fetchone()[0] == "quarantined"
            workspace = db.execute("SELECT workspace_id FROM integrations WHERE id=?",(integration_id,)).fetchone()[0]
            assert workspace is not None
            assert db.execute("SELECT role FROM workspace_memberships WHERE user_id=? AND workspace_id=?", (uid,workspace)).fetchone()[0] == "owner"
            assert db.execute("SELECT disposition FROM legacy_ownership_audit WHERE record_id=?",(integration_id,)).fetchone()[0] == "mapped"
