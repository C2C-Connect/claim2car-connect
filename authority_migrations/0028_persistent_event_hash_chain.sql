-- M1 persistent event-chain integrity, version event-hash-v1.
-- Uses pgcrypto SHA-256; exact UTF-8 text fields are hex encoded in the
-- fixed-field serialization to avoid delimiter ambiguity. Payload bytes/text
-- are committed as stored and are never rewritten by this migration.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE FUNCTION faos.event_chain_genesis_hash(p_tenant uuid,p_session text)
RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog,faos,public
AS $function$
 SELECT encode(public.digest(convert_to(
   'FAOS_EVENT_CHAIN_GENESIS_V1' || E'\n' || p_tenant::text || E'\n' ||
   encode(convert_to(p_session,'UTF8'),'hex'),'UTF8'),'sha256'),'hex')
$function$;

CREATE FUNCTION faos.event_chain_entry_hash(
 p_tenant uuid,p_session text,p_event_id text,p_sequence bigint,p_kind text,
 p_actor text,p_time text,p_reason text,p_payload text,p_schema_version text,
 p_previous_hash text)
RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog,faos,public
AS $function$
 SELECT encode(public.digest(convert_to(
   'FAOS_EVENT_HASH_V1' || E'\n' || p_tenant::text || E'\n' ||
   encode(convert_to(p_session,'UTF8'),'hex') || E'\n' ||
   encode(convert_to(p_event_id,'UTF8'),'hex') || E'\n' ||
   p_sequence::text || E'\n' ||
   encode(convert_to(p_kind,'UTF8'),'hex') || E'\n' ||
   encode(convert_to(p_actor,'UTF8'),'hex') || E'\n' ||
   encode(convert_to(p_time,'UTF8'),'hex') || E'\n' ||
   encode(convert_to(p_reason,'UTF8'),'hex') || E'\n' ||
   encode(convert_to(p_payload,'UTF8'),'hex') || E'\n' ||
   encode(convert_to(p_schema_version,'UTF8'),'hex') || E'\n' ||
   p_previous_hash,'UTF8'),'sha256'),'hex')
$function$;

ALTER TABLE faos.events ADD COLUMN previous_hash text;
ALTER TABLE faos.events ADD COLUMN entry_hash text;
ALTER TABLE faos.events ADD COLUMN hash_version text;

-- Deterministic backfill in session sequence order; any gap or malformed
-- historical row aborts the whole migration and leaves history untouched.
-- The migrator owns this table; temporarily disabling RLS is transaction-scoped
-- and the policies/forced-RLS mode are restored before the migration commits.
ALTER TABLE faos.events DISABLE ROW LEVEL SECURITY;
DO $backfill$
DECLARE r record; current_tenant uuid; current_session text;
        previous text; expected bigint; computed text;
BEGIN
 FOR r IN SELECT * FROM faos.events ORDER BY tenant_id,session_id,sequence LOOP
   IF current_tenant IS DISTINCT FROM r.tenant_id OR current_session IS DISTINCT FROM r.session_id THEN
     current_tenant := r.tenant_id; current_session := r.session_id;
     previous := faos.event_chain_genesis_hash(r.tenant_id,r.session_id);
     expected := 1;
   END IF;
   IF r.sequence IS DISTINCT FROM expected THEN
     RAISE EXCEPTION 'EVENT_CHAIN_BACKFILL_SEQUENCE_GAP:%:%:%',
       r.tenant_id,r.session_id,r.sequence;
   END IF;
   computed := faos.event_chain_entry_hash(
     r.tenant_id,r.session_id,r.event_id,r.sequence,r.kind,r.actor,
     r.occurred_at,r.reason,r.payload_json,r.schema_version,previous);
   UPDATE faos.events SET previous_hash=previous,entry_hash=computed,
     hash_version='event-hash-v1'
     WHERE tenant_id=r.tenant_id AND session_id=r.session_id AND event_id=r.event_id;
   previous := computed;
   expected := expected+1;
 END LOOP;
END
$backfill$;

ALTER TABLE faos.events ALTER COLUMN previous_hash SET NOT NULL;
ALTER TABLE faos.events ALTER COLUMN entry_hash SET NOT NULL;
ALTER TABLE faos.events ALTER COLUMN hash_version SET NOT NULL;
ALTER TABLE faos.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.events FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.events ADD CONSTRAINT events_previous_hash_format
 CHECK(previous_hash ~ '^[0-9a-f]{64}$');
