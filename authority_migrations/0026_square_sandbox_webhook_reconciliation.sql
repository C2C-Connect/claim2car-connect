-- Durable, deduplicated Square Sandbox payment webhook receipt and reconciliation.
-- Provider status is separate from financial ledger settlement.
CREATE TABLE faos.square_sandbox_payment_order_map(
 provider_order_id text PRIMARY KEY CHECK(length(trim(provider_order_id)) BETWEEN 1 AND 128),
 tenant_id uuid NOT NULL,
 payment_intent_id uuid NOT NULL,
 amount_cents bigint NOT NULL CHECK(amount_cents=27500),
 currency text NOT NULL CHECK(currency='USD'),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,payment_intent_id),
 FOREIGN KEY(tenant_id,payment_intent_id)
  REFERENCES faos.square_sandbox_payment_intents(tenant_id,payment_intent_id)
);
ALTER TABLE faos.square_sandbox_payment_order_map ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.square_sandbox_payment_order_map FORCE ROW LEVEL SECURITY;
CREATE POLICY writer_square_sandbox_payment_order_map ON faos.square_sandbox_payment_order_map
 TO faos_writer USING(true) WITH CHECK(true);
REVOKE ALL ON faos.square_sandbox_payment_order_map FROM PUBLIC,faos_app,faos_fixture;
GRANT SELECT,INSERT ON faos.square_sandbox_payment_order_map TO faos_writer;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER TABLE faos.square_sandbox_payment_order_map OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
INSERT INTO faos.square_sandbox_payment_order_map(provider_order_id,tenant_id,payment_intent_id,amount_cents,currency)
 SELECT provider_order_id,tenant_id,payment_intent_id,amount_cents,currency
 FROM faos.square_sandbox_payment_intents;

CREATE FUNCTION faos.capture_square_payment_order_mapping() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
BEGIN
 INSERT INTO faos.square_sandbox_payment_order_map(provider_order_id,tenant_id,payment_intent_id,amount_cents,currency)
 VALUES(NEW.provider_order_id,NEW.tenant_id,NEW.payment_intent_id,NEW.amount_cents,NEW.currency);
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION faos.capture_square_payment_order_mapping() FROM PUBLIC;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.capture_square_payment_order_mapping() OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
CREATE TRIGGER square_sandbox_payment_order_map_insert
 AFTER INSERT ON faos.square_sandbox_payment_intents
 FOR EACH ROW EXECUTE FUNCTION faos.capture_square_payment_order_mapping();

CREATE TABLE faos.square_sandbox_payment_reconciliations(
 tenant_id uuid NOT NULL,
 payment_intent_id uuid NOT NULL,
 provider_payment_id text NOT NULL CHECK(length(trim(provider_payment_id)) BETWEEN 1 AND 128),
 status text NOT NULL CHECK(status IN ('AUTHORIZED','PAID','FAILED','CANCELED')),
 provider_event_id text NOT NULL CHECK(length(trim(provider_event_id)) BETWEEN 1 AND 128),
 updated_at timestamptz NOT NULL,
 PRIMARY KEY(tenant_id,payment_intent_id),
 UNIQUE(provider_payment_id),
 FOREIGN KEY(tenant_id,payment_intent_id)
  REFERENCES faos.square_sandbox_payment_intents(tenant_id,payment_intent_id)
);
ALTER TABLE faos.square_sandbox_payment_reconciliations ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.square_sandbox_payment_reconciliations FORCE ROW LEVEL SECURITY;
CREATE POLICY app_square_sandbox_payment_reconciliations ON faos.square_sandbox_payment_reconciliations
 TO faos_app USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_square_sandbox_payment_reconciliations ON faos.square_sandbox_payment_reconciliations
 TO faos_writer USING(true) WITH CHECK(true);
REVOKE ALL ON faos.square_sandbox_payment_reconciliations FROM PUBLIC,faos_app,faos_fixture;
GRANT SELECT ON faos.square_sandbox_payment_reconciliations TO faos_app;
GRANT SELECT,INSERT,UPDATE ON faos.square_sandbox_payment_reconciliations TO faos_writer;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER TABLE faos.square_sandbox_payment_reconciliations OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;

