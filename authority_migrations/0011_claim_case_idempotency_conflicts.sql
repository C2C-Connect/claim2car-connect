-- Return domain conflicts as a controlled result so the API can report
-- an idempotency conflict without leaking PostgreSQL exception details.
CREATE OR REPLACE FUNCTION faos.create_claim_case(p_tenant uuid,p_claim uuid,p_request uuid,p_actor text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE existing faos.claim_cases%ROWTYPE;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_claim IS NULL OR p_request IS NULL OR p_actor IS NULL
 OR length(trim(p_actor)) NOT BETWEEN 1 AND 128 THEN
  RAISE EXCEPTION 'INVALID_CLAIM_CASE';
 END IF;
 INSERT INTO faos.claim_cases(tenant_id,claim_id,request_id,created_by)
 VALUES(p_tenant,p_claim,p_request,p_actor)
 ON CONFLICT(tenant_id,request_id) DO NOTHING
 RETURNING * INTO existing;
 IF FOUND THEN RETURN 'ACCEPTED'; END IF;
 SELECT * INTO existing FROM faos.claim_cases
  WHERE tenant_id=p_tenant AND request_id=p_request FOR UPDATE;
 IF NOT FOUND THEN RETURN 'CONFLICT'; END IF;
 IF ROW(existing.claim_id,existing.created_by)
    IS DISTINCT FROM ROW(p_claim,p_actor) THEN
  RETURN 'CONFLICT';
 END IF;
 RETURN 'DUPLICATE';
EXCEPTION WHEN unique_violation THEN
 RETURN 'CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.create_claim_case(uuid,uuid,uuid,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
