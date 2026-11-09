-- Tenant-scoped append-only financial obligations and reversals.
CREATE TABLE faos.financial_ledger_entries(
 tenant_id uuid NOT NULL,
 entry_id text NOT NULL CHECK(length(trim(entry_id))>0),
 sequence bigint NOT NULL CHECK(sequence>0),
 idempotency_key text NOT NULL CHECK(length(trim(idempotency_key)) BETWEEN 1 AND 256),
 session_id text NOT NULL,
 entry_kind text NOT NULL CHECK(entry_kind IN ('OBLIGATION_BOOKED','REVERSAL_BOOKED')),
 fee_type text NOT NULL CHECK(fee_type IN ('DEALER_ACQUISITION_FEE','REPAIR_SHOP_ACCEPTANCE_FEE')),
 partner_org_id text NOT NULL CHECK(length(trim(partner_org_id)) BETWEEN 1 AND 128),
 acceptance_id text NOT NULL CHECK(length(trim(acceptance_id)) BETWEEN 1 AND 128),
 amount_cents bigint NOT NULL CHECK(amount_cents>0),
 currency text NOT NULL CHECK(currency='USD_CENTS'),
 actor_id text NOT NULL CHECK(length(trim(actor_id)) BETWEEN 1 AND 128),
 occurred_at text NOT NULL,
 reason text NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 512),
 reverses_entry_id text,
 previous_hash text NOT NULL CHECK(previous_hash ~ '^[0-9a-f]{64}$'),
 entry_hash text NOT NULL CHECK(entry_hash ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(tenant_id,entry_id),
 UNIQUE(tenant_id,sequence),
 UNIQUE(tenant_id,idempotency_key),
 UNIQUE(tenant_id,reverses_entry_id),
 FOREIGN KEY(tenant_id,session_id) REFERENCES faos.sessions(tenant_id,session_id),
 FOREIGN KEY(tenant_id,reverses_entry_id) REFERENCES faos.financial_ledger_entries(tenant_id,entry_id),
 CHECK((entry_kind='OBLIGATION_BOOKED' AND reverses_entry_id IS NULL) OR
       (entry_kind='REVERSAL_BOOKED' AND reverses_entry_id IS NOT NULL))
);

CREATE TABLE faos.financial_ledger_postings(
 tenant_id uuid NOT NULL,
 entry_id text NOT NULL,
 line_number smallint NOT NULL CHECK(line_number>0),
 account_code text NOT NULL CHECK(length(trim(account_code)) BETWEEN 1 AND 160),
 direction text NOT NULL CHECK(direction IN ('DEBIT','CREDIT')),
 amount_cents bigint NOT NULL CHECK(amount_cents>0),
 PRIMARY KEY(tenant_id,entry_id,line_number),
 FOREIGN KEY(tenant_id,entry_id) REFERENCES faos.financial_ledger_entries(tenant_id,entry_id)
);

ALTER TABLE faos.financial_ledger_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.financial_ledger_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE faos.financial_ledger_postings ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.financial_ledger_postings FORCE ROW LEVEL SECURITY;
CREATE POLICY app_financial_entries ON faos.financial_ledger_entries TO faos_app
 USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_financial_entries ON faos.financial_ledger_entries TO faos_writer
 USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
CREATE POLICY app_financial_postings ON faos.financial_ledger_postings TO faos_app
 USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_financial_postings ON faos.financial_ledger_postings TO faos_writer
 USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.financial_ledger_entries,faos.financial_ledger_postings FROM PUBLIC,faos_app;
GRANT SELECT ON faos.financial_ledger_entries,faos.financial_ledger_postings TO faos_app;
GRANT SELECT,INSERT ON faos.financial_ledger_entries,faos.financial_ledger_postings TO faos_writer;

