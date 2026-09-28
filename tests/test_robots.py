import pytest
from backend import retrieval


@pytest.mark.parametrize("status,policy", [(403,""), (500,""), (302,""), (200,"User-agent: *\nDisallow: /"),
    (200,"User-agent: *\nDisallow: /private*"), (200,"User-agent: *\nCrawl-delay: 10"),
    (200,"User-agent: *\nAllow: /\nDisallow: /private")])
def test_policy_denial_never_fetches_source(monkeypatch, status, policy):
    calls = []
    monkeypatch.setattr(retrieval, "public_target", lambda url: ("example.com", "93.184.216.34", "/"))
    def fetch(url, **kwargs):
        calls.append(url)
        return status, "text/plain", policy, ""
    monkeypatch.setattr(retrieval, "fetch_public", fetch)
    with pytest.raises(retrieval.RetrievalError):
        retrieval.retrieve("https://example.com/private")
    assert calls == ["https://example.com/robots.txt"]


@pytest.mark.parametrize("policy_status", [200,404,410])
def test_permitted_policy_retains_evidence(monkeypatch, policy_status):
    monkeypatch.setattr(retrieval, "public_target", lambda url: ("example.com", "93.184.216.34", "/"))
    monkeypatch.setattr(retrieval, "fetch_public", lambda url, **kw:
        (policy_status,"text/plain","User-agent: *\nAllow: /","") if url.endswith("robots.txt") else (200,"text/html","<p>Evidence</p>",""))
    assert retrieval.retrieve("https://example.com/")["content"] == "Evidence"


@pytest.mark.parametrize("content,header", [("<p>Evidence</p>","noarchive"), ('<meta name="robots" content="noai"><p>Evidence</p>',"")])
def test_source_storage_optout_is_respected(monkeypatch, content, header):
    monkeypatch.setattr(retrieval, "public_target", lambda url: ("example.com", "93.184.216.34", "/"))
    monkeypatch.setattr(retrieval, "check_robots", lambda url: None)
    monkeypatch.setattr(retrieval, "fetch_public", lambda url: (200,"text/html",content,header))
    with pytest.raises(retrieval.RetrievalError):
        retrieval.retrieve("https://example.com/")
