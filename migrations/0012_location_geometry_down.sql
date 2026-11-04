-- Reverse of 0012_location_geometry.sql

DROP INDEX IF EXISTS faos.dealer_locations_geom_idx;
ALTER TABLE faos.dealer_locations DROP COLUMN IF EXISTS geom;
