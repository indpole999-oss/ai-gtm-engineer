"""Late contact projection uses persisted, validated research, never provider success."""
from uuid import UUID
import pytest
from sqlalchemy import select, func
from backend.database import AsyncSessionLocal, Contact
from backend.outcome_models import PipelineHistory, PipelineRecord
from test_workspace_security import signup, company
from test_research import published, create_job, execute_job, fake_research  # noqa: F401


def add_contact(client, headers, account, first="Jane", email="jane@example.com"):
    response = client.post("/api/v1/contacts/", headers=headers, json={
        "company_id": account["id"], "first_name": first, "last_name": "Buyer", "email": email})
    assert response.status_code == 200, response.text
    return response.json()


def contact_pipeline(client, headers, contact):
    rows = client.get("/api/v1/outcomes/pipeline", headers=headers)
    assert rows.status_code == 200
    row = next(x for x in rows.json() if x["contact_id"] == contact["id"])
    return client.get("/api/v1/outcomes/pipeline/" + row["id"], headers=headers).json()


def test_contact_added_after_research_persists_qualification_once(client, fake_research):
    a = signup(client, "late-contact@example.com")
    brain, account = published(client, a), company(client, a)
    job = create_job(client, a, brain, account)
    assert execute_job(client, a, job["id"]).status_code == 200
    contact = add_contact(client, a, account)
    for _ in range(2):
        row = contact_pipeline(client, a, contact)
        assert row["stage"] == "qualified"
        assert row["revision"] == 2
        assert [h["to_stage"] for h in row["history"]] == ["discovered", "qualified"]
        assert row["history"][-1]["evidence"]["research_job_id"] == job["id"]
    async def persisted():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(a["X-Workspace-ID"]), workspace_role="owner")
            from backend.pipeline_service import qualification_for_contact
            saved_contact = await db.scalar(select(Contact).where(Contact.id == UUID(contact["id"])))
            await qualification_for_contact(db, saved_contact)
            await db.commit()
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(a["X-Workspace-ID"]), workspace_role="owner")
            record = await db.scalar(select(PipelineRecord).where(PipelineRecord.contact_id == UUID(contact["id"])))
            history = await db.scalar(select(func.count()).select_from(PipelineHistory).where(
                PipelineHistory.pipeline_id == record.id, PipelineHistory.to_stage == "qualified"))
            return record.stage, history
    assert client.portal.call(persisted) == ("qualified", 1)
    from test_insights import query
    assert query(client, a)["funnel"]["observed_stage_entries"]["qualified"] == 1
    eligible = client.get("/api/v1/outreach/prospects/" + contact["id"] + "/eligibility", headers=a)
    assert eligible.status_code == 200 and eligible.json()[0]["id"] == job["id"]
    other = signup(client, "late-contact-other@example.com")
    assert client.get("/api/v1/outcomes/pipeline/" + row["id"], headers=other).status_code == 404


@pytest.mark.parametrize("case", ["wrong_name", "wrong_email", "unknown_fit", "not_a_fit", "newer_not_a_fit", "no_research"])
def test_late_contact_does_not_infer_unsupported_qualification(client, fake_research, case):
    a = signup(client, "unsupported-late-contact@example.com")
    brain, account = published(client, a), company(client, a)
    if case in {"unknown_fit", "not_a_fit"}:
        fake_research["fit"] = "unknown" if case == "unknown_fit" else "not_a_fit"
    if case != "no_research":
        job = create_job(client, a, brain, account)
        assert execute_job(client, a, job["id"]).status_code == 200
    if case == "newer_not_a_fit":
        fake_research["fit"] = "not_a_fit"
        newer = create_job(client, a, brain, account)
        assert execute_job(client, a, newer["id"]).status_code == 200
    contact = add_contact(client, a, account,
        first="Unmatched" if case == "wrong_name" else "Jane",
        email="unmatched@example.com" if case == "wrong_email" else "jane@example.com")
    row = contact_pipeline(client, a, contact)
    assert row["stage"] == "discovered" and row["revision"] == 1
    assert [h["to_stage"] for h in row["history"]] == ["discovered"]
