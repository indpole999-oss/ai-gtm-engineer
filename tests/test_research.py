from copy import deepcopy
from uuid import UUID
import hashlib
import socket
import httpx
from fastapi import HTTPException
import pytest
from backend import research_service, retrieval
from backend.research_models import ResearchJob
from backend.database import AsyncSessionLocal, WorkspaceMembership
from sqlalchemy import select
from test_workspace_security import signup, company
from test_company_brain import draft, save, BASE


def execute_job(client, headers, job_id):
    """Exercise the internal service; public execution now requires plan approval."""
    async def run():
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=UUID(headers["X-Workspace-ID"]), workspace_role="admin")
            job = await db.scalar(select(ResearchJob).where(ResearchJob.id == UUID(job_id)))
            try:
                await research_service.execute_research(db, job)
                return httpx.Response(200, json={"status": job.status})
            except HTTPException as error:
                return httpx.Response(error.status_code, json={"detail": error.detail})
    return client.portal.call(run)


def published(client, headers):
    row = save(client, headers, draft(client, headers)).json()
    response = client.post(f"{BASE}/versions/{row['id']}/publish", headers=headers, json={"revision": row["revision"], "reviewed": True})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def fake_research(monkeypatch):
    content = "Acme provides workflow analytics. Jane Buyer is VP Revenue. jane@example.com"
    capture = {"url": "https://example.com/", "title": "Acme", "publisher": "example.com", "content": content,
               "content_hash": hashlib.sha256(content.encode()).hexdigest(), "extractor_version": "test-v1"}
    output = {"claims": [{"text": "Acme provides workflow analytics.", "kind": "provider_assertion", "confidence": 0.7, "source_index": 0, "excerpt": content}],
              "icp_used": "Customer-reviewed icp", "fit": "potential_fit",
              "why_company": {"reasoning": "Potential match to the supplied ICP, subject to customer review", "claim_indices": [0]},
              "why_now": {"reasoning": "No dated buying signal found", "claim_indices": []},
              "buyers": [{"name": "Jane Buyer", "title": "VP Revenue", "email": "jane@example.com", "reasoning": "Revenue leader observed", "claim_indices": [0]}]}
    class Fake:
        async def analyze(self, profile, sources, target):
            assert target["name"]
            assert profile["icp"] == output["icp_used"] or output["icp_used"] == "wrong ICP"
            return deepcopy(output), "deterministic-test-v1"
    monkeypatch.setattr(research_service, "retrieve", lambda url: {**capture, "url": url})
    monkeypatch.setattr(research_service, "research_provider", Fake)
    return output


def create_job(client, headers, brain=None, account=None):
    brain = brain or published(client, headers)
    account = account or company(client, headers)
    response = client.post("/api/v1/research/jobs", headers=headers, json={"company_id": account["id"], "brain_version_id": brain["id"], "source_urls": ["https://example.com/"]})
    assert response.status_code == 201, response.text
    return response.json()


def test_evidence_chain_exact_brain_and_no_false_contact_verification(client, fake_research):
    a = signup(client, "research@example.com")
    brain = published(client, a)
    job = create_job(client, a, brain=brain)
    path = "/api/v1/research/jobs/" + job["id"]
    assert client.post(path + "/run", headers=a).status_code == 409
    result = execute_job(client, a, job["id"])
    assert result.status_code == 200, result.text
    report = client.get(path, headers=a).json()
    assert report["status"] == "completed"
    assert report["intelligence"]["brain_version_id"] == brain["id"]
    assert report["intelligence"]["brain_hash"] == brain["content_hash"]
    assert report["intelligence"]["buyers"][0]["verification_status"] == "unknown"
    assert report["claims"][0]["kind"] == "provider_assertion"
    assert report["claims"][0]["retrieved_at"] and report["claims"][0]["url"]
    assert report["claims"][0]["freshness"] == "recent_capture"
    assert client.post(path + "/run", headers=a).status_code == 409


