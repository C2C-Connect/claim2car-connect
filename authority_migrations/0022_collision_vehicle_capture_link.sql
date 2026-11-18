-- Persist the link from a collision to a vehicle identity established by
-- the collision's own consented capture session. The raw VIN is never copied
-- into the collision registry; only the server-generated keyed digest is stored.
ALTER TABLE faos.vehicles
 ADD COLUMN vin_hmac_sha256 text
   CHECK(vin_hmac_sha256 IS NULL OR vin_hmac_sha256 ~ '^[0-9a-f]{64}$'),
 ADD COLUMN vin_source text NOT NULL DEFAULT 'UNVERIFIED'
   CHECK(vin_source IN ('UNVERIFIED','CONSENTED_CAPTURE_SESSION')),
 ADD COLUMN vin_validation_status text NOT NULL DEFAULT 'UNVERIFIED'
   CHECK(vin_validation_status IN ('UNVERIFIED','CAPTURE_GATE_VALIDATED')),
 ADD COLUMN source_session_id text,
 ADD CONSTRAINT vehicles_source_session_fk
   FOREIGN KEY(tenant_id,source_session_id) REFERENCES faos.sessions(tenant_id,session_id);

CREATE UNIQUE INDEX vehicles_tenant_vin_hmac_uq
 ON faos.vehicles(tenant_id,vin_hmac_sha256)
 WHERE vin_hmac_sha256 IS NOT NULL;

ALTER TABLE faos.collision_vehicle_links
 ADD COLUMN request_id uuid,
 ADD COLUMN source_session_id text,
 ADD COLUMN source_event_id text,
 ADD CONSTRAINT collision_vehicle_source_session_fk
   FOREIGN KEY(tenant_id,source_session_id) REFERENCES faos.sessions(tenant_id,session_id);

CREATE UNIQUE INDEX collision_vehicle_request_uq
 ON faos.collision_vehicle_links(tenant_id,collision_id,request_id)
 WHERE request_id IS NOT NULL;

