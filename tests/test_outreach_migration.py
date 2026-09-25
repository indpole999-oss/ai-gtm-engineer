import sqlite3
from uuid import uuid4
import pytest
from test_workspace_migrations import migrate


def test_outreach_migration_sql_immutability_and_tenant_foreign_keys(tmp_path):
    path = tmp_path / "outreach-migration.db"
    migrate(path, "20260923_0009")
    wid, other, campaign, other_campaign, sequence, version, step = [uuid4().hex for _ in range(7)]
    with sqlite3.connect(path) as db:
        for key in (wid, other):
            db.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES(?,'Test',?,'active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (key,key))
    migrate(path, "head")
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260926_0010"
        for key, workspace in ((campaign, wid), (other_campaign, other)):
            db.execute("INSERT INTO campaigns(id,workspace_id,name,status,created_at) VALUES(?,?,'Test','active',CURRENT_TIMESTAMP)", (key,workspace))
        db.execute("INSERT INTO sequences(id,workspace_id,campaign_id,name,created_at) VALUES(?,?,?,'Test',CURRENT_TIMESTAMP)", (sequence,wid,campaign))
        db.execute("INSERT INTO sequence_versions(id,workspace_id,sequence_id,number,definition,content_hash,created_at) VALUES(?,?,?,1,'{}','hash',CURRENT_TIMESTAMP)", (version,wid,sequence))
        db.execute("INSERT INTO sequence_steps(id,workspace_id,version_id,position,delay_seconds,purpose,created_at) VALUES(?,?,?,0,0,'Test',CURRENT_TIMESTAMP)", (step,wid,version))
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE sequence_versions SET definition='[]' WHERE id=?", (version,))
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM sequence_steps WHERE id=?", (step,))
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            db.execute("INSERT INTO sequences(id,workspace_id,campaign_id,name,created_at) VALUES(?,?,?,'Cross workspace',CURRENT_TIMESTAMP)", (uuid4().hex,wid,other_campaign))
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
