-- M1 seal binding to verified chain prefix and capture protocol context.
-- Integrity binding only; no external signature or trusted timestamp is claimed.
CREATE FUNCTION faos.manifest_context_binding_hash(p_tenant uuid,p_session text,p_protocol text,p_sequence bigint,p_chain_hash text)
RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog,faos,public AS $$
 SELECT encode(public.digest(convert_to('FAOS_MANIFEST_CONTEXT_BINDING_V1'||E'\n'||p_tenant::text||E'\n'||
 encode(convert_to(p_session,'UTF8'),'hex')||E'\n'||encode(convert_to(p_protocol,'UTF8'),'hex')||E'\n'||
 p_sequence::text||E'\n'||p_chain_hash,'UTF8'),'sha256'),'hex')
$$;
ALTER TABLE faos.manifest_roots ADD COLUMN seal_sequence bigint;
ALTER TABLE faos.manifest_roots ADD COLUMN seal_chain_hash text;
ALTER TABLE faos.manifest_roots ADD COLUMN context_binding_hash text;
ALTER TABLE faos.manifest_roots ADD COLUMN binding_version text;

-- Migration-only cross-tenant backfill, transactionally restore forced RLS.
ALTER TABLE faos.events DISABLE ROW LEVEL SECURITY;
ALTER TABLE faos.sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE faos.manifest_roots DISABLE ROW LEVEL SECURITY;

-- Validate and backfill existing roots from exact persisted chain prefix.
DO $backfill$
DECLARE root_row record; e faos.events%ROWTYPE; previous text; expected bigint; computed text;
 protocol text; v_seq bigint; v_hash text; context_hash text; v_kind text; v_payload jsonb;
BEGIN
 FOR root_row IN SELECT * FROM faos.manifest_roots ORDER BY tenant_id,session_id,seal_event_id LOOP
  SELECT capture_protocol_version INTO protocol FROM faos.sessions WHERE tenant_id=root_row.tenant_id AND session_id=root_row.session_id;
  IF protocol IS NULL THEN RAISE EXCEPTION 'MANIFEST_BINDING_SESSION_MISSING'; END IF;
  IF protocol IS DISTINCT FROM root_row.shot_list_version THEN RAISE EXCEPTION 'MANIFEST_BINDING_PROTOCOL_MISMATCH'; END IF;
  SELECT kind,payload_json::jsonb,sequence,entry_hash INTO v_kind,v_payload,v_seq,v_hash FROM faos.events WHERE tenant_id=root_row.tenant_id AND session_id=root_row.session_id AND event_id=root_row.seal_event_id;
  IF v_seq IS NULL THEN RAISE EXCEPTION 'MANIFEST_BINDING_SEAL_MISSING'; END IF;
  IF v_kind IS DISTINCT FROM 'MANIFEST_SEALED' OR v_payload->>'manifest_digest' IS DISTINCT FROM root_row.manifest_digest OR v_payload->>'shot_list_version' IS DISTINCT FROM root_row.shot_list_version THEN RAISE EXCEPTION 'MANIFEST_BINDING_SEAL_PAYLOAD_MISMATCH'; END IF;
  previous:=faos.event_chain_genesis_hash(root_row.tenant_id,root_row.session_id); expected:=1;
  FOR e IN SELECT * FROM faos.events WHERE tenant_id=root_row.tenant_id AND session_id=root_row.session_id AND sequence<=v_seq ORDER BY sequence LOOP
   IF e.sequence IS DISTINCT FROM expected OR e.hash_version IS DISTINCT FROM 'event-hash-v1' OR e.previous_hash IS DISTINCT FROM previous THEN RAISE EXCEPTION 'MANIFEST_BINDING_CHAIN_INVALID'; END IF;
   computed:=faos.event_chain_entry_hash(e.tenant_id,e.session_id,e.event_id,e.sequence,e.kind,e.actor,e.occurred_at,e.reason,e.payload_json,e.schema_version,previous);
   IF computed IS DISTINCT FROM e.entry_hash THEN RAISE EXCEPTION 'MANIFEST_BINDING_CHAIN_INVALID'; END IF;
   previous:=computed; expected:=expected+1;
  END LOOP;
  IF expected-1 IS DISTINCT FROM v_seq OR previous IS DISTINCT FROM v_hash THEN RAISE EXCEPTION 'MANIFEST_BINDING_SEAL_PREFIX_INVALID'; END IF;
  context_hash:=faos.manifest_context_binding_hash(root_row.tenant_id,root_row.session_id,protocol,v_seq,v_hash);
  UPDATE faos.manifest_roots SET seal_sequence=v_seq,seal_chain_hash=v_hash,context_binding_hash=context_hash,binding_version='manifest-context-v1'
   WHERE tenant_id=root_row.tenant_id AND session_id=root_row.session_id AND seal_event_id=root_row.seal_event_id;
 END LOOP;
