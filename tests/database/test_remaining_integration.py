"""Tenant-isolated session/event and user RLS integration tests."""
import unittest
import uuid
import psycopg
from tenant_login import TenantLogin


class TestRemainingIntegration(unittest.TestCase):
    def setUp(self):
        self.tenants = (str(uuid.uuid4()), str(uuid.uuid4()))
        self.logins = [
            TenantLogin(tenant, organization_name='synthetic isolation fixture')
            for tenant in self.tenants
        ]
        for login in self.logins:
            self.addCleanup(login.close)
        self.connections = [login.connect(autocommit=False) for login in self.logins]
        for conn in self.connections:
            self.addCleanup(conn.close)
            self.addCleanup(conn.rollback)
        self.session = 'isolation-' + uuid.uuid4().hex
        for tenant, conn in zip(self.tenants, self.connections):
            self.set_context(conn, tenant)
            conn.execute(
                'INSERT INTO faos.sessions(tenant_id, session_id) VALUES (%s, %s)',
                (tenant, self.session),
            )
            outcome = conn.execute(
                'SELECT faos.append_event(%s::uuid, %s::text, %s::text, '
                '%s::bigint, %s::text, %s::text, %s::text, %s::text, '
                '%s::text, %s::text)',
                (tenant, self.session, 'event-1', 1, 'SESSION_CREATED',
                 'synthetic-test', '2026-01-01T00:00:00Z',
                 'tenant isolation', '{}', '0.1'),
            ).fetchone()[0]
            self.assertEqual(outcome, 'ACCEPTED')

    def set_context(self, conn, tenant):
        conn.execute("SELECT set_config('faos.tenant_id', %s, true)", (str(tenant),))

    def sessions(self, conn):
        return conn.execute(
            'SELECT tenant_id::text, session_id FROM faos.sessions WHERE session_id=%s',
            (self.session,),
        ).fetchall()

    def events(self, conn):
        return conn.execute(
            'SELECT tenant_id::text,session_id,event_id,sequence FROM faos.events WHERE session_id=%s',
            (self.session,),
        ).fetchall()

    def assert_own_rows_only(self, conn, tenant):
        self.assertEqual(self.sessions(conn), [(tenant, self.session)])
        self.assertEqual(self.events(conn), [(tenant, self.session, 'event-1', 1)])

    def test_bound_connections_expose_only_their_tenant_rows(self):
        for tenant, conn in zip(self.tenants, self.connections):
            with self.subTest(tenant=tenant):
                self.set_context(conn, tenant)
                self.assert_own_rows_only(conn, tenant)

    def test_cleared_context_exposes_neither_tenants_rows(self):
        for tenant, conn in zip(self.tenants, self.connections):
            with self.subTest(tenant=tenant):
                self.set_context(conn, tenant)
                self.assert_own_rows_only(conn, tenant)
                self.set_context(conn, '')
                self.assertIsNone(conn.execute('SELECT faos.tenant_id()').fetchone()[0])
                self.assertEqual(self.sessions(conn), [])
                self.assertEqual(self.events(conn), [])
                self.set_context(conn, tenant)
                self.assert_own_rows_only(conn, tenant)

    def seed_users(self):
        user = str(uuid.uuid4())
        for tenant, conn in zip(self.tenants, self.connections):
            self.set_context(conn, tenant)
            conn.execute(
                'INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
                (tenant, user, 'synthetic-' + tenant),
            )
        return user

    def test_cross_tenant_user_insert_denied(self):
        own, other = self.tenants
        own_conn, other_conn = self.connections
        user = str(uuid.uuid4())
        self.set_context(own_conn, own)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
            with own_conn.transaction():
                own_conn.execute(
                    'INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
                    (other, user, 'attempt-' + user),
                )
        self.assertEqual(caught.exception.sqlstate, '42501')
        self.set_context(other_conn, other)
        self.assertEqual(other_conn.execute('SELECT count(*) FROM faos.users WHERE user_id=%s', (user,)).fetchone()[0], 0)
        self.set_context(own_conn, own)
        own_conn.execute(
            'INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
            (own, user, 'own-' + user),
        )
        self.assertEqual(own_conn.execute('SELECT count(*) FROM faos.users WHERE user_id=%s', (user,)).fetchone()[0], 1)

    def test_cross_tenant_user_update_affects_no_rows(self):
        user = self.seed_users()
        own, other = self.tenants
        own_conn, other_conn = self.connections
        self.set_context(own_conn, own)
        denied = own_conn.execute(
            'UPDATE faos.users SET external_subject=%s WHERE tenant_id=%s AND user_id=%s',
            ('tampered', other, user),
        )
        self.assertEqual(denied.rowcount, 0)
        allowed = own_conn.execute(
            'UPDATE faos.users SET external_subject=%s WHERE tenant_id=%s AND user_id=%s',
            ('own-updated', own, user),
        )
        self.assertEqual(allowed.rowcount, 1)
        self.assertEqual(own_conn.execute('SELECT external_subject FROM faos.users WHERE user_id=%s', (user,)).fetchall(), [('own-updated',)])
        self.set_context(other_conn, other)
        self.assertEqual(other_conn.execute('SELECT external_subject FROM faos.users WHERE user_id=%s', (user,)).fetchall(), [('synthetic-' + other,)])

    def test_cross_tenant_user_delete_affects_no_rows(self):
        user = self.seed_users()
        own, other = self.tenants
        own_conn, other_conn = self.connections
        self.set_context(own_conn, own)
        denied = own_conn.execute('DELETE FROM faos.users WHERE tenant_id=%s AND user_id=%s', (other, user))
        self.assertEqual(denied.rowcount, 0)
        allowed = own_conn.execute('DELETE FROM faos.users WHERE tenant_id=%s AND user_id=%s', (own, user))
        self.assertEqual(allowed.rowcount, 1)
        self.assertEqual(own_conn.execute('SELECT count(*) FROM faos.users WHERE user_id=%s', (user,)).fetchone()[0], 0)
        self.set_context(other_conn, other)
        self.assertEqual(other_conn.execute('SELECT external_subject FROM faos.users WHERE user_id=%s', (user,)).fetchall(), [('synthetic-' + other,)])

    def test_missing_context_user_insert_denied(self):
        own, _ = self.tenants
        own_conn = self.connections[0]
        user = str(uuid.uuid4())
        self.set_context(own_conn, '')
        with self.assertRaises(psycopg.errors.InsufficientPrivilege) as caught:
            with own_conn.transaction():
                own_conn.execute(
                    'INSERT INTO faos.users(tenant_id,user_id,external_subject) VALUES (%s,%s,%s)',
                    (own, user, 'missing-context-' + user),
                )
        self.assertEqual(caught.exception.sqlstate, '42501')
        self.set_context(own_conn, own)
        self.assertEqual(own_conn.execute('SELECT count(*) FROM faos.users WHERE user_id=%s', (user,)).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
