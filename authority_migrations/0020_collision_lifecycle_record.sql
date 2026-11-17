-- Collision Lifecycle Record v1: collision identity is independent of claim identity.
-- All relationships are tenant-scoped. Sensitive person/claim details remain in
-- their owning domains; this aggregate stores opaque actor references only.

CREATE TABLE faos.collision_lifecycle_records (
 tenant_id uuid NOT NULL REFERENCES faos.organizations(tenant_id),
 collision_id uuid NOT NULL,
 request_id uuid NOT NULL,
 created_by text NOT NULL CHECK(length(trim(created_by)) BETWEEN 1 AND 128),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 state text NOT NULL DEFAULT 'OPEN' CHECK(state IN ('OPEN','RESOLVED','CLOSED')),
 resolved_at timestamptz,
 version bigint NOT NULL DEFAULT 1 CHECK(version > 0),
 PRIMARY KEY(tenant_id,collision_id),
 UNIQUE(tenant_id,request_id),
 CHECK((state='OPEN' AND resolved_at IS NULL) OR (state<>'OPEN' AND resolved_at IS NOT NULL))
);

CREATE TABLE faos.vehicles (
 tenant_id uuid NOT NULL REFERENCES faos.organizations(tenant_id),
 vehicle_id uuid NOT NULL,
 vin text,
 created_by text NOT NULL CHECK(length(trim(created_by)) BETWEEN 1 AND 128),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,vehicle_id),
 CHECK(vin IS NULL OR vin ~ '^[A-HJ-NPR-Z0-9]{17}$')
);
CREATE UNIQUE INDEX vehicles_tenant_vin_uq ON faos.vehicles(tenant_id,vin) WHERE vin IS NOT NULL;

CREATE TABLE faos.collision_vehicle_links (
 tenant_id uuid NOT NULL,
 collision_id uuid NOT NULL,
 vehicle_id uuid NOT NULL,
 relationship text NOT NULL CHECK(relationship IN ('INVOLVED','INSURED','THIRD_PARTY','UNKNOWN')),
 linked_by text NOT NULL CHECK(length(trim(linked_by)) BETWEEN 1 AND 128),
 linked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,collision_id,vehicle_id),
 FOREIGN KEY(tenant_id,collision_id) REFERENCES faos.collision_lifecycle_records(tenant_id,collision_id),
 FOREIGN KEY(tenant_id,vehicle_id) REFERENCES faos.vehicles(tenant_id,vehicle_id)
);

CREATE TABLE faos.collision_participants (
 tenant_id uuid NOT NULL,
 collision_id uuid NOT NULL,
 participant_id uuid NOT NULL,
 actor_ref text NOT NULL CHECK(length(trim(actor_ref)) BETWEEN 1 AND 160),
 role text NOT NULL CHECK(role IN ('DRIVER','OWNER','PASSENGER','WITNESS','CLAIMANT','REPRESENTATIVE','OPERATOR','PROVIDER')),
 linked_by text NOT NULL CHECK(length(trim(linked_by)) BETWEEN 1 AND 128),
 linked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,collision_id,participant_id),
 UNIQUE(tenant_id,collision_id,actor_ref,role),
 FOREIGN KEY(tenant_id,collision_id) REFERENCES faos.collision_lifecycle_records(tenant_id,collision_id)
);

CREATE TABLE faos.collision_claim_links (
 tenant_id uuid NOT NULL,
 collision_id uuid NOT NULL,
 claim_id uuid NOT NULL,
 linked_by text NOT NULL CHECK(length(trim(linked_by)) BETWEEN 1 AND 128),
 linked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,collision_id,claim_id),
 FOREIGN KEY(tenant_id,collision_id) REFERENCES faos.collision_lifecycle_records(tenant_id,collision_id),
 FOREIGN KEY(tenant_id,claim_id) REFERENCES faos.claim_cases(tenant_id,claim_id)
);

