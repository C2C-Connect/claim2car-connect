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
 FOREIGN KEY(tenant_id,source_session_id)
   REFERENCES faos.vehicle_identity_sources(tenant_id,source_session_id),
 CHECK(attributes_json IS NULL OR jsonb_typeof(attributes_json)='object'),
 CHECK((decode_status='REVOKED' AND revoked_at IS NOT NULL AND attributes_json IS NULL)
    OR (decode_status<>'REVOKED' AND revoked_at IS NULL)),
 CHECK((decode_status IN ('DECODED','PARTIAL') AND response_sha256 IS NOT NULL AND attributes_json IS NOT NULL)
    OR (decode_status='ERROR' AND attributes_json IS NOT NULL)
    OR decode_status='REVOKED')
);
CREATE INDEX vehicle_decode_latest_idx
 ON faos.vehicle_decode_snapshots(tenant_id,vehicle_id,recorded_at DESC);

ALTER TABLE faos.vehicle_decode_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.vehicle_decode_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY app_tenant ON faos.vehicle_decode_snapshots TO faos_app
 USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_tenant ON faos.vehicle_decode_snapshots TO faos_writer
 USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.vehicle_decode_snapshots FROM PUBLIC,faos_app,faos_writer;
GRANT SELECT ON faos.vehicle_decode_snapshots TO faos_app;
GRANT SELECT,INSERT,UPDATE ON faos.vehicle_decode_snapshots TO faos_writer;
