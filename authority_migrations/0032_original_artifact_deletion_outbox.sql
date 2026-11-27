-- Durable, per-original deletion intent and outcome for capture-consent withdrawal.
-- The row is both the retryable outbox entry and the eventual deletion receipt.
CREATE TABLE faos.original_artifact_deletion_outbox (
 tenant_id uuid NOT NULL,
 session_id text NOT NULL,
 artifact_id uuid NOT NULL,
 withdrawal_event_id text NOT NULL,
 requested_by text NOT NULL CHECK(length(trim(requested_by)) BETWEEN 1 AND 128),
 requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
 status text NOT NULL DEFAULT 'PENDING'
   CHECK(status IN ('PENDING','DELETED','ALREADY_ABSENT')),
 last_attempt_at timestamptz,
 completed_at timestamptz,
 last_error_code text CHECK(last_error_code IS NULL OR last_error_code IN (
   'ARTIFACT_STORAGE_UNAVAILABLE','DELETION_ATTEMPT_FAILED'
 )),
 PRIMARY KEY(tenant_id,session_id,artifact_id),
 FOREIGN KEY(tenant_id,session_id)
   REFERENCES faos.sessions(tenant_id,session_id),
 FOREIGN KEY(tenant_id,session_id,withdrawal_event_id)
   REFERENCES faos.events(tenant_id,session_id,event_id),
 CHECK((status='PENDING' AND completed_at IS NULL)
    OR (status IN ('DELETED','ALREADY_ABSENT') AND completed_at IS NOT NULL)),
 CHECK((status='PENDING') OR last_error_code IS NULL)
);

ALTER TABLE faos.original_artifact_deletion_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.original_artifact_deletion_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY app_tenant ON faos.original_artifact_deletion_outbox TO faos_app
 USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_tenant ON faos.original_artifact_deletion_outbox TO faos_writer
 USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.original_artifact_deletion_outbox FROM PUBLIC,faos_app;
GRANT SELECT ON faos.original_artifact_deletion_outbox TO faos_app;
GRANT SELECT,INSERT,UPDATE ON faos.original_artifact_deletion_outbox TO faos_writer;

CREATE FUNCTION faos.enqueue_original_artifact_deletions(
 p_tenant uuid,p_session text,p_owner text,p_withdrawal_event_id text
) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE withdrawal faos.events%ROWTYPE;
        latest faos.events%ROWTYPE;
        artifact record;
        inserted integer;
        total_inserted integer := 0;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_session IS NULL OR p_owner IS NULL OR length(trim(p_owner)) NOT BETWEEN 1 AND 128
 OR p_withdrawal_event_id IS NULL OR length(trim(p_withdrawal_event_id)) NOT BETWEEN 1 AND 256 THEN
  RAISE EXCEPTION 'INVALID_ARTIFACT_DELETION_REQUEST';
 END IF;

 SELECT * INTO withdrawal FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session
    AND event_id=p_withdrawal_event_id AND kind='CONSENT_RECORDED';
 IF NOT FOUND OR withdrawal.actor IS DISTINCT FROM p_owner
 OR withdrawal.payload_json::jsonb->>'owner_actor_id' IS DISTINCT FROM p_owner
 OR withdrawal.payload_json::jsonb->>'accepted' IS DISTINCT FROM 'false' THEN
  RAISE EXCEPTION 'CONSENT_WITHDRAWAL_EVENT_REQUIRED';
 END IF;
 SELECT * INTO latest FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session AND kind='CONSENT_RECORDED'
  ORDER BY sequence DESC LIMIT 1;
 IF NOT FOUND OR latest.actor IS DISTINCT FROM p_owner
 OR latest.payload_json::jsonb->>'owner_actor_id' IS DISTINCT FROM p_owner
 OR latest.payload_json::jsonb->>'accepted' IS DISTINCT FROM 'false' THEN
  RAISE EXCEPTION 'ACTIVE_OWNER_WITHDRAWAL_REQUIRED';
 END IF;

 IF EXISTS (
  SELECT 1 FROM faos.events e
  WHERE e.tenant_id=p_tenant AND e.session_id=p_session AND e.kind='ARTIFACT_REGISTERED'
   AND COALESCE(e.payload_json::jsonb->>'artifact_id','') !~
    '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
 ) THEN
  RAISE EXCEPTION 'INVALID_REGISTERED_ARTIFACT_ID';
 END IF;

 FOR artifact IN
  SELECT DISTINCT e.payload_json::jsonb->>'artifact_id' AS artifact_id
  FROM faos.events e
  WHERE e.tenant_id=p_tenant AND e.session_id=p_session AND e.kind='ARTIFACT_REGISTERED'
  ORDER BY artifact_id
 LOOP
  INSERT INTO faos.original_artifact_deletion_outbox(
   tenant_id,session_id,artifact_id,withdrawal_event_id,requested_by
  ) VALUES(p_tenant,p_session,artifact.artifact_id::uuid,p_withdrawal_event_id,p_owner)
  ON CONFLICT(tenant_id,session_id,artifact_id) DO NOTHING;
  GET DIAGNOSTICS inserted=ROW_COUNT;
  total_inserted := total_inserted + inserted;
 END LOOP;
 RETURN total_inserted;
