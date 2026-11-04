-- 0016_idempotency_keys.sql
-- Explicit idempotency keys for write endpoints.
-- Does not touch sealing or evidence tables.

CREATE TABLE IF NOT EXISTS faos.idempotency_keys (
  tenant_id uuid NOT NULL,
  key text NOT NULL,
  session_id uuid,
  response_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, key)
);

ALTER TABLE faos.idempotency_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON faos.idempotency_keys
  USING (tenant_id = current_setting('faos.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('faos.tenant_id')::uuid);
