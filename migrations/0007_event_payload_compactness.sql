-- Bounded remediation: compact JSON text only, not full Python canonical parity.
-- Key ordering, Unicode escaping and numeric spelling remain separate requirements.
CREATE FUNCTION faos.compact_json_text(p_value text)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog
AS $function$
DECLARE
 result text := '';
 inside_string boolean := false;
 escaped boolean := false;
 ch text;
 i integer;
BEGIN
 FOR i IN 1..length(p_value) LOOP
  ch := substr(p_value,i,1);
  IF inside_string THEN
   result := result || ch;
   IF escaped THEN
    escaped := false;
   ELSIF ch=chr(92) THEN
    escaped := true;
   ELSIF ch='"' THEN
    inside_string := false;
   END IF;
  ELSIF ch='"' THEN
   inside_string := true;
   result := result || ch;
  ELSIF ch NOT IN (' ',chr(9),chr(10),chr(13)) THEN
   result := result || ch;
  END IF;
 END LOOP;
 RETURN result;
END
$function$;

-- Executed transactionally with migration; these are helper self-checks,
-- not substitutes for direct-SQL event-boundary or whole-gate acceptance tests.
DO $verify$
DECLARE escaped_quote text := '{"q":"a' || chr(92) || '" b"}';
BEGIN
 IF faos.compact_json_text(' { "message" : "a b" } ') IS DISTINCT FROM '{"message":"a b"}' THEN
  RAISE EXCEPTION 'JSON_COMPACT_STRING_SPACE_REGRESSION';
 END IF;
 IF faos.compact_json_text(' {"a":[1, 2], "b":{"c":true}} ') IS DISTINCT FROM '{"a":[1,2],"b":{"c":true}}' THEN
  RAISE EXCEPTION 'JSON_COMPACT_NESTING_REGRESSION';
 END IF;
 IF faos.compact_json_text(escaped_quote) IS DISTINCT FROM escaped_quote THEN
  RAISE EXCEPTION 'JSON_COMPACT_ESCAPE_REGRESSION';
 END IF;
 IF faos.compact_json_text(chr(9)||'{}'||chr(10)||chr(13)) IS DISTINCT FROM '{}' THEN
  RAISE EXCEPTION 'JSON_COMPACT_CONTROL_WHITESPACE_REGRESSION';
 END IF;
END
$verify$;

-- Existing JSON-object validation remains in force. Validate all existing rows;
-- any invalid historical representation blocks the migration instead of rewriting it.
ALTER TABLE faos.events ADD CONSTRAINT event_payload_compact
 CHECK (payload_json=faos.compact_json_text(payload_json));
