"""
Backend Configuration - Settings with Pydantic BaseSettings
"""

from typing import List, Literal

from cryptography.fernet import Fernet
from pydantic import model_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from urllib.parse import urlsplit
import ipaddress


def public_https(value):
    try:
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            return False
        if url.hostname == "localhost" or url.hostname.endswith((".localhost", ".local")):
            return False
        try:
            if not ipaddress.ip_address(url.hostname).is_global:
                return False
        except ValueError:
            pass
        return url.port in (None, 443)
    except ValueError:
        return False


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # -----------------------------
    # App
    # -----------------------------

    APP_NAME: str = "AI GTM Engineer"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    AUTH_ADMISSION_STORE: Literal["database", "memory"] = "database"
    AUTH_PEER_LIMIT: int = Field(default=30, ge=1, le=10000)
    AUTH_GLOBAL_LIMIT: int = Field(default=300, ge=1, le=100000)

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Integration credential encryption
    INTEGRATION_ENCRYPTION_KEY: str = ""
    ALLOW_LEGACY_ENV_CREDENTIALS: bool = True


    # -----------------------------
    # CORS
    # -----------------------------

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8081",
        "https://ai-gtm-engineer-web.onrender.com",
    ]


    # -----------------------------
    # Database
    # -----------------------------

    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    AUTO_CREATE_TABLES: bool = True


    # -----------------------------
    # LLM Configuration
    # -----------------------------

    OPENAI_API_KEY: str = ""

    OPENAI_BASE_URL: str = (
        "https://api.openai.com/v1"
    )

    OPENAI_MODEL: str = (
        "gpt-4o-mini"
    )


    # NVIDIA NIM (Optional)

    NVIDIA_API_KEY: str = ""

    NVIDIA_BASE_URL: str = (
        "https://integrate.api.nvidia.com/v1"
    )

    NVIDIA_MODEL: str = (
        "meta/llama-3.1-70b-instruct"
    )


    # -----------------------------
    # Research Agent
    # -----------------------------

    SERPER_API_KEY: str = ""

    TAVILY_API_KEY: str = ""


    # -----------------------------
    # Enrichment Agent
    # -----------------------------

    APOLLO_API_KEY: str = ""

    CLEARBIT_API_KEY: str = ""

    PDL_API_KEY: str = ""


    # -----------------------------
    # Email Agent
    # -----------------------------

    EMAIL_PROVIDER: str = "resend"

    RESEND_API_KEY: str = ""

    SENDGRID_API_KEY: str = ""

    FROM_EMAIL: str = (
        "gtm@yourdomain.com"
    )

    FROM_NAME: str = (
        "AI GTM Engineer"
    )


    # SMTP fallback

    SMTP_HOST: str = (
        "smtp.gmail.com"
    )

    SMTP_PORT: int = 587

    SMTP_USER: str = ""

    SMTP_PASS: str = ""


    # -----------------------------
    # CRM Agent
    # -----------------------------

    CRM_PROVIDER: str = "hubspot"

    HUBSPOT_API_KEY: str = ""

    HUBSPOT_ACCESS_TOKEN: str = ""

    SALESFORCE_INSTANCE_URL: str = ""

    SALESFORCE_ACCESS_TOKEN: str = ""


    # -----------------------------
    # Calendar Agent
    # -----------------------------

    CALENDAR_PROVIDER: str = "google"

    FRONTEND_URL: str = "http://localhost:3000"

    GOOGLE_CLIENT_ID: str = ""

    GOOGLE_CLIENT_SECRET: str = ""

    GOOGLE_REDIRECT_URI: str = (
        "http://localhost:8000/api/v1/calendar/oauth/google/callback"
    )


    # -----------------------------
    # Supabase
    # -----------------------------

    SUPABASE_URL: str = ""

    SUPABASE_ANON_KEY: str = ""

    SUPABASE_SERVICE_KEY: str = ""


    # -----------------------------
    # Memory / Vector DB
    # -----------------------------

    PINECONE_API_KEY: str = ""

    PINECONE_ENV: str = (
        "gcp-starter"
    )


    # -----------------------------
    # n8n
    # -----------------------------

    N8N_WEBHOOK_URL: str = (
        "http://localhost:5678"
    )


    LOG_LEVEL: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() == "production"

    @model_validator(mode="after")
    def validate_security_configuration(self):
        """Reject unsafe production settings while keeping local setup simple."""
        if not self.is_production:
            return self

        errors: list[str] = []
        if self.AUTH_ADMISSION_STORE != "database":
            errors.append("AUTH_ADMISSION_STORE must use the shared database in production")
        if self.ALGORITHM != "HS256":
            errors.append("ALGORITHM must be HS256 for the configured symmetric signing key")
        if not public_https(self.FRONTEND_URL):
            errors.append("FRONTEND_URL must be a public HTTPS URL")
        if any(not public_https(origin) or urlsplit(origin).path for origin in self.CORS_ORIGINS):
            errors.append("CORS_ORIGINS must be public HTTPS origins without paths")
        if self.GOOGLE_CLIENT_ID and (not self.GOOGLE_CLIENT_SECRET or not public_https(self.GOOGLE_REDIRECT_URI)):
            errors.append("Configured Google OAuth requires a secret and public HTTPS callback")
        insecure_secrets = {
            "",
            "change-me-in-production",
            "your-secret-key-min-32-chars",
        }
        if self.SECRET_KEY in insecure_secrets or len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be a non-default value of at least 32 characters")

        if not self.INTEGRATION_ENCRYPTION_KEY:
            errors.append("INTEGRATION_ENCRYPTION_KEY is required")
        else:
            try:
                Fernet(self.INTEGRATION_ENCRYPTION_KEY.encode("utf-8"))
            except (TypeError, ValueError):
                errors.append("INTEGRATION_ENCRYPTION_KEY must be a valid Fernet key")

        if not self.DATABASE_URL.startswith(("postgresql+asyncpg://", "postgresql://")):
            errors.append("DATABASE_URL must use PostgreSQL in production")
        try:
            database_url = make_url(self.DATABASE_URL)
            if not database_url.host or not database_url.database:
                errors.append("DATABASE_URL must include a database host and name")
        except Exception:
            errors.append("DATABASE_URL is not a valid SQLAlchemy URL")
        if "[YOUR-" in self.DATABASE_URL or "localhost" in self.DATABASE_URL:
            errors.append("DATABASE_URL contains a placeholder or localhost production host")
        if self.DEBUG:
            errors.append("DEBUG must be disabled in production")
        if self.AUTO_CREATE_TABLES:
            errors.append("AUTO_CREATE_TABLES must be false in production; run Alembic first")
        if self.ALLOW_LEGACY_ENV_CREDENTIALS:
            errors.append("ALLOW_LEGACY_ENV_CREDENTIALS must be false in production")
        if not self.CORS_ORIGINS or any(origin == "*" for origin in self.CORS_ORIGINS):
            errors.append("CORS_ORIGINS must contain explicit trusted origins")

        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self


settings = Settings()
