-- Minimal structured incident intake. Sensitive incident fields are
-- separately deletable; the append-only event journal stores only consent and
-- a digest, never the location/date/type values themselves.
CREATE TABLE faos.claim_case_incident_intake(
 tenant_id uuid NOT NULL,
 claim_id uuid NOT NULL,
 owner_actor_id text NOT NULL CHECK(length(trim(owner_actor_id)) BETWEEN 1 AND 128),
 request_id uuid NOT NULL,
 incident_occurred_at timestamptz NOT NULL,
 incident_type text NOT NULL CHECK(incident_type IN ('collision','theft','weather','vandalism','other','unknown')),
 incident_city text NOT NULL CHECK(length(trim(incident_city)) BETWEEN 2 AND 80),
 incident_region text NOT NULL CHECK(incident_region ~ '^[A-Z]{2}$'),
 incident_postal_code text NOT NULL CHECK(incident_postal_code ~ '^[0-9]{5}(-[0-9]{4})?$'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,claim_id),
 UNIQUE(tenant_id,request_id),
 FOREIGN KEY(tenant_id,claim_id) REFERENCES faos.claim_cases(tenant_id,claim_id)
);
ALTER TABLE faos.claim_case_incident_intake ENABLE ROW LEVEL SECURITY;
ALTER TABLE faos.claim_case_incident_intake FORCE ROW LEVEL SECURITY;
CREATE POLICY app_claim_case_incident ON faos.claim_case_incident_intake TO faos_app
 USING(tenant_id=faos.tenant_id());
CREATE POLICY writer_claim_case_incident ON faos.claim_case_incident_intake TO faos_writer
 USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id());
REVOKE ALL ON faos.claim_case_incident_intake FROM PUBLIC,faos_app,faos_writer;
GRANT SELECT ON faos.claim_case_incident_intake TO faos_app;
GRANT SELECT,INSERT,DELETE ON faos.claim_case_incident_intake TO faos_writer;

CREATE FUNCTION faos.save_claim_case_incident(
 p_tenant uuid,p_claim uuid,p_owner text,p_request uuid,p_occurred timestamptz,
 p_type text,p_city text,p_region text,p_postal text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE existing faos.claim_case_incident_intake%ROWTYPE;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM faos.claim_cases c WHERE c.tenant_id=p_tenant
   AND c.claim_id=p_claim AND c.owner_actor_id=p_owner) THEN
  RETURN 'OWNER_BINDING_REQUIRED';
 END IF;
 INSERT INTO faos.claim_case_incident_intake(
  tenant_id,claim_id,owner_actor_id,request_id,incident_occurred_at,
  incident_type,incident_city,incident_region,incident_postal_code
 ) VALUES(p_tenant,p_claim,p_owner,p_request,p_occurred,p_type,p_city,p_region,p_postal)
 ON CONFLICT(tenant_id,claim_id) DO NOTHING
 RETURNING * INTO existing;
 IF FOUND THEN RETURN 'ACCEPTED'; END IF;
 SELECT * INTO existing FROM faos.claim_case_incident_intake
  WHERE tenant_id=p_tenant AND claim_id=p_claim;
 IF FOUND AND ROW(existing.owner_actor_id,existing.request_id,existing.incident_occurred_at,
   existing.incident_type,existing.incident_city,existing.incident_region,existing.incident_postal_code)
  IS NOT DISTINCT FROM ROW(p_owner,p_request,p_occurred,p_type,p_city,p_region,p_postal) THEN
  RETURN 'DUPLICATE';
 END IF;
 RETURN 'CONFLICT';
EXCEPTION WHEN unique_violation THEN
 RETURN 'CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.save_claim_case_incident(uuid,uuid,text,uuid,timestamptz,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.save_claim_case_incident(uuid,uuid,text,uuid,timestamptz,text,text,text,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.save_claim_case_incident(uuid,uuid,text,uuid,timestamptz,text,text,text,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;

CREATE FUNCTION faos.withdraw_claim_case_incident(p_tenant uuid,p_claim uuid,p_owner text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE deleted_count integer;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 DELETE FROM faos.claim_case_incident_intake
  WHERE tenant_id=p_tenant AND claim_id=p_claim AND owner_actor_id=p_owner;
 GET DIAGNOSTICS deleted_count=ROW_COUNT;
 RETURN CASE WHEN deleted_count=1 THEN 'DELETED' ELSE 'NOT_FOUND' END;
END $$;
REVOKE ALL ON FUNCTION faos.withdraw_claim_case_incident(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.withdraw_claim_case_incident(uuid,uuid,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.withdraw_claim_case_incident(uuid,uuid,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
