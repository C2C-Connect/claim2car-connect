"""Real faos authority-track integration in disposable databases."""
import os
from pathlib import Path
import unittest
import uuid
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from app.domain_events import DomainEvent
from database.journal import append, tenant_transaction
from database.readback import load_journal
from database.migrate import apply
from database.authority_migrate import migration_plan

class TenantAuthorityIntegration(unittest.TestCase):
    def setUp(self):
        url = os.getenv('MIGRATION_TEST_ADMIN_URL','postgresql://postgres:synthetic-container-only@127.0.0.1:55432/claim2car_test')
        config = conninfo_to_dict(url)
        if any(config.get(k)!=v for k,v in {'host':'127.0.0.1','port':'55432','dbname':'claim2car_test','user':'postgres'}.items()):
            raise ValueError('EXPLICIT_SYNTHETIC_ADMIN_TARGET_REQUIRED')
        self.admin = psycopg.connect(url,autocommit=True,connect_timeout=5)
        self.addCleanup(self.admin.close)
        self.roles = ['tenant_integration_'+uuid.uuid4().hex for _ in range(2)]
        passwords = [uuid.uuid4().hex for _ in self.roles]
        for role,password in zip(self.roles,passwords):
            self.admin.execute(sql.SQL('CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
            self.addCleanup(self.drop_role,role)
            self.admin.execute(sql.SQL('GRANT faos_app TO {}').format(sql.Identifier(role)))
        self.db = 'tenant_integration_'+uuid.uuid4().hex
        self.admin.execute(sql.SQL('CREATE DATABASE {} OWNER faos_migrator TEMPLATE template0').format(sql.Identifier(self.db)))
        self.addCleanup(self.drop_database)
        root = Path(__file__).resolve().parents[2]
        with psycopg.connect(make_conninfo(url,dbname=self.db,user='faos_migrator',password='synthetic-migrator-only'),autocommit=True,connect_timeout=5) as migrator:
            apply(migrator,migration_plan(root))
        self.seed = psycopg.connect(make_conninfo(url,dbname=self.db),autocommit=True,connect_timeout=5)
        self.addCleanup(self.seed.close)
        self.tenants = [str(uuid.uuid4()),str(uuid.uuid4())]
        self.session = 'shared-session'
        for role,tenant in zip(self.roles,self.tenants):
            self.seed.execute('INSERT INTO faos.organizations(tenant_id,name) VALUES (%s,%s)',(tenant,'synthetic authority integration'))
            self.seed.execute('INSERT INTO faos.sessions(tenant_id,session_id) VALUES (%s,%s)',(tenant,self.session))
            self.assertEqual(self.seed.execute('INSERT INTO faos.tenant_login_bindings(role_oid,role_name,tenant_id) SELECT oid,rolname,%s FROM pg_roles WHERE rolname=%s',(tenant,role)).rowcount,1)
        self.connections = []
        for role,password in zip(self.roles,passwords):
            conn = psycopg.connect(make_conninfo(url,dbname=self.db,user=role,password=password),autocommit=True,connect_timeout=5)
            self.addCleanup(conn.close)
            self.assertEqual(conn.execute('SELECT session_user,current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone(),(role,role,False,False))
            self.connections.append(conn)
        self.unbound = psycopg.connect(make_conninfo(url,dbname=self.db,user='faos_app',password='synthetic-app-only'),autocommit=True,connect_timeout=5)
        self.addCleanup(self.unbound.close)
        self.event = DomainEvent(self.session,'event-1',1,'SESSION_CREATED','synthetic-test','2026-01-01T00:00:00Z','real schema authority integration','{}')

    def drop_role(self,role):
        self.admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))

    def drop_database(self):
        self.admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(self.db)))

    def test_bound_logins_append_retry_and_read_actual_journal(self):
        for conn,tenant in zip(self.connections,self.tenants):
            self.assertEqual(append(conn,tenant,self.event),'ACCEPTED')
            self.assertEqual(append(conn,tenant,self.event),'DUPLICATE')
            self.assertEqual(load_journal(conn,tenant,self.session).events,(self.event,))

    def assert_no_authority(self,conn,tenant):
        with tenant_transaction(conn,tenant):
            self.assertIsNone(conn.execute('SELECT faos.tenant_id()').fetchone()[0])
            self.assertEqual(conn.execute('SELECT tenant_id FROM faos.sessions').fetchall(),[])
            self.assertEqual(conn.execute('SELECT tenant_id FROM faos.events').fetchall(),[])
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            append(conn,tenant,self.event)
        self.assertEqual(caught.exception.sqlstate,'P0001')
        self.assertEqual(caught.exception.diag.message_primary,'TENANT_CONTEXT_MISMATCH')

    def test_bound_login_cannot_impersonate_other_tenant(self):
        self.assertEqual(append(self.connections[1],self.tenants[1],self.event),'ACCEPTED')
        self.assert_no_authority(self.connections[0],self.tenants[1])
        self.assertEqual(load_journal(self.connections[1],self.tenants[1],self.session).events,(self.event,))

    def test_unbound_shared_login_fails_closed(self):
        for tenant in self.tenants:
            self.assert_no_authority(self.unbound,tenant)

    def test_application_cannot_read_or_modify_authority_registry(self):
        for statement in ('SELECT * FROM faos.tenant_login_bindings','UPDATE faos.tenant_login_bindings SET enabled=enabled'):
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
                    with self.connections[0].transaction():
                        self.connections[0].execute(statement)
                        raise AssertionError('AUTHORITY_REGISTRY_ACCESS_ALLOWED')
                self.assertEqual(caught.exception.sqlstate,'42501')

    def test_binding_revocation_blocks_subsequent_transactions(self):
        self.assertEqual(append(self.connections[0],self.tenants[0],self.event),'ACCEPTED')
        self.assertEqual(self.seed.execute('UPDATE faos.tenant_login_bindings SET enabled=false WHERE role_name=%s',(self.roles[0],)).rowcount,1)
        self.assert_no_authority(self.connections[0],self.tenants[0])
        self.assertEqual(append(self.connections[1],self.tenants[1],self.event),'ACCEPTED')
        self.assertEqual(load_journal(self.connections[1],self.tenants[1],self.session).events,(self.event,))

if __name__ == '__main__':
    unittest.main()