CREATE FUNCTION faos.link_collision_vehicle_from_capture(
 p_tenant uuid,p_collision uuid,p_claim uuid,p_requested_vehicle uuid,
 p_request uuid,p_relationship text,p_actor text,p_occurred timestamptz
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE capture_session text;
        consent_sequence bigint;
        vehicle_event faos.events%ROWTYPE;
        consent_payload jsonb;
        vin_digest text;
        resolved_vehicle uuid;
        existing_link faos.collision_vehicle_links%ROWTYPE;
        event_payload jsonb;
        event_result text;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_collision IS NULL OR p_claim IS NULL OR p_requested_vehicle IS NULL
 OR p_request IS NULL OR p_actor IS NULL OR length(trim(p_actor)) NOT BETWEEN 1 AND 128
 OR p_occurred IS NULL
 OR p_relationship NOT IN ('INVOLVED','INSURED','THIRD_PARTY','UNKNOWN') THEN
  RAISE EXCEPTION 'INVALID_COLLISION_VEHICLE_LINK';
 END IF;

 PERFORM 1 FROM faos.collision_lifecycle_records
  WHERE tenant_id=p_tenant AND collision_id=p_collision AND created_by=p_actor
  FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'COLLISION_VEHICLE_LINK_AUTHORITY_DENIED'; END IF;

 SELECT c.capture_session_id INTO capture_session
  FROM faos.collision_claim_links l
  JOIN faos.claim_cases c ON c.tenant_id=l.tenant_id AND c.claim_id=l.claim_id
  WHERE l.tenant_id=p_tenant AND l.collision_id=p_collision
    AND l.claim_id=p_claim AND c.created_by=p_actor
  FOR UPDATE OF l,c;
 IF capture_session IS NULL THEN
  RAISE EXCEPTION 'COLLISION_VEHICLE_CLAIM_LINK_REQUIRED';
 END IF;

 SELECT sequence,payload_json::jsonb INTO consent_sequence,consent_payload
  FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=capture_session
    AND kind='CONSENT_RECORDED'
  ORDER BY sequence DESC LIMIT 1;
 IF consent_sequence IS NULL OR consent_payload->>'accepted' IS DISTINCT FROM 'true'
    OR consent_payload->>'scope' IS DISTINCT FROM 'capture_review' THEN
  RAISE EXCEPTION 'ACTIVE_CAPTURE_CONSENT_REQUIRED';
 END IF;

 SELECT * INTO vehicle_event
  FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=capture_session
    AND kind='VEHICLE_RECORDED' AND sequence>consent_sequence
    AND actor=p_actor
  ORDER BY sequence DESC LIMIT 1;
 IF vehicle_event.event_id IS NULL THEN
  RAISE EXCEPTION 'CONSENTED_VEHICLE_REFERENCE_REQUIRED';
 END IF;
 IF vehicle_event.payload_json::jsonb->>'recorded_by_role' NOT IN ('operator','supervisor') THEN
  RAISE EXCEPTION 'VEHICLE_REFERENCE_SOURCE_INVALID';
 END IF;
 vin_digest := vehicle_event.payload_json::jsonb->>'vin_hmac_sha256';
 IF vin_digest IS NULL OR vin_digest !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'VEHICLE_REFERENCE_INTEGRITY_INVALID';
 END IF;

 SELECT * INTO existing_link FROM faos.collision_vehicle_links
  WHERE tenant_id=p_tenant AND collision_id=p_collision
    AND vehicle_id IN (
      SELECT vehicle_id FROM faos.vehicles
      WHERE tenant_id=p_tenant AND vin_hmac_sha256=vin_digest
    )
  FOR UPDATE;
 IF FOUND THEN
  IF existing_link.relationship IS DISTINCT FROM p_relationship THEN
   RAISE EXCEPTION 'COLLISION_VEHICLE_LINK_CONFLICT';
  END IF;
  RETURN 'DUPLICATE';
 END IF;

 INSERT INTO faos.vehicles(
  tenant_id,vehicle_id,vin_hmac_sha256,vin_source,vin_validation_status,
  source_session_id,created_by
 ) VALUES(
  p_tenant,p_requested_vehicle,vin_digest,'CONSENTED_CAPTURE_SESSION',
  'CAPTURE_GATE_VALIDATED',capture_session,p_actor
 ) ON CONFLICT(tenant_id,vin_hmac_sha256) WHERE vin_hmac_sha256 IS NOT NULL
 DO NOTHING;

 SELECT vehicle_id INTO resolved_vehicle FROM faos.vehicles
  WHERE tenant_id=p_tenant AND vin_hmac_sha256=vin_digest
  FOR UPDATE;
 IF resolved_vehicle IS NULL THEN
  RAISE EXCEPTION 'VEHICLE_REGISTRY_READBACK_FAILED';
 END IF;

 INSERT INTO faos.collision_vehicle_links(
  tenant_id,collision_id,vehicle_id,relationship,linked_by,
  request_id,source_session_id,source_event_id
 ) VALUES(
  p_tenant,p_collision,resolved_vehicle,p_relationship,p_actor,
  p_request,capture_session,vehicle_event.event_id
 );

 event_payload := jsonb_build_object(
  'vehicle_id',resolved_vehicle,'claim_id',p_claim,
  'capture_session_id',capture_session,'source_event_id',vehicle_event.event_id,
  'relationship',p_relationship,'vin_source','CONSENTED_CAPTURE_SESSION',
  'vin_validation_status','CAPTURE_GATE_VALIDATED','schema_version','1.0'
 );
 SELECT faos.append_collision_event(
  p_tenant,p_collision,p_request,p_request::text,'collision_vehicle_linked',
  p_actor,p_occurred,event_payload,NULL,NULL
 ) INTO event_result;
 IF event_result IS DISTINCT FROM 'ACCEPTED' THEN
  RAISE EXCEPTION 'COLLISION_VEHICLE_LINK_EVENT_FAILED';
 END IF;
 RETURN 'ACCEPTED';
EXCEPTION WHEN unique_violation THEN
 RAISE EXCEPTION 'COLLISION_VEHICLE_LINK_CONFLICT';
END $$;

REVOKE ALL ON FUNCTION faos.link_collision_vehicle_from_capture(uuid,uuid,uuid,uuid,uuid,text,text,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.link_collision_vehicle_from_capture(uuid,uuid,uuid,uuid,uuid,text,text,timestamptz) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.link_collision_vehicle_from_capture(uuid,uuid,uuid,uuid,uuid,text,text,timestamptz) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
