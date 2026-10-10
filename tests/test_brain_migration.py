"""Upgrade an existing Phase 2 database and test immutable SQL triggers."""
import sqlite3
from uuid import uuid4
import pytest
from test_workspace_migrations import migrate


def test_phase2_upgrade_and_published_database_guards(tmp_path):
    path = tmp_path / "brain-upgrade.db"
    migrate(path, "20260922_0005")
    uid, wid, bid, vid, sid = [uuid4().hex for _ in range(5)]
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users(id,email,hashed_password,is_active) VALUES(?,'brain@example.com','hash',1)", (uid,))
        db.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES(?,'Brain','brain','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (wid,))
    migrate(path, "head")
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("INSERT INTO company_brains(id,workspace_id,created_at) VALUES(?,?,CURRENT_TIMESTAMP)", (bid,wid))
        db.execute("INSERT INTO company_brain_versions(id,workspace_id,brain_id,number,status,profile,revision,created_by,created_at) VALUES(?,?,?,1,'draft','{}',1,?,CURRENT_TIMESTAMP)", (vid,wid,bid,uid))
        db.execute("INSERT INTO company_brain_sources(id,workspace_id,version_id,key,kind,title,content,content_hash,created_at) VALUES(?,?,?,'case','case_study','Case','Original','hash',CURRENT_TIMESTAMP)", (sid,wid,vid))
        db.execute("UPDATE company_brain_versions SET status='published' WHERE id=?", (vid,))
        db.commit()
        for statement, args in (
            ("UPDATE company_brain_versions SET profile='{}' WHERE id=?", (vid,)),
            ("DELETE FROM company_brain_versions WHERE id=?", (vid,)),
            ("UPDATE company_brain_sources SET content='tampered' WHERE id=?", (sid,)),
            ("DELETE FROM company_brain_sources WHERE id=?", (sid,)),
            ("INSERT INTO brain_claims(id,workspace_id,version_id,text,disposition) VALUES(?,?,?,'Added after review','approved')", (uuid4().hex,wid,vid)),
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(statement, args)
        assert db.execute("SELECT content FROM company_brain_sources WHERE id=?", (sid,)).fetchone() == ("Original",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