END $backfill$;
ALTER TABLE faos.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.events FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.manifest_roots ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.manifest_roots FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.manifest_roots ALTER COLUMN seal_sequence SET NOT NULL;
ALTER TABLE faos.manifest_roots ALTER COLUMN seal_chain_hash SET NOT NULL;
ALTER TABLE faos.manifest_roots ALTER COLUMN context_binding_hash SET NOT NULL;
ALTER TABLE faos.manifest_roots ALTER COLUMN binding_version SET NOT NULL;
ALTER TABLE faos.manifest_roots ADD CONSTRAINT manifest_root_seal_sequence_positive CHECK(seal_sequence>0);
ALTER TABLE faos.manifest_roots ADD CONSTRAINT manifest_root_seal_hash_format CHECK(seal_chain_hash ~ '^[0-9a-f]{64}$');
ALTER TABLE faos.manifest_roots ADD CONSTRAINT manifest_root_context_hash_format CHECK(context_binding_hash ~ '^[0-9a-f]{64}$');
ALTER TABLE faos.manifest_roots ADD CONSTRAINT manifest_root_binding_version_supported CHECK(binding_version='manifest-context-v1');

CREATE FUNCTION faos.verify_manifest_root_binding(p_tenant uuid,p_session text,p_seal text)
RETURNS boolean LANGUAGE plpgsql STABLE SET search_path=pg_catalog,faos,public,pg_temp AS $verify$
DECLARE root_row faos.manifest_roots%ROWTYPE; protocol text; e faos.events%ROWTYPE; previous text; expected bigint; computed text; context_hash text; seal_kind text; seal_payload jsonb;
BEGIN
 SELECT * INTO root_row FROM faos.manifest_roots WHERE tenant_id=p_tenant AND session_id=p_session AND seal_event_id=p_seal;
 IF NOT FOUND OR root_row.binding_version IS DISTINCT FROM 'manifest-context-v1' THEN RETURN false; END IF;
 SELECT capture_protocol_version INTO protocol FROM faos.sessions WHERE tenant_id=p_tenant AND session_id=p_session;
 IF protocol IS NULL OR protocol IS DISTINCT FROM root_row.shot_list_version THEN RETURN false; END IF;
 previous:=faos.event_chain_genesis_hash(p_tenant,p_session); expected:=1;
 FOR e IN SELECT * FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session AND sequence<=root_row.seal_sequence ORDER BY sequence LOOP
  IF e.sequence IS DISTINCT FROM expected OR e.hash_version IS DISTINCT FROM 'event-hash-v1' OR e.previous_hash IS DISTINCT FROM previous THEN RETURN false; END IF;
  computed:=faos.event_chain_entry_hash(e.tenant_id,e.session_id,e.event_id,e.sequence,e.kind,e.actor,e.occurred_at,e.reason,e.payload_json,e.schema_version,previous);
  IF computed IS DISTINCT FROM e.entry_hash THEN RETURN false; END IF;
  previous:=computed; expected:=expected+1;
 END LOOP;
 IF expected-1 IS DISTINCT FROM root_row.seal_sequence OR previous IS DISTINCT FROM root_row.seal_chain_hash THEN RETURN false; END IF;
 SELECT kind,payload_json::jsonb INTO seal_kind,seal_payload FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session AND event_id=p_seal AND sequence=root_row.seal_sequence;
 IF NOT FOUND OR seal_kind IS DISTINCT FROM 'MANIFEST_SEALED' OR seal_payload->>'manifest_digest' IS DISTINCT FROM root_row.manifest_digest OR seal_payload->>'shot_list_version' IS DISTINCT FROM root_row.shot_list_version THEN RETURN false; END IF;
 context_hash:=faos.manifest_context_binding_hash(p_tenant,p_session,protocol,root_row.seal_sequence,root_row.seal_chain_hash);
 RETURN context_hash IS NOT DISTINCT FROM root_row.context_binding_hash;
END $verify$;

