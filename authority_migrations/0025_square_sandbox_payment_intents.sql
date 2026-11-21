-- Durable, tenant-scoped registration of Sandbox checkout links.
-- Provider payments are not ledger settlement; this table only records the external checkout intent.
CREATE TABLE faos.square_sandbox_payment_intents(
 tenant_id uuid NOT NULL,
 payment_intent_id uuid NOT NULL,
 obligation_entry_id text NOT NULL,
 session_id text NOT NULL,
 acceptance_id text NOT NULL,
 partner_org_id text NOT NULL,
 provider text NOT NULL CHECK(provider='SQUARE_SANDBOX'),
 provider_link_id text NOT NULL CHECK(length(trim(provider_link_id)) BETWEEN 1 AND 128),
 provider_order_id text NOT NULL CHECK(length(trim(provider_order_id)) BETWEEN 1 AND 128),
 checkout_url text NOT NULL CHECK(length(checkout_url) BETWEEN 1 AND 2048),
 idempotency_key text NOT NULL CHECK(length(trim(idempotency_key)) BETWEEN 1 AND 192),
 amount_cents bigint NOT NULL CHECK(amount_cents=27500),
 currency text NOT NULL CHECK(currency='USD'),
 status text NOT NULL DEFAULT 'LINK_CREATED' CHECK(status IN ('LINK_CREATED','AUTHORIZED','PAID','FAILED','CANCELED')),
 created_by text NOT NULL CHECK(length(trim(created_by)) BETWEEN 1 AND 128),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,payment_intent_id),
 UNIQUE(tenant_id,idempotency_key),
 UNIQUE(tenant_id,obligation_entry_id),
 UNIQUE(provider_link_id),
 UNIQUE(provider_order_id),
 FOREIGN KEY(tenant_id,obligation_entry_id) REFERENCES faos.financial_ledger_entries(tenant_id,entry_id),
 FOREIGN KEY(tenant_id,session_id) REFERENCES faos.sessions(tenant_id,session_id)
);

ALTER TABLE faos.square_sandbox_payment_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.square_sandbox_payment_intents FORCE ROW LEVEL SECURITY;
CREATE POLICY app_square_sandbox_payment_intents ON faos.square_sandbox_payment_intents TO faos_app
 USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_square_sandbox_payment_intents ON faos.square_sandbox_payment_intents TO faos_writer
 USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.square_sandbox_payment_intents FROM PUBLIC,faos_app,faos_fixture;
GRANT SELECT ON faos.square_sandbox_payment_intents TO faos_app;
GRANT SELECT,INSERT,UPDATE ON faos.square_sandbox_payment_intents TO faos_writer;

