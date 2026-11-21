-- Durable, deduplicated Square Sandbox payment webhook receipt and reconciliation.
-- Webhook processing records provider facts; it does not settle/post the financial ledger.
ALTER TABLE faos.square_sandbox_payment_intents
 ADD COLUMN provider_payment_id text,
 ADD CONSTRAINT square_sandbox_payment_intents_payment_id_unique UNIQUE(provider_payment_id);

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
CREATE POLICY writer_square_sandbox_webhook_receipts ON faos.square_sandbox_webhook_receipts
 TO faos_writer USING(true) WITH CHECK(true);
REVOKE ALL ON faos.square_sandbox_webhook_receipts FROM PUBLIC,faos_app,faos_fixture;
GRANT SELECT,INSERT,UPDATE ON faos.square_sandbox_webhook_receipts TO faos_writer;

CREATE FUNCTION faos.reconcile_square_sandbox_webhook(
 p_event_id text,p_event_type text,p_payment_id text,p_order_id text,
 p_status text,p_amount bigint,p_currency text,p_event_created_at timestamptz,
 p_payload_sha256 text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE receipt faos.square_sandbox_webhook_receipts%ROWTYPE;
        intent faos.square_sandbox_payment_intents%ROWTYPE;
        next_status text;
BEGIN
 IF p_event_id IS NULL OR length(trim(p_event_id))=0 OR length(p_event_id)>128
 OR p_event_type NOT IN ('payment.created','payment.updated')
 OR p_payment_id IS NULL OR length(trim(p_payment_id))=0 OR length(p_payment_id)>128
 OR p_order_id IS NULL OR length(trim(p_order_id))=0 OR length(p_order_id)>128
 OR p_status NOT IN ('APPROVED','COMPLETED','CANCELED','FAILED')
 OR p_amount IS NULL OR p_amount<=0 OR p_currency IS DISTINCT FROM 'USD'
 OR p_event_created_at IS NULL OR p_payload_sha256 !~ '^[0-9a-f]{64}$'
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

 SELECT * INTO intent FROM faos.square_sandbox_payment_intents
  WHERE provider_order_id=p_order_id FOR UPDATE;
 IF NOT FOUND THEN
  UPDATE faos.square_sandbox_webhook_receipts SET reconciliation_status='UNMATCHED_ORDER'
   WHERE provider_event_id=p_event_id;
  RETURN 'UNMATCHED_ORDER';
 END IF;
 IF p_amount<>intent.amount_cents OR p_currency<>intent.currency THEN
  UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=intent.tenant_id,
   payment_intent_id=intent.payment_intent_id,reconciliation_status='AMOUNT_MISMATCH'
   WHERE provider_event_id=p_event_id;
  RETURN 'AMOUNT_MISMATCH';
 END IF;
 IF intent.provider_payment_id IS NOT NULL AND intent.provider_payment_id<>p_payment_id THEN
  UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=intent.tenant_id,
   payment_intent_id=intent.payment_intent_id,reconciliation_status='PAYMENT_ID_CONFLICT'
   WHERE provider_event_id=p_event_id;
  RETURN 'PAYMENT_ID_CONFLICT';
 END IF;
 IF EXISTS(SELECT 1 FROM faos.square_sandbox_payment_intents
    WHERE provider_payment_id=p_payment_id
      AND (tenant_id,payment_intent_id)<>(intent.tenant_id,intent.payment_intent_id)) THEN
  UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=intent.tenant_id,
   payment_intent_id=intent.payment_intent_id,reconciliation_status='PAYMENT_ID_CONFLICT'
   WHERE provider_event_id=p_event_id;
  RETURN 'PAYMENT_ID_CONFLICT';
 END IF;

 next_status:=CASE p_status WHEN 'APPROVED' THEN 'AUTHORIZED'
  WHEN 'COMPLETED' THEN 'PAID' WHEN 'CANCELED' THEN 'CANCELED' WHEN 'FAILED' THEN 'FAILED' END;
 -- Set tenant context only after resolving the order to a durable intent. This
 -- is inside a SECURITY DEFINER function and never accepts caller-supplied tenant.
 PERFORM set_config('faos.tenant_id',intent.tenant_id::text,true);
 IF intent.status<>'PAID' AND p_event_created_at>=intent.updated_at THEN
  UPDATE faos.square_sandbox_payment_intents
   SET provider_payment_id=p_payment_id,status=next_status,updated_at=p_event_created_at
   WHERE tenant_id=intent.tenant_id AND payment_intent_id=intent.payment_intent_id;
 ELSE
  UPDATE faos.square_sandbox_payment_intents
   SET provider_payment_id=COALESCE(provider_payment_id,p_payment_id)
   WHERE tenant_id=intent.tenant_id AND payment_intent_id=intent.payment_intent_id;
  IF intent.status='PAID' OR p_event_created_at<intent.updated_at THEN
   UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=intent.tenant_id,
    payment_intent_id=intent.payment_intent_id,reconciliation_status='STALE_EVENT'
    WHERE provider_event_id=p_event_id;
   RETURN 'STALE_EVENT';
  END IF;
 END IF;
 UPDATE faos.square_sandbox_webhook_receipts SET tenant_id=intent.tenant_id,
  payment_intent_id=intent.payment_intent_id,reconciliation_status='RECONCILED',reconciled_at=now()
  WHERE provider_event_id=p_event_id;
 RETURN 'RECONCILED';
END $$;
REVOKE ALL ON FUNCTION faos.reconcile_square_sandbox_webhook(text,text,text,text,text,bigint,text,timestamptz,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.reconcile_square_sandbox_webhook(text,text,text,text,text,bigint,text,timestamptz,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.reconcile_square_sandbox_webhook(text,text,text,text,text,bigint,text,timestamptz,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
