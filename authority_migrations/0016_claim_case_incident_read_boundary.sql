-- Remove direct application-role table reads. Incident details are exposed
-- only through an actor-checked SECURITY DEFINER read function.
REVOKE SELECT ON faos.claim_case_incident_intake FROM faos_app;

CREATE FUNCTION faos.read_claim_case_incident(p_tenant uuid,p_claim uuid,p_actor text)
RETURNS TABLE(
 request_id uuid,
 incident_occurred_at timestamptz,
 incident_type text,
 incident_city text,
 incident_region text,
 incident_postal_code text
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,faos,pg_temp
AS $$
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_actor IS NULL OR length(trim(p_actor)) NOT BETWEEN 1 AND 128 THEN
  RETURN;
 END IF;
 RETURN QUERY
 SELECT i.request_id,i.incident_occurred_at,i.incident_type,i.incident_city,
        i.incident_region,i.incident_postal_code
 FROM faos.claim_case_incident_intake i
 JOIN faos.claim_cases c
   ON c.tenant_id=i.tenant_id AND c.claim_id=i.claim_id
 WHERE i.tenant_id=p_tenant AND i.claim_id=p_claim
   AND (c.owner_actor_id=p_actor OR c.created_by=p_actor);
END $$;
REVOKE ALL ON FUNCTION faos.read_claim_case_incident(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.read_claim_case_incident(uuid,uuid,text) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.read_claim_case_incident(uuid,uuid,text) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
