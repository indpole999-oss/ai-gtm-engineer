import sqlite3
from uuid import uuid4
import pytest
from test_workspace_migrations import migrate


def test_populated_phase6_audit_and_outbox_survive_inbox_upgrade(tmp_path):
    path = tmp_path / "inbox-upgrade.db"
    migrate(path, "20260926_0010")
    user, workspace, brain, version, goal, plan, cycle, event, outbox, sender, thread, inbound, legacy = [uuid4().hex for _ in range(13)]
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users(id,email,hashed_password,is_active) VALUES(?,'old@example.com','hash',1)", (user,))
        db.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES(?,'Old','old','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (workspace,))
        db.execute("INSERT INTO companies(id,name,workspace_id) VALUES(?,'Quarantined',NULL)", (legacy,))
        db.execute("INSERT INTO company_brains(id,workspace_id,created_at) VALUES(?,?,CURRENT_TIMESTAMP)", (brain,workspace))
        db.execute("INSERT INTO company_brain_versions(id,workspace_id,brain_id,number,status,profile,revision,created_by,created_at) VALUES(?,?,?,1,'published','{}',1,?,CURRENT_TIMESTAMP)", (version,workspace,brain,user))
        db.execute("INSERT INTO goals(id,workspace_id,objective,brain_version_id,created_by,target_inputs,created_at) VALUES(?,?,'Old',?,?,'[]',CURRENT_TIMESTAMP)", (goal,workspace,version,user))
        db.execute("INSERT INTO plan_versions(id,workspace_id,goal_id,number,status,document,content_hash,revision,author_method,created_at) VALUES(?,?,?,1,'approved','{}','hash',1,'test',CURRENT_TIMESTAMP)", (plan,workspace,goal))
        db.execute("INSERT INTO execution_cycles(id,workspace_id,plan_id,plan_hash,status,created_at) VALUES(?,?,?,'hash','completed',CURRENT_TIMESTAMP)", (cycle,workspace,plan))
        db.execute("INSERT INTO workflow_runs(id,workspace_id,definition_version,created_at) VALUES(?,?,1,CURRENT_TIMESTAMP)", (cycle,workspace))
        db.execute("INSERT INTO domain_events(id,workspace_id,cycle_id,kind,data,created_at) VALUES(?,?,?,'existing_event','{}',CURRENT_TIMESTAMP)", (event,workspace,cycle))
        db.execute("INSERT INTO outbox_events(id,workspace_id,event_id,status,created_at) VALUES(?,?,?,'pending',CURRENT_TIMESTAMP)", (outbox,workspace,event))
        db.execute("INSERT INTO sender_identities(id,workspace_id,email,provider,status,daily_limit,created_at) VALUES(?,?,'sender@example.com','fake','connected',20,CURRENT_TIMESTAMP)", (sender,workspace))
    migrate(path, "20260926_0011")
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260926_0011"
        assert db.execute("SELECT cycle_id,kind FROM domain_events WHERE id=?", (event,)).fetchone() == (cycle,"existing_event")
        assert db.execute("SELECT status,attempts,due_at,lease_token FROM outbox_events WHERE id=?", (outbox,)).fetchone() == ("pending",0,None,None)
        assert db.execute("SELECT workspace_id FROM companies WHERE id=?", (legacy,)).fetchone() == (None,)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE domain_events SET kind='tampered' WHERE id=?", (event,))
        db.execute("INSERT INTO inbox_threads(id,workspace_id,sender_id,thread_key,created_at) VALUES(?,?,?,'thread:1',CURRENT_TIMESTAMP)", (thread,workspace,sender))
        db.execute("INSERT INTO inbound_messages(id,workspace_id,thread_id,sender_id,provider_message_id,sender_email,recipient_email,subject,body,auto_submitted,received_at,content_hash,association,created_at) VALUES(?,?,?,?,'message-1','buyer@example.com','sender@example.com','Re','Original','no',CURRENT_TIMESTAMP,'hash','unassociated',CURRENT_TIMESTAMP)", (inbound,workspace,thread,sender))
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE inbound_messages SET body='tampered' WHERE id=?", (inbound,))
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            db.execute("INSERT INTO inbox_threads(id,workspace_id,sender_id,thread_key,created_at) VALUES(?,?,?,'thread:1',CURRENT_TIMESTAMP)", (uuid4().hex,workspace,sender))
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
