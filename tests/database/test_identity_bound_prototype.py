"""Disposable authorization design tests, not remediation of faos tenant policies."""
import os
import unittest
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

class IdentityBoundPrototype(unittest.TestCase):
    def setUp(self):
        url = os.getenv('MIGRATION_TEST_ADMIN_URL','postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        self.admin = psycopg.connect(url,autocommit=True,connect_timeout=5)
        self.addCleanup(self.admin.close)
        self.roles = []
        passwords = []
        for index in range(2):
            role = 'identity_probe_' + uuid.uuid4().hex
            password = uuid.uuid4().hex
            self.admin.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS').format(sql.Identifier(role),sql.Literal(password)))
            self.addCleanup(self.drop_role,role)
            self.roles.append(role)
            passwords.append(password)
        self.schema = 'identity_probe_' + uuid.uuid4().hex
        self.admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        self.tenants = [str(uuid.uuid4()),str(uuid.uuid4())]
        s = sql.Identifier(self.schema)
        self.admin.execute(sql.SQL('CREATE TABLE {}.bindings(role_name name PRIMARY KEY,tenant_id uuid NOT NULL UNIQUE)').format(s))
        self.admin.execute(sql.SQL('CREATE TABLE {}.items(tenant_id uuid NOT NULL,value text NOT NULL,PRIMARY KEY(tenant_id,value))').format(s))
        for role,tenant in zip(self.roles,self.tenants):
            self.admin.execute(sql.SQL('INSERT INTO {}.bindings VALUES (%s,%s)').format(s),(role,tenant))
            self.admin.execute(sql.SQL('INSERT INTO {}.items VALUES (%s,%s)').format(s),(tenant,'synthetic-row'))
        body = sql.SQL('SELECT tenant_id FROM {}.bindings WHERE role_name=session_user').format(s).as_string(self.admin)
        self.admin.execute(sql.SQL('CREATE FUNCTION {}.bound_tenant() RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS {}').format(s,sql.Literal(body)))
        self.admin.execute(sql.SQL('REVOKE ALL ON FUNCTION {}.bound_tenant() FROM PUBLIC').format(s))
        self.admin.execute(sql.SQL('ALTER TABLE {}.items ENABLE ROW LEVEL SECURITY').format(s))
        self.admin.execute(sql.SQL('ALTER TABLE {}.items FORCE ROW LEVEL SECURITY').format(s))
        predicate = sql.SQL("tenant_id={}.bound_tenant() AND tenant_id=NULLIF(current_setting('faos.tenant_id',true),'')::uuid").format(s)
        self.admin.execute(sql.SQL('CREATE POLICY tenant_bound ON {}.items USING ({}) WITH CHECK ({})').format(s,predicate,predicate))
        self.connections = []
        database = self.admin.execute('SELECT current_database()').fetchone()[0]
        for role,password in zip(self.roles,passwords):
            r = sql.Identifier(role)
            self.admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database),r))
            self.admin.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(s,r))
            self.admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION {}.bound_tenant() TO {}').format(s,r))
            self.admin.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON {}.items TO {}').format(s,r))
            conn = psycopg.connect(make_conninfo(url,user=role,password=password),autocommit=True,connect_timeout=5)
            self.addCleanup(conn.close)
            self.assertEqual(conn.execute('SELECT session_user,current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone(),(role,role,False,False))
            self.connections.append(conn)
        self.conn = self.connections[0]

    def drop_schema(self):
        self.admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def drop_role(self,role):
        self.admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
        self.admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))

    def context(self,conn,tenant):
        conn.execute("SELECT set_config('faos.tenant_id',%s,true)",(tenant,))

    def rows(self,conn,tenant):
        with conn.transaction():
            self.context(conn,tenant)
            return conn.execute(sql.SQL('SELECT tenant_id::text,value FROM {}.items').format(sql.Identifier(self.schema))).fetchall()

    def test_each_login_reads_its_bound_tenant(self):
        for conn,tenant in zip(self.connections,self.tenants):
            self.assertEqual(self.rows(conn,tenant),[(tenant,'synthetic-row')])

    def test_switching_context_cannot_impersonate_other_tenant(self):
        self.assertEqual(self.rows(self.conn,self.tenants[1]),[])
        self.assertEqual(self.rows(self.conn,self.tenants[0]),[(self.tenants[0],'synthetic-row')])

    def test_spoofed_context_cannot_mutate_other_tenant(self):
        s = sql.Identifier(self.schema)
        with self.conn.transaction():
            self.context(self.conn,self.tenants[1])
            self.assertEqual(self.conn.execute(sql.SQL('UPDATE {}.items SET value=value').format(s)).rowcount,0)
            self.assertEqual(self.conn.execute(sql.SQL('DELETE FROM {}.items').format(s)).rowcount,0)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
            with self.conn.transaction():
                self.context(self.conn,self.tenants[1])
                self.conn.execute(sql.SQL('INSERT INTO {}.items VALUES (%s,%s)').format(s),(self.tenants[1],'forbidden'))
                raise AssertionError('CROSS_TENANT_INSERT_ALLOWED')
        self.assertEqual(caught.exception.sqlstate,'42501')
        self.assertEqual(self.rows(self.connections[1],self.tenants[1]),[(self.tenants[1],'synthetic-row')])

    def test_login_cannot_assume_other_tenant_role(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
            with self.conn.transaction():
                self.conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(self.roles[1])))
                raise AssertionError('TENANT_ROLE_ESCALATION_ALLOWED')
        self.assertEqual(caught.exception.sqlstate,'42501')
        self.assertEqual(self.conn.execute('SELECT session_user,current_user').fetchone(),(self.roles[0],self.roles[0]))

    def test_binding_table_is_not_application_accessible(self):
        for statement in ('SELECT * FROM {}.bindings','UPDATE {}.bindings SET tenant_id=tenant_id'):
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with self.conn.transaction():
                        self.conn.execute(sql.SQL(statement).format(sql.Identifier(self.schema)))
                        raise AssertionError('PRIVATE_BINDING_ACCESS_ALLOWED')
                self.assertEqual(caught.exception.sqlstate,'42501')

if __name__ == '__main__':
    unittest.main()