CREATE TABLE faos.square_sandbox_webhook_receipts(
 provider_event_id text PRIMARY KEY CHECK(length(trim(provider_event_id)) BETWEEN 1 AND 128),
 event_type text NOT NULL CHECK(event_type IN ('payment.created','payment.updated')),
 provider_payment_id text NOT NULL CHECK(length(trim(provider_payment_id)) BETWEEN 1 AND 128),
 provider_order_id text NOT NULL CHECK(length(trim(provider_order_id)) BETWEEN 1 AND 128),
 provider_status text NOT NULL CHECK(provider_status IN ('APPROVED','COMPLETED','CANCELED','FAILED')),
 amount_cents bigint NOT NULL CHECK(amount_cents>0),
 currency text NOT NULL CHECK(currency='USD'),
 event_created_at timestamptz NOT NULL,
 payload_sha256 text NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 tenant_id uuid,
 payment_intent_id uuid,
 reconciliation_status text NOT NULL DEFAULT 'RECEIVED'
  CHECK(reconciliation_status IN ('RECEIVED','RECONCILED','UNMATCHED_ORDER','AMOUNT_MISMATCH','PAYMENT_ID_CONFLICT','STALE_EVENT')),
 received_at timestamptz NOT NULL DEFAULT now(),
 reconciled_at timestamptz,
 CHECK((tenant_id IS NULL)=(payment_intent_id IS NULL))
);
ALTER TABLE faos.square_sandbox_webhook_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.square_sandbox_webhook_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY app_square_sandbox_webhook_receipts ON faos.square_sandbox_webhook_receipts
 TO faos_app USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_square_sandbox_webhook_receipts ON faos.square_sandbox_webhook_receipts
 TO faos_writer USING(true) WITH CHECK(true);
REVOKE ALL ON faos.square_sandbox_webhook_receipts FROM PUBLIC,faos_app,faos_fixture;
GRANT SELECT ON faos.square_sandbox_webhook_receipts TO faos_app;
GRANT SELECT,INSERT,UPDATE ON faos.square_sandbox_webhook_receipts TO faos_writer;
GRANT CREATE ON SCHEMA faos TO faos_writer;

