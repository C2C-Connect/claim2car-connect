-- 0013_location_brand.sql
-- Add brand affinity for brand-matched routing (Ford to Ford, etc.).
-- Does not touch sealing or evidence.

ALTER TABLE faos.dealer_locations
  ADD COLUMN IF NOT EXISTS brand text;

ALTER TABLE faos.dealer_locations
  ADD CONSTRAINT dealer_locations_brand_not_empty
  CHECK (brand IS NULL OR length(trim(brand)) > 0);

CREATE INDEX IF NOT EXISTS dealer_locations_brand_idx
  ON faos.dealer_locations (tenant_id, brand);
