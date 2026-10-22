-- First bounded timestamp remediation: PostgreSQL input validity only.
-- Does not enforce full Python ISO/timezone syntax parity or canonical JSON.
-- Existing invalid rows block migration; never silently rewrite event history.
ALTER TABLE faos.events ADD CONSTRAINT event_timestamp_input_valid
 CHECK (pg_catalog.pg_input_is_valid(occurred_at, 'timestamp with time zone'));
