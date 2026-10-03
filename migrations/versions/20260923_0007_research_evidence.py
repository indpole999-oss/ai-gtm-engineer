"""Add workspace research jobs, immutable source captures and account intelligence."""
from alembic import op
import sqlalchemy as sa
revision = "20260923_0007"
down_revision = "20260922_0006"
branch_labels = depends_on = None


def identity():
    return [sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False)]


def parent(column, table):
    return sa.ForeignKeyConstraint(["workspace_id", column], [table + ".workspace_id", table + ".id"])


def upgrade():
    op.create_table("research_jobs", *identity(),
        sa.Column("company_id", sa.Uuid(), nullable=False), sa.Column("brain_version_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("source_urls", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(80)), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("completed_at", sa.DateTime()),
        sa.UniqueConstraint("workspace_id", "id"), parent("company_id", "companies"), parent("brain_version_id", "company_brain_versions"))
    op.create_table("source_fetches", *identity(),
        sa.Column("job_id", sa.Uuid(), nullable=False), sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False), sa.Column("publisher", sa.String(255), nullable=False),
        sa.Column("published_at", sa.DateTime()), sa.Column("retrieved_at", sa.DateTime(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extractor_version", sa.String(80), nullable=False),
        sa.UniqueConstraint("workspace_id", "id"), parent("job_id", "research_jobs"))
    op.create_table("evidence_items", *identity(),
        sa.Column("fetch_id", sa.Uuid(), nullable=False), sa.Column("excerpt", sa.Text(), nullable=False),
        sa.UniqueConstraint("workspace_id", "id"), parent("fetch_id", "source_fetches"))
    op.create_table("research_claims", *identity(),
        sa.Column("job_id", sa.Uuid(), nullable=False), sa.Column("evidence_id", sa.Uuid()),
        sa.Column("text", sa.Text(), nullable=False), sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False), sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("verified_by", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("verified_at", sa.DateTime()),
        sa.UniqueConstraint("workspace_id", "id"), parent("job_id", "research_jobs"), parent("evidence_id", "evidence_items"))
    op.create_table("account_intelligence_reports", *identity(),
        sa.Column("job_id", sa.Uuid(), nullable=False, unique=True), sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), parent("job_id", "research_jobs"))
    db = op.get_bind()
    op.create_table("claim_verifications", *identity(),
        sa.Column("claim_id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), parent("claim_id", "research_claims"))
    tables = ("research_jobs", "source_fetches", "evidence_items", "research_claims", "account_intelligence_reports", "claim_verifications")
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
    if db.dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION protect_research_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Research evidence is immutable'; END $$""")
    for table in tables[1:]:
        if db.dialect.name == "postgresql":
            op.execute(f"CREATE TRIGGER immutable_research BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
        elif db.dialect.name == "sqlite":
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER immutable_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Research evidence is immutable'); END")


def downgrade():
    raise RuntimeError("Preserve evidence and provenance. Restore a verified backup.")
