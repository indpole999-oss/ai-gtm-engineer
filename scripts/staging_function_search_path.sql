-- PREPARED ONLY. Separate database-change approval required; after 0016 only.
-- Verify staging target independently; use reviewed function-owning migration identity.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='10s';
DO $$
DECLARE function_name text;
BEGIN
  IF (SELECT count(*) FROM public.alembic_version) <> 1 OR
     NOT EXISTS (SELECT 1 FROM public.alembic_version WHERE version_num='20261011_0016')
  THEN RAISE EXCEPTION 'Requires verified 0016 schema'; END IF;
  FOREACH function_name IN ARRAY ARRAY[
    'protect_brain_version','protect_brain_content','protect_research_snapshot',
    'protect_approved_plan','protect_message_approval','protect_enrollment_references',
    'protect_pipeline_records','protect_crm_mappings','protect_outcome_actions','protect_cancelled_message']
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc p
      WHERE p.oid=pg_catalog.to_regprocedure('public.'||function_name||'()')
      AND p.prorettype='pg_catalog.trigger'::pg_catalog.regtype AND NOT p.prosecdef)
    THEN RAISE EXCEPTION 'Required invoker trigger function missing'; END IF;
  END LOOP;
END $$;
-- Only this function contains relation lookups; qualify both explicitly.
CREATE OR REPLACE FUNCTION public.protect_brain_content() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
  IF TG_OP <> 'INSERT' AND EXISTS (SELECT 1 FROM public.company_brain_versions WHERE id=OLD.version_id AND status='published') THEN
    RAISE EXCEPTION 'Published brain content is immutable';
  END IF;
  IF TG_OP <> 'DELETE' AND EXISTS (SELECT 1 FROM public.company_brain_versions WHERE id=NEW.version_id AND status='published') THEN
    RAISE EXCEPTION 'Published brain content is immutable';
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;
ALTER FUNCTION public.protect_brain_version() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_research_snapshot() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_approved_plan() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_message_approval() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_enrollment_references() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_pipeline_records() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_crm_mappings() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_outcome_actions() SET search_path=pg_catalog;
ALTER FUNCTION public.protect_cancelled_message() SET search_path=pg_catalog;
COMMIT;