@pytest.mark.parametrize("tamper", ["quote", "icp", "reference", "buyer", "verified"])
def test_reject_unsupported_model_output_without_partial_report(client, fake_research, tamper):
    if tamper == "quote": fake_research["claims"][0]["excerpt"] = "Invented evidence"
    if tamper == "icp": fake_research["icp_used"] = "wrong ICP"
    if tamper == "reference": fake_research["why_company"]["claim_indices"] = [999]
    if tamper == "buyer": fake_research["buyers"][0]["email"] = "invented@example.com"
    if tamper == "verified": fake_research["claims"][0]["kind"] = "verified_fact"
    a = signup(client, "invalid-model@example.com")
    job = create_job(client, a)
    path = "/api/v1/research/jobs/" + job["id"]
    response = execute_job(client, a, job["id"])
    assert response.status_code == 422, response.text
    report = client.get(path, headers=a).json()
    assert report["status"] == "failed" and report["intelligence"] is None and report["claims"] == []


def test_research_cross_tenant_direct_collection_relationships_and_actions(client, fake_research):
    a, b = signup(client, "research-a@example.com"), signup(client, "research-b@example.com")
    ba, bb = published(client, a), published(client, b)
    ca, cb = company(client, a), company(client, b)
    job = create_job(client, b, bb, cb)
    assert client.get("/api/v1/research/jobs", headers=a).json() == []
    path = "/api/v1/research/jobs/" + job["id"]
    assert client.get(path, headers=a).status_code == 404
    assert client.post(path + "/run", headers=a).status_code == 404
    for account, brain in [(cb,ba),(ca,bb)]:
        assert client.post("/api/v1/research/jobs", headers=a, json={"company_id": account["id"], "brain_version_id": brain["id"], "source_urls": ["https://example.com/"]}).status_code == 404
    assert client.get("/api/v1/research/jobs", headers=a, params={"company_id": cb["id"]}).status_code == 404


@pytest.mark.parametrize("url,address", [("http://example.com/","93.184.216.34"),("https://localhost/","127.0.0.1"),("https://metadata.example/","169.254.169.254"),("https://internal.example/","10.0.0.1"),("https://example.com:444/","93.184.216.34"),("https://u:p@example.com/","93.184.216.34"),("https://example.com/","::1")])
def test_retrieval_rejects_ssrf_targets(monkeypatch, url, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a,**kw: [(socket.AF_INET,socket.SOCK_STREAM,6,"",(address,443))])
    with pytest.raises(retrieval.RetrievalError): retrieval.public_target(url)


def test_public_target_pins_resolved_address_and_strips_script_text(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a,**kw: [(socket.AF_INET,socket.SOCK_STREAM,6,"",("93.184.216.34",443))])
    assert retrieval.public_target("https://example.com/news?q=1") == ("example.com","93.184.216.34","/news?q=1")
    parser = retrieval.TextExtractor()
    parser.feed("<title>Company</title><script>secret instructions</script><p>Evidence</p>")
    assert "secret instructions" not in parser.parts and "Evidence" in parser.parts


@pytest.mark.parametrize("role,expected", [("owner",201),("admin",201),("member",403),("viewer",403)])
def test_fact_verification_is_audited_role_gated_and_tenant_scoped(client, fake_research, role, expected):
    a, b = signup(client, f"review-{role}@example.com"), signup(client, "review-other@example.com")
    job = create_job(client, a)
    path = "/api/v1/research/jobs/" + job["id"]
    assert execute_job(client, a, job["id"]).status_code == 200
    claim = client.get(path, headers=a).json()["claims"][0]
    verification = "/api/v1/research/claims/" + claim["id"] + "/verification"
    payload = {"reviewed_text": claim["text"], "decision": "verified", "reason": "Compared the exact claim with the captured primary source."}
    assert client.post(verification, headers=b, json=payload).status_code == 404
    async def change_role():
        async with AsyncSessionLocal() as db:
            row = await db.scalar(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == UUID(a["X-Workspace-ID"])))
            row.role = role
            await db.commit()
    client.portal.call(change_role)
    response = client.post(verification, headers=a, json=payload)
    assert response.status_code == expected, response.text
    if expected == 201:
        item = client.get(path, headers=a).json()["claims"][0]
        assert item["kind"] == "verified_fact" and item["original_kind"] == "provider_assertion"
        assert item["review"]["method"] == "workspace_admin_review"
        assert client.post(verification, headers=a, json={**payload, "decision": "rejected"}).status_code == 201
        item = client.get(path, headers=a).json()["claims"][0]
        assert item["review"]["decision"] == "rejected" and item["kind"] != "verified_fact"
    if role == "viewer":
        assert client.post(path + "/run", headers=a).status_code == 403
