-- Extend protected manifest roots to both immutable capture protocol versions.
-- The registered root must match the protocol bound to its session, not merely
-- the version claimed by the seal event.
ALTER TABLE faos.manifest_roots
  DROP CONSTRAINT manifest_roots_shot_list_version_check;
ALTER TABLE faos.manifest_roots
  ADD CONSTRAINT manifest_roots_shot_list_version_check
  CHECK (shot_list_version IN ('claims2car-12-v1','claims2car-16-v1'));

CREATE FUNCTION faos.enforce_manifest_root_session_protocol()
RETURNS trigger
LANGUAGE plpgsql
SET search_path=pg_catalog,faos,pg_temp
AS $function$
DECLARE
  session_version text;
BEGIN
  SELECT capture_protocol_version INTO session_version
  FROM faos.sessions
  WHERE tenant_id=NEW.tenant_id AND session_id=NEW.session_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'SESSION_NOT_FOUND';
  END IF;
  IF NEW.shot_list_version IS DISTINCT FROM session_version THEN
    RAISE EXCEPTION 'ROOT_PROTOCOL_SESSION_MISMATCH';
  END IF;
  RETURN NEW;
END
$function$;
REVOKE ALL ON FUNCTION faos.enforce_manifest_root_session_protocol() FROM PUBLIC;
CREATE TRIGGER manifest_root_session_protocol_binding
  BEFORE INSERT OR UPDATE OF shot_list_version,tenant_id,session_id
  ON faos.manifest_roots
  FOR EACH ROW EXECUTE FUNCTION faos.enforce_manifest_root_session_protocol();

CREATE OR REPLACE FUNCTION faos.register_manifest_root(
  p_tenant uuid,p_session text,p_seal text,p_digest text,p_version text
) RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $function$
DECLARE
  session_version text;
  seal_kind text;
  seal_payload jsonb;
  old faos.manifest_roots%ROWTYPE;
BEGIN
  IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
    RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
  END IF;
  PERFORM faos.lock_session_for_completion(p_tenant,p_session);
  SELECT capture_protocol_version INTO session_version
  FROM faos.sessions WHERE tenant_id=p_tenant AND session_id=p_session;
  IF NOT FOUND THEN RAISE EXCEPTION 'SESSION_NOT_FOUND'; END IF;
  IF session_version IS DISTINCT FROM p_version THEN
    RAISE EXCEPTION 'ROOT_PROTOCOL_SESSION_MISMATCH';
  END IF;
  SELECT kind,payload_json::jsonb INTO seal_kind,seal_payload
  FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session AND event_id=p_seal;
  IF NOT FOUND THEN RAISE EXCEPTION 'SEAL_EVENT_NOT_FOUND'; END IF;
  IF seal_kind IS DISTINCT FROM 'MANIFEST_SEALED' THEN
    RAISE EXCEPTION 'INVALID_SEAL_EVENT';
  END IF;
  IF seal_payload->>'schema_version' IS DISTINCT FROM '0.1'
     OR seal_payload->>'manifest_digest' IS DISTINCT FROM p_digest
     OR seal_payload->>'shot_list_version' IS DISTINCT FROM p_version THEN
    RAISE EXCEPTION 'ROOT_SEAL_MISMATCH';
  END IF;
  SELECT * INTO old FROM faos.manifest_roots
  WHERE tenant_id=p_tenant AND session_id=p_session AND seal_event_id=p_seal;
  IF FOUND THEN
    IF ROW(old.manifest_digest,old.shot_list_version)
       IS DISTINCT FROM ROW(p_digest,p_version) THEN
      RAISE EXCEPTION 'ROOT_CONFLICT';
    END IF;
    RETURN 'DUPLICATE';
  END IF;
  INSERT INTO faos.manifest_roots(tenant_id,session_id,seal_event_id,manifest_digest,shot_list_version)
  VALUES(p_tenant,p_session,p_seal,p_digest,p_version);
  RETURN 'REGISTERED';
END
$function$;
