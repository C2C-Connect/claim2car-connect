-- 0012_location_geometry.sql
-- Add geometry for capacity-aware spatial routing. Does not touch sealing or evidence.

ALTER TABLE faos.dealer_locations
  ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);

CREATE INDEX IF NOT EXISTS dealer_locations_geom_idx
  ON faos.dealer_locations USING GIST (geom);
