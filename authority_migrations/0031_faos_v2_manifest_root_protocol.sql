-- Complete the FAOS 16-v2 manifest-root path.
-- Migration 0027 enabled v2 sessions and migration 0030 wired root registration
-- into the live seal transaction, but the original 0019 root constraint still
-- admitted only 12-v1 and 16-v1. Preserve historical protocol IDs and allow
-- v2 roots to be registered and independently verified.
ALTER TABLE faos.manifest_roots
  DROP CONSTRAINT manifest_roots_shot_list_version_check;

ALTER TABLE faos.manifest_roots
  ADD CONSTRAINT manifest_roots_shot_list_version_check
  CHECK (shot_list_version IN (
    'claims2car-12-v1',
    'claims2car-16-v1',
    'claims2car-16-v2'
  ));
