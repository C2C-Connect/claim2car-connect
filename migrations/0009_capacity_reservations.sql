-- 0009_capacity_reservations.sql
-- Transactional capacity reservations. Does not touch sealing or evidence tables.

CREATE TABLE faos.location_capacity (
  tenant_id uuid NOT NULL,
  location_id uuid NOT NULL,
  capacity integer NOT NULL CHECK (capacity >= 0),
  PRIMARY KEY (tenant_id, location_id),
  FOREIGN KEY (tenant_id, location_id) REFERENCES faos.dealer_locations(tenant_id, location_id) ON DELETE RESTRICT
);

CREATE TABLE faos.capacity_reservations (
  tenant_id uuid NOT NULL,
  reservation_id uuid NOT NULL,
  location_id uuid NOT NULL,
  request_digest text NOT NULL,
  status text NOT NULL CHECK (status IN ('ACTIVE', 'EXPIRED', 'RELEASED')),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, reservation_id),
  UNIQUE (tenant_id, location_id, request_digest),
  FOREIGN KEY (tenant_id, location_id) REFERENCES faos.dealer_locations(tenant_id, location_id) ON DELETE RESTRICT
);

CREATE INDEX capacity_reservations_active_idx
  ON faos.capacity_reservations (tenant_id, location_id)
  WHERE status = 'ACTIVE';

-- RLS
ALTER TABLE faos.location_capacity ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.location_capacity FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.capacity_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.capacity_reservations FORCE ROW LEVEL SECURITY;

CREATE POLICY app_tenant ON faos.location_capacity TO faos_app
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());
CREATE POLICY fixture_tenant ON faos.location_capacity TO faos_fixture
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());

CREATE POLICY app_tenant ON faos.capacity_reservations TO faos_app
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());
CREATE POLICY fixture_tenant ON faos.capacity_reservations TO faos_fixture
  USING (tenant_id = faos.tenant_id()) WITH CHECK (tenant_id = faos.tenant_id());

GRANT SELECT, INSERT, UPDATE ON faos.location_capacity TO faos_app;
GRANT SELECT, INSERT ON faos.location_capacity TO faos_fixture;
GRANT SELECT, INSERT, UPDATE ON faos.capacity_reservations TO faos_app;
GRANT SELECT, INSERT ON faos.capacity_reservations TO faos_fixture;
