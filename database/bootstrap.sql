CREATE ROLE faos_migrator LOGIN;
CREATE ROLE faos_app LOGIN;
CREATE ROLE faos_fixture LOGIN;
ALTER DATABASE claim2car_test OWNER TO postgres;
CREATE ROLE faos_writer NOLOGIN;
GRANT CONNECT, CREATE ON DATABASE claim2car_test TO faos_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO faos_migrator;
GRANT faos_writer TO faos_migrator;
