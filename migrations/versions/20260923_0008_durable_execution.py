"""Goals, immutable approvals, leased commands and transactional audit/outbox."""
from alembic import op
import sqlalchemy as sa
revision = "20260923_0008"
down_revision = "20260923_0007"
branch_labels = depends_on = None


def identity():
    return [sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False)]


def parent(column, table):
    return sa.ForeignKeyConstraint(["workspace_id", column], [table + ".workspace_id", table + ".id"])


def upgrade():
    op.create_table("goals", *identity(), sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("brain_version_id", sa.Uuid(), nullable=False), sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_inputs", sa.JSON(), nullable=False), sa.UniqueConstraint("workspace_id", "id"), parent("brain_version_id", "company_brain_versions"))
    op.create_table("plan_versions", *identity(), sa.Column("goal_id", sa.Uuid(), nullable=False), sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("document", sa.JSON(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("author_method", sa.String(100), nullable=False),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("approved_at", sa.DateTime()),
        sa.UniqueConstraint("workspace_id", "id"), sa.UniqueConstraint("goal_id", "number"), parent("goal_id", "goals"))
    op.create_table("execution_cycles", *identity(), sa.Column("plan_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("plan_hash", sa.String(64), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("stop_reason", sa.String(100)),
        sa.UniqueConstraint("workspace_id", "id"), parent("plan_id", "plan_versions"))
    op.create_table("step_runs", *identity(), sa.Column("cycle_id", sa.Uuid(), nullable=False), sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("output", sa.JSON()),
        sa.UniqueConstraint("workspace_id", "id"), sa.UniqueConstraint("cycle_id", "position"), parent("cycle_id", "execution_cycles"))
    op.create_table("action_commands", *identity(), sa.Column("step_id", sa.Uuid(), nullable=False, unique=True), sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("lease_token", sa.Uuid()), sa.Column("lease_until", sa.DateTime()), sa.Column("error_code", sa.String(100)),
        sa.UniqueConstraint("workspace_id", "id"), sa.UniqueConstraint("workspace_id", "idempotency_key"), parent("step_id", "step_runs"), parent("cycle_id", "execution_cycles"))
    op.create_table("domain_events", *identity(), sa.Column("cycle_id", sa.Uuid(), nullable=False), sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False), sa.UniqueConstraint("workspace_id", "id"), parent("cycle_id", "execution_cycles"))
    op.create_table("outbox_events", *identity(), sa.Column("event_id", sa.Uuid(), nullable=False, unique=True), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("delivered_at", sa.DateTime()), parent("event_id", "domain_events"))
    tables = ("goals", "plan_versions", "execution_cycles", "step_runs", "action_commands", "domain_events", "outbox_events")
    db = op.get_bind()
    for table in tables:
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])
        if db.dialect.name == "postgresql":
            op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                if db.scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                    op.execute(f"REVOKE ALL ON TABLE {table} FROM {role}")
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            predicate = "workspace_id = nullif(current_setting('app.workspace_id',true),'')::uuid"
            op.execute(f"CREATE POLICY workspace_isolation ON {table} USING ({predicate}) WITH CHECK ({predicate})")
    op.create_index("ix_commands_ready", "action_commands", ["workspace_id", "status", "due_at"])
    if db.dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION protect_approved_plan() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF OLD.status='approved' THEN RAISE EXCEPTION 'Approved plan is immutable'; END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
        op.execute("CREATE TRIGGER immutable_approved_plan BEFORE UPDATE OR DELETE ON plan_versions FOR EACH ROW EXECUTE FUNCTION protect_approved_plan()")
        op.execute("CREATE TRIGGER immutable_execution_audit BEFORE UPDATE OR DELETE ON domain_events FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
    elif db.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER immutable_plan_{action} BEFORE {action} ON plan_versions WHEN OLD.status='approved' BEGIN SELECT RAISE(ABORT,'Approved plan is immutable'); END")
            op.execute(f"CREATE TRIGGER immutable_event_{action} BEFORE {action} ON domain_events BEGIN SELECT RAISE(ABORT,'Execution audit is immutable'); END")


def downgrade():
    raise RuntimeError("Preserve approvals and execution audit. Restore a verified backup.")
