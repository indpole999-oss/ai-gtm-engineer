"""Actual populated Phase 7 upgrade; no legacy ownership inference."""
import sqlite3
from contextlib import closing
from uuid import uuid4
import pytest
from test_workspace_migrations import migrate


def test_populated_phase7_upgrade_preserves_history_and_quarantine(tmp_path):
    path=tmp_path/"outcomes-migration.db"
    migrate(path,"20260926_0011")
    wid,cid,pid,legacy,user,sender,thread,inbound=[uuid4().hex for _ in range(8)]
    with closing(sqlite3.connect(path)) as db,db:
        db.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES(?,'Phase7','phase7','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",(wid,))
        db.execute("INSERT INTO users(id,email,hashed_password,is_active) VALUES(?,'old@example.com','hash',1)",(user,))
        db.execute("INSERT INTO companies(id,workspace_id,name) VALUES(?,?,'Owned'),(?,NULL,'Quarantined')",(cid,wid,legacy))
        db.execute("INSERT INTO contacts(id,workspace_id,company_id,email) VALUES(?,?,?,'old-contact@example.com')",(pid,wid,cid))
        db.execute("INSERT INTO sender_identities(id,workspace_id,email,provider,status,daily_limit,created_at) VALUES(?,?,'sender@example.com','fake','connected',20,CURRENT_TIMESTAMP)",(sender,wid))
        db.execute("INSERT INTO inbox_threads(id,workspace_id,sender_id,thread_key,created_at) VALUES(?,?,?,'old-thread',CURRENT_TIMESTAMP)",(thread,wid,sender))
        db.execute("INSERT INTO inbound_messages(id,workspace_id,thread_id,sender_id,provider_message_id,sender_email,recipient_email,subject,body,auto_submitted,received_at,content_hash,association,created_at) VALUES(?,?,?,?,'old-message','old-contact@example.com','sender@example.com','Old subject','Old reply','no',CURRENT_TIMESTAMP,'old-hash','unassociated',CURRENT_TIMESTAMP)",(inbound,wid,thread,sender))
    migrate(path,"head")
    with closing(sqlite3.connect(path)) as db,db:
        db.execute("PRAGMA foreign_keys=ON")
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="20260926_0012"
        assert db.execute("SELECT count(*) FROM pipeline_records").fetchone()[0]==2
        assert db.execute("SELECT count(*) FROM pipeline_history WHERE to_stage='discovered'").fetchone()[0]==2
        assert db.execute("SELECT workspace_id FROM companies WHERE id=?",(legacy,)).fetchone()==(None,)
        assert db.execute("SELECT body FROM inbound_messages WHERE id=?",(inbound,)).fetchone()==("Old reply",)
        assert db.execute("PRAGMA foreign_key_check").fetchall()==[]
        with pytest.raises(sqlite3.IntegrityError,match="immutable"):
            db.execute("UPDATE pipeline_history SET reason='forged'")
        with pytest.raises(sqlite3.IntegrityError,match="immutable"):
            db.execute("DELETE FROM pipeline_records")
        with pytest.raises(sqlite3.IntegrityError,match="immutable"):
            db.execute("UPDATE inbound_messages SET body='changed'")
