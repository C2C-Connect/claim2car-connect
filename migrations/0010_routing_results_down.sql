-- 0010_routing_results_down.sql
ALTER TABLE faos.dealer_locations DROP COLUMN IF EXISTS tier_rank;
DROP TABLE IF EXISTS faos.routing_results;
DROP TABLE IF EXISTS faos.routing_policies;
