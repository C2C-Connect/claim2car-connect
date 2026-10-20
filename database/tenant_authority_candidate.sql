-- Staged cutover SQL: exercised only in disposable integration databases.
-- Not automatically applied by the migration runner. Promote through a new
-- versioned migration only after fixture/connection compatibility is reviewed.
CREATE TABLE faos.tenant_login_bindings(
 role_oid oid PRIMARY KEY,
 role_name name NOT NULL UNIQUE,
 tenant_id uuid NOT NULL REFERENCES faos.organizations(tenant_id),
 enabled boolean NOT NULL DEFAULT true);
-- Administrative authorization registry, not application-managed tenant data.
REVOKE ALL ON faos.tenant_login_bindings FROM PUBLIC,faos_app,faos_fixture;
GRANT SELECT ON faos.tenant_login_bindings TO faos_writer;
CREATE OR REPLACE FUNCTION faos.tenant_id() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,faos,pg_temp
AS $$
 SELECT b.tenant_id FROM faos.tenant_login_bindings b
 JOIN pg_catalog.pg_roles r ON r.oid=b.role_oid AND r.rolname=b.role_name
 WHERE r.rolname=session_user AND b.enabled
 AND b.tenant_id=NULLIF(current_setting('faos.tenant_id',true),'')::uuid
$$;
REVOKE ALL ON FUNCTION faos.tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.tenant_id() TO faos_app,faos_writer,faos_fixture;
GRANT CREATE ON SCHEMA faos TO faos_writer;
ALTER FUNCTION faos.tenant_id() OWNER TO faos_writer;
REVOKE CREATE ON SCHEMA faos FROM faos_writer;
