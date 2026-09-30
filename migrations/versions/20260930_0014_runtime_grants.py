"""Grant staging runtime role access to migrator-owned application objects."""

from alembic import op

revision = "20260930_0014"
down_revision = "20260928_0013"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("GRANT USAGE ON SCHEMA public TO gaps_staging_runtime")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON ALL TABLES IN SCHEMA public TO gaps_staging_runtime"
    )
    op.execute(
        "GRANT USAGE, SELECT, UPDATE "
        "ON ALL SEQUENCES IN SCHEMA public TO gaps_staging_runtime"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gaps_staging_runtime"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO gaps_staging_runtime"
    )


def downgrade():
    raise RuntimeError("Forward-only migration; preserve runtime grants")
