"""Add ephemeral shared authentication admission counters; no customer mutations."""
from alembic import op
import sqlalchemy as sa

revision = "20260928_0013"
down_revision = "20260926_0012"
branch_labels = depends_on = None


def upgrade():
    op.create_table("auth_admission_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window", sa.BigInteger(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False))
    op.create_index("ix_auth_admission_window", "auth_admission_buckets", ["window"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("REVOKE ALL ON auth_admission_buckets FROM PUBLIC")


def downgrade():
    raise RuntimeError("Forward-only migration; preserve admission state")
