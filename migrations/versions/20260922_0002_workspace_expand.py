"""Expand: add workspace tables and nullable ownership without assigning data."""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0002"
down_revision = "20260921_0001"
branch_labels = depends_on = None
TABLES = ("companies", "contacts", "crm_records", "email_logs", "meetings", "integrations")


def upgrade():
    op.create_table("workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_workspace_status"))
    op.create_table("workspace_memberships",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="ck_membership_role"),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_membership_status"))
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])
    op.create_table("legacy_ownership_audit",
        sa.Column("table_name", sa.String(60), primary_key=True),
        sa.Column("record_id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("disposition", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    for table in TABLES:
        op.add_column(table, sa.Column("workspace_id", sa.Uuid(), nullable=True))


def downgrade():
    raise RuntimeError("Workspace downgrade could discard ownership. Restore a verified backup instead.")