END $$;

CREATE FUNCTION faos.pending_original_artifact_deletions(
 p_tenant uuid,p_session text,p_owner text
) RETURNS TABLE(artifact_id uuid,attempt_count integer)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE latest faos.events%ROWTYPE;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_owner IS NULL OR length(trim(p_owner)) NOT BETWEEN 1 AND 128 THEN
  RAISE EXCEPTION 'INVALID_ARTIFACT_DELETION_OWNER';
 END IF;
 SELECT * INTO latest FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session AND kind='CONSENT_RECORDED'
  ORDER BY sequence DESC LIMIT 1;
 IF NOT FOUND OR latest.actor IS DISTINCT FROM p_owner
 OR latest.payload_json::jsonb->>'owner_actor_id' IS DISTINCT FROM p_owner
 OR latest.payload_json::jsonb->>'accepted' IS DISTINCT FROM 'false' THEN
  RAISE EXCEPTION 'ACTIVE_OWNER_WITHDRAWAL_REQUIRED';
 END IF;
 RETURN QUERY
  SELECT d.artifact_id,d.attempt_count
  FROM faos.original_artifact_deletion_outbox d
  WHERE d.tenant_id=p_tenant AND d.session_id=p_session
    AND d.requested_by=p_owner AND d.status='PENDING'
  ORDER BY d.requested_at,d.artifact_id;
END $$;

CREATE FUNCTION faos.record_original_artifact_deletion_attempt(
 p_tenant uuid,p_session text,p_artifact uuid,p_owner text,
 p_outcome text,p_error_code text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE latest faos.events%ROWTYPE;
        old_status text;
        new_status text;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_session IS NULL OR p_artifact IS NULL OR p_owner IS NULL
 OR length(trim(p_owner)) NOT BETWEEN 1 AND 128 OR p_outcome IS NULL
 OR p_outcome NOT IN ('DELETED','ALREADY_ABSENT','FAILED') THEN
  RAISE EXCEPTION 'INVALID_ARTIFACT_DELETION_RESULT';
 END IF;
 IF p_outcome='FAILED' AND (p_error_code IS NULL OR p_error_code NOT IN
   ('ARTIFACT_STORAGE_UNAVAILABLE','DELETION_ATTEMPT_FAILED')) THEN
  RAISE EXCEPTION 'INVALID_ARTIFACT_DELETION_ERROR_CODE';
 END IF;
 IF p_outcome<>'FAILED' AND p_error_code IS NOT NULL THEN
  RAISE EXCEPTION 'INVALID_ARTIFACT_DELETION_ERROR_CODE';
 END IF;
 SELECT * INTO latest FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session AND kind='CONSENT_RECORDED'
  ORDER BY sequence DESC LIMIT 1;
 IF NOT FOUND OR latest.actor IS DISTINCT FROM p_owner
 OR latest.payload_json::jsonb->>'owner_actor_id' IS DISTINCT FROM p_owner
 OR latest.payload_json::jsonb->>'accepted' IS DISTINCT FROM 'false' THEN
  RAISE EXCEPTION 'ACTIVE_OWNER_WITHDRAWAL_REQUIRED';
 END IF;
 SELECT status INTO old_status
  FROM faos.original_artifact_deletion_outbox
  WHERE tenant_id=p_tenant AND session_id=p_session AND artifact_id=p_artifact
    AND requested_by=p_owner
  FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'ARTIFACT_DELETION_RECEIPT_NOT_FOUND'; END IF;
 IF old_status<>'PENDING' THEN RETURN old_status; END IF;
 new_status := CASE p_outcome
  WHEN 'DELETED' THEN 'DELETED'
  WHEN 'ALREADY_ABSENT' THEN 'ALREADY_ABSENT'
  ELSE 'PENDING' END;
 UPDATE faos.original_artifact_deletion_outbox
  SET attempt_count=attempt_count+1,
      status=new_status,
      last_attempt_at=clock_timestamp(),
      completed_at=CASE WHEN new_status='PENDING' THEN NULL ELSE clock_timestamp() END,
      last_error_code=CASE WHEN p_outcome='FAILED' THEN p_error_code ELSE NULL END
  WHERE tenant_id=p_tenant AND session_id=p_session AND artifact_id=p_artifact;
 RETURN new_status;
END $$;

REVOKE ALL ON FUNCTION faos.enqueue_original_artifact_deletions(uuid,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION faos.pending_original_artifact_deletions(uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION faos.record_original_artifact_deletion_attempt(uuid,text,uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.enqueue_original_artifact_deletions(uuid,text,text,text) TO faos_app;
GRANT EXECUTE ON FUNCTION faos.pending_original_artifact_deletions(uuid,text,text) TO faos_app;
GRANT EXECUTE ON FUNCTION faos.record_original_artifact_deletion_attempt(uuid,text,uuid,text,text,text) TO faos_app;

GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.enqueue_original_artifact_deletions(uuid,text,text,text) OWNER TO faos_writer;
ALTER FUNCTION faos.pending_original_artifact_deletions(uuid,text,text) OWNER TO faos_writer;
ALTER FUNCTION faos.record_original_artifact_deletion_attempt(uuid,text,uuid,text,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
