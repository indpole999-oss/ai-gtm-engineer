"""Phase 6 outreach snapshots, approvals, schedules and provider state."""
from alembic import op
import sqlalchemy as sa

revision = "20260926_0010"
down_revision = "20260923_0009"
branch_labels = depends_on = None


def parent(column, table):
    return sa.ForeignKeyConstraint(["workspace_id", column], [table + ".workspace_id", table + ".id"])


def col(name, kind, nullable=False, **kw):
    return sa.Column(name, kind, nullable=nullable, **kw)


def table(name, *columns):
    op.create_table(name, col("id", sa.Uuid(), primary_key=True),
        col("workspace_id", sa.Uuid()), col("created_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]), *columns)
    op.create_index(f"ix_{name}_workspace_id", name, ["workspace_id"])


def uq(*columns):
    return sa.UniqueConstraint(*(columns or ("workspace_id", "id")))


TABLES = ("campaigns", "sequences", "sequence_versions", "sequence_steps", "sender_identities", "enrollments", "scheduled_messages", "message_drafts", "messages", "delivery_events", "suppressions")
IMMUTABLE = ("sequence_versions", "sequence_steps", "scheduled_messages", "message_drafts", "delivery_events", "suppressions")


def upgrade():
    table("campaigns", col("name", sa.String(200)), col("status", sa.String(20)), uq())
    table("sequences", col("campaign_id", sa.Uuid()), col("name", sa.String(200)), uq(), parent("campaign_id", "campaigns"))
    table("sequence_versions", col("sequence_id", sa.Uuid()), col("number", sa.Integer()), col("definition", sa.JSON()), col("content_hash", sa.String(64)), uq(), uq("sequence_id", "number"), parent("sequence_id", "sequences"))
    table("sequence_steps", col("version_id", sa.Uuid()), col("position", sa.Integer()), col("delay_seconds", sa.Integer()), col("purpose", sa.Text()), uq(), uq("version_id", "position"), parent("version_id", "sequence_versions"), sa.CheckConstraint("delay_seconds >= 0"))
    table("sender_identities", col("email", sa.String(255)), col("provider", sa.String(40)), col("integration_id", sa.Uuid(), True), col("status", sa.String(20)), col("daily_limit", sa.Integer()), uq(), uq("workspace_id", "email"), parent("integration_id", "integrations"), sa.CheckConstraint("daily_limit > 0 AND daily_limit <= 100"))
    table("enrollments", col("version_id", sa.Uuid()), col("contact_id", sa.Uuid()), col("sender_id", sa.Uuid()), col("research_job_id", sa.Uuid()), col("status", sa.String(20)), uq(), uq("version_id", "contact_id"), parent("version_id", "sequence_versions"), parent("contact_id", "contacts"), parent("sender_id", "sender_identities"), parent("research_job_id", "research_jobs"))
    table("scheduled_messages", col("enrollment_id", sa.Uuid()), col("sequence_step_id", sa.Uuid()), col("due_at", sa.DateTime()), uq(), uq("enrollment_id", "sequence_step_id"), parent("enrollment_id", "enrollments"), parent("sequence_step_id", "sequence_steps"))
    table("message_drafts", col("scheduled_id", sa.Uuid()), col("envelope", sa.JSON()), col("content_hash", sa.String(64)), col("created_by", sa.Uuid()), sa.ForeignKeyConstraint(["created_by"], ["users.id"]), uq(), parent("scheduled_id", "scheduled_messages"))
    table("messages", col("draft_id", sa.Uuid()), col("scheduled_id", sa.Uuid()), col("approved_by", sa.Uuid()), col("approved_hash", sa.String(64)), col("plan_id", sa.Uuid()), col("state", sa.String(30)), col("provider_message_id", sa.String(255), True), col("attempted_at", sa.DateTime(), True), col("accepted_at", sa.DateTime(), True), col("error_code", sa.String(80), True), uq(), uq("draft_id"), uq("scheduled_id"), uq("plan_id"), sa.ForeignKeyConstraint(["approved_by"], ["users.id"]), parent("draft_id", "message_drafts"), parent("scheduled_id", "scheduled_messages"), parent("plan_id", "plan_versions"), sa.CheckConstraint("state != 'sent' OR (provider_message_id IS NOT NULL AND accepted_at IS NOT NULL)"))
    table("delivery_events", col("message_id", sa.Uuid()), col("provider_event_id", sa.String(255)), col("kind", sa.String(30)), uq("workspace_id", "provider_event_id"), parent("message_id", "messages"))
    table("suppressions", col("email", sa.String(255)), col("reason", sa.String(30)), uq("workspace_id", "email"))
    db = op.get_bind()
    if db.dialect.name == "postgresql":
        for name in TABLES:
            op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                if db.scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                    op.execute(f"REVOKE ALL ON TABLE {name} FROM {role}")
            op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
            predicate = "workspace_id = nullif(current_setting('app.workspace_id',true),'')::uuid"
            op.execute(f"CREATE POLICY workspace_isolation ON {name} USING ({predicate}) WITH CHECK ({predicate})")
        for name in IMMUTABLE:
            op.execute(f"CREATE TRIGGER immutable_{name} BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
        op.execute("""CREATE FUNCTION protect_message_approval() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF TG_OP='DELETE' OR OLD.state='sent' OR ROW(OLD.draft_id,OLD.scheduled_id,OLD.approved_by,OLD.approved_hash,OLD.plan_id,OLD.workspace_id)
        IS DISTINCT FROM ROW(NEW.draft_id,NEW.scheduled_id,NEW.approved_by,NEW.approved_hash,NEW.plan_id,NEW.workspace_id)
        THEN RAISE EXCEPTION 'Message approval is immutable'; END IF; RETURN NEW; END $$""")
        op.execute("CREATE TRIGGER immutable_message_approval BEFORE UPDATE OR DELETE ON messages FOR EACH ROW EXECUTE FUNCTION protect_message_approval()")
        op.execute("""CREATE FUNCTION protect_enrollment_references() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF ROW(OLD.version_id,OLD.contact_id,OLD.sender_id,OLD.research_job_id,OLD.workspace_id)
        IS DISTINCT FROM ROW(NEW.version_id,NEW.contact_id,NEW.sender_id,NEW.research_job_id,NEW.workspace_id)
        THEN RAISE EXCEPTION 'Enrollment references are immutable'; END IF; RETURN NEW; END $$""")
        op.execute("CREATE TRIGGER immutable_enrollment_references BEFORE UPDATE ON enrollments FOR EACH ROW EXECUTE FUNCTION protect_enrollment_references()")
    elif db.dialect.name == "sqlite":
        for name in IMMUTABLE:
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER immutable_{name}_{action} BEFORE {action} ON {name} BEGIN SELECT RAISE(ABORT,'Outreach snapshot is immutable'); END")
        op.execute("CREATE TRIGGER immutable_message_delete BEFORE DELETE ON messages BEGIN SELECT RAISE(ABORT,'Message approval is immutable'); END")
        op.execute("CREATE TRIGGER immutable_message_acceptance BEFORE UPDATE ON messages WHEN OLD.state='sent' BEGIN SELECT RAISE(ABORT,'Provider acceptance is immutable'); END")
        for name, fields in (("messages", ("draft_id", "scheduled_id", "approved_by", "approved_hash", "plan_id", "workspace_id")), ("enrollments", ("version_id", "contact_id", "sender_id", "research_job_id", "workspace_id"))):
            condition = " OR ".join(f"OLD.{field} IS NOT NEW.{field}" for field in fields)
            op.execute(f"CREATE TRIGGER immutable_{name}_references BEFORE UPDATE ON {name} WHEN {condition} BEGIN SELECT RAISE(ABORT,'Outreach references are immutable'); END")


def downgrade():
    raise RuntimeError("Preserve outreach approvals and provider history. Restore a verified backup.")
