-- Protected synthetic root registry. No authenticated production sealing service.
CREATE TABLE faos.manifest_roots(
 tenant_id uuid NOT NULL, session_id text NOT NULL, seal_event_id text NOT NULL,
 manifest_digest text NOT NULL CHECK(manifest_digest ~ '^[0-9a-f]{64}$'),
 shot_list_version text NOT NULL CHECK(shot_list_version='claims2car-12-v1'),
 registered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,session_id,seal_event_id),
 FOREIGN KEY(tenant_id,session_id,seal_event_id) REFERENCES faos.events(tenant_id,session_id,event_id));
ALTER TABLE faos.manifest_roots ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.manifest_roots FORCE ROW LEVEL SECURITY;
CREATE POLICY app_root_read ON faos.manifest_roots FOR SELECT TO faos_app USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_roots ON faos.manifest_roots TO faos_writer USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.manifest_roots FROM PUBLIC;
GRANT SELECT ON faos.manifest_roots TO faos_app;
GRANT SELECT,INSERT ON faos.manifest_roots TO faos_writer;
CREATE FUNCTION faos.register_manifest_root(p_tenant uuid,p_session text,p_seal text,p_digest text,p_version text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$ DECLARE seal_kind text; seal_payload jsonb; old faos.manifest_roots%ROWTYPE; BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH'; END IF;
 PERFORM faos.lock_session_for_completion(p_tenant,p_session);
 SELECT kind,payload_json::jsonb INTO seal_kind,seal_payload FROM faos.events
 WHERE tenant_id=p_tenant AND session_id=p_session AND event_id=p_seal;
 IF NOT FOUND THEN RAISE EXCEPTION 'SEAL_EVENT_NOT_FOUND'; END IF;
 IF seal_kind IS DISTINCT FROM 'MANIFEST_SEALED' THEN RAISE EXCEPTION 'INVALID_SEAL_EVENT'; END IF;
 IF seal_payload->>'schema_version' IS DISTINCT FROM '0.1'
 OR seal_payload->>'manifest_digest' IS DISTINCT FROM p_digest
 OR seal_payload->>'shot_list_version' IS DISTINCT FROM p_version THEN
  RAISE EXCEPTION 'ROOT_SEAL_MISMATCH'; END IF;
 SELECT * INTO old FROM faos.manifest_roots
 WHERE tenant_id=p_tenant AND session_id=p_session AND seal_event_id=p_seal;
 IF FOUND THEN
  IF ROW(old.manifest_digest,old.shot_list_version) IS DISTINCT FROM ROW(p_digest,p_version) THEN
   RAISE EXCEPTION 'ROOT_CONFLICT'; END IF;
  RETURN 'DUPLICATE';
 END IF;
 INSERT INTO faos.manifest_roots(tenant_id,session_id,seal_event_id,manifest_digest,shot_list_version)
 VALUES(p_tenant,p_session,p_seal,p_digest,p_version);
 RETURN 'REGISTERED';
END $$;
REVOKE ALL ON FUNCTION faos.register_manifest_root(uuid,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.register_manifest_root(uuid,text,text,text,text) TO faos_fixture;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.register_manifest_root(uuid,text,text,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
