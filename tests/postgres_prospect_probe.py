"""Concurrent prospect creation in an already-generated disposable CI database."""
import asyncio
import sys
from types import SimpleNamespace
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func
from backend.database import AsyncSessionLocal, Company, Contact, engine
from backend.routers.companies import CompanyCreate, create_company
from backend.routers.contacts import ContactCreate, create_contact


async def check():
    workspace, actor = map(UUID, sys.argv[1:3])
    async def create(fn, payload):
        async with AsyncSessionLocal() as db:
            db.info.update(workspace_id=workspace, workspace_role="owner")
            try:
                return await fn(payload, db, SimpleNamespace(id=actor))
            except HTTPException as error:
                await db.rollback()
                return error.status_code
    companies = await asyncio.wait_for(asyncio.gather(*[
        create(create_company, CompanyCreate(name="Concurrent fixture", domain="concurrent-prospect.example"))
        for _ in range(2)
    ]), 10)
    assert sum(isinstance(row, dict) for row in companies) == 1 and 409 in companies
    account = next(row for row in companies if isinstance(row, dict))
    contacts = await asyncio.wait_for(asyncio.gather(*[
        create(create_contact, ContactCreate(company_id=account["id"], first_name="Test", last_name="Buyer", email="concurrent@example.com"))
        for _ in range(2)
    ]), 10)
    assert sum(isinstance(row, dict) for row in contacts) == 1 and 409 in contacts
    async with AsyncSessionLocal() as db:
        db.info.update(workspace_id=workspace, workspace_role="owner")
        assert await db.scalar(select(func.count()).select_from(Company).where(Company.domain == "concurrent-prospect.example")) == 1
        assert await db.scalar(select(func.count()).select_from(Contact).where(Contact.email == "concurrent@example.com")) == 1
    await engine.dispose()


asyncio.run(check())
