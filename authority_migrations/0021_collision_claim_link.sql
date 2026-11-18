-- Authorized collision-to-claim association, audited as one event/outbox transaction.
CREATE FUNCTION faos.link_collision_claim(
 p_tenant uuid,p_collision uuid,p_claim uuid,p_request uuid,p_actor text,p_occurred timestamptz
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
DECLARE old faos.collision_events%ROWTYPE;
        event_result text;
        event_payload jsonb;
BEGIN
 IF faos.tenant_id() IS NULL OR p_tenant IS DISTINCT FROM faos.tenant_id() THEN
  RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH';
 END IF;
 IF p_collision IS NULL OR p_claim IS NULL OR p_request IS NULL
 OR p_actor IS NULL OR length(trim(p_actor)) NOT BETWEEN 1 AND 128
 OR p_occurred IS NULL THEN
  RAISE EXCEPTION 'INVALID_COLLISION_CLAIM_LINK';
 END IF;
 PERFORM 1 FROM faos.collision_lifecycle_records
  WHERE tenant_id=p_tenant AND collision_id=p_collision AND created_by=p_actor
  FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'COLLISION_CLAIM_LINK_AUTHORITY_DENIED'; END IF;
 PERFORM 1 FROM faos.claim_cases
  WHERE tenant_id=p_tenant AND claim_id=p_claim AND created_by=p_actor
  FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'COLLISION_CLAIM_LINK_AUTHORITY_DENIED'; END IF;
 event_payload := jsonb_build_object('claim_id',p_claim,'schema_version','1.0');
 SELECT * INTO old FROM faos.collision_events
  WHERE tenant_id=p_tenant AND collision_id=p_collision
    AND idempotency_key=p_request::text;
 IF FOUND THEN
  IF ROW(old.event_id,old.event_type,old.actor_ref,old.payload)
     IS DISTINCT FROM ROW(p_request,'claim_linked',p_actor,event_payload) THEN
   RAISE EXCEPTION 'COLLISION_EVENT_IDEMPOTENCY_CONFLICT';
  END IF;
  RETURN 'DUPLICATE';
 END IF;
 IF EXISTS(SELECT 1 FROM faos.collision_claim_links
           WHERE tenant_id=p_tenant AND collision_id=p_collision AND claim_id=p_claim) THEN
  RETURN 'DUPLICATE';
 END IF;
 INSERT INTO faos.collision_claim_links(tenant_id,collision_id,claim_id,linked_by)
 VALUES(p_tenant,p_collision,p_claim,p_actor);
 SELECT faos.append_collision_event(
  p_tenant,p_collision,p_request,p_request::text,'claim_linked',
  p_actor,p_occurred,event_payload,NULL,NULL
 ) INTO event_result;
 IF event_result IS DISTINCT FROM 'ACCEPTED' THEN
  RAISE EXCEPTION 'COLLISION_CLAIM_LINK_EVENT_FAILED';
 END IF;
 RETURN 'ACCEPTED';
EXCEPTION WHEN unique_violation THEN
 RAISE EXCEPTION 'COLLISION_CLAIM_LINK_CONFLICT';
END $$;
REVOKE ALL ON FUNCTION faos.link_collision_claim(uuid,uuid,uuid,uuid,text,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.link_collision_claim(uuid,uuid,uuid,uuid,text,timestamptz) TO faos_app;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.link_collision_claim(uuid,uuid,uuid,uuid,text,timestamptz) OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
