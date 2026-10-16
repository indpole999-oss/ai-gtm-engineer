"""Grant the backend runtime append/read access to immutable draft review events."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0015"
down_revision = "20261008_0014"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        role_exists = bind.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"),
            {"role": "gaps_staging_runtime"},
        ).scalar()
        if role_exists:
            op.execute("GRANT SELECT, INSERT ON TABLE draft_review_events TO gaps_staging_runtime")


def downgrade():
    raise RuntimeError("Preserve outreach review access history; use a forward migration")