CREATE FUNCTION faos.append_financial_entry(
 p_tenant uuid,p_entry_id text,p_sequence bigint,p_idempotency text,p_session text,
 p_entry_kind text,p_fee_type text,p_partner text,p_acceptance text,p_amount bigint,
 p_currency text,p_actor text,p_time text,p_reason text,p_reverses text,
 p_previous_hash text,p_entry_hash text,p_lines jsonb)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE last_sequence bigint; last_hash text; old faos.financial_ledger_entries%ROWTYPE;
        expected_lines jsonb; original faos.financial_ledger_entries%ROWTYPE;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,0));
 SELECT * INTO old FROM faos.financial_ledger_entries
  WHERE tenant_id=p_tenant AND idempotency_key=p_idempotency;
 IF FOUND THEN
  IF ROW(old.entry_id,old.session_id,old.entry_kind,old.fee_type,old.partner_org_id,
         old.acceptance_id,old.amount_cents,old.currency,old.actor_id,old.reason,
         old.reverses_entry_id,old.previous_hash,old.entry_hash)
     IS DISTINCT FROM
     ROW(p_entry_id,p_session,p_entry_kind,p_fee_type,p_partner,p_acceptance,p_amount,
         p_currency,p_actor,p_reason,p_reverses,p_previous_hash,p_entry_hash)
     OR (SELECT COALESCE(jsonb_agg(jsonb_build_object('account_code',account_code,
             'direction',direction,'amount_cents',amount_cents) ORDER BY line_number),'[]'::jsonb)
         FROM faos.financial_ledger_postings WHERE tenant_id=p_tenant AND entry_id=old.entry_id)
        IS DISTINCT FROM p_lines THEN
   RAISE EXCEPTION 'IDEMPOTENCY_KEY_CONFLICT';
  END IF;
  RETURN 'DUPLICATE';
 END IF;
 IF p_entry_kind NOT IN ('OBLIGATION_BOOKED','REVERSAL_BOOKED')
 OR p_fee_type NOT IN ('DEALER_ACQUISITION_FEE','REPAIR_SHOP_ACCEPTANCE_FEE')
 OR p_currency IS DISTINCT FROM 'USD_CENTS' OR p_amount<=0
 OR p_lines IS NULL OR jsonb_typeof(p_lines) IS DISTINCT FROM 'array'
 OR jsonb_array_length(p_lines)<>2 THEN
  RAISE EXCEPTION 'INVALID_FINANCIAL_ENTRY';
 END IF;
 IF p_entry_kind='OBLIGATION_BOOKED' THEN
  IF p_reverses IS NOT NULL THEN RAISE EXCEPTION 'INVALID_REVERSAL_REFERENCE'; END IF;
  IF p_fee_type='DEALER_ACQUISITION_FEE' THEN
   -- A dealer acceptance is not the approved fee trigger. Until the
   -- qualified-acquisition-close event is integrated, fail closed even for
   -- direct calls to this SECURITY DEFINER function.
   RAISE EXCEPTION 'DEALER_QUALIFIED_CLOSE_WORKFLOW_NOT_ENABLED';
   IF p_amount<>37500 THEN RAISE EXCEPTION 'FEE_SCHEDULE_MISMATCH'; END IF;
   expected_lines:=jsonb_build_array(
    jsonb_build_object('account_code','AR:DEALER:'||p_partner,'direction','DEBIT','amount_cents',37500),
    jsonb_build_object('account_code','REV:DEALER_ACQUISITION','direction','CREDIT','amount_cents',37500));
  ELSE
   IF p_amount<>27500 THEN RAISE EXCEPTION 'FEE_SCHEDULE_MISMATCH'; END IF;
   expected_lines:=jsonb_build_array(
    jsonb_build_object('account_code','AR:SHOP:'||p_partner,'direction','DEBIT','amount_cents',27500),
    jsonb_build_object('account_code','REV:REPAIR_SHOP_ACCEPTANCE','direction','CREDIT','amount_cents',27500));
  END IF;
 ELSE
  IF p_reverses IS NULL THEN RAISE EXCEPTION 'REVERSAL_REFERENCE_REQUIRED'; END IF;
  SELECT * INTO original FROM faos.financial_ledger_entries
   WHERE tenant_id=p_tenant AND entry_id=p_reverses;
  IF NOT FOUND OR original.entry_kind<>'OBLIGATION_BOOKED'
   OR ROW(original.session_id,original.fee_type,original.partner_org_id,original.acceptance_id,original.amount_cents)
      IS DISTINCT FROM ROW(p_session,p_fee_type,p_partner,p_acceptance,p_amount) THEN
   RAISE EXCEPTION 'INVALID_REVERSAL_REFERENCE';
  END IF;
  SELECT jsonb_agg(jsonb_build_object('account_code',account_code,
          'direction',CASE direction WHEN 'DEBIT' THEN 'CREDIT' ELSE 'DEBIT' END,
          'amount_cents',amount_cents) ORDER BY line_number)
   INTO expected_lines FROM faos.financial_ledger_postings
   WHERE tenant_id=p_tenant AND entry_id=p_reverses;
 END IF;
 IF p_lines IS DISTINCT FROM expected_lines THEN RAISE EXCEPTION 'INVALID_FINANCIAL_POSTINGS'; END IF;
 IF NOT EXISTS(SELECT 1 FROM faos.sessions WHERE tenant_id=p_tenant AND session_id=p_session) THEN
  RAISE EXCEPTION 'SESSION_NOT_FOUND';
 END IF;
 SELECT COALESCE(MAX(sequence),0) INTO last_sequence
  FROM faos.financial_ledger_entries WHERE tenant_id=p_tenant;
 SELECT entry_hash INTO last_hash FROM faos.financial_ledger_entries
  WHERE tenant_id=p_tenant ORDER BY sequence DESC LIMIT 1;
 last_hash:=COALESCE(last_hash,repeat('0',64));
 IF p_sequence IS DISTINCT FROM last_sequence+1 OR p_previous_hash IS DISTINCT FROM last_hash THEN
  RAISE EXCEPTION 'FINANCIAL_CHAIN_CONFLICT';
 END IF;
 IF p_entry_id IS NULL OR length(trim(p_entry_id))=0 OR p_idempotency IS NULL
 OR length(trim(p_idempotency))=0 OR p_partner IS NULL OR length(trim(p_partner))=0
 OR p_acceptance IS NULL OR length(trim(p_acceptance))=0 OR p_actor IS NULL
 OR length(trim(p_actor))=0 OR p_reason IS NULL OR length(trim(p_reason))=0
 OR p_entry_hash !~ '^[0-9a-f]{64}$' OR p_previous_hash !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'INVALID_FINANCIAL_ENTRY';
 END IF;
 INSERT INTO faos.financial_ledger_entries VALUES(
  p_tenant,p_entry_id,p_sequence,p_idempotency,p_session,p_entry_kind,p_fee_type,
  p_partner,p_acceptance,p_amount,p_currency,p_actor,p_time,p_reason,p_reverses,
  p_previous_hash,p_entry_hash);
 INSERT INTO faos.financial_ledger_postings(tenant_id,entry_id,line_number,account_code,direction,amount_cents)
 SELECT p_tenant,p_entry_id,(ordinality)::smallint,item->>'account_code',item->>'direction',
        (item->>'amount_cents')::bigint
 FROM jsonb_array_elements(p_lines) WITH ORDINALITY AS lines(item,ordinality);
 RETURN 'ACCEPTED';
END $$;
REVOKE ALL ON FUNCTION faos.append_financial_entry(uuid,text,bigint,text,text,text,text,text,text,bigint,text,text,text,text,text,text,text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.append_financial_entry(uuid,text,bigint,text,text,text,text,text,text,bigint,text,text,text,text,text,text,text,jsonb) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.append_financial_entry(uuid,text,bigint,text,text,text,text,text,text,bigint,text,text,text,text,text,text,text,jsonb) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
