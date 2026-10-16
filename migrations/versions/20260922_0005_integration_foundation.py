"""Workspace connection health, durable OAuth capability and credential audit."""
from alembic import op
import sqlalchemy as sa
revision = "20260922_0005"
down_revision = "20260922_0004"
branch_labels = depends_on = None


def upgrade():
    for column in (
        sa.Column("scopes",sa.JSON(),nullable=False,server_default="[]"),
        sa.Column("health",sa.String(50),nullable=False,server_default="unknown"),
        sa.Column("token_expires_at",sa.DateTime(),nullable=True),
        sa.Column("last_error_at",sa.DateTime(),nullable=True),
        sa.Column("reconnect_required",sa.Boolean(),nullable=False,server_default=sa.false()),
    ):
        op.add_column("integrations",column)
    op.create_table("oauth_attempts",
        sa.Column("state_hash",sa.String(64),primary_key=True),
        sa.Column("workspace_id",sa.Uuid(),sa.ForeignKey("workspaces.id"),nullable=False),
        sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("integration_id",sa.Uuid(),nullable=True),
        sa.Column("encrypted_verifier",sa.Text(),nullable=False),
        sa.Column("expires_at",sa.DateTime(),nullable=False),
        sa.Column("consumed_at",sa.DateTime(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_oauth_attempts_workspace_id","oauth_attempts",["workspace_id"])
    op.create_table("integration_audit",
        sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("workspace_id",sa.Uuid(),sa.ForeignKey("workspaces.id"),nullable=False),
        sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("integration_id",sa.Uuid(),nullable=False),
        sa.Column("action",sa.String(60),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_integration_audit_workspace_id","integration_audit",["workspace_id"])
    db=op.get_bind()
    if db.dialect.name == "postgresql":
        for table in ("oauth_attempts","integration_audit"):
            op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
            for role in ("anon","authenticated"):
                if db.scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"),{"role":role}):
                    op.execute(f"REVOKE ALL ON TABLE {table} FROM {role}")
        op.execute("ALTER TABLE integration_audit ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE integration_audit FORCE ROW LEVEL SECURITY")
        predicate="workspace_id = nullif(current_setting('app.workspace_id',true),'')::uuid"
        op.execute(f"CREATE POLICY workspace_isolation ON integration_audit USING ({predicate}) WITH CHECK ({predicate})")


def downgrade():
    raise RuntimeError("Preserve OAuth and integration audit. Restore a verified backup.")
