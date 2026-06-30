"""
Backend Configuration - Settings with Pydantic BaseSettings
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
      # App
      APP_NAME: str = "AI GTM Engineer"
      APP_VERSION: str = "1.0.0"
      DEBUG: bool = False
      SECRET_KEY: str = "change-me-in-production"
      ALGORITHM: str = "HS256"
      ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS
      CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Database (Supabase PostgreSQL)
      DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/gtm_db"

    # NVIDIA NIM
      NVIDIA_API_KEY: str = ""
      NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
      NVIDIA_MODEL: str = "meta/llama-3.1-70b-instruct"

    # Supabase
      SUPABASE_URL: str = ""
      SUPABASE_ANON_KEY: str = ""
      SUPABASE_SERVICE_KEY: str = ""

    # Resend (Email)
      RESEND_API_KEY: str = ""
      FROM_EMAIL: str = "gtm@yourdomain.com"

    # Apollo (Lead Enrichment)
      APOLLO_API_KEY: str = ""

    # Serper (Web Search)
      SERPER_API_KEY: str = ""

    # HubSpot CRM
      HUBSPOT_API_KEY: str = ""

    # Google Calendar
      GOOGLE_CLIENT_ID: str = ""
      GOOGLE_CLIENT_SECRET: str = ""

    # Pinecone (Vector Memory)
      PINECONE_API_KEY: str = ""
      PINECONE_ENV: str = "gcp-starter"

    # n8n Webhook
      N8N_WEBHOOK_URL: str = "http://localhost:5678"

    class Config:
              env_file = ".env"
              case_sensitive = True


settings = Settings()
