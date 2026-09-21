"""Configuration safety and database behavior tests."""

import logging

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError
from sqlalchemy import text

from backend.config import Settings
from backend.database import AsyncSessionLocal
from backend.logging_config import JsonFormatter, redact


def production_settings(**overrides):
    values = {
        "APP_ENV": "production",
        "SECRET_KEY": "a-secure-production-secret-that-is-long-enough",
        "INTEGRATION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "DATABASE_URL": "postgresql+asyncpg://app:password@database.internal/app",
        "ALLOW_LEGACY_ENV_CREDENTIALS": False,
        "DEBUG": False,
        "AUTO_CREATE_TABLES": False,
        "CORS_ORIGINS": ["https://app.example.com"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": "change-me-in-production"},
        {"INTEGRATION_ENCRYPTION_KEY": ""},
        {"INTEGRATION_ENCRYPTION_KEY": "not-a-fernet-key"},
        {"DATABASE_URL": "sqlite+aiosqlite:///production.db"},
        {"DATABASE_URL": "postgresql+asyncpg:///missing-host"},
        {"ALLOW_LEGACY_ENV_CREDENTIALS": True},
        {"DEBUG": True},
        {"AUTO_CREATE_TABLES": True},
        {"CORS_ORIGINS": ["*"]},
    ],
)
def test_unsafe_production_configuration_is_rejected(override):
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        production_settings(**override)


def test_safe_production_configuration_is_accepted():
    assert production_settings().is_production is True


def test_development_configuration_remains_practical():
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    assert settings.is_production is False


@pytest.mark.asyncio
async def test_async_database_session_executes_query(client):
    async with AsyncSessionLocal() as session:
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1


def test_redaction_removes_nested_and_inline_secrets():
    assert redact({"access_token": "secret", "safe": {"password": "hidden"}}) == {
        "access_token": "[REDACTED]",
        "safe": {"password": "[REDACTED]"},
    }
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "Authorization=Bearer abc123 password=hunter2",
        (),
        None,
    )
    rendered = JsonFormatter().format(record)
    assert "abc123" not in rendered
    assert "hunter2" not in rendered
    assert "db-password" not in redact(
        "postgresql+asyncpg://app:db-password@database.internal/app"
    )