ALTER TABLE faos.events ADD CONSTRAINT events_entry_hash_format
 CHECK(entry_hash ~ '^[0-9a-f]{64}$');
ALTER TABLE faos.events ADD CONSTRAINT events_hash_version_supported
 CHECK(hash_version='event-hash-v1');

CREATE FUNCTION faos.event_chain_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,public,pg_temp
AS $guard$
DECLARE last_sequence bigint; last_hash text; expected_previous text; expected_entry text;
        verify_row faos.events%ROWTYPE; verify_previous text; verify_expected bigint; verify_hash text;
BEGIN
 IF TG_OP <> 'INSERT' THEN
   RAISE EXCEPTION 'EVENT_HISTORY_IMMUTABLE';
 END IF;
 IF faos.tenant_id() IS NOT NULL AND NEW.tenant_id IS DISTINCT FROM faos.tenant_id() THEN
   RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 ELSIF faos.tenant_id() IS NULL AND NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls)
 ) THEN
   RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 PERFORM 1 FROM faos.sessions WHERE tenant_id=NEW.tenant_id AND session_id=NEW.session_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'SESSION_NOT_FOUND'; END IF;
 verify_previous := faos.event_chain_genesis_hash(NEW.tenant_id,NEW.session_id);
 verify_expected := 1;
 FOR verify_row IN SELECT * FROM faos.events WHERE tenant_id=NEW.tenant_id AND session_id=NEW.session_id ORDER BY sequence LOOP
   IF verify_row.sequence IS DISTINCT FROM verify_expected OR verify_row.hash_version IS DISTINCT FROM 'event-hash-v1' OR verify_row.previous_hash IS DISTINCT FROM verify_previous THEN
     RAISE EXCEPTION 'EVENT_CHAIN_INVALID';
   END IF;
   verify_hash := faos.event_chain_entry_hash(verify_row.tenant_id,verify_row.session_id,verify_row.event_id,
     verify_row.sequence,verify_row.kind,verify_row.actor,verify_row.occurred_at,verify_row.reason,
     verify_row.payload_json,verify_row.schema_version,verify_previous);
   IF verify_hash IS DISTINCT FROM verify_row.entry_hash THEN RAISE EXCEPTION 'EVENT_CHAIN_INVALID'; END IF;
   verify_previous := verify_hash; verify_expected := verify_expected+1;
 END LOOP;
 SELECT sequence,entry_hash INTO last_sequence,last_hash
 FROM faos.events WHERE tenant_id=NEW.tenant_id AND session_id=NEW.session_id
 ORDER BY sequence DESC LIMIT 1;
 IF last_sequence IS NULL THEN
   last_sequence := 0;
   expected_previous := faos.event_chain_genesis_hash(NEW.tenant_id,NEW.session_id);
 ELSE
   expected_previous := last_hash;
 END IF;
 IF NEW.sequence IS DISTINCT FROM last_sequence+1 THEN
   RAISE EXCEPTION 'SEQUENCE_CONFLICT';
 END IF;
 IF NEW.hash_version IS NULL THEN NEW.hash_version := 'event-hash-v1'; END IF;
 IF NEW.hash_version IS DISTINCT FROM 'event-hash-v1' THEN
   RAISE EXCEPTION 'UNSUPPORTED_EVENT_HASH_VERSION';
 END IF;
 IF NEW.previous_hash IS NULL THEN NEW.previous_hash := expected_previous; END IF;
 IF NEW.previous_hash IS DISTINCT FROM expected_previous THEN
   RAISE EXCEPTION 'PREVIOUS_HASH_MISMATCH';
 END IF;
 expected_entry := faos.event_chain_entry_hash(
   NEW.tenant_id,NEW.session_id,NEW.event_id,NEW.sequence,NEW.kind,NEW.actor,
   NEW.occurred_at,NEW.reason,NEW.payload_json,NEW.schema_version,expected_previous);
 IF NEW.entry_hash IS NULL THEN NEW.entry_hash := expected_entry; END IF;
 IF NEW.entry_hash IS DISTINCT FROM expected_entry THEN
   RAISE EXCEPTION 'EVENT_HASH_MISMATCH';
 END IF;
 RETURN NEW;
END
$guard$;

CREATE TRIGGER faos_event_chain_guard_insert
 BEFORE INSERT ON faos.events FOR EACH ROW EXECUTE FUNCTION faos.event_chain_guard();
