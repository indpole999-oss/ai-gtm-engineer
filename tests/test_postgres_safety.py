from types import SimpleNamespace
import pytest
from postgres_safety import require_disposable_service, verify_major

@pytest.mark.parametrize("url", ["postgresql://localhost/staging", "postgresql://staging.example/postgres", "postgresql://localhost/postgres?host=staging.example"])
def test_restore_rejects_non_disposable_destinations(monkeypatch, url):
    monkeypatch.setenv("POSTGRES_DISPOSABLE", "1")
    with pytest.raises(RuntimeError): require_disposable_service(url)

def test_restore_requires_opt_in_and_matching_major(monkeypatch):
    monkeypatch.delenv("POSTGRES_DISPOSABLE", raising=False)
    with pytest.raises(RuntimeError): require_disposable_service("postgresql://localhost/postgres")
    monkeypatch.setenv("POSTGRES_DISPOSABLE", "1")
    assert require_disposable_service("postgresql://localhost/postgres").host == "localhost"
    monkeypatch.setenv("POSTGRES_EXPECTED_MAJOR", "17")
    closed=[]
    with pytest.raises(RuntimeError): verify_major(SimpleNamespace(server_version=160000, close=lambda:closed.append(True)))
    assert closed
    verify_major(SimpleNamespace(server_version=170000))
