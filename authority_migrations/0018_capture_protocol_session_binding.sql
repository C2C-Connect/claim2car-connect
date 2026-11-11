-- Bind every capture session to an immutable, explicitly versioned protocol.
-- Existing sessions are historical 12-v1 and remain so; only new sessions
-- receive the approved 16-v1 default. The 16-v1 slot contract remains pending.
ALTER TABLE faos.sessions
 ADD COLUMN capture_protocol_version text NOT NULL DEFAULT 'claims2car-12-v1';
ALTER TABLE faos.sessions
 ADD CONSTRAINT sessions_capture_protocol_version_check
 CHECK (capture_protocol_version IN ('claims2car-12-v1','claims2car-16-v1'));
ALTER TABLE faos.sessions
 ALTER COLUMN capture_protocol_version SET DEFAULT 'claims2car-16-v1';

-- Replace the claim-case constructor so callers explicitly choose one of the
-- two governed protocol identifiers. Existing rows are not rewritten.
DROP FUNCTION faos.create_claim_case(uuid,uuid,uuid,text,text);
CREATE FUNCTION faos.create_claim_case(
 p_tenant uuid,p_claim uuid,p_request uuid,p_actor text,p_session text,
 p_protocol_version text
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
 OR length(trim(p_actor)) NOT BETWEEN 1 AND 128
 OR p_protocol_version NOT IN ('claims2car-12-v1','claims2car-16-v1') THEN
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
 INSERT INTO faos.sessions(tenant_id,session_id,capture_protocol_version)
 VALUES(p_tenant,p_session,p_protocol_version)
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
  '{"capture_protocol_version":"' || p_protocol_version || '","claim_id":"' || p_claim::text || '","synthetic":false}','0.1'
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
REVOKE ALL ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.create_claim_case(uuid,uuid,uuid,text,text,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.create_claim_case(uuid,uuid,uuid,text,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;

-- Protocol identity is immutable once a session exists.
CREATE FUNCTION faos.reject_capture_protocol_version_change()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,faos,pg_temp
AS $$
BEGIN
 IF NEW.capture_protocol_version IS DISTINCT FROM OLD.capture_protocol_version THEN
  RAISE EXCEPTION 'CAPTURE_PROTOCOL_VERSION_IMMUTABLE';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION faos.reject_capture_protocol_version_change() FROM PUBLIC;
CREATE TRIGGER sessions_capture_protocol_version_immutable
 BEFORE UPDATE OF capture_protocol_version ON faos.sessions
 FOR EACH ROW EXECUTE FUNCTION faos.reject_capture_protocol_version_change();
