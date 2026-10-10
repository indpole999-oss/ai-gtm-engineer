"""Versioned Company Brain with database-enforced published immutability."""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0006"
down_revision = "20260922_0005"
branch_labels = depends_on = None


def identity():
    return [sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False)]


def version_fk():
    return sa.ForeignKeyConstraint(["workspace_id", "version_id"], ["company_brain_versions.workspace_id", "company_brain_versions.id"])


def upgrade():
    op.create_table("company_brains", *identity(),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id"), sa.UniqueConstraint("workspace_id", "id"))
    op.create_table("company_brain_versions", *identity(),
        sa.Column("brain_id", sa.Uuid(), nullable=False), sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("content_hash", sa.String(64)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("published_at", sa.DateTime()),
        sa.UniqueConstraint("workspace_id", "id"), sa.UniqueConstraint("brain_id", "number"),
        sa.CheckConstraint("status IN ('draft','published')"),
        sa.ForeignKeyConstraint(["workspace_id", "brain_id"], ["company_brains.workspace_id", "company_brains.id"]))
    op.create_table("company_brain_sources", *identity(),
        sa.Column("version_id", sa.Uuid(), nullable=False), sa.Column("key", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False), sa.Column("title", sa.String(300), nullable=False),
        sa.Column("url", sa.Text()), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "id"), sa.UniqueConstraint("version_id", "key"), version_fk())
    op.create_table("brain_claims", *identity(),
        sa.Column("version_id", sa.Uuid(), nullable=False), sa.Column("text", sa.Text(), nullable=False),
        sa.Column("disposition", sa.String(20), nullable=False), sa.Column("source_key", sa.String(80)),
        sa.CheckConstraint("disposition IN ('approved','prohibited')"), version_fk(),
        sa.ForeignKeyConstraint(["version_id", "source_key"], ["company_brain_sources.version_id", "company_brain_sources.key"]))
    tables = ("company_brains", "company_brain_versions", "company_brain_sources", "brain_claims")
    for table in tables[1:]:
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])
    db = op.get_bind()
    if db.dialect.name == "postgresql":
        for table in tables:
            op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                if db.scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                    op.execute(f"REVOKE ALL ON TABLE {table} FROM {role}")
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            predicate = "workspace_id = nullif(current_setting('app.workspace_id',true),'')::uuid"
            op.execute(f"CREATE POLICY workspace_isolation ON {table} USING ({predicate}) WITH CHECK ({predicate})")
        op.execute("""CREATE FUNCTION protect_brain_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.status = 'published' THEN RAISE EXCEPTION 'Published brain is immutable'; END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $$""")
        op.execute("CREATE TRIGGER immutable_brain_version BEFORE UPDATE OR DELETE ON company_brain_versions FOR EACH ROW EXECUTE FUNCTION protect_brain_version()")
        op.execute("""CREATE FUNCTION protect_brain_content() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'INSERT' AND EXISTS (SELECT 1 FROM company_brain_versions WHERE id=OLD.version_id AND status='published') THEN
            RAISE EXCEPTION 'Published brain content is immutable';
          END IF;
          IF TG_OP <> 'DELETE' AND EXISTS (SELECT 1 FROM company_brain_versions WHERE id=NEW.version_id AND status='published') THEN
            RAISE EXCEPTION 'Published brain content is immutable';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $$""")
        for table in tables[2:]:
            op.execute(f"CREATE TRIGGER immutable_brain_content BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION protect_brain_content()")
    elif db.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER immutable_brain_version_{action} BEFORE {action} ON company_brain_versions WHEN OLD.status='published' BEGIN SELECT RAISE(ABORT,'Published brain is immutable'); END")
        for table in tables[2:]:
            for action in ("INSERT", "UPDATE", "DELETE"):
                refs = ["NEW"] if action == "INSERT" else ["OLD"] if action == "DELETE" else ["OLD", "NEW"]
                condition = " OR ".join(f"EXISTS (SELECT 1 FROM company_brain_versions WHERE id={ref}.version_id AND status='published')" for ref in refs)
                op.execute(f"CREATE TRIGGER immutable_{table}_{action} BEFORE {action} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT,'Published brain content is immutable'); END")


def downgrade():
    raise RuntimeError("Published knowledge and its provenance must be preserved. Restore a verified backup.")
