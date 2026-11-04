-- 0017_add_capture_vision_kinds.sql
-- Open the event journal to capture and vision outputs. Does not touch sealing tables.

ALTER TABLE faos.events DROP CONSTRAINT IF EXISTS events_kind_check;
ALTER TABLE faos.events ADD CONSTRAINT events_kind_check CHECK (kind IN (
  'SESSION_CREATED',
  'CONSENT_RECORDED',
  'VEHICLE_RECORDED',
  'ARTIFACT_REGISTERED',
  'QUALITY_RECORDED',
  'MANIFEST_SEALED',
  'REVIEW_RECORDED',
  'ROUTING_REQUESTED',
  'DEALER_ACCEPTED',
  'DEALER_PASSED',
  'SETTLEMENT_RECORDED',
  'VIN_DECODED',
  'DAMAGE_DETECTED',
  'PHYSICS_COMPUTED'
));
