"""Offline provider schema/response and transactional provenance regressions."""
import json
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from backend import hosted_model, research_service
from test_hosted_model import hosted, assert_strict
from test_research import fake_research, create_job, execute_job
from test_workspace_security import signup


def sources(*ids):
    return [{"url": "https://example.com/", "spans": [
        {"id": value, "text": "Exact persisted source.", "index": i,
         "start": i * 1200, "end": i * 1200 + 23} for i, value in enumerate(ids)]}]


def output(*ids):
    return {"claims": [{"kind": "provider_assertion", "text": None,
                       "confidence": .7, "span_id": value} for value in ids],
            "icp_used": "Synthetic ICP", "fit": "potential_fit",
            "why_company": {"reasoning": "Potential alignment", "claim_indices": list(range(len(ids)))},
            "why_now": {"reasoning": "Unknown", "claim_indices": []}, "buyers": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["valid", "unknown", "malformed", "other_job", "unoffered"])
async def test_groq_wire_enum_and_response_validation(hosted, monkeypatch, reference):
    allowed = [str(uuid4()), str(uuid4())]
    foreign = str(uuid4())
    unoffered = str(uuid4())
    supplied = sources(*allowed)
    result = output(*allowed)
    if reference != "valid":
        result["claims"][1]["span_id"] = {
            "unknown": str(uuid4()), "malformed": "invented-span",
            "other_job": foreign, "unoffered": unoffered}[reference]
    original = httpx.AsyncClient
    calls = []

    def handle(request):
        calls.append(request)
        payload = json.loads(request.content)
        contract = payload["response_format"]["json_schema"]
        assert contract["strict"] is True
        assert_strict(contract["schema"])
        field = contract["schema"]["$defs"]["SuppliedSpanClaim"]["properties"]["span_id"]
        choices = next(branch["enum"] for branch in field["anyOf"] if "enum" in branch)
        assert choices == allowed
        assert {foreign, unoffered}.isdisjoint(choices)
        prompt = json.loads(payload["messages"][1]["content"])
        assert [s["id"] for s in prompt["sources"][0]["spans"]] == choices
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

    monkeypatch.setattr(hosted_model.httpx, "AsyncClient",
                        lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    if reference == "valid":
        parsed, _ = await research_service.GroqResearchProvider().analyze({}, supplied, {})
        assert [c.span_id for c in parsed.claims] == allowed
    else:
        with pytest.raises(ValidationError):
            await research_service.GroqResearchProvider().analyze({}, supplied, {})
    assert len(calls) == 1


def test_schema_is_request_scoped_and_empty_set_only_allows_null():
    first, second = str(uuid4()), str(uuid4())
    original = research_service.ResearchOutput.model_json_schema()
    a = research_service.supplied_span_output(sources(first))
    b = research_service.supplied_span_output(sources(second))
    assert a.model_validate(output(first)).claims[0].span_id == first
    with pytest.raises(ValidationError):
        b.model_validate(output(first))
    unknown = output(None)
    unknown["claims"][0].update(kind="unknown", text="No evidence")
    unknown["fit"] = "unknown"
    assert research_service.supplied_span_output([]).model_validate(unknown)
    with pytest.raises(ValidationError):
        research_service.supplied_span_output([]).model_validate(output(first))
    assert research_service.ResearchOutput.model_json_schema() == original


@pytest.mark.parametrize("bad", [None, "malformed", "unknown"])
def test_backend_preserves_exact_text_or_rejects_whole_claim_batch(client, fake_research, bad):
    fake_research["buyers"] = []
    fake_research["claims"].append(deepcopy(fake_research["claims"][0]))
    if bad:
        fake_research["claims"][1]["span_id"] = "not-a-uuid" if bad == "malformed" else str(uuid4())
    headers = signup(client, "span-batch@example.com")
    job = create_job(client, headers)
    response = execute_job(client, headers, job["id"])
    report = client.get("/api/v1/research/jobs/" + job["id"], headers=headers).json()
    assert report["sources"][0]["spans"]  # Retained even on rejection.
    if bad:
        assert response.status_code == 422
        assert report["claims"] == [] and report["intelligence"] is None
    else:
        assert response.status_code == 200
        assert len(report["claims"]) == 2
        assert all(c["text"] == c["excerpt"] == report["sources"][0]["content"] for c in report["claims"])


@pytest.mark.asyncio
async def test_local_provider_uses_same_constrained_contract(monkeypatch):
    allowed, invalid = str(uuid4()), str(uuid4())
    original = httpx.AsyncClient
    def handle(request):
        schema = json.loads(request.content)["format"]
        field = schema["$defs"]["SuppliedSpanClaim"]["properties"]["span_id"]
        assert any(branch.get("const") == allowed for branch in field["anyOf"])
        return httpx.Response(200, json={"message": {"content": json.dumps(output(invalid))}})
    monkeypatch.setattr(research_service.httpx, "AsyncClient",
                        lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    with pytest.raises(ValidationError):
        await research_service.LocalResearchProvider().analyze({}, sources(allowed), {})
