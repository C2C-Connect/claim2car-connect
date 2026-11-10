-- Link every new persistent claim case to a separately scoped capture
-- session. The owner binding is set only by the consent function path.
ALTER TABLE faos.claim_cases ADD COLUMN capture_session_id text;
ALTER TABLE faos.claim_cases ADD COLUMN owner_actor_id text;
ALTER TABLE faos.claim_cases
 ADD CONSTRAINT claim_cases_capture_session_fk
 FOREIGN KEY(tenant_id,capture_session_id)
 REFERENCES faos.sessions(tenant_id,session_id);
CREATE UNIQUE INDEX claim_cases_capture_session_uq
 ON faos.claim_cases(tenant_id,capture_session_id)
 WHERE capture_session_id IS NOT NULL;
GRANT UPDATE(owner_actor_id) ON faos.claim_cases TO faos_writer;

DROP FUNCTION faos.create_claim_case(uuid,uuid,uuid,text);
CREATE FUNCTION faos.create_claim_case(
 p_tenant uuid,p_claim uuid,p_request uuid,p_actor text,p_session text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE
 existing faos.claim_cases%ROWTYPE;
 created_session text;
 append_result text;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_claim IS NULL OR p_request IS NULL OR p_session IS NULL OR p_actor IS NULL
 OR length(trim(p_actor)) NOT BETWEEN 1 AND 128 THEN
  RAISE EXCEPTION 'INVALID_CLAIM_CASE';
 END IF;
 SELECT * INTO existing FROM faos.claim_cases
  WHERE tenant_id=p_tenant AND request_id=p_request;
 IF FOUND THEN
  IF existing.claim_id=p_claim AND existing.created_by=p_actor
     AND existing.capture_session_id IS NOT NULL THEN
   RETURN 'DUPLICATE';
  END IF;
  RETURN 'CONFLICT';
 END IF;
 INSERT INTO faos.sessions(tenant_id,session_id)
 VALUES(p_tenant,p_session)
 ON CONFLICT DO NOTHING
 RETURNING session_id INTO created_session;
 IF NOT FOUND THEN RETURN 'CONFLICT'; END IF;
 INSERT INTO faos.claim_cases(
  tenant_id,claim_id,request_id,created_by,capture_session_id
 ) VALUES(p_tenant,p_claim,p_request,p_actor,p_session);
 SELECT faos.append_event(
  p_tenant,p_session,'claim-created',1,'SESSION_CREATED',p_actor,
  to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
  'persistent claim capture session created',
  '{"claim_id":"' || p_claim::text || '","synthetic":false}','0.1'
 ) INTO append_result;
 IF append_result IS DISTINCT FROM 'ACCEPTED' THEN
  RAISE EXCEPTION 'CLAIM_CAPTURE_SESSION_CREATION_FAILED';
 END IF;
 RETURN 'ACCEPTED';
EXCEPTION WHEN unique_violation THEN
 SELECT * INTO existing FROM faos.claim_cases
  WHERE tenant_id=p_tenant AND request_id=p_request;
 IF FOUND AND existing.claim_id=p_claim AND existing.created_by=p_actor
    AND existing.capture_session_id IS NOT NULL THEN
  RETURN 'DUPLICATE';
 END IF;
 RETURN 'CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.create_claim_case(uuid,uuid,uuid,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;

CREATE FUNCTION faos.bind_claim_case_owner(p_tenant uuid,p_session text,p_owner text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE current_owner text;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_session IS NULL OR p_owner IS NULL OR length(trim(p_owner)) NOT BETWEEN 1 AND 128 THEN
  RAISE EXCEPTION 'INVALID_CLAIM_CASE_OWNER';
 END IF;
 UPDATE faos.claim_cases SET owner_actor_id=p_owner
  WHERE tenant_id=p_tenant AND capture_session_id=p_session
    AND (owner_actor_id IS NULL OR owner_actor_id=p_owner)
  RETURNING owner_actor_id INTO current_owner;
 IF FOUND THEN RETURN 'BOUND'; END IF;
 SELECT owner_actor_id INTO current_owner FROM faos.claim_cases
  WHERE tenant_id=p_tenant AND capture_session_id=p_session;
 IF NOT FOUND THEN RETURN 'NOT_CLAIM_CASE'; END IF;
 IF current_owner=p_owner THEN RETURN 'BOUND'; END IF;
 RETURN 'CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.bind_claim_case_owner(uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.bind_claim_case_owner(uuid,text,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.bind_claim_case_owner(uuid,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
