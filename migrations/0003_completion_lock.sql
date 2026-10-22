-- Transaction-scoped serialization primitive for a future completion operation.
-- It does not evaluate evidence or persist completion. Call within a transaction.
CREATE FUNCTION faos.lock_session_for_completion(p_tenant uuid, p_session text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$ BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 PERFORM 1 FROM faos.sessions
 WHERE tenant_id=p_tenant AND session_id=p_session FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'SESSION_NOT_FOUND'; END IF;
END $$;
REVOKE ALL ON FUNCTION faos.lock_session_for_completion(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.lock_session_for_completion(uuid,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.lock_session_for_completion(uuid,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
