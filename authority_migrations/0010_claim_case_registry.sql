-- First persistent claim-case identity register. Case identity is immutable;
-- incident/owner data and evidence associations are added only through their
-- separately validated intake contracts.
CREATE TABLE faos.claim_cases(
 tenant_id uuid NOT NULL REFERENCES faos.organizations(tenant_id),
 claim_id uuid NOT NULL,
 request_id uuid NOT NULL,
 created_by text NOT NULL CHECK(length(trim(created_by)) BETWEEN 1 AND 128),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 state text NOT NULL DEFAULT 'INTAKE_OPEN' CHECK(state='INTAKE_OPEN'),
 PRIMARY KEY(tenant_id,claim_id),
 UNIQUE(tenant_id,request_id)
);
ALTER TABLE faos.claim_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.claim_cases FORCE ROW LEVEL SECURITY;
CREATE POLICY app_claim_cases ON faos.claim_cases TO faos_app
 USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_claim_cases ON faos.claim_cases TO faos_writer
 USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.claim_cases FROM PUBLIC,faos_app;
GRANT SELECT ON faos.claim_cases TO faos_app;
GRANT SELECT,INSERT ON faos.claim_cases TO faos_writer;

CREATE FUNCTION faos.create_claim_case(p_tenant uuid,p_claim uuid,p_request uuid,p_actor text)
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
 IF NOT FOUND THEN RAISE EXCEPTION 'CLAIM_CASE_ID_CONFLICT'; END IF;
 IF ROW(existing.claim_id,existing.created_by)
    IS DISTINCT FROM ROW(p_claim,p_actor) THEN
  RAISE EXCEPTION 'CLAIM_CASE_IDEMPOTENCY_CONFLICT';
 END IF;
 RETURN 'DUPLICATE';
EXCEPTION WHEN unique_violation THEN
 RAISE EXCEPTION 'CLAIM_CASE_ID_CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.create_claim_case(uuid,uuid,uuid,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
