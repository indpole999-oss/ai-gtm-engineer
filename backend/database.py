"""
Database - Async SQLAlchemy engine connected to Supabase PostgreSQL
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from backend.config import settings


# Create async engine
engine = create_async_engine(
      settings.DATABASE_URL,
      echo=settings.DEBUG,
      pool_pre_ping=True,
  )

# Session factory
AsyncSessionLocal = async_sessionmaker(
      engine,
      class_=AsyncSession,
      expire_on_commit=False,
  )


class Base(DeclarativeBase):
      pass


# ORM Models
class User(Base):
      __tablename__ = "users"
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      email = Column(String(255), unique=True, nullable=False, index=True)
      hashed_password = Column(String(255), nullable=False)
      full_name = Column(String(255))
      is_active = Column(Boolean, default=True)
      created_at = Column(DateTime, default=datetime.utcnow)


class Company(Base):
      __tablename__ = "companies"
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      name = Column(String(255), nullable=False)
      domain = Column(String(255), unique=True, index=True)
      industry = Column(String(255))
      employee_count = Column(Integer)
      revenue = Column(String(100))
      location = Column(String(255))
      description = Column(Text)
      metadata = Column(JSON, default=dict)
      created_at = Column(DateTime, default=datetime.utcnow)


class Contact(Base):
      __tablename__ = "contacts"
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))
      first_name = Column(String(100))
      last_name = Column(String(100))
      email = Column(String(255), unique=True, index=True)
      title = Column(String(255))
      linkedin_url = Column(String(500))
      phone = Column(String(50))
      enriched_data = Column(JSON, default=dict)
      created_at = Column(DateTime, default=datetime.utcnow)


class EmailLog(Base):
      __tablename__ = "email_logs"
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"))
      subject = Column(String(500))
      body = Column(Text)
      status = Column(String(50), default="pending")
      sent_at = Column(DateTime)
      opened_at = Column(DateTime)
      replied_at = Column(DateTime)
      created_at = Column(DateTime, default=datetime.utcnow)


# Dependency injection for FastAPI
async def get_db() -> AsyncSession:
      async with AsyncSessionLocal() as session:
                try:
                              yield session
                              await session.commit()
                          except Exception:
                                        await session.rollback()
                                        raise
