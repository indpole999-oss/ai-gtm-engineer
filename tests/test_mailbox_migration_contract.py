"""Verify the documented release head, ordered upgrades and safe rollback guard."""
import sqlite3
from uuid import uuid4
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from backend.routers.health import EXPECTED_REVISION
from test_workspace_migrations import migrate


def test_release_head_order_noop_and_preserved_data(tmp_path):
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_heads() == [EXPECTED_REVISION] == ["20261011_0016"]
    assert scripts.get_revision("20261011_0016").down_revision == "20261009_0015"
    assert scripts.get_revision("20261009_0015").down_revision == "20261008_0014"
    assert scripts.get_revision("20261008_0014").down_revision == "20260928_0013"
    path = tmp_path / "release-head.db"
    migrate(path, "20260928_0013")
    wid = uuid4().hex
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO workspaces(id,name,slug,status,created_at,updated_at) VALUES(?,'Preserved',?,'active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (wid, wid))
    for revision in ("20261008_0014", "head", "head"):
        migrate(path, revision)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (EXPECTED_REVISION,)
        assert db.execute("SELECT id,name FROM workspaces").fetchall() == [(wid, "Preserved")]
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='draft_review_events'").fetchone()
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    for revision in ("20261008_0014", "20261009_0015", "20261011_0016"):
        with pytest.raises(RuntimeError, match="Preserve"):
            scripts.get_revision(revision).module.downgrade()