CREATE FUNCTION faos.reconcile_square_sandbox_webhook(
 p_event_id text,p_event_type text,p_payment_id text,p_order_id text,
 p_status text,p_amount bigint,p_currency text,p_event_created_at timestamptz,
 p_payload_sha256 text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE receipt faos.square_sandbox_webhook_receipts%ROWTYPE;
        order_mapping faos.square_sandbox_payment_order_map%ROWTYPE;
        current_state faos.square_sandbox_payment_reconciliations%ROWTYPE;
        next_status text;
        state_found boolean;
BEGIN
 IF p_event_id IS NULL OR length(trim(p_event_id))=0 OR length(p_event_id)>128
 OR p_event_type IS NULL OR p_event_type NOT IN ('payment.created','payment.updated')
 OR p_payment_id IS NULL OR length(trim(p_payment_id))=0 OR length(p_payment_id)>128
 OR p_order_id IS NULL OR length(trim(p_order_id))=0 OR length(p_order_id)>128
 OR p_status IS NULL OR p_status NOT IN ('APPROVED','COMPLETED','CANCELED','FAILED')
 OR p_amount IS NULL OR p_amount<=0 OR p_currency IS DISTINCT FROM 'USD'
 OR p_event_created_at IS NULL OR p_payload_sha256 IS NULL
 OR p_payload_sha256 !~ '^[0-9a-f]{64}$'
 THEN RAISE EXCEPTION 'INVALID_SQUARE_SANDBOX_WEBHOOK_RECEIPT'; END IF;

 INSERT INTO faos.square_sandbox_webhook_receipts(
  provider_event_id,event_type,provider_payment_id,provider_order_id,provider_status,
  amount_cents,currency,event_created_at,payload_sha256)
 VALUES(p_event_id,p_event_type,p_payment_id,p_order_id,p_status,p_amount,p_currency,
        p_event_created_at,p_payload_sha256)
 ON CONFLICT(provider_event_id) DO NOTHING;
 SELECT * INTO receipt FROM faos.square_sandbox_webhook_receipts
  WHERE provider_event_id=p_event_id FOR UPDATE;
 IF receipt.payload_sha256 IS DISTINCT FROM p_payload_sha256
 OR ROW(receipt.event_type,receipt.provider_payment_id,receipt.provider_order_id,
        receipt.provider_status,receipt.amount_cents,receipt.currency,receipt.event_created_at)
    IS DISTINCT FROM ROW(p_event_type,p_payment_id,p_order_id,p_status,p_amount,p_currency,p_event_created_at)
 THEN RAISE EXCEPTION 'SQUARE_WEBHOOK_EVENT_ID_CONFLICT'; END IF;
 IF receipt.reconciliation_status='RECONCILED' THEN RETURN 'DUPLICATE'; END IF;

 SELECT * INTO order_mapping FROM faos.square_sandbox_payment_order_map
  WHERE provider_order_id=p_order_id FOR UPDATE;
 IF NOT FOUND THEN
  UPDATE faos.square_sandbox_webhook_receipts SET reconciliation_status='UNMATCHED_ORDER'
   WHERE provider_event_id=p_event_id;
  RETURN 'UNMATCHED_ORDER';
 END IF;
 IF p_amount<>order_mapping.amount_cents OR p_currency<>order_mapping.currency THEN
  UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=order_mapping.tenant_id,
   payment_intent_id=order_mapping.payment_intent_id,reconciliation_status='AMOUNT_MISMATCH'
   WHERE provider_event_id=p_event_id;
  RETURN 'AMOUNT_MISMATCH';
 END IF;
 SELECT * INTO current_state FROM faos.square_sandbox_payment_reconciliations
  WHERE tenant_id=order_mapping.tenant_id AND payment_intent_id=order_mapping.payment_intent_id FOR UPDATE;
 state_found:=FOUND;
 IF state_found AND current_state.provider_payment_id<>p_payment_id THEN
  UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=order_mapping.tenant_id,
   payment_intent_id=order_mapping.payment_intent_id,reconciliation_status='PAYMENT_ID_CONFLICT'
   WHERE provider_event_id=p_event_id;
  RETURN 'PAYMENT_ID_CONFLICT';
 END IF;
 IF EXISTS(SELECT 1 FROM faos.square_sandbox_payment_reconciliations
    WHERE provider_payment_id=p_payment_id
      AND (tenant_id,payment_intent_id)<>(order_mapping.tenant_id,order_mapping.payment_intent_id)) THEN
  UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=order_mapping.tenant_id,
   payment_intent_id=order_mapping.payment_intent_id,reconciliation_status='PAYMENT_ID_CONFLICT'
   WHERE provider_event_id=p_event_id;
  RETURN 'PAYMENT_ID_CONFLICT';
 END IF;
 next_status:=CASE p_status WHEN 'APPROVED' THEN 'AUTHORIZED'
  WHEN 'COMPLETED' THEN 'PAID' WHEN 'CANCELED' THEN 'CANCELED' WHEN 'FAILED' THEN 'FAILED' END;
 IF state_found AND (current_state.status='PAID' OR p_event_created_at<current_state.updated_at OR (p_event_created_at=current_state.updated_at AND next_status<>'PAID')) THEN
  UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=order_mapping.tenant_id,
   payment_intent_id=order_mapping.payment_intent_id,reconciliation_status='STALE_EVENT'
   WHERE provider_event_id=p_event_id;
  RETURN 'STALE_EVENT';
 END IF;
 INSERT INTO faos.square_sandbox_payment_reconciliations(
  tenant_id,payment_intent_id,provider_payment_id,status,provider_event_id,updated_at)
 VALUES(order_mapping.tenant_id,order_mapping.payment_intent_id,p_payment_id,next_status,p_event_id,p_event_created_at)
 ON CONFLICT(tenant_id,payment_intent_id) DO UPDATE SET
  provider_payment_id=excluded.provider_payment_id,status=excluded.status,
  provider_event_id=excluded.provider_event_id,updated_at=excluded.updated_at;
 UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=order_mapping.tenant_id,
  payment_intent_id=order_mapping.payment_intent_id,reconciliation_status='RECONCILED',reconciled_at=now()
  WHERE provider_event_id=p_event_id;
 RETURN 'RECONCILED';
END $$;
REVOKE ALL ON FUNCTION faos.reconcile_square_sandbox_webhook(text,text,text,text,text,bigint,text,timestamptz,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.reconcile_square_sandbox_webhook(text,text,text,text,text,bigint,text,timestamptz,text) TO faos_app;
ALTER FUNCTION faos.reconcile_square_sandbox_webhook(text,text,text,text,text,bigint,text,timestamptz,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
