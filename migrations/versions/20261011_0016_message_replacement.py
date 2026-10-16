"""Preserve cancelled approvals while allowing one active replacement per step."""
from alembic import op
import sqlalchemy as sa

revision = "20261011_0016"
down_revision = "20261009_0015"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    unique = next(item for item in sa.inspect(db).get_unique_constraints("messages")
                  if item["column_names"] == ["scheduled_id"])
    if db.dialect.name == "sqlite":
        triggers = list(db.execute(sa.text("SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name='messages'" )).scalars())
        convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
        with op.batch_alter_table("messages", naming_convention=convention) as batch:
            batch.drop_constraint(unique["name"] or "uq_messages_scheduled_id", type_="unique")
            batch.create_check_constraint("cancelled_message_unattempted",
                "state != 'cancelled' OR (attempted_at IS NULL AND accepted_at IS NULL AND provider_message_id IS NULL)")
        for statement in triggers:
            op.execute(statement)
        op.execute("""CREATE TRIGGER immutable_cancelled_message BEFORE UPDATE ON messages
            WHEN OLD.state='cancelled' OR (NEW.state='cancelled' AND
            (OLD.attempted_at IS NOT NULL OR OLD.accepted_at IS NOT NULL OR OLD.provider_message_id IS NOT NULL OR NEW.attempted_at IS NOT NULL OR NEW.accepted_at IS NOT NULL OR NEW.provider_message_id IS NOT NULL))
            BEGIN SELECT RAISE(ABORT,'Cancelled or attempted delivery is immutable'); END""")
    else:
        op.drop_constraint(unique["name"], "messages", type_="unique")
        op.execute("""CREATE FUNCTION protect_cancelled_message() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF OLD.state='cancelled' OR (NEW.state='cancelled' AND
          (OLD.attempted_at IS NOT NULL OR OLD.accepted_at IS NOT NULL OR OLD.provider_message_id IS NOT NULL OR NEW.attempted_at IS NOT NULL OR NEW.accepted_at IS NOT NULL OR NEW.provider_message_id IS NOT NULL))
        THEN RAISE EXCEPTION 'Cancelled or attempted delivery is immutable'; END IF; RETURN NEW; END $$""")
        op.execute("CREATE TRIGGER immutable_cancelled_message BEFORE UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION protect_cancelled_message()")
        op.create_check_constraint("cancelled_message_unattempted", "messages",
            "state != 'cancelled' OR (attempted_at IS NULL AND accepted_at IS NULL AND provider_message_id IS NULL)")
    op.create_index("uq_messages_active_scheduled", "messages", ["scheduled_id"], unique=True,
        postgresql_where=sa.text("state != 'cancelled'"), sqlite_where=sa.text("state != 'cancelled'"))


def downgrade():
    raise RuntimeError("Preserve cancelled approvals and replacement history; use a forward migration")
