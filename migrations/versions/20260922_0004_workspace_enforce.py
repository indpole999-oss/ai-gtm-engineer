"""Validate, index, constrain ownership and add PostgreSQL RLS defense in depth."""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0004"
down_revision = "20260922_0003"
branch_labels = depends_on = None
TABLES = ("companies", "contacts", "crm_records", "email_logs", "meetings", "integrations")
RELATIONS = {"contacts": ("company_id", "companies"), "crm_records": ("contact_id", "contacts"),
             "email_logs": ("contact_id", "contacts"), "meetings": ("contact_id", "contacts")}


def upgrade():
    db = op.get_bind()
    for table in TABLES:
        count = db.scalar(sa.text(f"SELECT count(*) FROM {table} t LEFT JOIN workspaces w ON t.workspace_id=w.id WHERE t.workspace_id IS NOT NULL AND w.id IS NULL"))
        if count:
            raise RuntimeError(f"Invalid ownership in {table}; manual review required")
    for table, (field, parent) in RELATIONS.items():
        count = db.scalar(sa.text(f"SELECT count(*) FROM {table} t LEFT JOIN {parent} p ON t.{field}=p.id WHERE t.workspace_id IS NOT NULL AND t.{field} IS NOT NULL AND (p.workspace_id IS NULL OR p.workspace_id<>t.workspace_id)"))
        if count:
            raise RuntimeError(f"Cross-workspace relationship in {table}; manual review required")
    # Only integrations have provable ownership for every baseline record.
    if db.scalar(sa.text("SELECT count(*) FROM integrations WHERE workspace_id IS NULL")):
        raise RuntimeError("Unowned integration requires manual mapping before enforcement")
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"fk_{table}_workspace", "workspaces", ["workspace_id"], ["id"])
            batch.create_index(f"ix_{table}_workspace_id", ["workspace_id"])
            batch.create_unique_constraint(f"uq_{table}_workspace_id_id", ["workspace_id", "id"])
            if table == "integrations":
                batch.alter_column("workspace_id", existing_type=sa.Uuid(), nullable=False)
    for table, (field, parent) in RELATIONS.items():
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"fk_{table}_workspace_parent", parent,
                                    ["workspace_id", field], ["workspace_id", "id"])
    for table, field in (("companies", "domain"), ("contacts", "email")):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_{field}")
            batch.create_index(f"ix_{table}_{field}", [field])
            batch.create_unique_constraint(f"uq_{table}_workspace_{field}", ["workspace_id", field])
    if db.dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            expression = "workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid"
            op.execute(f"CREATE POLICY workspace_isolation ON {table} USING ({expression}) WITH CHECK ({expression})")


def downgrade():
    raise RuntimeError("Global uniqueness cannot safely be restored after tenant writes. Restore a verified backup.")
