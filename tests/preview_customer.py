"""Disposable local customer UX fixture. Never connects to production or live providers.

Run .venv/Scripts/python.exe tests/preview_customer.py, then point the frontend at
http://127.0.0.1:8010. Sign in as outreach@example.com / test-password-only.
The database and provider ledgers are temporary and removed on exit.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    with tempfile.TemporaryDirectory(prefix="gaps-customer-preview-") as directory:
        root = Path(directory)
        os.environ.update(APP_ENV="test", DATABASE_URL="sqlite+aiosqlite:///" + (root / "preview.db").as_posix(),
            SECRET_KEY="disposable-local-preview-secret-only", ALLOW_LEGACY_ENV_CREDENTIALS="false",
            INTEGRATION_ENCRYPTION_KEY="", OPENAI_API_KEY="", SERPER_API_KEY="", NVIDIA_API_KEY="",
            CORS_ORIGINS='["http://127.0.0.1:5173","http://localhost:5173"]')
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        import pytest
        import uvicorn
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend import outreach_service, outcome_providers, providers
        from backend.providers import ProviderHealth
        from test_outreach import FakeProvider
        from test_research import fake_research
        from test_outcomes import FakeTransport, calendar_ready, create, run
        from test_planning_execution import approve
        from test_workspace_security import signup
        from backend.database import AsyncSessionLocal, WorkspaceMembership
        from sqlalchemy import select
        from uuid import UUID
        with pytest.MonkeyPatch.context() as patch:
            fake = fake_research.__wrapped__(patch)
            mail = FakeProvider(str(root / "mail.db"))
            transport = FakeTransport(root / "outcomes.db")
            patch.setattr(outreach_service, "delivery_provider", lambda sender: mail)
            patch.setattr(outcome_providers, "transport_for", lambda integration, credentials: transport)
            async def fake_verify(self, credentials, config):
                return ProviderHealth(status="healthy", scopes=["local-preview-only"])
            patch.setattr(providers.HttpProvider, "verify", fake_verify)
            with TestClient(app) as client:
                a, body = calendar_ready(client, fake, mail, transport)
                action = create(client, a, "/calendar/schedule", body)
                approve(client, a, action["plan"])
                run(client, a)
                b = signup(client, "empty-preview@example.com")
                async def viewer():
                    async with AsyncSessionLocal() as db:
                        membership = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
                        db.add(WorkspaceMembership(workspace_id=UUID(b["X-Workspace-ID"]), user_id=membership.user_id, role="viewer", status="active"))
                        await db.commit()
                client.portal.call(viewer)
            uvicorn.run(app, host="127.0.0.1", port=8010, log_level="warning")


if __name__ == "__main__":
    main()