CREATE OR REPLACE FUNCTION faos.register_manifest_root(p_tenant uuid,p_session text,p_seal text,p_digest text,p_version text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,public,pg_temp AS $register$
DECLARE protocol text; seal_kind text; seal_payload jsonb; v_seq bigint; v_hash text; binding text;
 e faos.events%ROWTYPE; previous text; expected bigint; computed text; old faos.manifest_roots%ROWTYPE;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH'; END IF;
 PERFORM faos.lock_session_for_completion(p_tenant,p_session);
 SELECT capture_protocol_version INTO protocol FROM faos.sessions WHERE tenant_id=p_tenant AND session_id=p_session;
 IF NOT FOUND THEN RAISE EXCEPTION 'SESSION_NOT_FOUND'; END IF;
 IF protocol IS DISTINCT FROM p_version THEN RAISE EXCEPTION 'ROOT_PROTOCOL_SESSION_MISMATCH'; END IF;
 SELECT kind,payload_json::jsonb,sequence,entry_hash INTO seal_kind,seal_payload,v_seq,v_hash FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session AND event_id=p_seal;
 IF NOT FOUND THEN RAISE EXCEPTION 'SEAL_EVENT_NOT_FOUND'; END IF;
 IF seal_kind IS DISTINCT FROM 'MANIFEST_SEALED' THEN RAISE EXCEPTION 'INVALID_SEAL_EVENT'; END IF;
 IF seal_payload->>'schema_version' IS DISTINCT FROM '0.1' OR seal_payload->>'manifest_digest' IS DISTINCT FROM p_digest OR seal_payload->>'shot_list_version' IS DISTINCT FROM p_version THEN RAISE EXCEPTION 'ROOT_SEAL_MISMATCH'; END IF;
 previous:=faos.event_chain_genesis_hash(p_tenant,p_session); expected:=1;
 FOR e IN SELECT * FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session AND sequence<=v_seq ORDER BY sequence LOOP
  IF e.sequence IS DISTINCT FROM expected OR e.hash_version IS DISTINCT FROM 'event-hash-v1' OR e.previous_hash IS DISTINCT FROM previous THEN RAISE EXCEPTION 'MANIFEST_BINDING_CHAIN_INVALID'; END IF;
  computed:=faos.event_chain_entry_hash(e.tenant_id,e.session_id,e.event_id,e.sequence,e.kind,e.actor,e.occurred_at,e.reason,e.payload_json,e.schema_version,previous);
  IF computed IS DISTINCT FROM e.entry_hash THEN RAISE EXCEPTION 'MANIFEST_BINDING_CHAIN_INVALID'; END IF;
  previous:=computed; expected:=expected+1;
 END LOOP;
 IF expected-1 IS DISTINCT FROM v_seq OR previous IS DISTINCT FROM v_hash THEN RAISE EXCEPTION 'MANIFEST_BINDING_SEAL_PREFIX_INVALID'; END IF;
 binding:=faos.manifest_context_binding_hash(p_tenant,p_session,protocol,v_seq,v_hash);
 SELECT * INTO old FROM faos.manifest_roots WHERE tenant_id=p_tenant AND session_id=p_session AND seal_event_id=p_seal;
 IF FOUND THEN
  IF ROW(old.manifest_digest,old.shot_list_version,old.seal_sequence,old.seal_chain_hash,old.context_binding_hash) IS DISTINCT FROM ROW(p_digest,p_version,v_seq,v_hash,binding) THEN RAISE EXCEPTION 'ROOT_CONFLICT'; END IF;
  RETURN 'DUPLICATE';
 END IF;
 INSERT INTO faos.manifest_roots(tenant_id,session_id,seal_event_id,manifest_digest,shot_list_version,seal_sequence,seal_chain_hash,context_binding_hash,binding_version)
 VALUES(p_tenant,p_session,p_seal,p_digest,p_version,v_seq,v_hash,binding,'manifest-context-v1');
 RETURN 'REGISTERED';
END $register$;

CREATE OR REPLACE FUNCTION faos.record_completion_receipt(p_tenant uuid,p_session text,p_request uuid,p_seal text,p_sequence bigint)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,public,pg_temp
AS $receipt$
DECLARE last_sequence bigint; last_seal text; old faos.completion_receipts%ROWTYPE;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH'; END IF;
 PERFORM faos.lock_session_for_completion(p_tenant,p_session);
 SELECT COALESCE(MAX(sequence),0) INTO last_sequence FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session;
 IF p_sequence IS DISTINCT FROM last_sequence THEN RAISE EXCEPTION 'COMPLETION_SEQUENCE_CHANGED'; END IF;
 SELECT event_id INTO last_seal FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session AND kind='MANIFEST_SEALED' ORDER BY sequence DESC LIMIT 1;
 IF last_seal IS NULL OR p_seal IS DISTINCT FROM last_seal THEN RAISE EXCEPTION 'SEAL_SNAPSHOT_CHANGED'; END IF;
 IF NOT faos.verify_manifest_root_binding(p_tenant,p_session,p_seal) THEN RAISE EXCEPTION 'MANIFEST_ROOT_BINDING_INVALID'; END IF;
 SELECT * INTO old FROM faos.completion_receipts WHERE tenant_id=p_tenant AND session_id=p_session AND request_id=p_request;
 IF FOUND THEN
  IF ROW(old.seal_event_id,old.event_sequence) IS DISTINCT FROM ROW(p_seal,p_sequence) THEN RAISE EXCEPTION 'RECEIPT_CONFLICT'; END IF;
  RETURN 'DUPLICATE';
 END IF;
 INSERT INTO faos.completion_receipts(tenant_id,session_id,request_id,seal_event_id,event_sequence)
 VALUES(p_tenant,p_session,p_request,p_seal,p_sequence);
 RETURN 'RECORDED';
END $receipt$;

REVOKE ALL ON FUNCTION faos.manifest_context_binding_hash(uuid,text,text,bigint,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION faos.verify_manifest_root_binding(uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.manifest_context_binding_hash(uuid,text,text,bigint,text) TO faos_app,faos_writer,faos_fixture;
GRANT EXECUTE ON FUNCTION faos.verify_manifest_root_binding(uuid,text,text) TO faos_app,faos_writer,faos_fixture;
GRANT EXECUTE ON FUNCTION faos.register_manifest_root(uuid,text,text,text,text) TO faos_fixture;
