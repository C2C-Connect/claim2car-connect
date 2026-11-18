-- Add separately consented, provenance-attributed NHTSA vehicle profiles.
-- Only normalized attributes and a response digest are retained; never raw VIN
-- or the provider's raw response. Profile records are not physics inputs.
ALTER TABLE faos.events DROP CONSTRAINT events_kind_check;
ALTER TABLE faos.events ADD CONSTRAINT events_kind_check CHECK(kind IN (
 'SESSION_CREATED','CONSENT_RECORDED','VEHICLE_RECORDED',
 'ARTIFACT_REGISTERED','QUALITY_RECORDED','MANIFEST_SEALED',
 'REVIEW_RECORDED','SESSION_ABORTED',
 'INCIDENT_INTAKE_CONSENT_RECORDED','INCIDENT_INTAKE_RECORDED',
 'VEHICLE_DECODE_CONSENT_RECORDED','VEHICLE_PROFILE_DECODED'
));

CREATE TABLE faos.vehicle_decode_snapshots (
 tenant_id uuid NOT NULL,
 vehicle_id uuid NOT NULL,
 source_session_id text NOT NULL,
 request_id uuid NOT NULL,
 provider text NOT NULL CHECK(provider='NHTSA_VPIC'),
 provider_api text NOT NULL CHECK(provider_api='DecodeVinValuesExtended'),
 requested_at timestamptz NOT NULL,
 response_sha256 text CHECK(response_sha256 IS NULL OR response_sha256 ~ '^[0-9a-f]{64}$'),
 decode_status text NOT NULL CHECK(decode_status IN ('DECODED','PARTIAL','ERROR','REVOKED')),
 decode_error_code text,
 attributes_json jsonb,
 recorded_by text NOT NULL CHECK(length(trim(recorded_by)) BETWEEN 1 AND 128),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 revoked_at timestamptz,
 PRIMARY KEY(tenant_id,request_id),
 FOREIGN KEY(tenant_id,vehicle_id) REFERENCES faos.vehicles(tenant_id,vehicle_id),
 FOREIGN KEY(tenant_id,source_session_id) REFERENCES faos.vehicle_identity_sources(tenant_id,source_session_id),
 CHECK(attributes_json IS NULL OR jsonb_typeof(attributes_json)='object'),
 CHECK((decode_status='REVOKED' AND revoked_at IS NOT NULL AND attributes_json IS NULL)
    OR (decode_status<>'REVOKED' AND revoked_at IS NULL)),
 CHECK((decode_status IN ('DECODED','PARTIAL') AND response_sha256 IS NOT NULL AND attributes_json IS NOT NULL)
    OR (decode_status='ERROR' AND attributes_json IS NOT NULL)
    OR decode_status='REVOKED')
);
CREATE INDEX vehicle_decode_latest_idx ON faos.vehicle_decode_snapshots(tenant_id,vehicle_id,recorded_at DESC);
ALTER TABLE faos.vehicle_decode_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.vehicle_decode_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY app_tenant ON faos.vehicle_decode_snapshots TO faos_app USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_tenant ON faos.vehicle_decode_snapshots TO faos_writer USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.vehicle_decode_snapshots FROM PUBLIC,faos_app,faos_writer;
GRANT SELECT ON faos.vehicle_decode_snapshots TO faos_app;
GRANT SELECT,INSERT,UPDATE ON faos.vehicle_decode_snapshots TO faos_writer;

