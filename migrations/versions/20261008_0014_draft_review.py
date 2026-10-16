"""Durable outreach review history; no existing snapshots are rewritten."""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0014"
down_revision = "20260928_0013"
branch_labels = depends_on = None


def upgrade():
    op.create_table("draft_review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("scheduled_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("workspace_id", "id"),
        sa.UniqueConstraint("scheduled_id", "revision"),
        sa.ForeignKeyConstraint(["workspace_id", "scheduled_id"], ["scheduled_messages.workspace_id", "scheduled_messages.id"]),
        sa.ForeignKeyConstraint(["workspace_id", "draft_id"], ["message_drafts.workspace_id", "message_drafts.id"]),
        sa.CheckConstraint("revision > 0"),
        sa.CheckConstraint("action IN ('created','revised','submitted','approved','rejected','changes_requested')"))
    op.create_index("ix_draft_review_events_workspace_id", "draft_review_events", ["workspace_id"])
    db = op.get_bind()
    if db.dialect.name == "postgresql":
        op.execute("REVOKE ALL ON draft_review_events FROM PUBLIC")
        for role in ("anon", "authenticated"):
            if db.scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                op.execute(f"REVOKE ALL ON draft_review_events FROM {role}")
        op.execute("ALTER TABLE draft_review_events ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE draft_review_events FORCE ROW LEVEL SECURITY")
        predicate = "workspace_id = nullif(current_setting('app.workspace_id',true),'')::uuid"
        op.execute(f"CREATE POLICY workspace_isolation ON draft_review_events USING ({predicate}) WITH CHECK ({predicate})")
        op.execute("CREATE TRIGGER immutable_draft_review_events BEFORE UPDATE OR DELETE ON draft_review_events FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
    else:
        for operation in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER immutable_draft_review_events_{operation.lower()} BEFORE {operation} ON draft_review_events BEGIN SELECT RAISE(ABORT,'Draft review history is immutable'); END")


def downgrade():
    raise RuntimeError("Preserve review history; restore a verified backup")