CREATE TABLE faos.collision_events (
 tenant_id uuid NOT NULL,
 collision_id uuid NOT NULL,
 event_id uuid NOT NULL,
 sequence bigint NOT NULL CHECK(sequence > 0),
 idempotency_key text NOT NULL CHECK(length(trim(idempotency_key)) BETWEEN 1 AND 256),
 event_type text NOT NULL CHECK(event_type ~ '^[a-z][a-z0-9_]{1,95}$'),
 actor_ref text NOT NULL CHECK(length(trim(actor_ref)) BETWEEN 1 AND 160),
 occurred_at timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 schema_version text NOT NULL DEFAULT '1.0' CHECK(schema_version='1.0'),
 correlation_id uuid,
 causation_id uuid,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 PRIMARY KEY(tenant_id,collision_id,event_id),
 UNIQUE(tenant_id,collision_id,sequence),
 UNIQUE(tenant_id,collision_id,idempotency_key),
 FOREIGN KEY(tenant_id,collision_id) REFERENCES faos.collision_lifecycle_records(tenant_id,collision_id),
 FOREIGN KEY(tenant_id,collision_id,causation_id)
   REFERENCES faos.collision_events(tenant_id,collision_id,event_id)
   DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE faos.collision_outbox (
 tenant_id uuid NOT NULL,
 collision_id uuid NOT NULL,
 message_id uuid NOT NULL,
 event_id uuid NOT NULL,
 topic text NOT NULL CHECK(length(trim(topic)) BETWEEN 1 AND 128),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts >= 0),
 available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 delivered_at timestamptz,
 last_error text,
 PRIMARY KEY(tenant_id,message_id),
 UNIQUE(tenant_id,event_id),
 FOREIGN KEY(tenant_id,collision_id,event_id)
   REFERENCES faos.collision_events(tenant_id,collision_id,event_id)
);

-- Every CLR-owned table is tenant isolated. Application reads are scoped by
-- tenant; mutations are performed through SECURITY DEFINER domain functions.
DO $$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY[
  'collision_lifecycle_records','vehicles','collision_vehicle_links',
  'collision_participants','collision_claim_links','collision_events','collision_outbox'
 ] LOOP
  EXECUTE format('ALTER TABLE faos.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE faos.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY app_tenant ON faos.%I TO faos_app USING(tenant_id=faos.tenant_id())',t);
  EXECUTE format('CREATE POLICY writer_tenant ON faos.%I TO faos_writer USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id())',t);
 END LOOP;
END $$;

REVOKE ALL ON faos.collision_lifecycle_records,faos.vehicles,faos.collision_vehicle_links,
 faos.collision_participants,faos.collision_claim_links,faos.collision_events,
 faos.collision_outbox FROM PUBLIC,faos_app;
GRANT SELECT ON faos.collision_lifecycle_records,faos.vehicles,faos.collision_vehicle_links,
 faos.collision_participants,faos.collision_claim_links,faos.collision_events TO faos_app;
GRANT SELECT,INSERT,UPDATE ON faos.collision_lifecycle_records,faos.vehicles,
 faos.collision_vehicle_links,faos.collision_participants,faos.collision_claim_links,
 faos.collision_events,faos.collision_outbox TO faos_writer;

CREATE FUNCTION faos.reject_collision_event_mutation()
RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,faos,pg_temp
AS $$
BEGIN
 RAISE EXCEPTION 'COLLISION_EVENT_IMMUTABLE';
END $$;
REVOKE ALL ON FUNCTION faos.reject_collision_event_mutation() FROM PUBLIC;
CREATE TRIGGER collision_events_immutable
 BEFORE UPDATE OR DELETE ON faos.collision_events
 FOR EACH ROW EXECUTE FUNCTION faos.reject_collision_event_mutation();

