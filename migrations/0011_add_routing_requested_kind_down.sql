-- Reverse of 0011_add_routing_requested_kind.sql
-- Restores the original events_kind_check without ROUTING_REQUESTED.

ALTER TABLE faos.events DROP CONSTRAINT IF EXISTS events_kind_check;

ALTER TABLE faos.events ADD CONSTRAINT events_kind_check CHECK (
  kind IN (
    'SESSION_CREATED',
    'CONSENT_RECORDED',
    'VEHICLE_RECORDED',
    'ARTIFACT_REGISTERED',
    'QUALITY_RECORDED',
    'MANIFEST_SEALED',
    'REVIEW_RECORDED'
  )
);
