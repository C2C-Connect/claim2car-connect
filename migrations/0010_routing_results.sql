-- 0010_routing_results.sql
-- Routing provenance and explicit unresolved state. Does not touch sealing or evidence tables.

CREATE TABLE faos.routing_policies (
  tenant_id uuid NOT NULL,
  policy_id uuid NOT NULL,
  version text NOT NULL,
  service_radius_meters integer NOT NULL CHECK (service_radius_meters > 0),
  expiry_window_seconds integer NOT NULL CHECK (expiry_window_seconds > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, policy_id),
  UNIQUE (tenant_id, version)
);

CREATE TABLE faos.routing_results (
  tenant_id uuid NOT NULL,
  result_id uuid NOT NULL,
  request_digest text NOT NULL,
  policy_version text NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('ROUTED', 'UNRESOLVED', 'HUMAN_REVIEW')),
  selected_location_id uuid,
  candidates_json jsonb NOT NULL,
  exclusion_reasons_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, result_id),
  UNIQUE (tenant_id, request_digest),
  FOREIGN KEY (tenant_id, selected_location_id) REFERENCES faos.dealer_locations(tenant_id, location_id) ON DELETE RESTRICT
);

-- Numeric tier rank (not alphabetical)
ALTER TABLE faos.dealer_locations ADD COLUMN tier_rank integer NOT NULL DEFAULT 0;

-- RLS
ALTER TABLE faos.routing_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.routing_policies FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.routing_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.routing_results FORCE ROW LEVEL SECURITY;

CREATE POLICY app_tenant ON faos.routing_policies TO faos_app
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());
CREATE POLICY fixture_tenant ON faos.routing_policies TO faos_fixture
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());

CREATE POLICY app_tenant ON faos.routing_results TO faos_app
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());
CREATE POLICY fixture_tenant ON faos.routing_results TO faos_fixture
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());

GRANT SELECT, INSERT ON faos.routing_policies TO faos_app, faos_fixture;
GRANT SELECT, INSERT ON faos.routing_results TO faos_app, faos_fixture;
