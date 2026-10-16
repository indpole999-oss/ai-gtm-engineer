-- PROPOSAL ONLY: execute only after explicit staging permission-change approval.
-- Operator must independently verify staging project/host before connecting.
-- psql --set ON_ERROR_STOP=on --file ... ; use private credentials, never shell URL.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10s';
DO $$
BEGIN
  IF current_user <> 'gaps_staging_migrator' OR
     (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.alembic_version'::regclass)
        <> 'gaps_staging_migrator' OR
     (SELECT count(*) FROM public.alembic_version) <> 1 OR
     NOT EXISTS (SELECT 1 FROM public.alembic_version WHERE version_num IN ('20261009_0015','20261011_0016')) OR
     pg_has_role('gaps_staging_runtime','gaps_staging_migrator','MEMBER')
  THEN RAISE EXCEPTION 'Staging migration identity/revision precondition failed'; END IF;
END $$;
REVOKE ALL PRIVILEGES ON TABLE public.alembic_version FROM gaps_staging_runtime;
GRANT SELECT ON TABLE public.alembic_version TO gaps_staging_runtime;
DO $$
BEGIN
  IF NOT has_table_privilege('gaps_staging_runtime','public.alembic_version','SELECT') OR
     EXISTS (SELECT 1 FROM unnest(ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p
             WHERE has_table_privilege('gaps_staging_runtime','public.alembic_version',p))
  THEN RAISE EXCEPTION 'Inherited/PUBLIC privileges remain; transaction refused'; END IF;
END $$;
COMMIT;
