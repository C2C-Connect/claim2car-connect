-- 0014_add_dealer_decision_kinds_down.sql
-- Reverse the addition of dealer decision event kinds.

ALTER TABLE faos.events DROP CONSTRAINT IF EXISTS events_kind_check;

ALTER TABLE faos.events ADD CONSTRAINT events_kind_check CHECK (
  kind IN (
    'SESSION_CREATED',
    'CONSENT_RECORDED',
    'VEHICLE_RECORDED',
    'ARTIFACT_REGISTERED',
    'QUALITY_RECORDED',
    'MANIFEST_SEALED',
    'REVIEW_RECORDED',
    'ROUTING_REQUESTED'
  )
);
