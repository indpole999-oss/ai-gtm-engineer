"""Add durable pipeline, CRM mappings and approved calendar/provider outcomes."""
from alembic import op
import sqlalchemy as sa
from uuid import UUID, uuid5
from datetime import datetime

revision = "20260926_0012"
down_revision = "20260926_0011"
branch_labels = depends_on = None

TABLES = ('pipeline_records', 'pipeline_history', 'crm_mappings', 'outcome_actions', 'calendar_bookings', 'crm_receipts')

def upgrade():
    op.create_table('pipeline_records',
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('record_key', sa.String(length=80), nullable=False),
        sa.Column('stage', sa.String(length=30), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False, primary_key=True),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('workspace_id','record_key'),
        sa.ForeignKeyConstraint(['workspace_id', 'company_id'], ['companies.workspace_id', 'companies.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.UniqueConstraint('workspace_id','id'),
        sa.ForeignKeyConstraint(['workspace_id', 'contact_id'], ['contacts.workspace_id', 'contacts.id']),
        sa.CheckConstraint("stage IN ('discovered','qualified','contacted','engaged','interested','meeting','opportunity','won','lost')"),
    )
    op.create_index('ix_pipeline_records_workspace_id','pipeline_records',['workspace_id'])
    op.create_table('pipeline_history',
        sa.Column('pipeline_id', sa.Uuid(), nullable=False),
        sa.Column('source_key', sa.String(length=255), nullable=False),
        sa.Column('from_stage', sa.String(length=30), nullable=True),
        sa.Column('to_stage', sa.String(length=30), nullable=False),
        sa.Column('applied', sa.Boolean(), nullable=False),
        sa.Column('source', sa.String(length=40), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('cycle_id', sa.Uuid(), nullable=True),
        sa.Column('campaign_id', sa.Uuid(), nullable=True),
        sa.Column('sequence_version_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, primary_key=True),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'cycle_id'], ['execution_cycles.workspace_id', 'execution_cycles.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.UniqueConstraint('workspace_id','id'),
        sa.ForeignKeyConstraint(['workspace_id', 'campaign_id'], ['campaigns.workspace_id', 'campaigns.id']),
        sa.UniqueConstraint('pipeline_id','source_key'),
        sa.ForeignKeyConstraint(['workspace_id', 'pipeline_id'], ['pipeline_records.workspace_id', 'pipeline_records.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'sequence_version_id'], ['sequence_versions.workspace_id', 'sequence_versions.id']),
    )
    op.create_index('ix_pipeline_history_time','pipeline_history',['workspace_id', 'pipeline_id', 'created_at'])
    op.create_index('ix_pipeline_history_workspace_id','pipeline_history',['workspace_id'])
    op.create_table('crm_mappings',
        sa.Column('integration_id', sa.Uuid(), nullable=False),
        sa.Column('pipeline_id', sa.Uuid(), nullable=False),
        sa.Column('object_type', sa.String(length=30), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('remote_version', sa.String(length=255), nullable=True),
        sa.Column('remote_snapshot', sa.JSON(), nullable=True),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('sync_state', sa.String(length=30), nullable=False),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(length=100), nullable=True),
        sa.Column('cursor', sa.String(length=500), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, primary_key=True),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id', 'pipeline_id'], ['pipeline_records.workspace_id', 'pipeline_records.id']),
        sa.UniqueConstraint('workspace_id','id'),
        sa.CheckConstraint("object_type IN ('company','contact','opportunity')"),
        sa.UniqueConstraint('integration_id','pipeline_id','object_type'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.UniqueConstraint('integration_id','object_type','external_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'integration_id'], ['integrations.workspace_id', 'integrations.id']),
    )
    op.create_index('ix_crm_mappings_workspace_id','crm_mappings',['workspace_id'])
    op.create_table('outcome_actions',
        sa.Column('integration_id', sa.Uuid(), nullable=False),
        sa.Column('pipeline_id', sa.Uuid(), nullable=False),
        sa.Column('mapping_id', sa.Uuid(), nullable=True),
        sa.Column('plan_id', sa.Uuid(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('request_key', sa.String(length=255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('state', sa.String(length=30), nullable=False),
        sa.Column('attempted_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('receipt', sa.JSON(), nullable=True),
        sa.Column('last_error', sa.String(length=100), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, primary_key=True),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id', 'mapping_id'], ['crm_mappings.workspace_id', 'crm_mappings.id']),
        sa.UniqueConstraint('workspace_id','request_key'),
        sa.ForeignKeyConstraint(['workspace_id', 'integration_id'], ['integrations.workspace_id', 'integrations.id']),
        sa.UniqueConstraint('plan_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'plan_id'], ['plan_versions.workspace_id', 'plan_versions.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'pipeline_id'], ['pipeline_records.workspace_id', 'pipeline_records.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.CheckConstraint("kind IN ('crm_sync','calendar_schedule')"),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.UniqueConstraint('workspace_id','id'),
    )
    op.create_index('ix_outcome_actions_workspace_id','outcome_actions',['workspace_id'])
    op.create_table('calendar_bookings',
        sa.Column('action_id', sa.Uuid(), nullable=False),
        sa.Column('integration_id', sa.Uuid(), nullable=False),
        sa.Column('pipeline_id', sa.Uuid(), nullable=False),
        sa.Column('inbound_message_id', sa.Uuid(), nullable=False),
        sa.Column('classification_id', sa.Uuid(), nullable=False),
        sa.Column('calendar_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('attendees', sa.JSON(), nullable=False),
        sa.Column('timezone', sa.String(length=100), nullable=False),
        sa.Column('start_at', sa.DateTime(), nullable=False),
        sa.Column('end_at', sa.DateTime(), nullable=False),
        sa.Column('duplicate_key', sa.String(length=64), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False, primary_key=True),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('action_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'integration_id'], ['integrations.workspace_id', 'integrations.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'classification_id'], ['reply_classifications.workspace_id', 'reply_classifications.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'action_id'], ['outcome_actions.workspace_id', 'outcome_actions.id']),
        sa.UniqueConstraint('workspace_id','id'),
        sa.ForeignKeyConstraint(['workspace_id', 'pipeline_id'], ['pipeline_records.workspace_id', 'pipeline_records.id']),
        sa.CheckConstraint('end_at > start_at'),
        sa.UniqueConstraint('workspace_id','duplicate_key'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'inbound_message_id'], ['inbound_messages.workspace_id', 'inbound_messages.id']),
    )
    op.create_index('ix_calendar_bookings_workspace_id','calendar_bookings',['workspace_id'])
    op.create_index('ix_calendar_time','calendar_bookings',['workspace_id', 'start_at', 'end_at'])
    op.create_table('crm_receipts',
        sa.Column('integration_id', sa.Uuid(), nullable=False),
        sa.Column('mapping_id', sa.Uuid(), nullable=False),
        sa.Column('provider_event_id', sa.String(length=255), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False, primary_key=True),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.UniqueConstraint('workspace_id','id'),
        sa.UniqueConstraint('integration_id','provider_event_id'),
        sa.ForeignKeyConstraint(['workspace_id', 'integration_id'], ['integrations.workspace_id', 'integrations.id']),
        sa.ForeignKeyConstraint(['workspace_id', 'mapping_id'], ['crm_mappings.workspace_id', 'crm_mappings.id']),
    )
    op.create_index('ix_crm_receipts_workspace_id','crm_receipts',['workspace_id'])
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
        op.execute("CREATE TRIGGER immutable_pipeline_history BEFORE UPDATE OR DELETE ON pipeline_history FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
        op.execute("CREATE TRIGGER immutable_calendar_bookings BEFORE UPDATE OR DELETE ON calendar_bookings FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
        op.execute("CREATE TRIGGER immutable_crm_receipts BEFORE UPDATE OR DELETE ON crm_receipts FOR EACH ROW EXECUTE FUNCTION protect_research_snapshot()")
        op.execute("CREATE FUNCTION protect_pipeline_records() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Outcome history is immutable'; END IF; IF OLD.company_id IS DISTINCT FROM NEW.company_id OR OLD.contact_id IS DISTINCT FROM NEW.contact_id OR OLD.record_key IS DISTINCT FROM NEW.record_key THEN RAISE EXCEPTION 'Outcome identity is immutable'; END IF; RETURN NEW; END $$")
        op.execute("CREATE TRIGGER immutable_pipeline_records BEFORE UPDATE OR DELETE ON pipeline_records FOR EACH ROW EXECUTE FUNCTION protect_pipeline_records()")
        op.execute("CREATE FUNCTION protect_crm_mappings() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Outcome history is immutable'; END IF; IF OLD.integration_id IS DISTINCT FROM NEW.integration_id OR OLD.pipeline_id IS DISTINCT FROM NEW.pipeline_id OR OLD.object_type IS DISTINCT FROM NEW.object_type OR OLD.provider IS DISTINCT FROM NEW.provider OR (OLD.external_id IS NOT NULL AND OLD.external_id IS DISTINCT FROM NEW.external_id) THEN RAISE EXCEPTION 'Outcome identity is immutable'; END IF; RETURN NEW; END $$")
        op.execute("CREATE TRIGGER immutable_crm_mappings BEFORE UPDATE OR DELETE ON crm_mappings FOR EACH ROW EXECUTE FUNCTION protect_crm_mappings()")
        op.execute("CREATE FUNCTION protect_outcome_actions() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Outcome history is immutable'; END IF; IF OLD.integration_id IS DISTINCT FROM NEW.integration_id OR OLD.pipeline_id IS DISTINCT FROM NEW.pipeline_id OR OLD.mapping_id IS DISTINCT FROM NEW.mapping_id OR OLD.plan_id IS DISTINCT FROM NEW.plan_id OR OLD.kind IS DISTINCT FROM NEW.kind OR OLD.request_key IS DISTINCT FROM NEW.request_key OR OLD.payload::jsonb IS DISTINCT FROM NEW.payload::jsonb OR OLD.content_hash IS DISTINCT FROM NEW.content_hash OR OLD.created_by IS DISTINCT FROM NEW.created_by OR OLD.state = 'confirmed' THEN RAISE EXCEPTION 'Outcome identity is immutable'; END IF; RETURN NEW; END $$")
        op.execute("CREATE TRIGGER immutable_outcome_actions BEFORE UPDATE OR DELETE ON outcome_actions FOR EACH ROW EXECUTE FUNCTION protect_outcome_actions()")
    elif db.dialect.name == "sqlite":
        op.execute("CREATE TRIGGER immutable_pipeline_history_UPDATE BEFORE UPDATE ON pipeline_history BEGIN SELECT RAISE(ABORT,'Outcome evidence is immutable'); END")
        op.execute("CREATE TRIGGER immutable_pipeline_history_DELETE BEFORE DELETE ON pipeline_history BEGIN SELECT RAISE(ABORT,'Outcome evidence is immutable'); END")
        op.execute("CREATE TRIGGER immutable_calendar_bookings_UPDATE BEFORE UPDATE ON calendar_bookings BEGIN SELECT RAISE(ABORT,'Outcome evidence is immutable'); END")
        op.execute("CREATE TRIGGER immutable_calendar_bookings_DELETE BEFORE DELETE ON calendar_bookings BEGIN SELECT RAISE(ABORT,'Outcome evidence is immutable'); END")
        op.execute("CREATE TRIGGER immutable_crm_receipts_UPDATE BEFORE UPDATE ON crm_receipts BEGIN SELECT RAISE(ABORT,'Outcome evidence is immutable'); END")
        op.execute("CREATE TRIGGER immutable_crm_receipts_DELETE BEFORE DELETE ON crm_receipts BEGIN SELECT RAISE(ABORT,'Outcome evidence is immutable'); END")
        op.execute("CREATE TRIGGER immutable_pipeline_records_UPDATE BEFORE UPDATE ON pipeline_records WHEN OLD.company_id IS NOT NEW.company_id OR OLD.contact_id IS NOT NEW.contact_id OR OLD.record_key IS NOT NEW.record_key BEGIN SELECT RAISE(ABORT,'Outcome identity is immutable'); END")
        op.execute("CREATE TRIGGER immutable_pipeline_records_DELETE BEFORE DELETE ON pipeline_records BEGIN SELECT RAISE(ABORT,'Outcome history is immutable'); END")
        op.execute("CREATE TRIGGER immutable_crm_mappings_UPDATE BEFORE UPDATE ON crm_mappings WHEN OLD.integration_id IS NOT NEW.integration_id OR OLD.pipeline_id IS NOT NEW.pipeline_id OR OLD.object_type IS NOT NEW.object_type OR OLD.provider IS NOT NEW.provider OR (OLD.external_id IS NOT NULL AND OLD.external_id IS NOT NEW.external_id) BEGIN SELECT RAISE(ABORT,'Outcome identity is immutable'); END")
        op.execute("CREATE TRIGGER immutable_crm_mappings_DELETE BEFORE DELETE ON crm_mappings BEGIN SELECT RAISE(ABORT,'Outcome history is immutable'); END")
        op.execute("CREATE TRIGGER immutable_outcome_actions_UPDATE BEFORE UPDATE ON outcome_actions WHEN OLD.integration_id IS NOT NEW.integration_id OR OLD.pipeline_id IS NOT NEW.pipeline_id OR OLD.mapping_id IS NOT NEW.mapping_id OR OLD.plan_id IS NOT NEW.plan_id OR OLD.kind IS NOT NEW.kind OR OLD.request_key IS NOT NEW.request_key OR OLD.payload IS NOT NEW.payload OR OLD.content_hash IS NOT NEW.content_hash OR OLD.created_by IS NOT NEW.created_by OR OLD.state = 'confirmed' BEGIN SELECT RAISE(ABORT,'Outcome identity is immutable'); END")
        op.execute("CREATE TRIGGER immutable_outcome_actions_DELETE BEFORE DELETE ON outcome_actions BEGIN SELECT RAISE(ABORT,'Outcome history is immutable'); END")
    # Only unambiguous, already-owned records receive discovered history.
    # Legacy NULL ownership remains quarantined; no prior business outcome inferred.
    records = sa.table("pipeline_records", sa.column("id", sa.Uuid()), sa.column("workspace_id", sa.Uuid()),
        sa.column("company_id", sa.Uuid()), sa.column("contact_id", sa.Uuid()), sa.column("record_key", sa.String()),
        sa.column("stage", sa.String()), sa.column("revision", sa.Integer()), sa.column("created_at", sa.DateTime()))
    history = sa.table("pipeline_history", sa.column("id", sa.Uuid()), sa.column("workspace_id", sa.Uuid()),
        sa.column("pipeline_id", sa.Uuid()), sa.column("source_key", sa.String()), sa.column("from_stage", sa.String()),
        sa.column("to_stage", sa.String()), sa.column("applied", sa.Boolean()), sa.column("source", sa.String()),
        sa.column("reason", sa.Text()), sa.column("evidence", sa.JSON()), sa.column("created_at", sa.DateTime()))
    workspaces = sa.table("workspaces", sa.column("id", sa.Uuid()))
    accounts = sa.table("companies", sa.column("id", sa.Uuid()), sa.column("workspace_id", sa.Uuid()))
    people = sa.table("contacts", sa.column("id", sa.Uuid()), sa.column("workspace_id", sa.Uuid()), sa.column("company_id", sa.Uuid()))
    # Explicit tenant context also supports a migration owner without BYPASSRLS.
    for wid in db.scalars(sa.select(workspaces.c.id)).all():
        if db.dialect.name == "postgresql":
            db.execute(sa.text("SELECT set_config('app.workspace_id', :wid, true)"), {"wid":str(wid)})
        companies = db.execute(sa.select(accounts.c.id).where(accounts.c.workspace_id == wid)).all()
        contacts = db.execute(sa.select(people.c.id, people.c.company_id).select_from(people.join(accounts,
            sa.and_(people.c.company_id == accounts.c.id, people.c.workspace_id == accounts.c.workspace_id))).where(people.c.workspace_id == wid)).all()
        for item, company, contact in [(i,i,None) for (i,) in companies] + [(i,a,i) for i,a in contacts]:
            key = ("contact:" if contact else "company:") + str(item)
            rid = uuid5(wid, key)
            op.bulk_insert(records, [dict(id=rid,workspace_id=wid,company_id=company,contact_id=contact,record_key=key,stage="discovered",revision=1,created_at=datetime.utcnow())])
            op.bulk_insert(history, [dict(id=uuid5(rid,"discovered"),workspace_id=wid,pipeline_id=rid,source_key="discovered",from_stage=None,to_stage="discovered",applied=True,source="migration",reason="Existing owned account/prospect; no business outcome inferred",evidence={"record":key},created_at=datetime.utcnow())])
    if db.dialect.name == "postgresql":
        db.execute(sa.text("SELECT set_config('app.workspace_id', '', true)"))



def downgrade():
    raise RuntimeError("Preserve outcome history and provider identities. Restore a verified backup.")
