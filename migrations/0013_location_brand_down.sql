-- 0013_location_brand_down.sql
-- Reverse brand column addition.

ALTER TABLE faos.dealer_locations
  DROP CONSTRAINT IF EXISTS dealer_locations_brand_not_empty;

DROP INDEX IF EXISTS dealer_locations_brand_idx;

ALTER TABLE faos.dealer_locations
  DROP COLUMN IF EXISTS brand;