CREATE FUNCTION faos.append_collision_event(
 p_tenant uuid,p_collision uuid,p_event uuid,p_idempotency text,p_type text,
 p_actor text,p_occurred timestamptz,p_payload jsonb,p_correlation uuid,p_causation uuid
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE old faos.collision_events%ROWTYPE;
        next_sequence bigint;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_event IS NULL OR p_collision IS NULL OR p_occurred IS NULL
 OR p_payload IS NULL OR jsonb_typeof(p_payload) IS DISTINCT FROM 'object'
 OR p_actor IS NULL OR length(trim(p_actor)) NOT BETWEEN 1 AND 160
 OR p_idempotency IS NULL OR length(trim(p_idempotency)) NOT BETWEEN 1 AND 256
 OR p_type IS NULL OR p_type !~ '^[a-z][a-z0-9_]{1,95}$' THEN
  RAISE EXCEPTION 'INVALID_COLLISION_EVENT';
 END IF;
 PERFORM 1 FROM faos.collision_lifecycle_records
  WHERE tenant_id=p_tenant AND collision_id=p_collision FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'COLLISION_NOT_FOUND'; END IF;
 SELECT * INTO old FROM faos.collision_events
  WHERE tenant_id=p_tenant AND collision_id=p_collision
    AND idempotency_key=p_idempotency;
 IF FOUND THEN
  IF ROW(old.event_id,old.event_type,old.actor_ref,old.occurred_at,
         old.payload,old.correlation_id,old.causation_id)
     IS DISTINCT FROM
     ROW(p_event,p_type,p_actor,p_occurred,p_payload,p_correlation,p_causation) THEN
   RAISE EXCEPTION 'COLLISION_EVENT_IDEMPOTENCY_CONFLICT';
  END IF;
  RETURN 'DUPLICATE';
 END IF;
 SELECT COALESCE(MAX(sequence),0)+1 INTO next_sequence
  FROM faos.collision_events
  WHERE tenant_id=p_tenant AND collision_id=p_collision;
 INSERT INTO faos.collision_events(
  tenant_id,collision_id,event_id,sequence,idempotency_key,event_type,
  actor_ref,occurred_at,payload,correlation_id,causation_id
 ) VALUES(
  p_tenant,p_collision,p_event,next_sequence,p_idempotency,p_type,
  p_actor,p_occurred,p_payload,p_correlation,p_causation
 );
 INSERT INTO faos.collision_outbox(
  tenant_id,collision_id,message_id,event_id,topic,payload
 ) VALUES(
  p_tenant,p_collision,p_event,p_event,p_type,
  jsonb_build_object('event_id',p_event,'collision_id',p_collision,
                     'sequence',next_sequence,'event_type',p_type,
                     'schema_version','1.0','payload',p_payload)
 );
 RETURN 'ACCEPTED';
END $$;
REVOKE ALL ON FUNCTION faos.append_collision_event(uuid,uuid,uuid,text,text,text,timestamptz,jsonb,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.append_collision_event(uuid,uuid,uuid,text,text,text,timestamptz,jsonb,uuid,uuid) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.append_collision_event(uuid,uuid,uuid,text,text,text,timestamptz,jsonb,uuid,uuid) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;

CREATE FUNCTION faos.create_collision_lifecycle_record(
 p_tenant uuid,p_collision uuid,p_request uuid,p_actor text,p_occurred timestamptz
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE existing faos.collision_lifecycle_records%ROWTYPE;
        event_result text;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_collision IS NULL OR p_request IS NULL OR p_actor IS NULL
 OR length(trim(p_actor)) NOT BETWEEN 1 AND 128 OR p_occurred IS NULL THEN
  RAISE EXCEPTION 'INVALID_COLLISION_RECORD';
 END IF;
 INSERT INTO faos.collision_lifecycle_records(
  tenant_id,collision_id,request_id,created_by
 ) VALUES(p_tenant,p_collision,p_request,p_actor)
 ON CONFLICT(tenant_id,request_id) DO NOTHING
 RETURNING * INTO existing;
 IF NOT FOUND THEN
  SELECT * INTO existing FROM faos.collision_lifecycle_records
   WHERE tenant_id=p_tenant AND request_id=p_request FOR UPDATE;
  IF NOT FOUND OR existing.collision_id IS DISTINCT FROM p_collision
     OR existing.created_by IS DISTINCT FROM p_actor THEN
   RETURN 'CONFLICT';
  END IF;
  RETURN 'DUPLICATE';
 END IF;
 SELECT faos.append_collision_event(
  p_tenant,p_collision,p_collision,'collision-created','collision_registered',
  p_actor,p_occurred,jsonb_build_object('state','OPEN','schema_version','1.0'),NULL,NULL
 ) INTO event_result;
 IF event_result IS DISTINCT FROM 'ACCEPTED' THEN
  RAISE EXCEPTION 'COLLISION_EVENT_CREATION_FAILED';
 END IF;
 RETURN 'ACCEPTED';
EXCEPTION WHEN unique_violation THEN
 RETURN 'CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.create_collision_lifecycle_record(uuid,uuid,uuid,text,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.create_collision_lifecycle_record(uuid,uuid,uuid,text,timestamptz) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.create_collision_lifecycle_record(uuid,uuid,uuid,text,timestamptz) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
