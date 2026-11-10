-- Unify direct-SQL event acceptance with the Python DomainEvent contract.
-- This migration rejects incompatible historical rows; it never rewrites event history.

CREATE FUNCTION faos.canonical_event_jsonb(p_value jsonb)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
SET search_path=pg_catalog,faos
AS $function$
DECLARE
  result text;
  value_kind text := jsonb_typeof(p_value);
BEGIN
  IF value_kind = 'object' THEN
    SELECT '{' || COALESCE(string_agg(
      to_json(entry.key)::text || ':' || faos.canonical_event_jsonb(entry.value),
      ',' ORDER BY entry.key COLLATE "C"
    ), '') || '}'
    INTO result
    FROM jsonb_each(p_value) AS entry(key,value);
    RETURN result;
  ELSIF value_kind = 'array' THEN
    SELECT '[' || COALESCE(string_agg(
      faos.canonical_event_jsonb(entry.value), ',' ORDER BY entry.ordinality
    ), '') || ']'
    INTO result
    FROM jsonb_array_elements(p_value) WITH ORDINALITY AS entry(value,ordinality);
    RETURN result;
  ELSIF value_kind = 'string' THEN
    RETURN to_json(p_value #>> '{}')::text;
  ELSE
    RETURN p_value::text;
  END IF;
END
$function$;

CREATE FUNCTION faos.event_jsonb_uses_integer_numbers(p_value jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
SET search_path=pg_catalog,faos
AS $function$
DECLARE
  value_kind text := jsonb_typeof(p_value);
  valid boolean;
BEGIN
  IF value_kind = 'number' THEN
    RETURN (p_value::text ~ '^-?(0|[1-9][0-9]*)$');
  ELSIF value_kind = 'object' THEN
    SELECT COALESCE(bool_and(faos.event_jsonb_uses_integer_numbers(entry.value)),true)
      INTO valid FROM jsonb_each(p_value) AS entry(key,value);
    RETURN valid;
  ELSIF value_kind = 'array' THEN
    SELECT COALESCE(bool_and(faos.event_jsonb_uses_integer_numbers(entry.value)),true)
      INTO valid FROM jsonb_array_elements(p_value) AS entry(value);
    RETURN valid;
  END IF;
  RETURN true;
END
$function$;

CREATE FUNCTION faos.event_payload_is_canonical(p_value text)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
SET search_path=pg_catalog,faos
AS $function$
DECLARE
  parsed jsonb;
BEGIN
  parsed := p_value::jsonb;
  IF jsonb_typeof(parsed) IS DISTINCT FROM 'object' THEN
    RETURN false;
  END IF;
  IF NOT faos.event_jsonb_uses_integer_numbers(parsed) THEN
    RETURN false;
  END IF;
  RETURN p_value = faos.canonical_event_jsonb(parsed);
EXCEPTION WHEN others THEN
  RETURN false;
END
$function$;

-- Python uses RFC3339 timestamps with an explicit UTC marker or numeric offset.
-- The input-validity check rejects impossible calendar dates; the regex rejects
-- PostgreSQL-only forms such as timezone-naive timestamps and space separators.
ALTER TABLE faos.events
  ADD CONSTRAINT event_timestamp_rfc3339
  CHECK (
    occurred_at ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-5][0-9]:[0-5][0-9]([.][0-9]{1,6})?(Z|[+](0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]|-(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9])$'
    AND pg_catalog.pg_input_is_valid(occurred_at,'timestamp with time zone')
  );

ALTER TABLE faos.events
  ADD CONSTRAINT event_payload_python_canonical
  CHECK (faos.event_payload_is_canonical(payload_json));

-- Keep the SQL allowlist exactly aligned with app.domain_events.KINDS.
ALTER TABLE faos.events DROP CONSTRAINT events_kind_check;
ALTER TABLE faos.events ADD CONSTRAINT events_kind_check CHECK(kind IN (
  'SESSION_CREATED','CONSENT_RECORDED','VEHICLE_RECORDED',
  'ARTIFACT_REGISTERED','QUALITY_RECORDED','MANIFEST_SEALED',
  'REVIEW_RECORDED','SESSION_ABORTED',
  'INCIDENT_INTAKE_CONSENT_RECORDED','INCIDENT_INTAKE_RECORDED'
));
