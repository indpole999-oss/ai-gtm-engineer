"""Seed an actual 0015 approval and verify its bytes after 0016 upgrade."""
import sys
import json
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import engine, AsyncSessionLocal
from backend.outreach_models import Message
from test_live_integration_boundaries import boundaries
from test_research import fake_research
from test_message_replacement import prepared
from test_outreach import get_message

path = Path(sys.argv[1])
with pytest.MonkeyPatch.context() as patch, TestClient(app) as client:
    research, state = fake_research.__wrapped__(patch), boundaries.__wrapped__(patch)
    async def snapshot(workspace_id, message_id):
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(workspace_id), workspace_role="owner")
            message = await db.get(Message, UUID(message_id))
            return {column.name: str(getattr(message, column.name)) for column in message.__table__.columns}
    if len(sys.argv) == 2:
        a, data, integration, reviewed = prepared(client, research, state)
        workspace_id, message_id = a["X-Workspace-ID"], reviewed["message"]["id"]
        path.write_text(json.dumps({"workspace_id": workspace_id, "message_id": message_id,
            "message": client.portal.call(snapshot, workspace_id, message_id)}))
    else:
        saved = json.loads(path.read_text())
        assert client.portal.call(snapshot, saved["workspace_id"], saved["message_id"]) == saved["message"]
    client.portal.call(engine.dispose)
