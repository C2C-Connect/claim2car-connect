-- Privileged historical snapshot receipts; this primitive does not evaluate evidence.
-- Receipts do not freeze sessions or establish current eligibility after later events.
CREATE TABLE faos.completion_receipts(
 tenant_id uuid NOT NULL, session_id text NOT NULL, request_id uuid NOT NULL,
 seal_event_id text NOT NULL, event_sequence bigint NOT NULL CHECK(event_sequence>0),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 authority_role name NOT NULL DEFAULT current_user,
 authority_session name NOT NULL DEFAULT session_user,
 PRIMARY KEY(tenant_id,session_id,request_id),
 FOREIGN KEY(tenant_id,session_id,seal_event_id) REFERENCES faos.manifest_roots(tenant_id,session_id,seal_event_id),
 FOREIGN KEY(tenant_id,session_id,event_sequence) REFERENCES faos.events(tenant_id,session_id,sequence));
ALTER TABLE faos.completion_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.completion_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY app_receipt_read ON faos.completion_receipts FOR SELECT TO faos_app USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_receipts ON faos.completion_receipts TO faos_writer USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.completion_receipts FROM PUBLIC;
GRANT SELECT ON faos.completion_receipts TO faos_app;
GRANT SELECT,INSERT ON faos.completion_receipts TO faos_writer;
CREATE FUNCTION faos.record_completion_receipt(p_tenant uuid,p_session text,p_request uuid,p_seal text,p_sequence bigint)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$ DECLARE last_sequence bigint; last_seal text; old faos.completion_receipts%ROWTYPE; BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH'; END IF;
 PERFORM faos.lock_session_for_completion(p_tenant,p_session);
 SELECT COALESCE(MAX(sequence),0) INTO last_sequence FROM faos.events
 WHERE tenant_id=p_tenant AND session_id=p_session;
 IF p_sequence IS DISTINCT FROM last_sequence THEN RAISE EXCEPTION 'COMPLETION_SEQUENCE_CHANGED'; END IF;
 SELECT event_id INTO last_seal FROM faos.events
 WHERE tenant_id=p_tenant AND session_id=p_session AND kind='MANIFEST_SEALED'
 ORDER BY sequence DESC LIMIT 1;
 IF last_seal IS NULL OR p_seal IS DISTINCT FROM last_seal THEN RAISE EXCEPTION 'SEAL_SNAPSHOT_CHANGED'; END IF;
 SELECT * INTO old FROM faos.completion_receipts
 WHERE tenant_id=p_tenant AND session_id=p_session AND request_id=p_request;
 IF FOUND THEN
  IF ROW(old.seal_event_id,old.event_sequence) IS DISTINCT FROM ROW(p_seal,p_sequence) THEN
   RAISE EXCEPTION 'RECEIPT_CONFLICT'; END IF;
  RETURN 'DUPLICATE';
 END IF;
 INSERT INTO faos.completion_receipts(tenant_id,session_id,request_id,seal_event_id,event_sequence)
 VALUES(p_tenant,p_session,p_request,p_seal,p_sequence);
 RETURN 'RECORDED';
END $$;
REVOKE ALL ON FUNCTION faos.record_completion_receipt(uuid,text,uuid,text,bigint) FROM PUBLIC;
-- No grant to faos_app or faos_fixture: only the trusted writer owner may call.
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.record_completion_receipt(uuid,text,uuid,text,bigint) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