CREATE TRIGGER faos_event_chain_guard_mutation
 BEFORE UPDATE OR DELETE ON faos.events FOR EACH ROW EXECUTE FUNCTION faos.event_chain_guard();

CREATE OR REPLACE FUNCTION faos.append_event(p_tenant uuid,p_session text,p_id text,p_sequence bigint,
 p_kind text,p_actor text,p_time text,p_reason text,p_payload text,p_version text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,public,pg_temp
AS $append$
DECLARE old faos.events%ROWTYPE; r faos.events%ROWTYPE; last_sequence bigint;
        previous text; computed text; expected bigint;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
   RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 PERFORM 1 FROM faos.sessions WHERE tenant_id=p_tenant AND session_id=p_session FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'SESSION_NOT_FOUND'; END IF;

 previous := faos.event_chain_genesis_hash(p_tenant,p_session);
 expected := 1;
 FOR r IN SELECT * FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session ORDER BY sequence LOOP
   IF r.sequence IS DISTINCT FROM expected THEN RAISE EXCEPTION 'EVENT_SEQUENCE_GAP_OR_REORDER'; END IF;
   IF r.hash_version IS DISTINCT FROM 'event-hash-v1' THEN RAISE EXCEPTION 'UNSUPPORTED_EVENT_HASH_VERSION'; END IF;
   IF r.previous_hash IS DISTINCT FROM previous THEN RAISE EXCEPTION 'PREVIOUS_HASH_MISMATCH'; END IF;
   computed := faos.event_chain_entry_hash(r.tenant_id,r.session_id,r.event_id,r.sequence,
     r.kind,r.actor,r.occurred_at,r.reason,r.payload_json,r.schema_version,previous);
   IF computed IS DISTINCT FROM r.entry_hash THEN RAISE EXCEPTION 'EVENT_HASH_MISMATCH'; END IF;
   previous := computed; expected := expected+1;
 END LOOP;
 last_sequence := expected-1;

 SELECT * INTO old FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session AND event_id=p_id;
 IF FOUND THEN
   IF ROW(old.sequence,old.kind,old.actor,old.occurred_at,old.reason,old.payload_json,old.schema_version)
     IS DISTINCT FROM ROW(p_sequence,p_kind,p_actor,p_time,p_reason,p_payload,p_version)
   THEN RAISE EXCEPTION 'CONFLICTING_EVENT_DUPLICATE'; END IF;
   RETURN 'DUPLICATE';
 END IF;
 IF p_sequence IS DISTINCT FROM last_sequence+1 THEN RAISE EXCEPTION 'SEQUENCE_CONFLICT'; END IF;
 computed := faos.event_chain_entry_hash(p_tenant,p_session,p_id,p_sequence,p_kind,p_actor,
   p_time,p_reason,p_payload,p_version,previous);
 INSERT INTO faos.events(tenant_id,session_id,event_id,sequence,kind,actor,occurred_at,
   reason,payload_json,schema_version,previous_hash,entry_hash,hash_version)
 VALUES(p_tenant,p_session,p_id,p_sequence,p_kind,p_actor,p_time,p_reason,p_payload,p_version,
   previous,computed,'event-hash-v1');
 RETURN 'ACCEPTED';
END
$append$;

REVOKE ALL ON FUNCTION faos.event_chain_genesis_hash(uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION faos.event_chain_entry_hash(uuid,text,text,bigint,text,text,text,text,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION faos.event_chain_guard() FROM PUBLIC;
REVOKE ALL ON FUNCTION faos.append_event(uuid,text,text,bigint,text,text,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.event_chain_genesis_hash(uuid,text) TO faos_app,faos_writer;
GRANT EXECUTE ON FUNCTION faos.event_chain_entry_hash(uuid,text,text,bigint,text,text,text,text,text,text,text) TO faos_app,faos_writer;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.event_chain_genesis_hash(uuid,text) OWNER TO faos_writer;
ALTER FUNCTION faos.event_chain_entry_hash(uuid,text,text,bigint,text,text,text,text,text,text,text) OWNER TO faos_writer;
ALTER FUNCTION faos.event_chain_guard() OWNER TO faos_writer;
ALTER FUNCTION faos.append_event(uuid,text,text,bigint,text,text,text,text,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
GRANT EXECUTE ON FUNCTION faos.append_event(uuid,text,text,bigint,text,text,text,text,text,text) TO faos_app;
