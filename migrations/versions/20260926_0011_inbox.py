"""Durable inbox evidence and an internal consumer of the existing outbox."""
from alembic import op
import sqlalchemy as sa

revision = "20260926_0011"
down_revision = "20260926_0010"
branch_labels = depends_on = None


def col(name, kind, nullable=False):
    return sa.Column(name, kind, nullable=nullable)


def parent(column, name):
    return sa.ForeignKeyConstraint(["workspace_id", column], [name + ".workspace_id", name + ".id"])


def table(name, *fields):
    op.create_table(name, sa.Column("id", sa.Uuid(), primary_key=True), col("workspace_id", sa.Uuid()), col("created_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]), sa.UniqueConstraint("workspace_id", "id"), *fields)
    op.create_index("ix_" + name + "_workspace_id", name, ["workspace_id"])


TABLES = ("inbox_threads", "inbound_messages", "inbound_receipts", "inbox_thread_links", "reply_classifications", "inbox_pauses", "suggested_reply_drafts")
CATEGORIES = ("positive", "negative", "objection", "out_of_office", "wrong_person", "question", "meeting_intent", "unsubscribe", "other")


def upgrade():
    # Existing approved execution events retain their original cycle IDs. Only
    # new independent inbound events can have no execution-cycle origin.
    with op.batch_alter_table("domain_events") as batch:
        batch.alter_column("cycle_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("outbox_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    for name, kind in (("due_at", sa.DateTime()), ("lease_token", sa.Uuid()), ("lease_until", sa.DateTime()), ("error_code", sa.String(100))):
        op.add_column("outbox_events", sa.Column(name, kind))
    op.create_index("ix_outbox_ready", "outbox_events", ["workspace_id", "status", "due_at"])
    op.create_index("ix_domain_event_kind", "domain_events", ["workspace_id", "kind"])
    table("inbox_threads", col("sender_id", sa.Uuid()), col("provider_thread_id", sa.String(255), True), col("thread_key", sa.String(300)),
        parent("sender_id", "sender_identities"), sa.UniqueConstraint("sender_id", "thread_key"))
    references = {"thread_id": "inbox_threads", "sender_id": "sender_identities", "outbound_message_id": "messages", "contact_id": "contacts",
        "company_id": "companies", "campaign_id": "campaigns", "sequence_id": "sequences", "sequence_version_id": "sequence_versions",
        "enrollment_id": "enrollments", "brain_version_id": "company_brain_versions", "research_job_id": "research_jobs"}
    table("inbound_messages", *[col(name, sa.Uuid(), name not in {"thread_id", "sender_id"}) for name in references],
        col("provider_message_id", sa.String(255)), col("in_reply_to", sa.String(255), True), col("sender_email", sa.String(255)),
        col("recipient_email", sa.String(255)), col("subject", sa.String(500)), col("body", sa.Text()), col("auto_submitted", sa.String(20)),
        col("received_at", sa.DateTime()), col("content_hash", sa.String(64)), col("association", sa.String(30)),
        *[parent(name, target) for name, target in references.items()], sa.UniqueConstraint("sender_id", "provider_message_id"))
    op.create_index("ix_inbound_thread_received", "inbound_messages", ["workspace_id", "thread_id", "received_at"])
    table("inbound_receipts", col("sender_id", sa.Uuid()), col("provider_event_id", sa.String(255)), col("content_hash", sa.String(64)), col("inbound_message_id", sa.Uuid()),
        parent("sender_id", "sender_identities"), parent("inbound_message_id", "inbound_messages"), sa.UniqueConstraint("sender_id", "provider_event_id"))
    table("inbox_thread_links", col("thread_id", sa.Uuid()), col("outbound_message_id", sa.Uuid()), parent("thread_id", "inbox_threads"), parent("outbound_message_id", "messages"), sa.UniqueConstraint("thread_id", "outbound_message_id"))
    table("reply_classifications", col("inbound_message_id", sa.Uuid()), col("number", sa.Integer()), col("category", sa.String(30)), col("confidence", sa.Float(), True),
        col("reason", sa.Text()), col("evidence", sa.JSON()), col("classifier_version", sa.String(80)), col("recommended_action", sa.String(80)),
        col("requires_review", sa.Boolean()), col("manual_override", sa.Boolean()), col("overridden_by", sa.Uuid(), True), sa.ForeignKeyConstraint(["overridden_by"], ["users.id"]),
        parent("inbound_message_id", "inbound_messages"), sa.UniqueConstraint("inbound_message_id", "number"),
        sa.CheckConstraint("category IN (" + ",".join(repr(c) for c in CATEGORIES) + ")"), sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"))
    table("inbox_pauses", col("inbound_message_id", sa.Uuid()), col("enrollment_id", sa.Uuid()), col("reason", sa.String(30)),
        parent("inbound_message_id", "inbound_messages"), parent("enrollment_id", "enrollments"), sa.UniqueConstraint("enrollment_id", "inbound_message_id"))
    table("suggested_reply_drafts", col("inbound_message_id", sa.Uuid()), col("classification_id", sa.Uuid()), col("subject", sa.String(500)), col("body", sa.Text()), col("context", sa.JSON()),
        col("created_by", sa.Uuid()), sa.ForeignKeyConstraint(["created_by"], ["users.id"]), parent("inbound_message_id", "inbound_messages"), parent("classification_id", "reply_classifications"),
        sa.UniqueConstraint("inbound_message_id", "classification_id"))
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
            op.execute(f"CREATE TRIGGER immutable_{name} BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
    elif db.dialect.name == "sqlite":
        for name in TABLES:
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER immutable_{name}_{action} BEFORE {action} ON {name} BEGIN SELECT RAISE(ABORT,'Inbox evidence is immutable'); END")
        # SQLite batch rebuilding does not preserve the original audit triggers.
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_event_{action} BEFORE {action} ON domain_events BEGIN SELECT RAISE(ABORT,'Execution audit is immutable'); END")


def downgrade():
    raise RuntimeError("Preserve inbound evidence, reply holds and audit. Restore a verified backup.")
