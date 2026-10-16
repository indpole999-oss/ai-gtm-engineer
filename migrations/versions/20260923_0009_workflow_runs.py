"""Explicit workflow runs, deterministically linked to existing execution cycles."""
from alembic import op
import sqlalchemy as sa

revision = "20260923_0009"
down_revision = "20260923_0008"
branch_labels = depends_on = None


def upgrade():
    op.create_table("workflow_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.ForeignKeyConstraint(["workspace_id", "id"], ["execution_cycles.workspace_id", "execution_cycles.id"]))
    # Ownership is proven by the existing cycle FK; no customer reassignment.
    op.execute("INSERT INTO workflow_runs(id,workspace_id,created_at,definition_version) SELECT id,workspace_id,created_at,1 FROM execution_cycles")
    with op.batch_alter_table("step_runs") as batch:
        batch.create_foreign_key("fk_step_workflow", "workflow_runs", ["workspace_id", "cycle_id"], ["workspace_id", "id"])
    op.create_index("ix_workflow_runs_workspace_id", "workflow_runs", ["workspace_id"])
    db = op.get_bind()
    if db.dialect.name == "postgresql":
        op.execute("REVOKE ALL ON TABLE workflow_runs FROM PUBLIC")
        for role in ("anon", "authenticated"):
            if db.scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                op.execute(f"REVOKE ALL ON TABLE workflow_runs FROM {role}")
        op.execute("ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE workflow_runs FORCE ROW LEVEL SECURITY")
        predicate = "workspace_id = nullif(current_setting('app.workspace_id',true),'')::uuid"
        op.execute(f"CREATE POLICY workspace_isolation ON workflow_runs USING ({predicate}) WITH CHECK ({predicate})")


def downgrade():
    raise RuntimeError("Preserve workflow history. Restore a verified backup.")
