"""Deterministic operator-tool safety tests; no hosted DB or provider connections."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet

spec = importlib.util.spec_from_file_location("release_preflight", Path(__file__).parents[1] / "scripts/staging_release_preflight.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def valid_env():
    env = {name: "false" for name in probe.OFF}
    env.update(APP_ENV="production", AUTH_ADMISSION_STORE="database", ALGORITHM="HS256",
               SECRET_KEY="synthetic-secret-" + "x" * 32,
               INTEGRATION_ENCRYPTION_KEY=Fernet.generate_key().decode(),
               DATABASE_URL="synthetic-private-url", FRONTEND_URL="https://" + probe.WEB_HOST,
               CORS_ORIGINS=json.dumps(["https://" + probe.WEB_HOST]))
    return env


def test_preflight_redacts_all_values(capsys):
    env = valid_env()
    assert probe.main([], env) == 0
    output = capsys.readouterr().out
    for key in ("SECRET_KEY", "INTEGRATION_ENCRYPTION_KEY", "DATABASE_URL", "FRONTEND_URL"):
        assert env[key] not in output
    assert all(json.loads(output)["checks"].values())


@pytest.mark.parametrize("name", probe.OFF)
def test_missing_or_enabled_gate_fails(name):
    env = valid_env()
    del env[name]
    assert not probe.environment_report(env)["checks"][name + "_off"]
    env[name] = "true"
    assert not probe.environment_report(env)["checks"][name + "_off"]


@pytest.mark.parametrize("origin", ["https://evil.example", "https://" + probe.WEB_HOST + ".evil.example",
                                    "https://user:secret@" + probe.WEB_HOST, "https://" + probe.WEB_HOST + "/bad",
                                    "https://" + probe.WEB_HOST + "?secret=x", "http://" + probe.WEB_HOST])
def test_untrusted_origin_fails(origin):
    assert not probe.origin_matches(origin, probe.WEB_HOST)


def test_connection_exception_never_discloses_secrets(monkeypatch, capsys):
    monkeypatch.setattr(probe, "database_report", Mock(side_effect=RuntimeError("secret-password-url")))
    assert probe.main(["--database"], valid_env()) == 1
    assert "secret-password-url" not in capsys.readouterr().out


@pytest.mark.parametrize("url", ["postgresql://user:secret@localhost/db",
    "postgresql://gaps_staging_runtime:secret@db.qjkcqdiznthffbqmltrr.supabase.co/db?sslmode=verify-full&sslrootcert=ca",
    "postgresql://gaps_staging_runtime:secret@db.xhjkahbtckrrhuzamysr.supabase.co/db?sslmode=require"])
def test_invalid_target_rejected_before_connection(monkeypatch, url):
    import psycopg2
    connect = Mock(side_effect=AssertionError("Must not connect"))
    monkeypatch.setattr(psycopg2, "connect", connect)
    with pytest.raises(ValueError):
        probe.database_report({"STAGING_PREFLIGHT_DATABASE_URL": url,
            "STAGING_PREFLIGHT_EXPECTED_HOST": "db.xhjkahbtckrrhuzamysr.supabase.co",
            "STAGING_PREFLIGHT_EXPECTED_DATABASE": "db"})
    connect.assert_not_called()


def test_readonly_database_queries_and_effective_privilege_failure(monkeypatch):
    import psycopg2
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    cursor.fetchone.side_effect = [(True,) * 5, (False,)]
    cursor.fetchall.return_value = [(True,)]
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.cursor.return_value = cursor
    connect = Mock(return_value=connection)
    monkeypatch.setattr(psycopg2, "connect", connect)
    report = probe.database_report({"STAGING_PREFLIGHT_DATABASE_URL":
        "postgresql://gaps_staging_runtime:secret@db.xhjkahbtckrrhuzamysr.supabase.co/db?sslmode=verify-full&sslrootcert=ca",
        "STAGING_PREFLIGHT_EXPECTED_HOST": "db.xhjkahbtckrrhuzamysr.supabase.co",
        "STAGING_PREFLIGHT_EXPECTED_DATABASE": "db"})
    assert report["tls_connection"] and not report["revision_select_only"]
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]
    assert all(call.args[0].startswith("SELECT ") for call in cursor.execute.call_args_list)


def test_frontend_existing_public_origin():
    assert probe.environment_report({"VITE_API_BASE_URL": "https://" + probe.API_HOST}, True)["checks"]["staging_api_origin"]
    assert not probe.environment_report({}, True)["checks"]["staging_api_origin"]
