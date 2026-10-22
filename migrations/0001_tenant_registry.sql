CREATE SCHEMA faos;
REVOKE ALL ON SCHEMA faos FROM PUBLIC;
GRANT USAGE ON SCHEMA faos TO faos_app,faos_writer,faos_fixture;
CREATE FUNCTION faos.tenant_id() RETURNS uuid LANGUAGE sql STABLE
AS $$ SELECT NULLIF(current_setting('faos.tenant_id',true),'')::uuid $$;
REVOKE ALL ON FUNCTION faos.tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION faos.tenant_id() TO faos_app,faos_writer,faos_fixture;
CREATE TABLE faos.organizations(tenant_id uuid PRIMARY KEY,name text NOT NULL);
CREATE TABLE faos.users(tenant_id uuid NOT NULL REFERENCES faos.organizations,user_id uuid NOT NULL,
 external_subject text NOT NULL,PRIMARY KEY(tenant_id,user_id),UNIQUE(tenant_id,external_subject));
CREATE TABLE faos.memberships(tenant_id uuid NOT NULL,user_id uuid NOT NULL,membership_id uuid NOT NULL,
 role_name text NOT NULL,PRIMARY KEY(tenant_id,membership_id),FOREIGN KEY(tenant_id,user_id) REFERENCES faos.users(tenant_id,user_id));
CREATE TABLE faos.dealer_groups(tenant_id uuid NOT NULL REFERENCES faos.organizations,group_id uuid NOT NULL,
 name text NOT NULL,PRIMARY KEY(tenant_id,group_id));
CREATE TABLE faos.dealer_locations(tenant_id uuid NOT NULL,location_id uuid NOT NULL,group_id uuid NOT NULL,
 name text NOT NULL,enabled boolean NOT NULL DEFAULT false,PRIMARY KEY(tenant_id,location_id),
 FOREIGN KEY(tenant_id,group_id) REFERENCES faos.dealer_groups(tenant_id,group_id));
CREATE TABLE faos.brands(brand_id uuid PRIMARY KEY,normalized_name text NOT NULL UNIQUE);
CREATE TABLE faos.location_brands(tenant_id uuid NOT NULL,location_id uuid NOT NULL,
 brand_id uuid NOT NULL REFERENCES faos.brands,PRIMARY KEY(tenant_id,location_id,brand_id),
 FOREIGN KEY(tenant_id,location_id) REFERENCES faos.dealer_locations(tenant_id,location_id));
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['organizations','users','memberships','dealer_groups','dealer_locations','location_brands'] LOOP
 EXECUTE format('ALTER TABLE faos.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE faos.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('CREATE POLICY app_tenant ON faos.%I TO faos_app USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id())',t);
 EXECUTE format('CREATE POLICY fixture_tenant ON faos.%I TO faos_fixture USING(tenant_id=faos.tenant_id()) WITH CHECK(tenant_id=faos.tenant_id())',t);
 EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON faos.%I TO faos_app',t);
 EXECUTE format('GRANT SELECT,INSERT ON faos.%I TO faos_fixture',t);
 END LOOP;
END $$;
GRANT SELECT ON faos.brands TO faos_app;
GRANT SELECT,INSERT ON faos.brands TO faos_fixture;
