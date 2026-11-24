-- Runtime registration path for the M1 seal-to-root binding.
-- Applications may append a seal only through their authorized service; this
-- function permits registration only for that exact current seal, actor,
-- request, protocol, and complete latest artifact-ID set.
GRANT EXECUTE ON FUNCTION faos.register_manifest_root(uuid,text,text,text,text) TO faos_writer;

CREATE FUNCTION faos.register_manifest_root_from_capture(
 p_tenant uuid,
 p_session text,
 p_seal text,
 p_digest text,
 p_version text,
 p_actor text,
 p_request uuid
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,public,pg_temp
AS $capture_register$
DECLARE
 protocol text;
 seal_row faos.events%ROWTYPE;
 seal_payload jsonb;
 previous_capture_kind text;
 seal_ids text[];
 latest_ids text[];
 latest_count integer;
 unique_latest_count integer;
 expected_slots integer;
 expected_slot_names text[];
 expected_slot_set text[];
 latest_slots text[];
 existing_root boolean;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_actor IS NULL OR length(trim(p_actor))=0 OR p_request IS NULL
    OR p_seal IS DISTINCT FROM 'seal:'||p_request::text THEN
  RAISE EXCEPTION 'INVALID_CAPTURE_SEAL_IDENTITY';
 END IF;
 PERFORM faos.lock_session_for_completion(p_tenant,p_session);
 SELECT capture_protocol_version INTO protocol
 FROM faos.sessions WHERE tenant_id=p_tenant AND session_id=p_session;
 IF NOT FOUND THEN RAISE EXCEPTION 'SESSION_NOT_FOUND'; END IF;
 IF protocol IS DISTINCT FROM p_version THEN RAISE EXCEPTION 'ROOT_PROTOCOL_SESSION_MISMATCH'; END IF;
 SELECT * INTO seal_row FROM faos.events
 WHERE tenant_id=p_tenant AND session_id=p_session AND event_id=p_seal;
 IF NOT FOUND THEN RAISE EXCEPTION 'SEAL_EVENT_NOT_FOUND'; END IF;
 IF seal_row.kind IS DISTINCT FROM 'MANIFEST_SEALED'
    OR seal_row.actor IS DISTINCT FROM p_actor THEN
  RAISE EXCEPTION 'CAPTURE_SEAL_ACTOR_OR_KIND_MISMATCH';
 END IF;
 seal_payload:=seal_row.payload_json::jsonb;
 IF seal_payload->>'request_id' IS DISTINCT FROM p_request::text
    OR seal_payload->>'manifest_digest' IS DISTINCT FROM p_digest
    OR seal_payload->>'shot_list_version' IS DISTINCT FROM p_version
    OR seal_payload->>'schema_version' IS DISTINCT FROM '0.1'
    OR jsonb_typeof(seal_payload->'artifact_ids') IS DISTINCT FROM 'array' THEN
  RAISE EXCEPTION 'ROOT_SEAL_MISMATCH';
 END IF;
 SELECT kind INTO previous_capture_kind FROM faos.events
 WHERE tenant_id=p_tenant AND session_id=p_session AND sequence<seal_row.sequence
   AND kind NOT IN ('VEHICLE_DECODE_CONSENT_RECORDED','VEHICLE_PROFILE_DECODED')
 ORDER BY sequence DESC LIMIT 1;
 IF previous_capture_kind IS DISTINCT FROM 'QUALITY_RECORDED' THEN
  RAISE EXCEPTION 'QUALITY_REVIEW_REQUIRED_BEFORE_SEAL';
 END IF;
 expected_slot_names:=CASE protocol
  WHEN 'claims2car-16-v1' THEN ARRAY[
   '00_front_exterior','01_front_right_exterior','02_right_side_exterior','03_rear_right_exterior',
   '04_rear_exterior','05_rear_left_exterior','06_left_side_exterior','07_front_left_exterior',
   '08_wheel_front_left','09_wheel_front_right','10_wheel_rear_right','11_wheel_rear_left',
   '12_cabin_front_airbags','13_instrument_cluster_odometer','14_physical_vin','15_license_and_insurance_docs'
  ]
  WHEN 'claims2car-16-v2' THEN ARRAY[
   '00_front_exterior','01_front_right_exterior','02_right_side_exterior','03_rear_right_exterior',
   '04_rear_exterior','05_rear_left_exterior','06_left_side_exterior','07_front_left_exterior',
   '08_front_left_structural','09_front_right_structural','10_rear_right_structural','11_rear_left_structural',
   '12_front_cabin_restraints','13_rear_cabin_restraints','14_instrument_cluster_telemetry','15_vehicle_identity_vin'
  ]
  WHEN 'claims2car-12-v1' THEN ARRAY[
   'vin_ocr','doc_ocr','front','front_left','driver_side','rear_left',
   'rear','rear_right','passenger_side','front_right','interior_front','undercarriage_engine'
  ]
  ELSE NULL
 END;
 IF expected_slot_names IS NULL THEN RAISE EXCEPTION 'UNSUPPORTED_CAPTURE_PROTOCOL'; END IF;
 expected_slots:=cardinality(expected_slot_names);
 SELECT array_agg(value ORDER BY value) INTO expected_slot_set
 FROM unnest(expected_slot_names) AS expected(value);
 SELECT array_agg(value ORDER BY value) INTO seal_ids
 FROM jsonb_array_elements_text(seal_payload->'artifact_ids') AS item(value);
 WITH latest AS (
  SELECT DISTINCT ON (payload_json::jsonb->>'slot') payload_json::jsonb AS payload
  FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session
    AND sequence<seal_row.sequence AND kind='ARTIFACT_REGISTERED'
  ORDER BY payload_json::jsonb->>'slot',sequence DESC
 )
 SELECT array_agg(payload->>'artifact_id' ORDER BY payload->>'artifact_id'),
        array_agg(payload->>'slot' ORDER BY payload->>'slot'),
        count(*),count(DISTINCT payload->>'artifact_id')
 INTO latest_ids,latest_slots,latest_count,unique_latest_count
 FROM latest;
 IF latest_count IS DISTINCT FROM expected_slots
    OR unique_latest_count IS DISTINCT FROM expected_slots
    OR cardinality(seal_ids) IS DISTINCT FROM expected_slots
    OR seal_ids IS DISTINCT FROM latest_ids
    OR latest_slots IS DISTINCT FROM expected_slot_set THEN
  RAISE EXCEPTION 'SEALED_ARTIFACT_SET_MISMATCH';
 END IF;
 SELECT EXISTS(SELECT 1 FROM faos.manifest_roots
   WHERE tenant_id=p_tenant AND session_id=p_session AND seal_event_id=p_seal)
 INTO existing_root;
 IF NOT existing_root AND seal_row.sequence IS DISTINCT FROM
   (SELECT max(sequence) FROM faos.events WHERE tenant_id=p_tenant AND session_id=p_session) THEN
  RAISE EXCEPTION 'SEAL_NOT_CURRENT_EVENT';
 END IF;
 RETURN faos.register_manifest_root(p_tenant,p_session,p_seal,p_digest,p_version);
END
$capture_register$;

GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.register_manifest_root_from_capture(uuid,text,text,text,text,text,uuid)
 OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
REVOKE ALL ON FUNCTION faos.register_manifest_root_from_capture(uuid,text,text,text,text,text,uuid)
 FROM PUBLIC,faos_fixture;
GRANT EXECUTE ON FUNCTION faos.register_manifest_root_from_capture(uuid,text,text,text,text,text,uuid)
 TO faos_app;
