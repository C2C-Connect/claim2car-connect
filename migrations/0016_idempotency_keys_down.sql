-- 0016_idempotency_keys_down.sql

DROP POLICY IF EXISTS tenant_isolation ON faos.idempotency_keys;
DROP TABLE IF EXISTS faos.idempotency_keys;
