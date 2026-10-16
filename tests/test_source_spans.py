import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from backend.source_spans import source_spans
from backend.research_service import ResearchOutput, research_prompt
from test_research import fake_research, create_job, execute_job, published
from test_workspace_security import signup, company


def test_spans_are_stable_exact_complete_and_capture_scoped():
    content = ("Unicode café\n  exact spacing\t" * 130) + "tail"
    row = SimpleNamespace(id=uuid4(), content=content, content_hash=hashlib.sha256(content.encode()).hexdigest())
    spans = source_spans(row)
    assert spans == source_spans(row)
    assert "".join(s["text"] for s in spans) == content
    assert all(s["text"] == content[s["start"]:s["end"]] for s in spans)
    assert [s["index"] for s in spans] == list(range(len(spans)))
    row.id = uuid4()
    assert not {s["id"] for s in spans} & {s["id"] for s in source_spans(row)}
    row.content += "tampered"
    with pytest.raises(ValueError, match="hash mismatch"):
        source_spans(row)


def test_prompt_only_offers_exact_spans_and_schema_forbids_free_excerpts():
    spans = [{"id": str(uuid4()), "index": 0, "start": 0, "end": 4, "text": "real"}]
    prompt = research_prompt({}, [{"url": "https://example.com", "spans": spans}], {})
    assert prompt["sources"][0]["spans"] == spans
    assert "content" not in prompt["sources"][0]
    schema = ResearchOutput.model_json_schema()["$defs"]["ExtractedClaim"]
    assert "span_id" in schema["properties"]
    assert "excerpt" not in schema["properties"] and "source_index" not in schema["properties"]
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("kind,text,span,fit,accepted", [
    ("model_inference", "Potential alignment, requiring review", "first", "potential_fit", True),
    ("unknown", "Insufficient evidence", None, "unknown", True),
    ("model_inference", "Invented inference", None, "potential_fit", False),
    ("unknown", "Uncertain", "first", "unknown", False),
    ("provider_assertion", "Fabricated assertion", "first", "potential_fit", False),
    ("model_inference", "Unsupported index", "999", "unknown", False),
])
def test_claim_contract_and_unknown_fit(client, fake_research, kind, text, span, fit, accepted):
    fake_research["claims"][0].update(kind=kind, text=text, span_id=span)
    fake_research.update(fit=fit, buyers=[])
    a = signup(client, "span-contract@example.com")
    job = create_job(client, a)
    response = execute_job(client, a, job["id"])
    assert response.status_code == (200 if accepted else 422)
    report = client.get("/api/v1/research/jobs/" + job["id"], headers=a).json()
    assert len(report["sources"]) == 1
    if not accepted:
        assert report["claims"] == [] and report["intelligence"] is None
    elif kind == "unknown":
        assert report["intelligence"]["fit"] == "unknown"
        assert report["claims"][0]["excerpt"] is None
        assert all(r["stage"] == "discovered" for r in client.get("/api/v1/outcomes/pipeline", headers=a).json())
    else:
        assert report["claims"][0]["span_id"]
        assert report["claims"][0]["excerpt"] == report["sources"][0]["content"]


def test_reference_to_other_job_fails_even_for_same_source_content(client, fake_research):
    a = signup(client, "cross-job-span@example.com")
    brain, account = published(client, a), company(client, a)
    first = create_job(client, a, brain=brain, account=account)
    assert execute_job(client, a, first["id"]).status_code == 200
    report = client.get("/api/v1/research/jobs/" + first["id"], headers=a).json()
    assert report["claims"][0]["text"] == report["sources"][0]["content"]
    fake_research["claims"][0]["span_id"] = report["claims"][0]["span_id"]
    second = create_job(client, a, brain=brain, account=account)
    assert execute_job(client, a, second["id"]).status_code == 422


@pytest.mark.parametrize("kind,text,accepted", [
    ("provider_assertion", None, True),
    ("provider_assertion", "Acme provides analytics", False),
    ("provider_assertion", "Acme—provides analytics!", False),
    ("model_inference", "Acme may help analyze workflows.", True),
])
def test_whitespace_punctuation_and_paraphrases(client, fake_research, monkeypatch, kind, text, accepted):
    from backend import research_service
    original = research_service.retrieve
    content = "Acme—provides  analytics!\n\tOriginal spacing."
    def retrieve(url):
        return {**original(url), "content": content, "content_hash": hashlib.sha256(content.encode()).hexdigest()}
    monkeypatch.setattr(research_service, "retrieve", retrieve)
    fake_research.update(buyers=[])
    fake_research["claims"][0].update(kind=kind, text=text)
    a = signup(client, "punctuation@example.com")
    job = create_job(client, a)
    assert execute_job(client, a, job["id"]).status_code == (200 if accepted else 422)
    report = client.get("/api/v1/research/jobs/" + job["id"], headers=a).json()
    assert report["sources"][0]["spans"][0]["text"] == content
    if accepted:
        assert report["claims"][0]["excerpt"] == content
        assert report["claims"][0]["text"] == (content if kind == "provider_assertion" else text)


def test_unoffered_span_and_buyer_without_shared_source_fail(client, fake_research, monkeypatch):
    from backend import research_service
    original = research_service.retrieve
    content = "Jane Buyer".ljust(1200) + "VP Revenue jane@example.com".ljust(30000)
    def retrieve(url):
        return {**original(url), "content": content, "content_hash": hashlib.sha256(content.encode()).hexdigest()}
    monkeypatch.setattr(research_service, "retrieve", retrieve)
    a = signup(client, "split-buyer@example.com")
    brain, account = published(client, a), company(client, a)
    job = create_job(client, a, brain, account)
    # A buyer's name/title/email cannot be assembled across unrelated chunks.
    assert execute_job(client, a, job["id"]).status_code == 422
    report = client.get("/api/v1/research/jobs/" + job["id"], headers=a).json()
    assert len(report["sources"][0]["spans"]) == 26
    class Outside:
        async def analyze(self, profile, sources, target):
            from copy import deepcopy
            result = deepcopy(fake_research)
            result["buyers"] = []
            # Derive the final persisted span ID, which was not offered to model.
            from backend.research_models import SourceFetch
            from sqlalchemy import select
            from backend.database import AsyncSessionLocal
            from uuid import UUID
            async with AsyncSessionLocal() as db:
                db.info.update(workspace_id=UUID(a["X-Workspace-ID"]), workspace_role="viewer")
                fetch = await db.scalar(select(SourceFetch).where(SourceFetch.job_id == UUID(second["id"])))
                result["claims"][0]["span_id"] = source_spans(fetch)[-1]["id"]
            assert result["claims"][0]["span_id"] not in [s["id"] for s in sources[0]["spans"]]
            return result, "test"
    second = create_job(client, a, brain, account)
    monkeypatch.setattr(research_service, "research_provider", Outside)
    assert execute_job(client, a, second["id"]).status_code == 422