CREATE FUNCTION faos.register_square_sandbox_payment_intent(
 p_tenant uuid,p_payment_intent uuid,p_obligation_entry text,
 p_provider_link text,p_provider_order text,p_checkout_url text,
 p_idempotency text,p_actor text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE existing faos.square_sandbox_payment_intents%ROWTYPE;
        obligation faos.financial_ledger_entries%ROWTYPE;
        expected_lines jsonb; actual_lines jsonb;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_payment_intent IS NULL OR p_obligation_entry IS NULL OR length(trim(p_obligation_entry))=0
 OR p_provider_link IS NULL OR length(trim(p_provider_link))=0
 OR p_provider_order IS NULL OR length(trim(p_provider_order))=0
 OR p_idempotency IS NULL OR length(trim(p_idempotency))=0
 OR length(p_idempotency)>192 OR p_actor IS NULL OR length(trim(p_actor))=0
 OR p_checkout_url IS NULL OR length(trim(p_checkout_url))=0
 OR length(p_checkout_url)>2048
 OR p_checkout_url !~ '^https://(sandbox\.square\.link|square\.link|checkout\.square\.site)/[^#]+$'
 THEN RAISE EXCEPTION 'INVALID_SQUARE_SANDBOX_PAYMENT_INTENT'; END IF;

 SELECT * INTO existing FROM faos.square_sandbox_payment_intents
  WHERE tenant_id=p_tenant AND idempotency_key=p_idempotency FOR UPDATE;
 IF FOUND THEN
  IF ROW(existing.obligation_entry_id,existing.provider_link_id,existing.provider_order_id,
         existing.checkout_url,existing.created_by)
     IS DISTINCT FROM ROW(p_obligation_entry,p_provider_link,p_provider_order,p_checkout_url,p_actor) THEN
   RAISE EXCEPTION 'SQUARE_PAYMENT_IDEMPOTENCY_CONFLICT';
  END IF;
  RETURN 'DUPLICATE';
 END IF;
 SELECT * INTO obligation FROM faos.financial_ledger_entries
  WHERE tenant_id=p_tenant AND entry_id=p_obligation_entry;
 IF NOT FOUND OR obligation.entry_kind<>'OBLIGATION_BOOKED'
 OR obligation.fee_type<>'REPAIR_SHOP_ACCEPTANCE_FEE'
 OR obligation.amount_cents<>27500 OR obligation.currency<>'USD_CENTS'
 OR obligation.partner_org_id IS NULL OR obligation.acceptance_id IS NULL
 THEN RAISE EXCEPTION 'SHOP_ACCEPTANCE_OBLIGATION_NOT_ELIGIBLE'; END IF;
 IF EXISTS(SELECT 1 FROM faos.financial_ledger_entries
   WHERE tenant_id=p_tenant AND reverses_entry_id=p_obligation_entry)
 THEN RAISE EXCEPTION 'SHOP_ACCEPTANCE_OBLIGATION_REVERSED'; END IF;
 expected_lines:=jsonb_build_array(
  jsonb_build_object('account_code','AR:SHOP:'||obligation.partner_org_id,'direction','DEBIT','amount_cents',27500),
  jsonb_build_object('account_code','REV:REPAIR_SHOP_ACCEPTANCE','direction','CREDIT','amount_cents',27500));
 SELECT COALESCE(jsonb_agg(jsonb_build_object('account_code',account_code,
   'direction',direction,'amount_cents',amount_cents) ORDER BY line_number),'[]'::jsonb)
 INTO actual_lines FROM faos.financial_ledger_postings
 WHERE tenant_id=p_tenant AND entry_id=p_obligation_entry;
 IF actual_lines IS DISTINCT FROM expected_lines THEN
  RAISE EXCEPTION 'SHOP_ACCEPTANCE_OBLIGATION_POSTINGS_INVALID';
 END IF;
 IF EXISTS(SELECT 1 FROM faos.square_sandbox_payment_intents
   WHERE tenant_id=p_tenant AND obligation_entry_id=p_obligation_entry)
 THEN RAISE EXCEPTION 'SQUARE_PAYMENT_INTENT_ALREADY_EXISTS'; END IF;
 INSERT INTO faos.square_sandbox_payment_intents(
  tenant_id,payment_intent_id,obligation_entry_id,session_id,acceptance_id,partner_org_id,
  provider,provider_link_id,provider_order_id,checkout_url,idempotency_key,
  amount_cents,currency,status,created_by)
 VALUES(p_tenant,p_payment_intent,obligation.entry_id,obligation.session_id,obligation.acceptance_id,
  obligation.partner_org_id,'SQUARE_SANDBOX',p_provider_link,p_provider_order,p_checkout_url,
  p_idempotency,27500,'USD','LINK_CREATED',p_actor);
 RETURN 'CREATED';
END $$;
REVOKE ALL ON FUNCTION faos.register_square_sandbox_payment_intent(uuid,uuid,text,text,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.register_square_sandbox_payment_intent(uuid,uuid,text,text,text,text,text,text) TO faos_app;
ALTER FUNCTION faos.register_square_sandbox_payment_intent(uuid,uuid,text,text,text,text,text,text) OWNER TO faos_writer;
