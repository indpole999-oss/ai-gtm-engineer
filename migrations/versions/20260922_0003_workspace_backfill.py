"""Backfill only provable ownership; inventory every ambiguous legacy record."""
from datetime import datetime
from uuid import UUID, uuid5, NAMESPACE_URL
from alembic import op
import sqlalchemy as sa

revision = "20260922_0003"
down_revision = "20260922_0002"
branch_labels = depends_on = None
TABLES = ("companies", "contacts", "crm_records", "email_logs", "meetings", "integrations")


def upgrade():
    db = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=db)
    # SQLite reflection sees UUID columns as CHAR(32); restore bind processors.
    for table in meta.tables.values():
        for column in table.columns:
            if column.name in {"id", "user_id", "workspace_id", "record_id", "company_id", "contact_id"}:
                column.type = sa.Uuid()
    now = datetime.utcnow()
    owners = {}
    for user in db.execute(sa.select(meta.tables["users"])).mappings():
        uid = UUID(str(user["id"]))
        wid = uuid5(NAMESPACE_URL, f"gaps-ai:legacy-user:{uid}")
        owners[uid] = wid
        db.execute(meta.tables["workspaces"].insert().values(
            id=wid, name=f"{user['full_name'] or 'My'} workspace",
            slug=f"legacy-{uid.hex}", status="active", created_at=now, updated_at=now))
        db.execute(meta.tables["workspace_memberships"].insert().values(
            workspace_id=wid, user_id=uid, role="owner",
            status="active" if user["is_active"] else "suspended", created_at=now, updated_at=now))
    audit = meta.tables["legacy_ownership_audit"]
    for name in TABLES:
        table = meta.tables[name]
        for row in db.execute(sa.select(table)).mappings():
            owner = owners.get(UUID(str(row["user_id"]))) if name == "integrations" and row["user_id"] else None
            if owner:
                db.execute(table.update().where(table.c.id == row["id"]).values(workspace_id=owner))
            db.execute(audit.insert().values(table_name=name, record_id=row["id"], workspace_id=owner,
                disposition="mapped" if owner else "quarantined",
                reason="Existing integration.user_id foreign key" if owner else "No provable user ownership in Phase 0 schema",
                created_at=now))


def downgrade():
    raise RuntimeError("Backfill audit must be preserved. Restore a verified backup instead.")
