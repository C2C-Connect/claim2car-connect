-- Dispatch routing schema (Slice 7): synthetic road networks for pgRouting.
-- Tables hold synthetic test/demo networks only; production networks are a
-- separately reviewed provisioning step.
CREATE SCHEMA IF NOT EXISTS dispatch;
REVOKE ALL ON SCHEMA dispatch FROM PUBLIC;
GRANT USAGE ON SCHEMA dispatch TO faos_app, faos_fixture;
CREATE TABLE dispatch.network_nodes(
 node_id bigint PRIMARY KEY,
 label text NOT NULL,
 lon double precision NOT NULL CHECK (lon BETWEEN -180 AND 180),
 lat double precision NOT NULL CHECK (lat BETWEEN -90 AND 90));
CREATE TABLE dispatch.network_edges(
 edge_id bigint PRIMARY KEY,
 source bigint NOT NULL REFERENCES dispatch.network_nodes(node_id),
 target bigint NOT NULL REFERENCES dispatch.network_nodes(node_id),
 cost_minutes double precision NOT NULL CHECK (cost_minutes > 0),
 reverse_cost_minutes double precision CHECK (reverse_cost_minutes IS NULL OR reverse_cost_minutes > 0),
 CHECK (source <> target));
CREATE INDEX dispatch_network_edges_source_idx ON dispatch.network_edges(source);
CREATE INDEX dispatch_network_edges_target_idx ON dispatch.network_edges(target);
GRANT SELECT, INSERT, DELETE ON dispatch.network_nodes, dispatch.network_edges TO faos_app, faos_fixture;
