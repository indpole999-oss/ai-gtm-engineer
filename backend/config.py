"""
Backend Configuration - Settings with Pydantic BaseSettings
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):

    # -----------------------------
    # App
    # -----------------------------

    APP_NAME: str = "AI GTM Engineer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Integration credential encryption
    INTEGRATION_ENCRYPTION_KEY: str = ""


    # -----------------------------
    # CORS
    # -----------------------------

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8081",
    ]


    # -----------------------------
    # Database
    # -----------------------------

    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"


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


    class Config:

        env_file = ".env"

        case_sensitive = True

        extra = "ignore"


settings = Settings()