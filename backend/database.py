"""
Database Layer
AI GTM Engineer

Async SQLAlchemy database models.
Supports customer-specific universal integrations.
Supports both SQLite (local development) and PostgreSQL/Supabase (production).
"""

import uuid
import logging

from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Text,
    Integer,
    ForeignKey,
    JSON,
    Uuid,
    UniqueConstraint,
    CheckConstraint,
    ForeignKeyConstraint,
    event,
)

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


logger = logging.getLogger(__name__)


# ==============================
# DATABASE ENGINE
# ==============================

DATABASE_URL = settings.DATABASE_URL

if DATABASE_URL.startswith("postgresql://"):
    # SQLAlchemy's async engine requires an async PostgreSQL driver.
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


if is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ==============================
# BASE MODEL
# ==============================

class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (CheckConstraint("status IN ('active', 'suspended')", name="ck_workspace_status"),)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), primary_key=True, index=True)
    role = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="ck_membership_role"),
        CheckConstraint("status IN ('active', 'suspended')", name="ck_membership_status"),
    )


class WorkspaceOwned:
    # NULL is reserved for quarantined legacy records. Application inserts must
    # always supply ownership; the session guard enforces this before flush.
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)


# ==============================
# USER TABLE
# ==============================

class User(Base):

    __tablename__ = "users"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    hashed_password = Column(
        String(255),
        nullable=False
    )

    full_name = Column(
        String(255),
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==============================
# COMPANY TABLE
# ==============================

class Company(WorkspaceOwned, Base):

    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("workspace_id", "domain", name="uq_companies_workspace_domain"), UniqueConstraint("workspace_id", "id", name="uq_companies_workspace_id_id"),)

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    name = Column(
        String(255),
        nullable=False
    )

    domain = Column(
        String(255),
        index=True
    )

    industry = Column(
        String(255)
    )

    employee_count = Column(
        Integer
    )

    revenue = Column(
        String(100)
    )

    location = Column(
        String(255)
    )

    description = Column(
        Text
    )

    extra_data = Column(
        JSON,
        default=dict
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==============================
# CONTACT TABLE
# ==============================

class Contact(WorkspaceOwned, Base):

    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uq_contacts_workspace_email"), UniqueConstraint("workspace_id", "id", name="uq_contacts_workspace_id_id"), ForeignKeyConstraint(["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_contacts_workspace_parent"),)

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    company_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id"),
        nullable=True
    )

    first_name = Column(
        String(100)
    )

    last_name = Column(
        String(100)
    )

    email = Column(
        String(255),
        index=True
    )

    title = Column(
        String(255)
    )

    linkedin_url = Column(
        String(500)
    )

    phone = Column(
        String(50)
    )

    enriched_data = Column(
        JSON,
        default=dict
    )

    lead_score = Column(
        Integer,
        default=0
    )

    priority = Column(
        String(50),
        default="low"
    )

    insights = Column(
        Text,
        nullable=True
    )

    enriched_at = Column(
        DateTime,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==============================
# CRM TABLE
# ==============================

class CRMRecord(WorkspaceOwned, Base):

    __tablename__ = "crm_records"
    __table_args__ = (UniqueConstraint("workspace_id", "id", name="uq_crm_records_workspace_id_id"), ForeignKeyConstraint(["workspace_id", "contact_id"], ["contacts.workspace_id", "contacts.id"], name="fk_crm_records_workspace_parent"),)

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    contact_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id"),
        nullable=True
    )

    stage = Column(
        String(50),
        default="new"
    )

    status = Column(
        String(50),
        default="active"
    )

    # External CRM provider
    # Example: hubspot / salesforce
    provider = Column(
        String(100),
        nullable=True
    )

    # External object/contact ID returned by CRM
    external_id = Column(
        String(255),
        nullable=True
    )

    # Backward-compatible CRM ID field
    crm_id = Column(
        String(255),
        nullable=True
    )

    # Time when the CRM synchronization succeeded
    synced_at = Column(
        DateTime,
        nullable=True
    )

    notes = Column(
        Text
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==============================
# EMAIL LOG TABLE
# ==============================

class EmailLog(WorkspaceOwned, Base):

    __tablename__ = "email_logs"
    __table_args__ = (UniqueConstraint("workspace_id", "id", name="uq_email_logs_workspace_id_id"), ForeignKeyConstraint(["workspace_id", "contact_id"], ["contacts.workspace_id", "contacts.id"], name="fk_email_logs_workspace_parent"),)

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    contact_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id"),
        nullable=True
    )

    subject = Column(
        String(500)
    )

    body = Column(
        Text
    )

    status = Column(
        String(50),
        default="pending"
    )

    sent_at = Column(
        DateTime,
        nullable=True
    )

    opened_at = Column(
        DateTime,
        nullable=True
    )

    replied_at = Column(
        DateTime,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==============================
# MEETING TABLE
# ==============================

class Meeting(WorkspaceOwned, Base):

    __tablename__ = "meetings"
    __table_args__ = (UniqueConstraint("workspace_id", "id", name="uq_meetings_workspace_id_id"), ForeignKeyConstraint(["workspace_id", "contact_id"], ["contacts.workspace_id", "contacts.id"], name="fk_meetings_workspace_parent"),)

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    contact_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id"),
        nullable=True
    )

    title = Column(
        String(255),
        nullable=False
    )

    contact_email = Column(
        String(255),
        nullable=False
    )

    meeting_time = Column(
        DateTime
    )

    duration_minutes = Column(
        Integer,
        default=30
    )

    status = Column(
        String(50),
        default="scheduled"
    )

    notes = Column(
        Text
    )

    google_event_id = Column(
        String(255),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# ==============================
# UNIVERSAL INTEGRATIONS TABLE
# ==============================

class Integration(WorkspaceOwned, Base):

    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)

    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("workspace_id", "id", name="uq_integrations_workspace_id_id"),)

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    scopes = Column(JSON, nullable=False, default=list)
    health = Column(String(50), nullable=False, default="unknown")
    token_expires_at = Column(DateTime, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    reconnect_required = Column(Boolean, nullable=False, default=False)

    # Customer / user who owns this integration
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Integration category:
    # crm, enrichment, email, calendar, ai, workflow
    category = Column(
        String(50),
        nullable=False,
        index=True
    )

    # Provider name:
    # salesforce, hubspot, zoho, clay, apollo,
    # gmail, outlook, calendly, custom, etc.
    provider = Column(
        String(100),
        nullable=False,
        index=True
    )

    # Authentication mechanism:
    # oauth2, api_key, bearer, basic, custom
    auth_type = Column(
        String(50),
        nullable=False,
        default="api_key"
    )

    # Encrypted credentials will be stored here.
    # Never expose this field directly to the frontend.
    credentials = Column(
        JSON,
        nullable=False,
        default=dict
    )

    # Non-secret provider configuration.
    # Examples: instance URL, workspace ID, API version, etc.
    config = Column(
        JSON,
        nullable=False,
        default=dict
    )

    # connected / disconnected / error
    status = Column(
        String(50),
        nullable=False,
        default="disconnected"
    )

    # Last successful connection test
    last_connected_at = Column(
        DateTime,
        nullable=True
    )

    # Last error message, if connection failed
    last_error = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


# ==============================
# DATABASE SESSION
# ==============================

async def get_db():

    async with AsyncSessionLocal() as session:

        try:

            yield session

            await session.commit()

        except Exception as e:

            await session.rollback()

            logger.error("Database operation failed", extra={"error_type": type(e).__name__})

            raise


# ==============================
# CREATE TABLES
# ==============================

async def create_tables():

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

    logger.info(
        "Database tables created successfully"
    )


class OAuthAttempt(Base):
    __tablename__ = "oauth_attempts"
    state_hash = Column(String(64), primary_key=True)
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    integration_id = Column(Uuid(as_uuid=True), nullable=True)
    encrypted_verifier = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class IntegrationAudit(WorkspaceOwned, Base):
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    __tablename__ = "integration_audit"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    integration_id = Column(Uuid(as_uuid=True), nullable=False)
    action = Column(String(60), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