CREATE FUNCTION faos.record_vehicle_decode_snapshot(
 p_tenant uuid,p_vehicle uuid,p_session text,p_request uuid,
 p_provider text,p_api text,p_requested_at timestamptz,p_response_sha256 text,
 p_status text,p_error text,p_attributes jsonb,p_actor text,p_vin_hmac_sha256 text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp AS $$
DECLARE capture_actor text; capture_payload jsonb; decode_actor text; decode_payload jsonb; source_owner text;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH'; END IF;
 IF p_provider IS DISTINCT FROM 'NHTSA_VPIC' OR p_api IS DISTINCT FROM 'DecodeVinValuesExtended'
    OR p_status NOT IN ('DECODED','PARTIAL','ERROR') OR p_requested_at IS NULL
    OR p_attributes IS NULL OR jsonb_typeof(p_attributes) IS DISTINCT FROM 'object'
    OR p_actor IS NULL OR length(trim(p_actor)) NOT BETWEEN 1 AND 128
    OR p_vin_hmac_sha256 IS NULL OR p_vin_hmac_sha256 !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'INVALID_VEHICLE_PROFILE_SNAPSHOT';
 END IF;
 SELECT actor,payload_json::jsonb INTO capture_actor,capture_payload FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session AND kind='CONSENT_RECORDED' ORDER BY sequence DESC LIMIT 1;
 IF capture_actor IS NULL OR capture_payload->>'accepted' IS DISTINCT FROM 'true'
    OR capture_payload->>'scope' IS DISTINCT FROM 'capture_review'
    OR capture_payload->>'disclosure_version' IS DISTINCT FROM 'disclosure-v1'
    OR capture_payload->>'owner_actor_id' IS DISTINCT FROM capture_actor THEN
  RAISE EXCEPTION 'ACTIVE_CAPTURE_OWNER_CONSENT_REQUIRED';
 END IF;
 SELECT actor,payload_json::jsonb INTO decode_actor,decode_payload FROM faos.events
  WHERE tenant_id=p_tenant AND session_id=p_session AND kind='VEHICLE_DECODE_CONSENT_RECORDED'
  ORDER BY sequence DESC LIMIT 1;
 IF decode_actor IS DISTINCT FROM capture_actor OR decode_payload->>'accepted' IS DISTINCT FROM 'true'
    OR decode_payload->>'scope' IS DISTINCT FROM 'nhtsa_vpic_decode'
    OR decode_payload->>'disclosure_version' IS DISTINCT FROM 'vehicle-decode-disclosure-v1' THEN
  RAISE EXCEPTION 'ACTIVE_VEHICLE_DECODE_CONSENT_REQUIRED';
 END IF;
 SELECT owner_actor_id INTO source_owner FROM faos.vehicle_identity_sources
  WHERE tenant_id=p_tenant AND vehicle_id=p_vehicle AND source_session_id=p_session
    AND owner_actor_id=capture_actor AND vin_hmac_sha256=p_vin_hmac_sha256 AND source_status='ACTIVE' FOR UPDATE;
 IF source_owner IS NULL THEN RAISE EXCEPTION 'ACTIVE_CONSENTED_VEHICLE_IDENTITY_REQUIRED'; END IF;
 IF NOT EXISTS(SELECT 1 FROM faos.claim_cases WHERE tenant_id=p_tenant AND capture_session_id=p_session AND created_by=p_actor) THEN
  RAISE EXCEPTION 'CAPTURE_AUTHORITY_DENIED';
 END IF;
 INSERT INTO faos.vehicle_decode_snapshots(
  tenant_id,vehicle_id,source_session_id,request_id,provider,provider_api,requested_at,response_sha256,
  decode_status,decode_error_code,attributes_json,recorded_by
 ) VALUES (p_tenant,p_vehicle,p_session,p_request,p_provider,p_api,p_requested_at,p_response_sha256,
  p_status,p_error,p_attributes,p_actor);
 RETURN 'ACCEPTED';
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'VEHICLE_PROFILE_REQUEST_CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.record_vehicle_decode_snapshot(uuid,uuid,text,uuid,text,text,timestamptz,text,text,text,jsonb,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.record_vehicle_decode_snapshot(uuid,uuid,text,uuid,text,text,timestamptz,text,text,text,jsonb,text,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.record_vehicle_decode_snapshot(uuid,uuid,text,uuid,text,text,timestamptz,text,text,text,jsonb,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;

CREATE FUNCTION faos.revoke_vehicle_decode_profiles(p_tenant uuid,p_session text,p_owner text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp AS $$
DECLARE changed integer := 0;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH'; END IF;
 IF NOT EXISTS(SELECT 1 FROM faos.claim_cases WHERE tenant_id=p_tenant AND capture_session_id=p_session AND owner_actor_id=p_owner) THEN
  RAISE EXCEPTION 'VEHICLE_DECODE_CONSENT_OWNER_REQUIRED';
 END IF;
 UPDATE faos.vehicle_decode_snapshots SET decode_status='REVOKED',attributes_json=NULL,revoked_at=clock_timestamp()
  WHERE tenant_id=p_tenant AND source_session_id=p_session AND decode_status IN ('DECODED','PARTIAL','ERROR');
 GET DIAGNOSTICS changed=ROW_COUNT;
 RETURN changed;
END $$;
REVOKE ALL ON FUNCTION faos.revoke_vehicle_decode_profiles(uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.revoke_vehicle_decode_profiles(uuid,text,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.revoke_vehicle_decode_profiles(uuid,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
