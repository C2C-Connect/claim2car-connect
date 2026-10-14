CREATE TABLE faos.sessions(tenant_id uuid NOT NULL REFERENCES faos.organizations,
 session_id text NOT NULL CHECK(length(trim(session_id))>0),PRIMARY KEY(tenant_id,session_id));
CREATE TABLE faos.events(tenant_id uuid NOT NULL,session_id text not NULL,
 event_id text NOT NULL CHECK(length(trim(event_id))>0),sequence bigint NOT NULL CHECK(sequence>0),
 kind text NOT NULL CHECK(kind IN ('SESSION_CREATED','CONSENT_RECORDED','VEHICLE_RECORDED','ARTIFACT_REGISTERED','QUALITY_RECORDED','MANIFEST_SEALED','REVIEW_RECORDED')),
 actor text NOT NULL CHECK(length(trim(actor))>0),occurred_at text NOT NULL,
 reason text NOT NULL CHECK(length(trim(reason))>0),payload_json text NOT NULL CHECK(jsonb_typeof(payload_json::jsonb)='object'),
 schema_version text NOT NULL CHECK(schema_version='0.1'),PRIMARY KEY(tenant_id,session_id,event_id),
 UNIQUE(tenant_id,session_id,sequence),FOREIGN KEY(tenant_id,session_id) REFERENCES faos.sessions(tenant_id,session_id));
ALTER TABLE faos.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.events FORCE ROW LEVEL SECURITY;
CREATE POLICY app_tenant ON faos.sessions TO faos_app USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
CREATE POLICY app_tenant ON faos.events TO faos_app USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
CREATE POLICY writer_tenant ON faos.sessions TO faos_writer USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
CREATE POLICY writer_tenant ON faos.events TO faos_writer USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
GRANT SELECT,INSERT ON faos.sessions TO faos_app;
GRANT SELECT,UPDATE ON faos.sessions TO faos_writer;
GRANT SELECT ON faos.events TO faos_app;
GRANT SELECT,INSERT ON faos.events TO faos_writer;
CREATE FUNCTION faos.append_event(p_tenant uuid,p_session text,p_id text,p_sequence bigint,
 p_kind text,p_actor text,p_time text,p_reason text,p_payload text,p_version text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$ DECLARE old faos.events%ROWTYPE; last_sequence bigint; BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
 RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH'; END IF;
 PERFORM 1 FROM faos.sessions WHERE tenant_id=p_tenant AND session_id=p_session FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'SESSION_NOT_FOUND'; END IF;
 SELECT * INTO old FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session AND event_id=p_id;
 IF FOUND THEN
 IF ROW(old.sequence,old.kind,old.actor,old.occurred_at,old.reason,old.payload_json,old.schema_version)
 IS DISTINCT FROM ROW(p_sequence,p_kind,p_actor,p_time,p_reason,p_payload,p_version)
 THEN RAISE EXCEPTION 'CONFLICTING_EVENT_DUPLICATE'; END IF;
 RETURN 'DUPLICATE'; END IF;
 SELECT COALESCE(MAX(sequence),0) INTO last_sequence FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session;
 IF p_sequence IS DISTINCT FROM last_sequence+1 THEN RAISE EXCEPTION 'SEQUENCE_CONFLICT'; END IF;
 INSERT INTO faos.events(tenant_id,session_id,event_id,sequence,kind,actor,occurred_at,reason,payload_json,schema_version)
 VALUES(p_tenant,p_session,p_id,p_sequence,p_kind,p_actor,p_time,p_reason,p_payload,p_version);
 RETURN 'ACCEPTED';
END $$;
REVOKE ALL ON FUNCTION faos.append_event(uuid,text,text,bigint,text,text,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.append_event(uuid,text,text,bigint,text,text,text,text,text,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.append_event(uuid,text,text,bigint,text,text,text,text,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
